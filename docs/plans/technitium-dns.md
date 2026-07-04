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

- ~~Second Technitium instance on `nas`~~ → now **Phase 2** below (done).
- ~~Decommissioning pi-hole and the Ansible `roles/dns-setup` role~~ → done; pi-hole is
  decommissioned and the Ansible config lives in the archived `homelab-old` repo.

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

---

# Phase 2: NAS secondary instance + Technitium clustering

## Goal

Stand up a **second** Technitium instance on the `nas` host and cluster it with the
docker_vm instance so the two form an HA pair — config, blocklists, users, and zones sync
across both, and either can answer LAN DNS if the other is down. Reuses the same
group-agnostic `deploys/dns/` code, parameterised per host through `group_data`.

## Decisions (confirmed with user)

- **Rename the existing (docker_vm) console domain** `dns.dv.zone` → **`dns1.dv.zone`**.
- **New NAS instance console domain** → **`dns2.dv.zone`**.
- **NAS instance macvlan IP** → **`192.168.1.210`** (inside the NAS macvlan range
  `192.168.1.192/27`; `.223` is the host aux-address, `.193–.222` otherwise free — only
  cAdvisor/portainer-agent run on the NAS and they use *host* ports, not macvlan).
- **SSO enabled on both nodes**, mirroring the same `DNS_SERVER_SSO_*` env (same Authelia
  client id/secret/authority). Admin-password login remains as a fallback on both.
- **Clustering is configured in the Technitium web UI** (Administration → Cluster) — it has
  **no `DNS_SERVER_*` env-var support**. pyinfra stands up the node; the cluster *join* is a
  one-time manual UI step. Nodes talk **node-to-node over TCP `53443`** (the HTTPS web
  service) authenticated with **DANE-EE**. Config/blocklists/users/API-tokens/catalog-zones
  sync primary→secondary; cache, logs and login sessions stay per-node.
  Ref: <https://blog.technitium.com/2025/11/understanding-clustering-and-how-to.html>.
- **Primary = docker_vm (`dns1`)**, **secondary = NAS (`dns2`)**.

## Reachability findings (verified during planning, from the NAS)

Cross-subnet routing between the NAS LAN (`192.168.1.0/24`) and the docker_vm macvlan
(`192.168.50.0/24`) works via the gateway (`192.168.1.1`):

- NAS → `192.168.50.30:53` (**live primary DNS**) — **open**.
- NAS → `192.168.50.10:22` (docker_vm host) — **open**.
- NAS → `auth.dv.zone` → `192.168.50.21:443`, `GET /.well-known/openid-configuration` →
  **HTTP 200**. So the secondary **can** complete a server-side SSO token exchange.
- NAS → `192.168.50.30:53443` — *refused* today, only because the HTTPS web service /
  cluster port isn't enabled on the primary yet (**not** a routing block). Enabling it on
  both nodes is part of the cluster-init step.

> A bare-TCP `/dev/tcp` probe to the caddy IPs gave a false "unreachable"; the authoritative
> `curl` (real TLS handshake) returns 200. Trust the `curl`/`dig` result, not `/dev/tcp`.

## Code changes

### 1. Parameterise the console subdomain (template currently hardcodes `dns.`)

- `group_data/docker_vm.py`: add `dns_console_subdomain = "dns1"`.
- `group_data/nas.py`: add `dns_console_subdomain = "dns2"`, `dns_ip = "192.168.1.210"`, and
  `external_reverse_proxy_ip = "192.168.50.21"` (the template's `extra_hosts` auth-pin reads
  it; confirmed reachable from the NAS).
- `deploys/dns/templates/technitium-dns.yaml.j2`: replace every literal `dns.[[ host.data.domain ]]`
  with `[[ host.data.dns_console_subdomain ]].[[ host.data.domain ]]` (in `DNS_SERVER_DOMAIN`
  and the `caddy_internal` label). The `sso/callback` redirect is derived by Technitium from
  the request host, so no template change there.

### 2. Branch the console-proxy path (caddy-internal exists only on docker_vm)

The NAS has no `caddy-internal` network and no caddy — so the container's caddy network
membership + `caddy_internal*` labels must be docker_vm-only.

