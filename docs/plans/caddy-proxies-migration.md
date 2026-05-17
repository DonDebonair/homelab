# Migrate Caddy proxies stack from Ansible to pyinfra (iterative)

## Context

The Ansible role `roles/proxies` provisions a four-stack Caddy setup on the **NAS**:
- `caddy-internal` — LAN-only Caddy (macvlan IP), terminates TLS for Docker-labeled apps and a static `extra_proxied_domains` list, layer-4 routes :22 → forgejo:22.
- `caddy-external` — internet-facing Caddy (macvlan IP), used as origin behind the Cloudflare tunnel.
- `authelia` + redis — SSO/forward-auth for the Caddys.
- `cloudflared` — Cloudflare tunnel sidecar.

The repo is being migrated from Ansible (NAS-only) to pyinfra (everything else). This change ports the proxy stack to a new pyinfra deploy that targets the `docker_vm` host instead of the NAS — i.e. the Caddy stack moves from running on Synology to running on the dedicated Debian VM that already has Docker provisioned by `deploys/docker_vm/docker`. The NAS-resident apps (sonarr/radarr/plex/etc.) stay on the NAS; caddy-internal's LAN reverse-proxy entries simply point back at the NAS over the LAN.

The work is split into **three milestones** so the user can dry-run and validate each stage before moving on. Each stage builds on the previous one and leaves the deploy in a runnable, testable state.

User decisions captured before planning:
- All static Authelia secrets + JWKS PEM pair move to 1Password (no plaintext files in the repo).
- caddy-internal macvlan IP = `192.168.50.20`, caddy-external = `192.168.50.21`.
- `host_proxied_domains` is renamed to `extra_proxied_domains`; entries default their IP to the NAS (`nas_ip` from `group_data/all.py`).
- The Ansible `roles/proxies` role stays in place for now (no deletion in this change).
- Verification at each stage is `uv run pyinfra inventory.py --limit docker_vm deploy.py --dry`.
- **Volume policy**: `ComposeApp.volumes` holds `BindMount | NamedVolume`. `BindMount.source` discriminates: an absolute path (`/var/run/docker.sock`) is a system bind mount the helper leaves alone; a relative path (`authelia/config`) is resolved under `host.data.docker_volumes_base` and the helper creates that host directory with the BindMount's `uid` / `gid`. `NamedVolume.external` is a per-volume choice: `external=False` (default) means compose owns the volume's lifecycle (project-scoped name, vulnerable only to `docker compose down -v`); `external=True` means the volume lives outside compose's lifecycle, survives `down -v`, and uses an unscoped name. The helper pre-creates every external named volume via `docker.volume(present=True)` so the compose `up` finds it. Compose templates iterate `app.volumes` instead of hardcoding mounts. Named volumes for runtime state; bind mounts only for host-rendered template files (Authelia config/secrets, cloudflared config/credentials) and system paths (docker socket).

---

## Stage 0 — Foundation (shared across all stages)

These pieces are needed from the start but never gain Authelia/Cloudflare-specific bits.

### `group_data/docker_vm.py` (edit)
Add the host data the deploy/templates reference. None of these are Authelia- or Cloudflare-specific:

```python
default_group = docker_user                   # primary group of the user created by docker_setup
docker_volumes_base = "/srv/docker/volumes"   # managed bind mounts live here
docker_compose_base = "/srv/docker/compose"   # rendered compose stacks live here
docker_build_base   = "/srv/docker/build"     # image build contexts live here
internal_reverse_proxy_ip = "192.168.50.20"
external_reverse_proxy_ip = "192.168.50.21"
extra_proxied_domains = [                     # entries default their target IP to host.data.nas_ip
    {"domain": "tv.dv.zone",       "port": 8989},
    {"domain": "movies.dv.zone",   "port": 8310},
    {"domain": "plex.dv.zone",     "port": 32400},
    {"domain": "dns.dv.zone",      "port": 8080},
    {"domain": "indexers.dv.zone", "port": 9696},
    {"domain": "cmd.dv.zone",      "port": 1337},
]
```

### `deploys/docker_vm/__init__.py`
Already re-exports `setup_caddy_proxies` — no edit needed.

### `deploy.py` (edit, once at the start of stage 1)
Add `setup_caddy_proxies()` after `docker_setup()`:

