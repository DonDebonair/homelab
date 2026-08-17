# Plan: RomM (retro game library + player) on docker_vm

## Context

[RomM](https://romm.app) is a self-hosted ROM manager: it scans a library folder, enriches it
with metadata/artwork from external providers, and plays games in the browser via EmulatorJS.
Next off the [apps-to-try](apps-to-try.md) wishlist.

Standard `ComposeApp` + per-app template deploy on `docker_vm`, LAN-only behind
`caddy-internal` at **`romm.dv.zone`**, backed by the shared **postgres_lxc** and gated by
**native OIDC against Authelia** — same shape as Outline / AFFiNE / Vikunja. The ROM library
lives on the NAS and comes in over NFS, like the *arr/qbittorrent/BookOrbit stack.

**Decisions locked:**

- **Image/version:** `rommapp/romm:5.1.0` — latest stable (released 2026-07-29; verified via the
  GitHub releases API). The **full** variant, not `-slim`: slim drops the bundled EmulatorJS
  cores, and in-browser play is the point. Picked up automatically by Renovate manager M1
  (adjacent `image=`/`version=`).
- **Database: PostgreSQL on postgres_lxc** (`ROMM_DB_DRIVER=postgresql`). RomM's default is
  MariaDB; Postgres is a first-class documented driver (`postgresql+psycopg` under
  SQLAlchemy/Alembic) and lets us skip a bundled DB container entirely. Bonus: the MariaDB path
  has a nasty `log_bin_trust_function_creators` / `SUPER` prerequisite for its trigger DDL that
  Postgres doesn't share.
- **Redis: the image's embedded valkey.** RomM bundles valkey for sessions, the RQ task queue
  and metadata caching, used automatically whenever `REDIS_HOST` is unset. No sidecar (unlike
  outline/affine), just a volume for `/redis-data`.
- **Auth: OIDC against Authelia, local login left enabled.** RomM matches OIDC users to local
  accounts **by e-mail**, and the very first account (created in the setup wizard) is the only
  one that starts as Admin — so a local account has to exist first, and keeping local login on
  is the break-glass path. `DISABLE_USERPASS_LOGIN=true` is a deliberate follow-up, not part of
  this deploy.
- **Metadata providers: IGDB + SteamGridDB + RetroAchievements.** All three are API-key based
  and need 1Password items (below). Hasheous (`HASHEOUS_API_ENABLED`, no account needed) is
  deliberately **not** enabled — see follow-ups.
- **Runs as `2000:100`**, the NAS-facing docker identity — not root, and not the image default.
  See "Container user" below.

## Already done (uncommitted, present in the working tree)

`cmd.py db add-db romm --display-name RomM` has been run, so:

- `deploys/postgres_lxc/databases/vars.py` — `PostgresDBConfig(name="romm", user="romm", …)`
- `deploys/postgres_lxc/databases/secrets.py` — `romm_password` →
  `op://Homelab/PostgreSQL RomM user/password`

**No `extensions=[...]` is needed.** RomM's migration `0084_add_roms_search_index` runs
`CREATE EXTENSION IF NOT EXISTS pg_trgm` on Postgres. `pg_trgm` is a *trusted* extension since
PG 13 (postgres_lxc runs **18.4**), and the `romm` role owns the `romm` database, so it can
install it itself. This is not the AFFiNE/BookOrbit `vector` case, where an untrusted extension
had to be pre-created by the superuser.

The library folders are also already staged on the NAS (see below). Neither change has been
applied to a host yet.

## Library on the NAS (already laid out)

`/volume1/entertainment/media/emulation/` on the NAS holds `roms/{gamegear,genesis,nds,nes,sms,snes}`
(~157 GB). That is RomM's **Structure A** (`library/roms/{platform}/`, the recommended one), and
all six folder names are already exact RomM platform slugs — verified against the supported-platforms
list — so **no `system.platforms` mapping in `config.yml` is needed**.

The mount is therefore the `emulation` dir, not the share root:

```python
NfsVolume(name="romm-library", mount_path="/romm/library",
          server=nas_ip, path="/volume1/entertainment/media/emulation")
```

Project-scoped (not `external=True`), mirroring `pinchflat-downloads`, which mounts the
`media/youtube` subdir of the same tree. Deliberately **not** the shared `entertainment`
external volume the download clients use: that one exports the share *root*, and with
`roms/` absent at that level RomM would fall back to Structure B and read `media/`,
`torrents/`, `usenet/` and `#recycle` as platform folders.

Synology's `@eaDir` sidecar folders and `@SynoResource` files are already in RomM's **default**
`exclude.roms.*` lists, so they need no config either.

## Container user: `2000:100`, not root

> **Revised 2026-08-15, after deployment.** This section originally ran the container as root
> and dismissed `user: 2000:100` as a cosmetic gain. That was wrong, and it broke every
> download — see "Downloads 403 as root" in the deployment notes.

The image creates a `romm` user (1000:1000) but sets no `USER`, so left alone it runs as root.
The catch: RomM does not serve ROM downloads (nor the in-browser player's ROM fetch) from
Python — the backend hands off to **nginx**, and the init script drops nginx to the image's own
`romm` user (`nginx -g 'user romm;'`) precisely *because* the container is root. So the process
that opens the ROM file is uid 1000 no matter what the container itself runs as.

Access to the library is decided by the NAS's **Synology ACL**, not the mode bits (the
`-rwxrwxrwx` seen over NFS is cosmetic). Measured inside the container: uid 0 reads (only thanks
to the export's `no_root_squash`), uid 2000 reads (the `dockervm` ACL entry), uid 1000 does
not — and neither does 1026, the files' nominal owner.

So the container runs as **`2000:100`**, the identity qbittorrent / sabnzbd / bookorbit /
pinchflat already use, which also gives anything RomM writes to the share the right ownership.
Two supporting facts verified before switching:

- nginx is fine unprivileged: its pid and every `*_temp_path` sit under `/tmp`, and its logs go
  to `/dev/stdout` / `/dev/stderr`, so it needs nothing from the root-owned `/var/cache/nginx`
  or `/var/log/nginx`. With `EUID != 0` the init runs plain `nginx` and skips the drop entirely.
- The volumes need a one-shot chown first — `/romm` and `/redis-data` ship owned by 1000, and
  whatever the root-era container wrote is `0:0` — so the template gains a `romm-init` service
  on the `vikunja-init` pattern.

**`romm-init` must never `chown -R /romm`.** In the main service `/romm/library` is the NFS
mount, and with `no_root_squash` a recursive chown from a root container would rewrite ownership
across the entire ROM library on the NAS. It chowns the four subdirs explicitly, and does not
mount the library at all.

## Storage: one external volume at `/romm`

```python
NamedVolume(name="romm-data", mount_path="/romm", external=True)     # resources, assets, config, cache
NamedVolume(name="romm-redis", mount_path="/redis-data")             # embedded valkey, disposable
```

`/romm` holds `resources/` (fetched covers/screenshots/manuals), `assets/` (**user saves, save
states, in-app screenshots — irreplaceable**), `config/config.yml`, and `cache/zips`. External per
[[feedback_named_volumes_external]], so `down -v` can't wipe the saves.

Mounting the parent rather than each subdir is intentional: the image declares
`VOLUME ["/romm"]` specifically so its subdirs share one `st_dev` and RomM's cross-directory
`os.link()` calls don't hit `EXDEV`. Mounting `resources`/`assets`/`config` separately (as the
upstream example does) would split them across devices *and* leave an anonymous volume for
`/romm` itself. The NFS library nests under this at `/romm/library`; Docker orders mounts by
path depth, so the deeper NFS mount lands on top correctly.

`config.yml` is written **by RomM** (Library → Library Management is a two-way view of that
file), so it is deliberately not a `TemplateFile` — a rendered template would fight the UI on
every deploy. Nothing in it is needed for this deploy anyway (see the library section).

`/redis-data` is sessions + the RQ queue + cached provider metadata: rebuildable, so a plain
project-scoped volume, like `paperless-redis` / `outline-redis`. Losing it logs everyone out and
drops in-flight scans; nothing more.

## Database

Discrete `DB_*` settings, and RomM builds the URL with SQLAlchemy's `URL.create()`
(`backend/config/config_manager.py`), which escapes the password itself — so pass it **raw**,
like Vikunja/paperless, *not* percent-encoded like AFFiNE/BookOrbit. Values are rendered
double-quoted in the template because generated passwords can start with `!` or `?`, which a
plain YAML scalar rejects.

```yaml
ROMM_DB_DRIVER: postgresql
DB_HOST: [[ host.data.postgres_lxc_ip ]]
DB_PORT: 5432          # RomM's default is 3306 -- MUST be set explicitly
DB_NAME: romm
DB_USER: romm
DB_PASSWD: "…"
```

`DB_PORT` is the easy one to miss: it defaults to `3306` regardless of driver. No TLS
(`DB_QUERY_JSON` unused) — the LXC hop is on the trusted LAN, matching every other app here.

Alembic runs `alembic upgrade head` at container start (96 migrations on a fresh DB) and the
init script aborts the container if it fails, so a broken DB shows up immediately in the logs.

## OIDC wiring

Callback path is fixed at **`/api/oauth/openid`** (`backend/endpoints/auth.py`), so the
registered redirect URI is `https://romm.dv.zone/api/oauth/openid` — exact match, no trailing
slash.

Register the client with the helper:

```bash
uv run python cmd.py oidc add-client RomM https://romm.dv.zone/api/oauth/openid --claims-policy default
```

That appends a `romm` client to `deploys/docker_vm/proxies/vars.py` (two_factor,
`client_secret_basic`, scopes `openid groups email profile`) and creates
`op://Homelab/RomM OIDC client/password`.

`claims_policy: default` is **required**, not optional: RomM reads claims out of the ID token
(authlib's `userinfo` from `authorize_access_token`), and Authelia 4.39+ strips non-standard
claims from the ID token unless a policy restores them. Our `default` policy emits exactly
`groups, email, email_verified, preferred_username, name` — which is precisely the set RomM's
own Authelia guide asks for. Specifically:

- `email` — hard requirement; login 400s without it.
- `email_verified` — RomM *rejects* the login unless this is `true` whenever the provider
  advertises `email_verified` in `claims_supported` (Authelia does). Authelia always emits
  `true` for users with an e-mail, so this passes.
- `preferred_username` — the default `OIDC_USERNAME_ATTRIBUTE`; also a hard requirement.

The template already renders `userinfo_signed_response_alg: none` for every client, which is
what RomM's guide requires.

**No role mapping.** `OIDC_CLAIM_ROLES` is left unset on purpose: as soon as it *is* set, RomM
rejects any user whose claim matches none of the configured groups (403 "User has not been
granted any roles"), and the code compares `OIDC_ROLE_ADMIN` as a *single string* against the
group list despite the docs' comma-separated phrasing. With it unset, every OIDC user is
provisioned as a plain User — and admin comes from the e-mail match below.

`dns: [host.data.dns_ip]` on the container, same as affine/vikunja/bookorbit: RomM does OIDC
discovery against `https://auth.dv.zone/.well-known/openid-configuration` from the server at
runtime ([[project_portainer_oidc_dns_pin]]).

No `import secure` on the Caddy labels — a blanket forward-auth would double-gate and break the
OAuth callback.

### Admin bootstrap (ordering matters)

1. First browser visit hits the **setup wizard**; create the admin account there and give it
   **the same e-mail address Authelia has for your account**.
2. Then log in via the OIDC button. RomM matches by e-mail, finds that admin, and signs you in
   as it.

Get step 1's e-mail wrong and the OIDC login silently creates a *second*, non-admin account
alongside the admin one.

## Scanning: scheduled, not inotify

`ENABLE_RESCAN_ON_FILESYSTEM_CHANGE` stays **false**. RomM's watcher is `watchfiles`/inotify on
`/romm/library`, and inotify does not see changes made on the NFS *server* — ROMs dropped onto
the NAS from anywhere else would never fire an event. Use the cron-driven scan instead:

```yaml
ENABLE_SCHEDULED_RESCAN: "true"                        # SCHEDULED_RESCAN_CRON default: 0 3 * * *
ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES: "true"    # default: 0 5 * * *
ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC: "true"
```

`SCAN_WORKERS` stays at its default of 1 for the first full scan (hashing 157 GB over NFS is
I/O-bound); raise it later if scans drag.

## Secrets

| Variable | 1Password ref | Status |
|---|---|---|
| `romm_db_password` | `op://Homelab/PostgreSQL RomM user/password` | exists (`db add-db`) |
| `romm_oidc_client_secret` | `op://Homelab/RomM OIDC client/password` | created by `oidc add-client` |
| `romm_auth_secret_key` | `op://Homelab/RomM secrets/auth secret key` | **must be created** |
| `romm_igdb_client_id` | `op://Homelab/RomM secrets/IGDB/client id` | **must be created** |
| `romm_igdb_client_secret` | `op://Homelab/RomM secrets/IGDB/client secret` | **must be created** |
| `romm_steamgriddb_api_key` | `op://Homelab/RomM secrets/SteamGridDB/api key` | **must be created** |
| `romm_retroachievements_api_key` | `op://Homelab/RomM secrets/RetroAchievements/api key` | **must be created** |

Per [[feedback_user_creates_1password_items]] these are created by hand, in one `RomM secrets`
item in the `Homelab` vault, with field **ids** matching the paths above
([[feedback_op_sdk_resolves_by_field_id]] — `op read` matching the *label* is not proof). Same
nested shape as the existing `Paperless secrets` item.

- **auth secret key** — `openssl rand -hex 32`. Signs session/refresh tokens. If unset, the
  entrypoint generates a random one **per start** and logs a warning, invalidating every session
  on each restart. Blocking.
- **IGDB** — Twitch developer app (`api-docs.igdb.com`): needs a Twitch account with phone 2FA;
  register a *uniquely* named application (`romm-<random hex>`; a duplicate name fails silently),
  OAuth redirect `localhost`, type Confidential. Yields client id + secret.
- **SteamGridDB** — log in with Steam, key from Preferences → API.
- **RetroAchievements** — key from RA account settings.

Deploy is blocked only on the auth secret key; the three provider credentials can land later
(RomM just runs without those providers until they do), but a first scan without any metadata
provider is not worth doing, so treat them as part of the same batch.

## Files to create / change

1. **`deploys/docker_vm/proxies/vars.py`** — the `romm` OIDC client (generated by the helper
   command above, not hand-written).

2. **`deploys/docker_vm/apps/secrets.py`** — the seven `SecretString`s above (before
   `populate_cache_sync()`), with a comment noting the DB password is passed **raw** (SQLAlchemy
   `URL.create()` escapes it) and that the OIDC secret is the plaintext behind the `romm`
   client's pbkdf2 hash in `proxies/vars.py`.

3. **`deploys/docker_vm/apps/apps.py`** — the library NFS volume constant + the app:

   ```python
   # RomM's ROM library: the `emulation` subtree of the NAS entertainment share, laid out as
   # RomM "Structure A" (roms/{platform}/). Deliberately NOT the shared `entertainment`
   # external volume -- that exports the share root, where RomM would find no roms/ dir and
   # fall back to reading media//torrents//usenet/ as platform folders. Project-scoped, like
   # pinchflat-downloads.
   ROMM_LIBRARY_NFS = NfsVolume(
       name="romm-library",
       mount_path="/romm/library",
       server=nas_ip,
       path="/volume1/entertainment/media/emulation",
   )

   ComposeApp(
       name="romm",
       image="rommapp/romm",
       # Full variant (not -slim): slim drops the bundled EmulatorJS cores.
       version="5.1.0",
       domain="romm.dv.zone",
       volumes=[
           # resources/ (fetched artwork), assets/ (saves + states -- irreplaceable),
           # config/config.yml and cache/. Mounted at the parent /romm on purpose: the image
           # declares VOLUME ["/romm"] so its subdirs stay on one device and RomM's
           # cross-directory os.link() doesn't hit EXDEV. external -> `down -v` can't wipe saves.
           NamedVolume(name="romm-data", mount_path="/romm", external=True),
           # Embedded valkey's snapshot (sessions, RQ queue, cached provider metadata).
           # Rebuildable -> plain project-scoped volume, like paperless-redis.
           NamedVolume(name="romm-redis", mount_path="/redis-data"),
           ROMM_LIBRARY_NFS,
       ],
   )
   ```

4. **`deploys/docker_vm/apps/templates/romm.yaml.j2`** — new compose template, one service:

   - `romm`: `dns: [host.data.dns_ip]`, network `caddy-internal`, volumes via
     `vol.service_volumes(app)`, `expose: 8080`, `restart: unless-stopped`. No `user:` (runs as
     root — see above), no `depends_on` (nothing else in the project).
   - env: `TZ`, `ROMM_BASE_URL: https://[[ app.domain ]]`, `ROMM_AUTH_SECRET_KEY`,
     `ROMM_SESSION_SECURE_COOKIE: "true"`, `ROMM_CORS_ALLOWED_ORIGINS: https://[[ app.domain ]]`,
     the six `DB_*`/`ROMM_DB_DRIVER` settings, the four provider credentials, the six `OIDC_*`
     settings (`ENABLED`, `PROVIDER: authelia`, `CLIENT_ID: romm`, `CLIENT_SECRET`,
     `REDIRECT_URI`, `SERVER_APPLICATION_URL: https://auth.[[ host.data.domain ]]`) plus
     `OIDC_RP_INITIATED_LOGOUT: "true"` + `OIDC_END_SESSION_ENDPOINT: https://auth.…/logout`,
     and the three `ENABLE_SCHEDULED_*` flags.
   - labels: `caddy_internal: [[ app.domain ]]`,
     `caddy_internal.reverse_proxy: "{{upstreams 8080}}"`, `homepage.group: Entertainment`,
     `homepage.name: RomM`, `homepage.icon: romm`, `homepage.href`, `homepage.weight: 350`
     (after bookorbit 340), and the widget: `homepage.widget.type: romm`,
     `homepage.widget.url: http://romm:8080` — container-direct, since homepage shares
     `caddy-internal`. RomM's `/api/stats` needs no auth, so the widget takes **no key**.

5. **`docs/plans/apps-to-try.md`** — flip RomM ⬜ → ✅.

No new facts/operations, so **no `pyinfra-testing` cases**. No DNS work either: `*.dv.zone`
already resolves to the internal Caddy ([[project_wildcard_dns_dv_zone]]). No Caddy body-size
tuning: unlike nginx, Caddy has no default request-body cap, so large ROM uploads pass through.

## Order of operations

1. Create the `RomM secrets` 1Password item (auth secret key + the three provider credentials).
2. Run `cmd.py oidc add-client` (above) — creates the client entry and its 1Password item.
3. Apply the DB:
   `uv run pyinfra inventory.py deploys.postgres_lxc.databases.databases_and_users -y --limit postgres_lxc`.
4. Apply Authelia:
   `uv run pyinfra inventory.py deploys.docker_vm.proxies.setup_caddy_proxies -y --limit docker_vm`
   (the rendered `configuration.yml` is `restart_on_change`, so Authelia restarts itself).
5. Write the code changes (2–4 above).
6. Deploy the app:
   `uv run pyinfra inventory.py deploys.docker_vm.apps.setup_apps -y --limit docker_vm`.
7. Setup wizard → admin account with your Authelia e-mail → OIDC login → first scan.
8. Verify (below), then commit to `main` ([[feedback_trunk_based]]) — push only if asked.

## Verification

- `ssh dockervm.dv.zone 'docker compose -p romm ps'` → `romm` up; `docker logs romm` shows the
  banner, "Starting internal valkey", "Database migrations succeeded", and **no**
  `ROMM_AUTH_SECRET_KEY not set` warning.
- `psql` on postgres_lxc: `\dt` in the `romm` DB lists the tables, and `\dx` shows `pg_trgm`
  (proves the role installed the trusted extension itself).
- `docker exec romm ls /romm/library/roms` → the six platform dirs; `df -h /romm/library` inside
  the container shows the NAS export, not the overlay.
- `curl -s https://romm.dv.zone/api/heartbeat` → JSON; the same over `http://romm:8080` from the
  homepage container is what the widget uses.
- Browser: `https://romm.dv.zone` → setup wizard → admin created → **log out** → the OIDC button
  round-trips through `auth.dv.zone` and lands back signed in **as the admin** (not a second
  account — check Settings → Users shows one user).
- Run a scan of one platform (`nes`): ROMs appear with IGDB metadata and cover art, and
  `docker logs romm` shows no `EACCES`/`Permission denied` on the library.
- Open a game in the browser player (EmulatorJS), save a state, restart the container
  (`docker restart romm`) and confirm the session survives (auth secret is pinned) and the state
  is still listed (`/romm/assets` persisted).

## Deployment notes (2026-08-15)

Deployed as planned; the app came up on the second attempt after two separate DB-password
problems, both worth remembering:

1. **`postgres.role` never alters an existing role.** The `romm` role already existed from an
   earlier hand-provisioning, so the `databases_and_users` apply left its old password in place
   while the app got the 1Password one — `FATAL: password authentication failed for user "romm"`.
   pyinfra documents this explicitly ("pyinfra will not attempt to change existing roles"), so
   there is nothing to fix in the deploy; a rotated DB password always needs a manual
   `ALTER ROLE <role> WITH PASSWORD …` as the superuser to go with it.
2. **Docker Compose interpolates `$` in the compose file.** The generated password contained
   `$Lrif`, a *valid* variable reference, so compose expanded it to nothing and the container
   received a truncated password — no error, just a "variable is not set" warning. `$` has
   therefore been removed from `SPECIAL_CHARS` in `commands/secrets.py`; per-call-site `$$`
   escaping was rejected because it only has to be forgotten once, and jinja's `|replace`
   can't do it (a `SecretString` expands only via `__str__`, so the filter would rewrite the
   `op://` reference instead of the secret). The RomM password was then rotated in 1Password
   and synced to the role.

   A sweep of the other rendered compose files found a literal `$` in only two more —
   forgejo's `FORGEJO__database__PASSWD` and outline's `DATABASE_URL`. Both survive by luck:
   the character after the `$` makes them invalid variable references, which compose leaves
   alone. Neither is broken, but both are one rotation away from it.

Verified after the fix: `Database migrations succeeded` (alembic at `0103_roms_facets_provider_ids`,
32 tables), `pg_trgm` present in the `romm` DB **created by the `romm` role itself** — confirming
no superuser `extensions=[...]` entry is needed — plus both `*_trgm` GIN indexes; `/romm/library`
mounted `nfs4` with the six platform dirs; and `https://romm.dv.zone/api/heartbeat` reporting
5.1.0 with `OIDC.ENABLED=true`, provider `authelia`, and IGDB/SteamGridDB/RetroAchievements all
enabled. No `ROMM_AUTH_SECRET_KEY not set` warning, so sessions survive restarts.

### Downloads 403 as root (found during the first scan)

With the container running as root — the plan's original call — the scan, hashing and metadata
all worked, but **every ROM download and in-browser play failed**:

```text
open() "/romm/library/roms/genesis/....gen" failed (13: Permission denied)
request: "GET /api/roms/1073/content/....gen", referrer: "https://romm.dv.zone/rom/1073/ejs"
```

RomM serves ROM content through nginx, which its init script drops to uid 1000, and the NAS ACL
grants only uid 2000 (plus root via `no_root_squash`). Fixed by running as `2000:100` with the
`romm-init` chown one-shot; see the revised "Container user" section for the measurements and
for why `chown -R /romm` would be dangerous. Applied after the first scan finished, since the
switch recreates the container and RomM's scan is an in-memory RQ job.

Still to do by hand, in the browser: the setup wizard (admin account, **with your Authelia
e-mail**), then the OIDC login, then the first library scan.

## Follow-ups / out of scope

- **Hasheous** (`HASHEOUS_API_ENABLED=true`) — free, no account, hash-based matching that
  proxies IGDB data; a good complement to IGDB for files whose names don't match cleanly. One
  env var whenever you want it.
- **`DISABLE_USERPASS_LOGIN=true`** — lock out local accounts once OIDC admin login is proven.
  Optionally `OIDC_AUTOLOGIN=true` to skip the login page entirely.
- **BIOS/firmware** — `bios/{platform}/` alongside `roms/` in the same `emulation` dir; needed
  for PS1/GBA-class emulation. Nothing to configure, just files.
- **More platforms** — any new folder under `roms/` must be named with a RomM platform slug, or
  mapped via `system.platforms` in `config.yml`.
- **Companion apps** (muOS/Argosy/Playnite, `docs/ecosystem/`) are LAN-only here; reaching them
  off-network would mean exposing `romm.dv.zone` through the Cloudflare tunnel, which is a
  separate decision (large ROM downloads over a tunnel, and Cloudflare's ToS on media).
- **Observability** — RomM speaks OpenTelemetry (`OTEL_*` env vars auto-enable it); could feed
  the docker_vm monitoring stack later.
- **Backups** — `romm-data` (saves/states) belongs in whatever the backup-strategy review
  ([[project_backup_strategy_review]]) settles on; the library itself is already on the NAS.