- `group_data/docker_vm.py`: add `dns_console_via_caddy_labels = True`.
- `group_data/nas.py`: leave it unset/`False`.
- Template: wrap the `caddy-internal:` network entry **and** the `labels:` block in
  `[% if host.data.dns_console_via_caddy_labels %] … [% endif %]`. On the NAS the container
  joins only `macvlan`, and the top-level `caddy-internal` external network is likewise
  guarded out.
- Proxy the NAS console from the **docker_vm** caddy instead: add to
  `group_data/docker_vm.py` `extra_proxied_domains`:
  `{"domain": "dns2.dv.zone", "ip": "192.168.1.210", "port": 5380}`. The caddy-internal
  template already supports the optional `ip` override
  (`domain.ip | default(host.data.nas_ip, true)`).

### 3. Authelia OIDC client (`deploys/docker_vm/proxies/vars.py`)

In the existing `technitium-dns` client (reused by both nodes):

- Change `redirect_uris` `https://dns.dv.zone/sso/callback` → `https://dns1.dv.zone/sso/callback`.
- **Add** `https://dns2.dv.zone/sso/callback` to the same list.

### 4. Wire the NAS deploy (`deploy.py`)

`setup_technitium_dns` is already imported. In the `if "nas" in host.groups:` block, call
`setup_technitium_dns()` **after** `nas_docker_setup()` (which creates the NAS `macvlan`
network and compose dirs the stack references).

### 5. Domain-rename touchpoints (`dns` → `dns1`) — summary

- `group_data/docker_vm.py` — `dns_console_subdomain = "dns1"` (item 1).
- `deploys/docker_vm/proxies/vars.py` — redirect_uri rename (item 3).
- This doc — Phase-1 references to `dns.dv.zone` (verification step 6, the SSO section) become
  `dns1.dv.zone`.
