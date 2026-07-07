# Plan: Stand up Shelfmark (replaces `cwa-dl`) — docker_vm/pyinfra

## Context

`cwa-dl` (Calibre-Web-Automated-Book-Downloader, `books-dl.dv.zone`) was the
companion downloader that fed books into CWA's auto-ingest. On the NAS it ran as a
two-service `:latest` compose stack: the downloader plus a
`ghcr.io/sarperavci/cloudflarebypassforscraping` sidecar it talked to over
`CLOUDFLARE_PROXY_URL`, both behind Authelia forward-auth (`import secure *`).

It is **not** migrated. Per `docs/plans/open-todos.md` §3 and
`docs/plans/cwa-migration.md` "Follow-ups #2", `cwa-dl` is **superseded by
[Shelfmark](https://github.com/calibrain/shelfmark)** and stood up **fresh** on
docker_vm — no config/state carried over — pointed at the **same** CWA ingest
bind so downloads keep flowing into CWA's auto-ingest.

### Key facts (from Shelfmark's docs)

- **No Cloudflare-bypass sidecar needed.** The full `ghcr.io/calibrain/shelfmark`
  image bundles the bypasser (`USE_CF_BYPASS=true`, `USING_EXTERNAL_BYPASSER=false`
  by default). Only the separate `shelfmark-lite` image needs an external
  FlareSolverr via `EXT_BYPASSER_URL`. We use the full image, so the sidecar the
  NAS `cwa-dl` stack ran is dropped entirely.
- **Port 8084** (`FLASK_PORT` default) — same port the old `cwa-dl` used.
- **Config dir `/config`** (`CONFIG_DIR` default): app settings, users, sources,
  the request queue, and the OIDC provider config (see below).
- **Download dir via `INGEST_DIR`** (default `/books`): where completed downloads
  land. We point this at the CWA ingest bind so CWA picks them up.
- **OIDC is configured in Shelfmark's own UI** (Settings → Security →
  Authentication Method → OIDC), persisted in `/config` — exactly like CWA. So
  there is **nothing OIDC-related in the compose template and no secret in
  `apps/secrets.py`**; the config is entered once and survives redeploys on the
  external `/config` volume. Shelfmark constructs its callback from
  `X-Forwarded-Proto`/`X-Forwarded-Host` (caddy sets both by default) and uses
  **PKCE (S256) automatically**.
- Pinned version: **`v1.3.2`** (latest release; the project is stable/frozen as of
  May 2026, per its README).

## Implementation

### App entry — `deploys/docker_vm/apps/apps.py`

```python
ComposeApp(
    name="shelfmark",
    image="ghcr.io/calibrain/shelfmark",
    version="v1.3.2",
    domain="shelfmark.dv.zone",
    volumes=[
        NamedVolume(name="shelfmark-config", mount_path="/config", external=True),
        BindMount(source="cwa/ingest", mount_path="/cwa-book-ingest"),
    ],
)
```

- **Config** is an external named volume (`shelfmark-config`, `external=True`):
  fresh install, but users/sources/requests + the OIDC provider config have a
  non-trivial recovery cost, so `down -v` must not wipe them.
- **Ingest** reuses CWA's existing `cwa/ingest` bind (host
  `/srv/docker/volumes/cwa/ingest`, mounted here at `/cwa-book-ingest`). Shelfmark
  writes completed downloads there and CWA's watcher ingests + removes them —
  same handoff the old `cwa-dl` did. No secret, so `apps/secrets.py` is untouched.

### Compose template — `deploys/docker_vm/apps/templates/shelfmark.yaml.j2`

Modelled on `cwa.yaml.j2`. Port 8084, `INGEST_DIR=/cwa-book-ingest`,
**PUID 2000 / PGID 100** (matches CWA so both share ownership of the ingest files
— same uid means CWA can read/delete what Shelfmark writes), reverse-proxy on
`caddy-internal`, and an Entertainment homepage tile (`shelfmark.png` icon, no
widget — Shelfmark has no homepage widget, same as `cwa-dl`). **No `import
secure`**: Shelfmark gates itself with its own native OIDC against Authelia
(client `shelfmark`; provider configured once in Shelfmark's UI), so OIDC is the
sole gate rather than a blanket forward-auth. The bundled CF bypass means a
single-service stack (no sidecar, no extra network).

## Authelia OIDC client (owned by the operator, not this repo)

Same pattern as CWA: the client lives in `deploys/docker_vm/proxies/vars.py` and
the secret in 1Password; **nothing in this repo resolves the `op://` ref at deploy
time** (only the pbkdf2 hash is in `vars.py`). Register it with:

```bash
uv run python cmd.py oidc add-client "Shelfmark" \
  "https://shelfmark.dv.zone/api/auth/oidc/callback" --pkce
```

- **Redirect URI:** `https://shelfmark.dv.zone/api/auth/oidc/callback`
- **Auth method:** `client_secret_basic` (default), **PKCE S256** (`--pkce`).
- **Scopes:** `openid groups email profile` (default). No `claims_policy` needed —
  Shelfmark reads the `groups` claim from Authelia's userinfo endpoint (same as
  CWA), so the `groups` scope delivers it without a claims policy.
