# Plan: Run Technitium DNS on the Docker VM (pyinfra)

## Context

The homelab currently runs **pi-hole** as its DNS server, deployed on the Synology NAS
via the legacy Ansible `roles/dns-setup` role. We are moving to **Technitium DNS**,
managed by pyinfra. The end state is *two* Technitium instances — one on the `docker_vm`
host, one on the `nas` host — for DNS redundancy, eventually retiring pi-hole.

This document covers **phase 1: a single Technitium instance on `docker_vm`** via Docker
Compose, using the shared `docker_compose` helper, with its web console exposed through the
existing caddy-internal reverse proxy. pi-hole, the Ansible `dns-setup` role, and the
second (NAS) instance are out of scope for this phase.

Because two instances are coming, the deploy code lives in a **group-agnostic
`deploys/dns/` package** (not `deploys/docker_vm/dns/`). The shared helper resolves
everything through `host.data.*`, so the same `@deploy` function can later be invoked from
the `nas` block with NAS-specific `group_data`. This mirrors how `deploys/common/` holds
cross-host code while `deploys/<group>/` holds host-specific code.

## Decisions

- **App name:** `technitium-dns` (container, compose project, volumes, template all use this).
- **Networking:** macvlan static IP **`192.168.50.30`** on the existing `macvlan` network
  (caddy uses `.20`/`.21`; the VM host itself is `.10`). Avoids the systemd-resolved
  port-53 conflict that host-mode / published-ports would cause, and gives DNS a real
  routable LAN IP for `:53`.
- **Web console:** exposed via **caddy-internal using caddy-docker-proxy labels** (same
  pattern as authelia). `technitium-dns` also joins the `caddy-internal` bridge network so
  caddy resolves it directly (no reliance on macvlan↔macvlan routing). Console auth is
  **Technitium native OIDC** against Authelia (not caddy forward_auth) — see the SSO section.
- **Config scope:** declarative — set forwarders, `RECURSION=AllowOnlyForPrivateNetworks`,
  blocking + blocklist URLs via env vars so a clean volume boots pi-hole-like.
- **Admin password:** stored in 1Password, rendered to a secret file, injected via
  `DNS_SERVER_ADMIN_PASSWORD_FILE`. Reference: `op://Homelab/Technitium DNS/password`.

## Prerequisite (user action)

Create the 1Password item **`Homelab / Technitium DNS`** with a `password` field before the
first deploy (secret resolution happens at import time via `SecretString`).

## Files created

```
deploys/dns/
├── __init__.py                       # @deploy("Provision Technitium DNS with Docker") -> setup_technitium_dns()
├── apps.py                           # ComposeApp definition (volumes + secret TemplateFile)
├── secrets.py                        # SecretString refs + populate_cache_sync()
├── vars.py                           # version, forwarders, blocklist URLs, admin pw import
└── templates/
    ├── technitium-dns.yaml.j2        # compose stack (filename must match app.name)
    └── ADMIN_PASSWORD.j2             # single-line secret file
```

Reuses the shared helper and models (no new helper code):
- `deploys/common/docker_compose/docker_compose()` — `deploys/common/docker_compose/__init__.py`
- `ComposeApp`, `NamedVolume`, `BindMount`, `TemplateFile` — `deploys/common/docker_compose/models.py`
- Volume macros `vol.service_volumes(app)` / `vol.top_level_volumes(app)` — `deploys/common/docker_compose/templates/_volumes.j2`

## Files modified

- **`group_data/docker_vm.py`**
  - Added `dns_ip = "192.168.50.30"`.
  - Removed the stale pi-hole entry `{"domain": "dns.dv.zone", "port": 8080}` from
    `extra_proxied_domains` — the Technitium console is now proxied via container labels
    instead, so a static entry would double-define `dns.dv.zone`.
- **`deploy.py`** — imports `setup_technitium_dns` and calls it inside the
  `if "docker_vm" in host.groups:` block, **after** `docker_setup()` (creates the `macvlan`
  network) and `setup_caddy_proxies()` (creates the `caddy-internal` network) — the compose
  file references both as `external: true`.

## Key implementation notes

- `/etc/dns` is an **external** named volume (`technitium-dns-config`) — precious DNS
  config/zones/blocklists survive `docker compose down -v`. Logs are a compose-owned
  (disposable) named volume.