- **No client reconfiguration:** LAN resolvers point at the *IP* `192.168.50.30`, not at
  `dns.dv.zone` (that's only the console/OIDC hostname), and `.30` is unchanged. Nothing on
  the resolution path breaks from the rename.

### External volume note

`technitium-dns-config` is `external=True`; the `docker_compose` helper auto-creates it via
`docker.volume(present=True)` on whichever host runs the stack — **no manual pre-creation on
the NAS**. The secondary can boot with an empty config volume; clustering then syncs state
from the primary.

### 6. Cluster domain + multi-domain caddy support (deployed 2026-07-04)

Technitium clustering requires a **cluster domain that has no existing primary zone** — so
**not `dv.zone`** (which is served as a zone). We use **`cluster.dv.zone`**, giving the nodes
the FQDNs **`dns1.cluster.dv.zone`** / **`dns2.cluster.dv.zone`**
([discussion #1722](https://github.com/TechnitiumSoftware/DnsServer/discussions/1722#discussioncomment-15725615)).
Those node FQDNs need **real TLS certs** for node-to-node HTTPS. Technitium's HTTP service
ignores the `Host` header, so each node is reachable under *both* its console name and its
cluster name on the same `:5380` upstream — so caddy just serves both names (one LE cert each,
same reverse_proxy).

To let a single Technitium container advertise two console domains, caddy now accepts
**multiple domains per service** (the caddy-docker-proxy `caddy: a.com, b.com` form):

- **Labels path (dns1, on docker_vm):** `group_data/docker_vm.py` gains
  `dns_console_domains = ["dns1.dv.zone", "dns1.cluster.dv.zone"]`; the Technitium template
  renders `caddy_internal: [[ host.data.dns_console_domains | join(', ') ]]`. (`DNS_SERVER_DOMAIN`
  still uses `dns_console_subdomain` and stays `dns1.dv.zone`.)
- **extra_proxied_domains path (dns2, proxied from docker_vm caddy):** an entry may now carry a
  `domains` list instead of a single `domain`; `caddy-internal.yaml.j2` renders
  `[[ (domain.get('domains') or [domain.domain]) | join(', ') ]]` (back-compatible — existing
  single-`domain` entries are untouched). The dns2 entry is
  `{"domains": ["dns2.dv.zone", "dns2.cluster.dv.zone"], "ip": "192.168.1.210", "port": 5380}`.

**Verified:** all four names return HTTP 200 through caddy `.20`, and both `*.cluster.dv.zone`
names present a valid Let's Encrypt cert (`SSL certificate verify ok`, obtained via DNS-01).
For the cluster to actually *use* those names, `dns1/dns2.cluster.dv.zone` must resolve to the
nodes — set up in the Technitium cluster zone during cluster init (below).

## Manual post-deploy step: form the cluster (web UI) — ✅ DONE 2026-07-04

The cluster is **formed and working** (dns1 primary + dns2 secondary, config/blocklists/users
syncing). Steps that were performed:

0. Cluster domain = **`cluster.dv.zone`** (no primary zone exists for it); node names
   **`dns1.cluster.dv.zone`** / **`dns2.cluster.dv.zone`** (caddy already serves valid certs
   for both — see §6).
1. Enable the **HTTPS web service on `53443`** on **both** nodes (self-signed cert is fine —
   DANE-EE pins it). Do this in each console's *Settings → Web Service*, or pre-set the
   `DNS_SERVER_WEB_SERVICE_*` env (exact var names TBD during implementation — confirm
   against the Technitium docker README; UI is the fallback).
2. On **dns1** (primary): *Administration → Cluster* → initialise the cluster.
3. On **dns2** (secondary): *Administration → Cluster* → join, pointing at the primary.
   Nodes exchange over `53443`/DANE-EE and populate the cluster catalog zone.
4. Confirm blocklists, users, and settings replicate to dns2.

## Router / DHCP (manual, outside pyinfra)

Hand out **both** resolvers to LAN clients so redundancy is real: add `192.168.1.210` as the
secondary DNS alongside `192.168.50.30` in the router's DHCP scope. (Not required for the
deploy itself; needed for clients to actually fail over.)

## Tests

Any change to the `technitium-dns.yaml.j2` template is not fact/operation-covered (it's a
compose template, not a custom fact/op), so no `pyinfra-testing` cases are added. Still run
`uv run pytest` to confirm nothing regressed.

## Verification

1. `uv run pytest` green.
2. Dry-run both: `uv run pyinfra inventory.py --limit nas deploy.py --dry` and
   `--limit docker_vm deploy.py --dry`; review the rendered NAS compose (only `macvlan`, no
   caddy network/labels) and the docker_vm `dns2` proxy entry.
3. Apply (`-y`): `--limit nas` then `--limit docker_vm`.
4. On the NAS: `docker ps` shows `technitium-dns` at `192.168.1.210` on `macvlan`; rendered
   compose at `<compose_base>/technitium-dns/compose.yaml`, secret files under
   `<volumes_base>/technitium-dns/secrets/`.
5. From a LAN client: `dig @192.168.1.210 example.com` answers; `dig @192.168.1.210 <ad-domain>`
   returns `0.0.0.0`/NXDOMAIN (blocking works).
6. Consoles: `https://dns1.dv.zone` **and** `https://dns2.dv.zone` both load with valid LE
   certs; SSO login works on both.
7. Form the cluster (above); change a block rule on dns1 → confirm it appears on dns2.

## Status — ✅ COMPLETE (2026-07-04)

Phase 2 is **fully done**: both instances deployed *and* clustered.

- ✅ docker_vm primary renamed `dns` → **`dns1.dv.zone`** (console via caddy → HTTP 200, LE
  cert); primary DNS answering on `192.168.50.30`.
- ✅ NAS secondary **`dns2.dv.zone`** up at macvlan `192.168.1.210` — resolves on `:53` and its
  console loads through the docker_vm caddy (HTTP 200, valid LE cert), confirming the
  cross-subnet `caddy(.20) → NAS(192.168.1.210:5380)` proxy path works.
- ✅ Authelia `technitium-dns` OIDC client lists both `dns1`/`dns2` `sso/callback` URIs; SSO
  works on both.
- ✅ Cluster domain `cluster.dv.zone`; nodes `dns1/dns2.cluster.dv.zone` serve valid LE certs
  (caddy multi-domain). **Cluster formed and working** — config/blocklists/users sync
  primary→secondary.

pi-hole is decommissioned. The only remaining follow-up is the router-DHCP secondary-resolver
handout (manual, outside pyinfra) — see the "Router / DHCP" section above.

## Resolved verification items

- ✅ **Primary (`192.168.50.30`) ↔ secondary (`192.168.1.210`) on `53443`** — cluster link is
  up; nodes exchange over `53443`/DANE-EE. (Routing was already proven; the `53443` listener
  was enabled during cluster init.)
- Moot: pre-enabling HTTPS/`53443` via `DNS_SERVER_WEB_SERVICE_*` env was never needed — the
  listener was enabled in the UI as part of cluster init.
