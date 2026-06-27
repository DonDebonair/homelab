# Plan: Port paperless-ngx from the NAS to the Docker VM (Ansible → pyinfra)

## Context

Fourth app in the `docker-apps` migration ([docker-apps-migration.md](docker-apps-migration.md)),
and the first **multi-container + stateful** one. paperless-ngx ran on the Synology
NAS via the Ansible `roles/docker-apps` role (`paperless.yml.j2`) with a webserver +
redis + gotenberg + tika, a Postgres DB in the NAS `postgres-db` container, OIDC via
Authelia, Gmail OAuth mail fetching, and ~1300 documents on disk under
`/volume2/docker/paperless`.

Two things were **already provisioned** on the pyinfra side before this work:

- the `paperless` Postgres DB + user on `postgres_lxc` (`deploys/postgres_lxc/databases/vars.py`);
- the `paperless` Authelia OIDC client (`deploys/docker_vm/proxies/vars.py`) — PKCE + 2FA,
  redirect `https://docs.dv.zone/accounts/oidc/authelia/login/callback/`.

So the work was: the compose stack, the `ComposeApp` + secrets wiring, and a clean
data migration.

## Decisions

- **Single template, sidecars inline.** `ComposeApp` is single-image, so `paperless.yaml.j2`
  holds 4 services — `paperless` (webserver) + `paperless-redis`/`paperless-gotenberg`/`paperless-tika`
  pinned inline — hand-writing each service's volume mounts and using
  `vol.top_level_volumes(app)`, exactly like `authelia.yaml.j2`.
- **Internal-only.** Webserver on `caddy-internal` (`docs.dv.zone`, matching the NAS
  `exposure: internal`), plus a private compose `paperless` bridge for webserver↔sidecars.
  Reaching `auth.dv.zone` (caddy-external `.21`) for OIDC works via the macvlan-shim
  host route (see [../../deploys/docker_vm/macvlan_shim](../../deploys/docker_vm/macvlan_shim)).
- **Volumes by recovery cost** ([feedback: external named volumes]). `paperless-data`
  (index/ML) + `paperless-media` (documents) are `NamedVolume(external=True)` so
  `down -v` can't wipe them; `paperless-redis` is a plain named volume (disposable
  broker); `paperless/export` + `paperless/consume` are **host-accessible BindMounts**
  (the migration import lands in `export`, and `consume` is the inbox on the host fs).
- **Real `PAPERLESS_SECRET_KEY` (security over faithful-port).** The NAS never set one,
  so it ran on paperless's *public default* key. Because paperless self-auths (it is
  **not** behind Authelia forward-auth — same as miniflux) and signs its session cookies
  with `SECRET_KEY`, a known key means LAN-local session forgery. We set a real key
  (`op://Homelab/Paperless secrets/secret key`). (We expected this to force a one-time
  Gmail mail re-auth; in practice it did **not** — the imported OAuth refresh token kept
  working, see Verification.)
- **Pinned versions** (looked up live): paperless `2.20.15` (latest stable; 3.0 is beta),
  gotenberg `8.34.0`, tika `3.3.1.0-full`, redis `7.4.9`.

## Implementation (done)

- `deploys/docker_vm/apps/apps.py` — `paperless` `ComposeApp` (image
  `ghcr.io/paperless-ngx/paperless-ngx:2.20.15`, the 5 volumes above).
- `deploys/docker_vm/apps/templates/paperless.yaml.j2` — the 4-service stack.
- `deploys/docker_vm/apps/secrets.py` — `paperless_db_password`
  (`op://Homelab/PostgreSQL Paperless user/password`), `paperless_secret_key`
  (`op://Homelab/Paperless secrets/secret key`), `paperless_oidc_client_secret`
  (`op://Homelab/Paperless secrets/oidc secret`), `paperless_gmail_oauth_client_id` +
  `paperless_gmail_oauth_client_secret` (`op://Homelab/Paperless secrets/googleapis …`).
  **All five 1Password items must exist before any apps deploy** — `populate_cache_sync()`
  fails the whole module otherwise.