- The admin password file is rendered into a managed bind dir
  (`<docker_volumes_base>/technitium-dns/secrets`) and mounted read-only at `/run/secrets`,
  rather than nesting a bind mount inside the `/etc/dns` named volume.
- Compose templates use custom Jinja delimiters (`[[ ]]` / `[% %]`), set by the helper to
  avoid clashing with compose / caddy syntax. `{{upstreams 5380}}` is literal
  caddy-docker-proxy syntax and passes through untouched (matches authelia's `{{upstreams 9091}}`).
- caddy-internal ingress works because that network sets `CADDY_INGRESS_NETWORKS=caddy-internal`
  with label prefix `caddy_internal`; caddy discovers `technitium-dns` and proxies `dns.dv.zone`.

## SSO via Authelia (Technitium native OIDC)

Technitium is registered as a confidential OIDC client of the existing Authelia IdP, using
Technitium's built-in SSO (`DNS_SERVER_SSO_*` env vars) — not caddy forward_auth.

- **Authelia side** (`deploys/docker_vm/proxies/vars.py`): a `technitium-dns` entry added to
  `oidc_clients` — `policy: two_factor`, `redirect_uris: [https://dns.dv.zone/sso/callback]`,
  `scopes: [openid, email, profile]`, `auth_method: client_secret_post`, inline `secret_hash`
  (non-secret pbkdf2, sourced from the `OIDC client secret hash` field of the 1Password item).
- **Technitium side** (`deploys/dns/`): env vars `DNS_SERVER_SSO_ENABLED=true`,
  `DNS_SERVER_SSO_AUTHORITY=https://auth.dv.zone`, `DNS_SERVER_SSO_CLIENT_ID=technitium-dns`,
  `DNS_SERVER_SSO_CLIENT_SECRET_FILE=/run/secrets/SSO_CLIENT_SECRET`,
  `DNS_SERVER_SSO_SCOPES=openid,profile,email`, `DNS_SERVER_SSO_ALLOW_SIGNUP=false`.
  The plaintext client secret comes from `op://Homelab/Technitium DNS/OIDC client secret`,
  rendered to a file via the same `/run/secrets` bind dir as the admin password.
- **No auto-signup**: only pre-existing Technitium accounts can use SSO — link/create the
  account in the Technitium UI first.
- **Auth-method caveat**: `client_secret_post` is the assumed token-endpoint auth method
  (Technitium uses a custom OIDC client at `/sso/callback`). If token exchange fails at
  login, flip both sides to `client_secret_basic`.

## Out of scope (future phases)

- Second Technitium instance on `nas` (add `dns_ip` to `group_data/nas.py`, call
  `setup_technitium_dns()` in the `nas` block — same `deploys/dns/` code).
- Decommissioning pi-hole and the Ansible `roles/dns-setup` role.

## Verification

1. Ensure `OP_SERVICE_ACCOUNT_TOKEN` is exported and the `Homelab / Technitium DNS` item exists.
2. Dry run and review: `uv run pyinfra inventory.py --limit docker_vm deploy.py --dry`
3. Apply: `uv run pyinfra inventory.py --limit docker_vm deploy.py`
4. Sanity-check existing pyinfra unit tests still pass: `uv run pytest`
5. On the VM: `docker ps` shows `technitium-dns` running with IP `192.168.50.30` on `macvlan`
   and attached to `caddy-internal`. Confirm rendered compose at
   `/srv/docker/compose/technitium-dns/compose.yaml` and secret at
   `/srv/docker/volumes/technitium-dns/secrets/ADMIN_PASSWORD`.
6. From a LAN client (not the VM host — macvlan isolates host↔container):
   - `dig @192.168.50.30 example.com` returns an answer (recursion/forwarding works).
   - `dig @192.168.50.30 <a-known-ad-domain>` returns `0.0.0.0`/NXDOMAIN (blocking works).
   - Console via proxy: `https://dns.dv.zone` (valid LE cert via caddy-internal), log in as
     `admin` with the 1Password value.
7. Persistence: `docker compose -p technitium-dns down -v`, re-run the deploy, confirm
   settings survive (external `technitium-dns-config` volume).

> Note: Technitium applies `DNS_SERVER_*` env vars on startup. If env config and later UI
> edits to the same settings diverge, treat the env vars as the source of truth.