- Store the printed secret in 1Password at
  `op://Homelab/Shelfmark OIDC client/password`; paste the printed block into
  `proxies/vars.py`.

## Deploy

```bash
uv run pyinfra inventory.py --limit docker_vm deploy.py    # dry-run first
uv run pyinfra inventory.py --limit docker_vm deploy.py -y # apply (needs -y)
```

Deploy the Authelia client (from `vars.py`) and Shelfmark together (or the client
first). `setup_apps()` picks up the new app automatically; `setup_caddy_proxies()`
runs first, so `caddy-internal` exists. `OP_SERVICE_ACCOUNT_TOKEN` must be set.

## One-time OIDC setup in Shelfmark's UI (rollout order matters)

Shelfmark comes up with local auth first; configure OIDC, verify, then disable
local auth so OIDC is the sole gate — the CWA ordering, to avoid lockout.

1. First deploy → Shelfmark reachable at `https://shelfmark.dv.zone`. Create/local
   the initial admin.
2. **Settings → Security → Authentication Method → OIDC:**
   - **Discovery URL** = `https://auth.dv.zone/.well-known/openid-configuration`
   - **Client ID** = `shelfmark`
   - **Client Secret** = value from `op://Homelab/Shelfmark OIDC client/password`
   - **Scopes** = `openid email profile` (the `groups` claim is added
     automatically when admin-group authorization is on)
   - **Admin Group Name** = your Authelia/LLDAP admin group
   - Use **Test Connection**, then log out and confirm the OIDC button completes
     the round-trip and an admin-group member lands with admin rights.
3. Only after OIDC works: set **`DISABLE_LOCAL_AUTH: "true"`** in
   `shelfmark.yaml.j2` and redeploy (or `HIDE_LOCAL_AUTH` to keep the local
   fallback but hide it). This makes OIDC the sole gate.

## Verification

- **Dry-run:** `shelfmark-config` external volume pre-created; the `cwa/ingest`
  bind dir already exists (shared with CWA); compose rendered to
  `/srv/docker/compose/shelfmark/compose.yaml` as a single service with the named
  + bind volumes and `INGEST_DIR=/cwa-book-ingest`. Re-run → noop.
- **Container:** `docker ps` shows `shelfmark` up on `caddy-internal`;
  `docker logs shelfmark` clean; `curl -I https://shelfmark.dv.zone` reachable.
- **Ingest handoff:** trigger a download in Shelfmark → the file lands in
  `/srv/docker/volumes/cwa/ingest` and CWA ingests + removes it.
- **Homepage:** Entertainment tile links to `https://shelfmark.dv.zone`.

## Decommission (NAS `cwa-dl`) — Ansible side (`homelab-old`)

Once Shelfmark is verified: stop/remove the NAS `cwa-dl` compose stack **and its
`cloudflarebypass` sidecar**, delete its bind data, and remove the Ansible config
(`roles/docker-apps/templates/cwa-dl.yml.j2` + the `cwa-dl` entry in
`roles/docker-apps/vars/main.yml`). Then flip open-todos §3 Shelfmark to ✅.

## Status

**Deployed and verified 2026-07-07.** `shelfmark` is up on docker_vm at
`shelfmark.dv.zone` (`ghcr.io/calibrain/shelfmark:v1.3.2`), single service (no
sidecar — built-in CF bypass), running `2000:100`, `/config` on the external
`shelfmark-config` volume, and `/cwa-book-ingest` bound to the shared
`/srv/docker/volumes/cwa/ingest`. `https://shelfmark.dv.zone` returns 200 through
caddy-internal. The Authelia `shelfmark` OIDC client is registered
(`proxies/vars.py`, PKCE S256, secret in `op://Homelab/Shelfmark OIDC client`) and
Authelia reloaded to pick it up.

**Complete.** OIDC is configured in Shelfmark's UI and local login disabled, so
OIDC is the sole gate; the NAS `cwa-dl` stack + its `cloudflarebypass` sidecar are
decommissioned. open-todos §3 flipped to ✅.
