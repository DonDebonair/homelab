# Plan: Migrate Calibre-Web-Automated (CWA) — NAS/Ansible → docker_vm/pyinfra

## Context

CWA (`books.dv.zone`, Calibre-Web-Automated) is one of the remaining apps on the
legacy Ansible/NAS stack. On the NAS it runs as a `:latest` compose service
(`roles/docker-apps/templates/cwa.yml.j2`) with three bind mounts under
`/volume2/docker/cwa/`: `config → /config`, `ingest → /cwa-book-ingest`,
`calibre-library → /calibre-library`. It's internal on `caddy-internal` behind
Authelia forward-auth (`import secure *`); there is no native OIDC client.

This ports CWA to the pyinfra `docker_vm` stack using the standard
one-`ComposeApp`-entry + one-`<app>.yaml.j2` pattern, with three deliberate
changes:

1. **Library on the existing NFS share.** The calibre library moves to
   `/volume1/entertainment/calibre-library` on the NAS — the *same* share
   qbittorrent/sabnzbd already mount — and is mounted into the container over NFS
   at `/calibre-library`. Because that share is already exported for the
   docker_vm subnet with the `dockervm` (uid 2000) ACL granted, **no new
   export/firewall/ACL work is needed**. Since calibre's `metadata.db` is SQLite
   on a network share, the container sets **`NETWORK_SHARE_MODE=true`** (CWA's
   supported switch: disables WAL on `metadata.db` + `app.db`, skips recursive
   chowns that fail on network filesystems, and uses polling watchers instead of
   inotify — see CWA README → "Deploying on Network Shares (NFS/SMB)").
2. **Config as an external named volume** (`cwa-config`, `external=True`), bridged
   from the NAS config dir.
3. **Ingest as a docker_vm bind mount** (`/srv/docker/volumes/cwa/ingest`).

**Scope: CWA only.** The companion `cwa-dl` downloader stack (+ `cloudflarebypass`
sidecar, `books-dl.dv.zone`) shares CWA's ingest dir; it is a **follow-up** (see
the last section) because it needs a multi-service compose template.

## Implementation

### App entry — `deploys/docker_vm/apps/apps.py`

`ComposeApp(name="cwa", image="crocodilestick/calibre-web-automated",
version="v4.0.6", domain="books.dv.zone", ...)` with three volumes:
`NamedVolume("cwa-config", "/config", external=True)`,
`BindMount("cwa/ingest", "/cwa-book-ingest")`, and
`NfsVolume("cwa-library", "/calibre-library", server=nas_ip,
path="/volume1/entertainment/calibre-library")`. No secrets (no homepage widget
key, no OIDC), so `secrets.py` is untouched.

### Compose template — `deploys/docker_vm/apps/templates/cwa.yaml.j2`

Modelled on `qbittorrent.yaml.j2` (NFS + PUID 2000/PGID 100) and
`tautulli.yaml.j2` (external config vol, Entertainment homepage). Port `8083`,
`caddy_internal.import: secure *`, `NETWORK_SHARE_MODE: "true"`, and the homepage
labels carried over from the Ansible template.

**PUID/PGID = 2000/100.** The library is on NFS (maps by numeric id) and the NAS
`dockervm` account's primary group is `users` (gid 100). This differs from
tautulli (2000/2000) because tautulli had no NFS mount. The migrated config files
are therefore chowned to `2000:100` on the way in.

## Data migration runbook

Two data moves. **Stop the NAS `cwa` container first** so `metadata.db` /
`app.db` are checkpointed cleanly (no lingering `-wal`).

**Library — NAS relocation across volumes** (volume2 → volume1 crosses
filesystems, so `rsync` not `mv`; `dockervm` is uid 2000, group `users`=100):
```
ssh nas.dv.zone \
  'sudo rsync -a /volume2/docker/cwa/calibre-library/ /volume1/entertainment/calibre-library/ \
   && sudo chown -R dockervm:users /volume1/entertainment/calibre-library'
# verify book count + metadata.db present, then drop the old copy:
# ssh nas.dv.zone 'sudo rm -rf /volume2/docker/cwa/calibre-library'
```
The moved dir is a child of the exported `entertainment` folder, so it inherits
the `dockervm` R/W ACL.