```python
if "docker_vm" in host.groups:
    docker_setup()
    setup_caddy_proxies()
```

### Reused utilities (do not duplicate)
- `deploys.common.docker_compose.docker_compose` — orchestrates host bind-mount dirs, pre-creation of external named volumes, file/template uploads, compose-file renders, and `docker compose up` (via `deploy_compose_files`). Accepts a `variables` module via `normalize_vars` and passes the per-app `ComposeApp` instance into the Jinja context as `app`.
- `deploys.common.docker_compose.models.ComposeApp / BindMount / NamedVolume / TemplateFile` — dataclasses. `BindMount(source, mount_path, uid=None, gid=None, read_only=False)` represents both bind-mount cases: if `source` is absolute, it's a pre-existing system path (e.g. `/var/run/docker.sock`) and the helper does nothing; if `source` is relative, it's resolved under `host.data.docker_volumes_base` and the helper creates the host directory with `uid` / `gid`. `BindMount.is_managed` is a convenience property (= `not source.startswith("/")`). `NamedVolume(name, mount_path, external=False, read_only=False)` is a Docker named volume; `external=False` means compose creates it and project-scopes the name, `external=True` means the helper pre-creates it via `docker.volume(present=True)` and the compose template marks it `external: true` so compose finds it instead of creating it. Both classes carry a `kind: ClassVar[str]` (`"bind"` / `"named"`) that compose templates use to discriminate the two types — refactor-safe and reachable from Jinja. `ComposeApp.volumes` accepts a list of either.
- `op_secrets.SecretString` — same pattern as every other deploy package.
- `pyinfra.operations.docker.build`, `docker.network`, `docker.compose` — built-ins cover image/network/compose actions; no custom operation needed.

---

## Stage 1 — Caddy build + caddy-internal + caddy-external (DNS-01 ACME, no Authelia, no Cloudflare tunnel)

**Goal:** verify the custom Caddy image builds, the two proxies come up on their macvlan IPs, and the LAN reverse-proxy labels render correctly — with real Let's Encrypt certificates via the Cloudflare DNS-01 challenge from day one. No Authelia and no Cloudflare tunnel yet.

### Files to create

`deploys/docker_vm/proxies/__init__.py` — entrypoint:
1. `files.directory` for `{docker_build_base}/caddy` (= `/srv/docker/build/caddy`).
2. `files.put` the Dockerfile (plain, no Jinja).
3. `docker.build` with `tags=[f"caddy-custom:{caddy_version}"]`, `path={docker_build_base}/caddy`. Tag-idempotent so re-runs no-op.
4. `docker.network` for `caddy-internal` and `caddy-external` (matching the Ansible IPAM exactly: 172.101.0.0/16 ip_range 172.101.0.0/24 gw 172.101.0.1, and 172.102.0.0/16 ip_range 172.102.0.0/24 gw 172.102.0.1). **Do not** create `authelia` or `tunnel` networks yet.
5. Call the shared `docker_compose` helper with the two ComposeApps from `apps.py`. The helper renders the compose files and brings each stack up via its own `deploy_compose_files` step.

`deploys/docker_vm/proxies/secrets.py`:

```python
from op_secrets import SecretString

cloudflare_api_token = SecretString("op://Homelab/Cloudflare API Token/credential")

SecretString.populate_cache_sync()
```

`deploys/docker_vm/proxies/vars.py`:
- `caddy_version = "2.11.3"`
- Re-export `cloudflare_api_token` from `secrets.py` so the Caddy compose templates can reference it as `[[ cloudflare_api_token ]]`.

`deploys/docker_vm/proxies/apps.py` — two ComposeApps. Volumes are declared on the model; the templates iterate them:
- `caddy-internal`:
  - `BindMount(source="/var/run/docker.sock", mount_path="/var/run/docker.sock")` — the docker socket.
  - `NamedVolume(name="caddy-internal-data", mount_path="/data", external=True)` — Caddy's runtime state, including the ACME account keys and issued cert cache. `external=True` with a globally-unique (un-project-scoped) name so `docker compose down -v` cannot wipe the LE account keys (re-registration is rate-limited by Let's Encrypt). Pre-created by the shared helper via `docker.volume(present=True)`.