`setup_apps()` picks the app up from the list automatically; no `deploy.py` change.

## Data migration runbook (official exporter/importer)

The clean, DB-agnostic, version-tolerant path. Key invariant: **import into the empty
DB before the first SSO login** — DNS stays on the NAS until after import, which
guarantees nobody logs in (and auto-creates a conflicting user) early. Ownership
survives because the export serializes users + per-document `owner` FKs; on first
login Authelia's identity re-links to the imported user by `sub`/email
(`PAPERLESS_SOCIALACCOUNT_EMAIL_AUTHENTICATION: true`).

```bash
# 1. Export — on the NAS (quiet window)
docker exec -t paperless-webserver document_exporter /usr/src/paperless/export --no-progress-bar
cat /volume2/docker/paperless/export/metadata.json   # confirm "version" <= target (2.20.15)

# 2. Deploy the new stack — from the repo (OP_SERVICE_ACCOUNT_TOKEN set); then DO NOT log in
uv run pyinfra inventory.py --limit docker_vm deploy.py
#    verify on docker_vm: 4 containers Up, and the DB is reachable + migrated + empty:
docker exec -w /usr/src/paperless/src paperless \
  python3 manage.py shell -c "from documents.models import Document; print('docs:', Document.objects.count())"   # -> docs: 0

# 3. Transfer the export -> docker_vm bind mount.
#    Gotcha: NAS SSH is daanadmin@nas.dv.zone PORT 22910 (key auth from the workstation
#    only); docker_vm has NO SSH to the NAS, and the Synology rejects `--rsync-path="sudo rsync"`.
#    chown the export to daanadmin on the NAS first, then stream via the workstation:
ssh nas.dv.zone 'cd /volume2/docker/paperless/export && tar cf - .' \
  | ssh daan@192.168.50.10 'mkdir -p ~/paperless-export && tar xf - -C ~/paperless-export'
#    then on docker_vm (sudo needs a password — no NOPASSWD):
sudo cp -a ~/paperless-export/. /srv/docker/volumes/paperless/export/
sudo chown -R 2000:2000 /srv/docker/volumes/paperless/export

# 4. Import — on docker_vm (docker exec works without sudo; daan is in the docker group)
docker exec paperless document_importer /usr/src/paperless/export --no-progress-bar
docker exec paperless document_index reindex

# 5. Cut over DNS — point docs.dv.zone -> 192.168.50.20 (caddy-internal) in Technitium
dig +short docs.dv.zone @192.168.50.30   # expect 192.168.50.20

# 6. Log in via SSO at https://docs.dv.zone (first login = the imported superuser)
```

## Verification (2026-06-27)

- Pre-import DB check: `docs: 0` (connection to `192.168.1.41` OK, schema migrated, empty).
- Import: **17,563 objects / 1337 documents** (4 users, 91 tags, 180 correspondents,
  9 doc types, the `Business` custom field, 1 Gmail mail account); reindexed all 1337.
- Cutover: `docs.dv.zone` → `192.168.50.20`; `curl https://docs.dv.zone/` → `302
  /accounts/login/` with a valid public cert.
- SSO login lands on the imported superuser; all documents present.
- **Gmail mail fetch works with no re-auth** — scheduled `process_mail_accounts` logged
  `POST https://oauth2.googleapis.com/token "200 OK"`, i.e. the imported refresh token
  still mints access tokens. (So the SECRET_KEY/encrypted-mail-token concern did not
  apply to paperless-ngx mail accounts.)

## Follow-ups

- Clean the leftover import dump from the export bind mount:
  `sudo rm -rf /srv/docker/volumes/paperless/export/*` on docker_vm (~2.9 G; the data
  now lives in `paperless-media`).
- Regenerate a paperless API token and add it as `homepage.widget.key` if you want the
  homepage widget stats (the NAS's hardcoded key was dropped).
- Decommission the NAS instance after a few days of confidence: stop the NAS containers,
  remove the `paperless` entries from `roles/docker-apps/`, and only then delete
  `/volume2/docker/paperless`.
- Commit the deploy (still uncommitted alongside the miniflux + macvlan-shim work).