**Config — bridge NAS → workstation → docker_vm named volume** (the NAS and
docker_vm can't reach each other; same pattern as tautulli/sabnzbd):
```
ssh dockervm.dv.zone 'docker volume create cwa-config'
ssh nas.dv.zone 'tar -C /volume2/docker/cwa/config -cf - .' \
  | ssh dockervm.dv.zone 'docker run --rm -i -v cwa-config:/dest alpine tar --numeric-owner -xf - -C /dest'
# match the container's runtime ids (NFS-app convention: PUID 2000 / PGID 100)
ssh dockervm.dv.zone 'docker run --rm -v cwa-config:/dest alpine chown -R 2000:100 /dest'
```
Domain is unchanged (`books.dv.zone`), so no CWA URL/base-path edit is needed.
Ingest is transient — nothing to migrate; the deploy creates the bind dir.

## Deploy

```bash
uv run pyinfra inventory.py --limit docker_vm deploy.py    # dry-run first
uv run pyinfra inventory.py --limit docker_vm deploy.py -y # apply (needs -y)
```
`setup_apps()` picks up the new app automatically; `setup_caddy_proxies()` runs
first, so `caddy-internal` exists. `-y` is required or non-dry applies EOFError.
`OP_SERVICE_ACCOUNT_TOKEN` must be in the env.

## Verification

- **Dry-run:** `cwa-config` external volume pre-created; `cwa/ingest` bind dir
  created; compose rendered to `/srv/docker/compose/cwa/compose.yaml` with the
  NFS + named + bind volumes and `NETWORK_SHARE_MODE=true`. Re-run → noop.
- **Container:** `docker ps` shows `cwa` up on `caddy-internal`; `docker logs cwa`
  shows the migrated `app.db` loaded (existing users, not first-run) and
  `/calibre-library` mounted (book count matches the NAS). No SQLite
  `database is locked` / WAL errors.
- **NFS:** `docker exec cwa ls /calibre-library` lists the library + `metadata.db`;
  edit a book's metadata and confirm it persists to
  `/volume1/entertainment/calibre-library` on the NAS.
- **Ingest:** drop a test epub into `/srv/docker/volumes/cwa/ingest`; confirm CWA
  ingests it and removes the source file.
- **Proxy/auth:** `curl -I https://books.dv.zone` → 302 Authelia; after login the
  UI loads. Homepage shows the CWA tile.

## Decommission (NAS)

Once verified: stop/remove the NAS `cwa` compose stack and remove its entry from
the Ansible side (`nas.yml` apps list + `roles/docker-apps/templates/cwa.yml.j2`).
Keep `/volume2/docker/cwa/config` and the old library path until confident, then
clean up. Flip the `cwa` row in `docs/plans/docker-apps-migration.md` to ✅ and
bump the count.

## Status

**Deployed and verified 2026-07-03** — CWA is up on docker_vm at `books.dv.zone`
with the migrated config volume and the NFS library, working end-to-end.

## Follow-ups (TODO)

### 1. Add OIDC auth to CWA — ✅ done 2026-07-07

**Verified:** native OIDC login via Authelia works end-to-end; standard login is
disabled, so CWA's own OIDC is the sole gate.

CWA now authenticates with its own **native generic-OIDC client** against Authelia
instead of a blanket Authelia forward-auth gate, so SSO identities map to CWA
users/permissions (incl. admin-by-group) rather than everyone past the gate being
treated the same.

**Important constraint — CWA has no env/config-file OIDC.** Unlike paperless
(env-driven `PAPERLESS_SOCIALACCOUNT_PROVIDERS`), CWA v4 configures generic OIDC
**only through its admin UI**, persisting it in the `oauthProvider` table +
`config_login_type` inside `app.db`. That DB lives on the external `cwa-config`
volume, so the config survives redeploys/`down -v` and only has to be entered once.
Consequently there is **nothing OIDC-related in `cwa.yaml.j2` and no secret in
`apps/secrets.py`** — the template can't carry it. CWA reads `preferred_username` /
`email` / `groups` from Authelia's **userinfo endpoint** (not the ID token), so —
unlike Grafana — **no Authelia `claims_policy` is needed**; the `groups`/`profile`/
`email` scopes deliver those claims at userinfo directly. The blueprint uses no
PKCE and `client_secret_basic`.

**Done as code:**
- Authelia client `calibre-web` registered in `deploys/docker_vm/proxies/vars.py`
  (via `uv run python cmd.py oidc add-client "Calibre-Web"
  "https://books.dv.zone/login/generic/authorized"`): `two_factor`,
  `client_secret_basic`, scopes `openid groups email profile`, no PKCE, no claims
  policy. Redirect URI is CWA's generic-provider callback
  `https://books.dv.zone/login/generic/authorized`.
- Client secret stored in 1Password at `op://Homelab/Calibre-Web OIDC client/password`
  (the run's token is read-only for writes, so the item is created by hand — the
  script prints the raw secret + the exact fields). Only the pbkdf2 hash lives in
  `vars.py`; nothing resolves the `op://` ref at deploy time.
- `caddy_internal.import: secure *` **removed** from `cwa.yaml.j2` so CWA's own OIDC
  is the sole gate (matches `paperless.yaml.j2`, which carries no `import secure`).

**One-time manual setup (rollout order matters — avoids lockout/exposure):**
1. `uv run pyinfra inventory.py --limit docker_vm deploy.py -y` — deploys the
   Authelia client (so it knows `calibre-web`) **and** drops the forward-auth gate.
   CWA stays reachable via its migrated local admin account until step 4.
2. In CWA: **Admin → Edit Basic Configuration → Feature Configuration**, set
   **Login type = "Use OAuth (requires HTTPS)"**, then under **Generic OAuth
   Provider**:
   - **OAuth Metadata URL** = `https://auth.dv.zone/.well-known/openid-configuration`
     → click **Test Metadata** to auto-fill base/authorize/token/userinfo endpoints.
   - **OAuth Scopes** = `openid profile email groups`
   - **OAuth Client Id** = `calibre-web`
   - **OAuth Client Secret** = the value from `op://Homelab/Calibre-Web OIDC client/password`
   - **Username Field** = `preferred_username`, **Email Field** = `email` (defaults)
   - **OAuth group for Admin** = your Authelia/LLDAP admin group (grants CWA admin)
   - **Login Button Text** = `Authelia`
3. Save, log out, and verify the **"Login with Authelia"** button completes the
   round-trip — a first login auto-creates the CWA user; confirm an admin-group
   member lands with admin rights.
4. Only after OIDC works: re-open the config and tick **Disable Standard Login
   (Username/Password)** so OIDC is the sole gate. (CWA warns about lockout if you
   disable standard login without a working OAuth setup — hence the ordering.)

### 2. Replace `cwa-dl` with Shelfmark (not a migration — clean slate)

**Decision:** do **not** port the old `calibre-web-automated-book-downloader`
(`cwa-dl`) or its data to docker_vm. It is superseded by its successor
**Shelfmark** (https://github.com/calibrain/shelfmark). Stand up Shelfmark fresh on
docker_vm (its own `ComposeApp` + template), pointed at the same
`/srv/docker/volumes/cwa/ingest` bind mount so downloads still flow into CWA's
auto-ingest. No config/state carried over from `cwa-dl`. Once Shelfmark is up,
decommission the NAS `cwa-dl` stack (+ its `cloudflarebypass` sidecar) on the
Ansible side. Check whether Shelfmark still needs a cloudflare-bypass sidecar or
bundles that itself.