- `caddy-external`: same two entries, named volume `caddy-external-data` (also `external=True`).

`deploys/docker_vm/proxies/templates/`:
- `Dockerfile` — uses `ARG CADDY_VERSION` (no default; value is supplied by `docker.build`'s `build_args` from `vars.caddy_version`). Builder + xcaddy plugins (`caddy-docker-proxy`, `caddy-dns/cloudflare`, `caddy-l4`). The `caddy-dns/cloudflare` plugin is used from day one for the DNS-01 ACME challenge.
- `caddy-internal.yaml.j2` — a stripped version of `roles/proxies/templates/caddy-internal.yml.j2`:
  - **Drop**: the `caddy_internal_90 (secure)` forward_auth snippet (re-added in stage 2).
  - **Keep**: `caddy_internal_0.acme_dns: cloudflare [[ cloudflare_api_token ]]` for real LE certs via the Cloudflare DNS-01 challenge.
  - **Keep**: macvlan attachment, `extra_proxied_domains` loop, layer-4 :22 → forgejo:22 route, the email global option (used for LE account registration).
  - **Volumes**: no hardcoded mount lines. Iterate `app.volumes` to emit the service-level list. For a `BindMount`: `{docker_volumes_base}/{source}:{mount_path}` when `v.is_managed`, else `{source}:{mount_path}`. For a `NamedVolume`: `{name}:{mount_path}`. Emit the top-level `volumes:` block from the `NamedVolume` entries only, marking each `external: true` where `v.external`.
  - Networks: `caddy-internal`, `macvlan`. **Drop** any tunnel/authelia network refs.
- `caddy-external.yaml.j2` — a stripped version of `roles/proxies/templates/caddy-external.yml.j2`:
  - **Drop**: the `(trusted_proxy_list)` snippet and the `(secure)` forward_auth snippet (both re-added in stage 2).
  - **Drop**: `tunnel` network (added back in stage 3).
  - **Keep**: `caddy_external_0.acme_dns: cloudflare [[ cloudflare_api_token ]]`, macvlan attachment, the email global option.
  - **Volumes**: iterate `app.volumes` as above.
  - Networks: `caddy-external`, `macvlan`. **Drop** `tunnel`.

### 1Password prerequisite (must be uploaded before stage 1 runs live)
1. Cloudflare API token (currently `!vault` in `roles/proxies/vars/main.yml`). Must have DNS edit permission for every domain Caddy issues certs for (so it can write `_acme-challenge.<domain>` TXT records).

### Verification
- `uv run pyinfra inventory.py --limit docker_vm deploy.py --dry` should plan out: dir create, Dockerfile put, image build, two network creates, **two `docker.volume` pre-creates** (`caddy-internal-data`, `caddy-external-data`), two compose-file renders (into `/srv/docker/compose/caddy-internal/compose.yaml` and `/srv/docker/compose/caddy-external/compose.yaml`), two `docker compose up`. **No** host directory create under `/srv/docker/volumes/caddy-*`. No errors.
- After live run (when the user is ready): `docker ps` shows `caddy-internal` and `caddy-external` `Up`. `docker volume ls` shows the unscoped `caddy-internal-data` and `caddy-external-data` volumes. `docker logs caddy-internal 2>&1 | grep -i 'certificate obtained successfully'` confirms ACME issuance against the LAN domains in `extra_proxied_domains`. `curl --resolve <domain>:443:192.168.50.20 https://<domain>` for one of those domains returns a valid LE cert chain (no `-k` needed).

---

## Stage 2 — Authelia + forward_auth integration

**Goal:** add Authelia (+ redis) and re-introduce the forward_auth labels on both Caddys.

### Files to modify

`deploys/docker_vm/proxies/secrets.py` (already exists from stage 1 with `cloudflare_api_token`) — extend with the Authelia references. All but the LDAP creds and DB password live in a single shared 1P item `Authelia Secrets`; LDAP creds are in their own `Authelia LDAP client` item; the JWKS pair are *file attachments* on `Authelia Secrets` (referenceable directly by filename in the `op://` path).

```python
from op_secrets import SecretString

# stage 1
cloudflare_api_token        = SecretString("op://Homelab/Cloudflare/apikey")

# stage 2 — authelia
authelia_redis_password     = SecretString("op://Homelab/Authelia Secrets/redis-password")
authelia_smtp_password      = SecretString("op://Homelab/Authelia Secrets/smtp-password")
authelia_smtp_username      = SecretString("op://Homelab/Authelia Secrets/smtp-username")
authelia_jwt_secret         = SecretString("op://Homelab/Authelia Secrets/jwt-secret")
authelia_session_secret     = SecretString("op://Homelab/Authelia Secrets/session-secret")
authelia_storage_encryption = SecretString("op://Homelab/Authelia Secrets/storage-encryption-key")
authelia_hmac_secret        = SecretString("op://Homelab/Authelia Secrets/hmac-secret")
authelia_jwks_private_pem   = SecretString("op://Homelab/Authelia Secrets/oidc-jwks-private.pem")
authelia_jwks_public_pem    = SecretString("op://Homelab/Authelia Secrets/oidc-jwks-public.pem")
authelia_ldap_username      = SecretString("op://Homelab/Authelia LDAP client/name")
authelia_ldap_password      = SecretString("op://Homelab/Authelia LDAP client/password")
authelia_db_password        = SecretString("op://Homelab/PostgreSQL Authelia user/password")

SecretString.populate_cache_sync()
```

Note: `op://Homelab/Authelia Secrets/smtp-username` requires that the field be renamed from its current `smpt-username` (typo) in 1P before this runs.

`deploys/docker_vm/proxies/vars.py`:
- Add `oidc_clients` — a list of dicts (id, name, secret_hash, policy, redirect_uris, scopes, auth_method, signed_alg, require_pkce). The hashed `client_secret` values from `roles/proxies/templates/configuration.yml.j2` are pbkdf2 hashes (not raw secrets) so they live in code; this just parameterises the loop instead of inlining.
- Re-export the new Authelia secrets from `secrets.py` so the templates can reference them.
- Add SMTP server constants (these are non-secret config, not user identity): `smtp_server = "smtp.eu.mailgun.org"`, `smtp_port = 587`. The LDAP and SMTP usernames now come from 1P via `authelia_ldap_username` / `authelia_smtp_username` and are no longer hardcoded in `vars.py`.

`deploys/docker_vm/proxies/apps.py`:
- Add `authelia` ComposeApp:
  - Volumes:
    - `BindMount(source="authelia/config", mount_path="/config")` — managed bind mount (relative source) under `docker_volumes_base` so host-rendered config/secret templates land where Authelia reads them. (`authelia/config/secrets` and `authelia/config/secrets/jwks` are subdirs of the same mount; the helper creates the parent dir, the template upload steps create the subdirs.)
    - `NamedVolume(name="redis-data", mount_path="/data")` — redis runtime state. Compose-owned; becomes `authelia_redis-data`.
  - Templates: `configuration.yml`, `STORAGE_PASSWORD`, `REDIS_PASSWORD`, `SMTP_PASSWORD`, `LDAP_PASSWORD`, `JWT_SECRET`, `SESSION_SECRET`, `STORAGE_ENCRYPTION_KEY`, `HMAC_SECRET`, `jwks/private.pem`, `jwks/public.pem`.
  - The four "static file" templates (`JWT_SECRET.j2`, etc.) and the JWKS PEM templates are now one-line Jinja templates that emit the resolved SecretString — no `files=`, since secrets come from 1Password.

`deploys/docker_vm/proxies/__init__.py`:
- Add `docker.network` calls for `authelia` (172.103.0.0/16, ip_range 172.103.0.0/24, gw 172.103.0.1).
- The shared `docker_compose` call now sees three apps.

`deploys/docker_vm/proxies/templates/`:
- New: `authelia.yaml.j2` — port from `roles/proxies/templates/authelia.yml.j2`. Networks: `caddy-internal`, `caddy-external`, `authelia`. **Note:** the original `postgres` Docker network is dropped — Authelia now talks directly to the PostgreSQL LXC via its IP (`host.data.postgres_lxc_ip`), so no Docker-level networking to Postgres is needed.
- New: `configuration.yml.j2` — port from `roles/proxies/templates/configuration.yml.j2`. Changes from the original: storage.postgres.address now resolves to `[[ host.data.postgres_lxc_ip ]]:5432` (was the Docker hostname `postgres-db:5432`); the hardcoded OIDC client list is replaced by a `[% for c in oidc_clients %]` loop; `nas_ip`, `authelia_ldap_username`, `authelia_smtp_username`, `smtp_server`, `smtp_port` come through `host.data` / `vars`.
- New: `STORAGE_PASSWORD.j2`, `REDIS_PASSWORD.j2`, `SMTP_PASSWORD.j2`, `LDAP_PASSWORD.j2`, `JWT_SECRET.j2`, `SESSION_SECRET.j2`, `STORAGE_ENCRYPTION_KEY.j2`, `HMAC_SECRET.j2` — each a one-liner: `[[ secret_var ]]`.
- New: `jwks/private.pem.j2`, `jwks/public.pem.j2` — also one-liners emitting the SecretString PEM content. (PEM is multi-line text; SecretString resolves to the full content as a string.)
- **Modify** `caddy-internal.yaml.j2` — re-add the `caddy_internal_90: (secure)` forward_auth snippet that points to `authelia:9091`. Add `authelia` to its networks list so it can reach Authelia.
- **Modify** `caddy-external.yaml.j2` — re-add the `(trusted_proxy_list)` snippet (since forward_auth imports it) and the `(secure)` forward_auth snippet. Add `authelia` to its networks list. (Still no `tunnel`.)

### 1Password prerequisite (must be in place before stage 2 runs live)

All Authelia material lives in three existing 1P items in the `Homelab` vault:

**`Authelia Secrets`** — fields:
- `redis-password` (CONCEALED) — was `!vault` in `roles/proxies/vars/main.yml`
- `smtp-password` (CONCEALED) — was `!vault` in `roles/proxies/vars/main.yml`
- `smtp-username` (STRING) — currently labeled `smpt-username` in 1P; **rename to `smtp-username` before running stage 2**
- `jwt-secret` (CONCEALED) — was in `roles/proxies/files/JWT_SECRET`
- `session-secret` (CONCEALED) — was in `roles/proxies/files/SESSION_SECRET`
- `storage-encryption-key` (CONCEALED) — was in `roles/proxies/files/STORAGE_ENCRYPTION_KEY`
- `hmac-secret` (CONCEALED) — was in `roles/proxies/files/HMAC_SECRET`
- File attachment `oidc-jwks-private.pem` — was in `roles/proxies/files/jwks/`
- File attachment `oidc-jwks-public.pem` — was in `roles/proxies/files/jwks/`

**`Authelia LDAP client`** — fields:
- `name` (STRING) — the LDAP bind UID (was hardcoded as `authelia-ldap-client` in `roles/proxies/vars/main.yml`). Note: the `username` field (label `email`) on this item holds the user's contact email, not the LDAP UID; the bind UID lives in `name`.
- `password` (CONCEALED) — was `!vault` in `roles/proxies/vars/main.yml`

**`PostgreSQL Authelia user`** (unchanged from existing usage) — field `password`.

### Verification
- `uv run pyinfra inventory.py --limit docker_vm deploy.py --dry` should plan out: an extra network create (`authelia`), the four authelia volume dirs, all the secret/config template renders, the authelia + redis compose stack up, plus updated Caddy compose files (forward_auth labels back). No errors.
- Live run (when the user is ready): `docker ps` shows `authelia` and `redis` `Up`. Visit any of the configured `(secure)`-gated domains (e.g. `https://tv.dv.zone` if DNS resolves) — expect a redirect to `https://auth.dv.zone`. (That redirect won't actually resolve until stage 3 brings the tunnel up.)

---

## Stage 3 — Cloudflare tunnel

**Goal:** add `cloudflared` and the `tunnel` network so caddy-external can serve traffic from the internet via the Cloudflare tunnel. (Real ACME is already in place from stage 1.)

### Files to modify

`deploys/docker_vm/proxies/secrets.py`:
- Add two more SecretStrings (the Cloudflare API token is already declared in stage 1):
  ```python
  cloudflare_tunnel_id         = SecretString("op://Homelab/Cloudflare Tunnel/id")
  cloudflared_credentials_json = SecretString("op://Homelab/Cloudflare Tunnel/credentials.json")
  ```

`deploys/docker_vm/proxies/vars.py`:
- Re-export the two Cloudflare tunnel secrets so templates can reference them.
- Add `CLOUDFLARE_UID = 65532`, `CLOUDFLARE_GID = 65532` (the cloudflared image's nonroot user).

`deploys/docker_vm/proxies/apps.py`:
- Add `cloudflared` ComposeApp:
  - Volume: `BindMount(source="cloudflared", mount_path="/etc/cloudflared", uid=CLOUDFLARE_UID, gid=CLOUDFLARE_GID)` — managed bind mount (relative source) so the rendered `config.yml` and `<tunnel_id>.json` templates can be read by cloudflared. No persistent runtime state worth a named volume.
  - Templates: `cloudflared-config.yml` → `cloudflared/config.yml`, `cloudflared-credentials.json` → `cloudflared/<tunnel_id>.json`.

`deploys/docker_vm/proxies/__init__.py`:
- Add `docker.network` for `tunnel` (172.104.0.0/16, ip_range 172.104.0.0/24, gw 172.104.0.1).
- The shared `docker_compose` call now sees four apps.

`deploys/docker_vm/proxies/templates/`:
- New: `cloudflared.yaml.j2` — port from `roles/proxies/templates/cloudflared.yml.j2`. Networks: `tunnel`.
- New: `cloudflared-config.yml.j2` — port from `roles/proxies/templates/cloudflared-config.yml.j2` (ingress list, tunnel id from `host.data` / vars).
- New: `cloudflared-credentials.json.j2` — one-liner emitting the SecretString JSON.
- **Modify** `caddy-external.yaml.j2`:
  - Add `tunnel` to its networks list (so cloudflared can reach it via `https://caddy-external:443`).
- `caddy-internal.yaml.j2` is unchanged in this stage.

### 1Password prerequisite (must be uploaded before stage 3 runs live)
1. Cloudflare tunnel id (`110e25f1-...` from `roles/proxies/vars/main.yml`) — store as a plain field, since the value is non-sensitive but we want it managed in one place.
2. `credentials.json` for the tunnel — must be obtained from the existing NAS host (`/volume2/docker/cloudflared/<tunnel_id>.json`) or by re-running `cloudflared tunnel login`. **Not in the repo today.**

(The Cloudflare API token was already uploaded as a stage 1 prerequisite.)

### Verification
- `uv run pyinfra inventory.py --limit docker_vm deploy.py --dry` should plan out: an extra network create (`tunnel`), the cloudflared volume dir, the config + credentials templates, the cloudflared compose stack up, plus an updated caddy-external compose file (`tunnel` network added). No errors.
- Live run: `docker ps` shows `cloudflared` `Up`. From the internet: `https://auth.dv.zone` resolves through the Cloudflare tunnel to caddy-external → authelia. SSO end-to-end on any `(secure)`-gated domain works.

---

## Critical files

- `deploys/docker_vm/proxies/__init__.py` (new — built up across stages)
- `deploys/docker_vm/proxies/apps.py`, `vars.py`, `secrets.py` (new — built up across stages)
- `deploys/docker_vm/proxies/templates/*` (new — added to across stages)
- `group_data/docker_vm.py` (edited once in stage 0)
- `deploy.py` (edited once in stage 1)

Reference files (read but not modified):
- `roles/proxies/{tasks,vars,templates,files}/*` — source of truth for the port
- `deploys/common/docker_compose/__init__.py` — helper signature/behavior
- `deploys/nas/docker/__init__.py` — pattern for an end-to-end docker_compose deploy
- `nas.yml` lines 18–60 — variable values currently in scope when the role runs

## Cut-over notes (out of scope of this change)

- The Ansible `proxies` role still runs when `nas.yml` is invoked, which would re-create the same Caddy stack on the NAS. After confirming the docker_vm version works end-to-end, the user comments the role out of `nas.yml` (or removes it).
- DNS in Cloudflare may need updating: any record currently aimed at the NAS macvlan IPs needs to flip to the docker_vm macvlan IPs (192.168.50.20 / .21). The Cloudflare tunnel itself is hostname-based (`hostname → service: https://caddy-external:443`), so it follows wherever cloudflared runs.
