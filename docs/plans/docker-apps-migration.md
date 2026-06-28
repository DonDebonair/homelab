# Plan: Port docker apps from the NAS to the Docker VM (Ansible → pyinfra)

## Context

The homelab runs 20 docker apps on the Synology NAS via the legacy Ansible
`roles/docker-apps` role. We are migrating these onto the pyinfra-managed
`docker_vm` host, app by app. The section below tracks **overall progress**; the
rest of this document is the original write-up of the **first step** — standing
up the **common scaffolding** for ordinary docker apps and porting `dozzle` (a
stateless docker log viewer) end-to-end as the proving case.

## Migration tracker

20 apps in the Ansible `roles/docker-apps` role (source of truth:
`roles/docker-apps/vars/main.yml`). **6 ported, 12 left to port, 2 won't be
ported** (superseded/dropped). Ported apps live in
`deploys/docker_vm/apps/apps.py` with a `templates/<app>.yaml.j2` each.

| App | Domain | Homepage group | Exposure | State / dependencies | Status |
|-----|--------|----------------|----------|----------------------|--------|
| dozzle | dozzle.dv.zone | Admin | internal | docker socket only (stateless) | ✅ Ported |
| whoami | whoami.dv.zone | — | external | none (stateless) | ✅ Ported |
| miniflux | rss.dv.zone | Bookmarks | external | postgres `miniflux`, OIDC | ✅ Ported |
| paperless | docs.dv.zone | Office | internal | postgres `paperless`, redis/tika/gotenberg sidecars, external named vols, OIDC, secrets | ✅ Ported |
| homepage | home.dv.zone | — | internal | bind-mount config + docker socket; `homepage.*` labels drive the dashboard | ✅ Ported |
| pgadmin | pgadmin.dv.zone | Databases | internal | `pgadmin/{data,config}` vols (uid/gid 5050), `config_local.py` template, OIDC | ⬜ To port |
| portainer | docker.dv.zone | Admin | internal | `portainer` vol, docker socket | ⬜ To port |
| tautulli | tautulli.dv.zone | Entertainment | internal | `tautulli/config` vol | ⬜ To port |
| overseerr | requests.dv.zone | Entertainment | internal | `overseerr` vol | ⬜ To port |
| sabnzbd | nzb.dv.zone | Downloaders | internal | `sabnzbd/config` vol | ⬜ To port |
| qbittorrent | torrent.dv.zone | Downloaders | internal | `qbittorrent/config` vol | ⬜ To port |
| forgejo | git.dv.zone | Development | internal | postgres `forgejo`, external `forgejo-data` vol, git-over-SSH via caddy-internal layer4; upgraded 8→15.0.3 (LTS) | ✅ Ported |
| nocodb | nocodb.dv.zone | Databases | internal | postgres `nocodb`, `nocodb` vol | ⬜ To port |
| n8n | n8n.dv.zone | Automation | internal | postgres `n8n`, `n8n` vol (uid/gid 1000) | ⬜ To port |
| pinchflat | pinchflat.dv.zone | Entertainment | internal | `pinchflat/config` vol | ⬜ To port |
| stash | xxx.dv.zone | — | internal | 6 vols (config/data/metadata/cache/blobs/generated) | ⬜ To port |
| cwa (calibre-web-automated) | books.dv.zone | Entertainment | internal | `cwa/{config,ingest,calibre-library}` vols | ⬜ To port |
| cwa-dl | books-dl.dv.zone | Entertainment | internal | none (stateless) | ⬜ To port |
| pihole | — | Admin | — | **superseded** by the Technitium DNS migration (already on docker_vm) — not ported | 🚫 Won't port |
| watchtower | — | — | — | auto-updater; to be dropped in favour of Renovate-driven version bumps | 🚫 Won't port |

Notes:
- **Postgres-backed apps** (`forgejo`, `nocodb`, `n8n`, plus the done `miniflux`/`paperless`)
  target the `postgres_lxc` instead of the NAS's in-compose `postgres-db`. Each
  needs its DB/user provisioned there and a `secrets.py` entry for the password.
- **OIDC apps** (`pgadmin`, plus done `miniflux`/`paperless`) need an Authelia
  client + redirect registered in `deploys/docker_vm/proxies/vars.py`.
- When porting each app, add its `homepage.*` labels (group/name/icon/href/weight,
  and a `homepage.widget.key` from 1Password where a widget applies) so it
  self-registers on the homepage dashboard.
- `exposure: external` apps join `caddy-external` and must already be in the
  cloudflared ingress; `internal` apps join `caddy-internal` behind Authelia.

Most of the heavy lifting already exists and is **reused, not rebuilt**:

- `deploys/common/docker_compose/__init__.py` — `docker_compose(apps, template_dir, variables)`
  orchestrator (creates managed volume dirs, external named volumes, renders
  templates, renders `<app>.yaml.j2` → `compose.yaml`, runs `docker compose up`).
- `deploys/common/docker_compose/models.py` — `ComposeApp`, `BindMount`,
  `NamedVolume`, `TemplateFile`.
- `deploys/common/docker_compose/templates/_volumes.j2` — `service_volumes(app)` /
  `top_level_volumes(app)` macros.
- Caddy (`caddy-internal`), Authelia, and the `caddy-internal` / `authelia` /
  `macvlan` networks are already deployed via `deploys/docker_vm/proxies/`. A new
  app only needs to join `caddy-internal` and carry the right caddy-docker-proxy
  labels.

What's genuinely new is a **home for "regular" apps**: a single collection
package `deploys/docker_vm/apps/` (mirroring the Ansible `docker-apps` role) into
which all future apps accumulate.

## Decisions

- **Structure — single `deploys/docker_vm/apps/` package.** `apps.py` accumulates
  every `ComposeApp`; `templates/` holds one `<app>.yaml.j2` per app; one
  `setup_apps()` deploy runs them all. Less per-app boilerplate than a
  package-per-app, and matches how the Ansible role grouped all apps together.
  (Contrast: `proxies/` and `dns/` are their own feature packages because they
  own networks/build steps; plain apps don't.)
- **Dozzle auth — behind Authelia forward-auth.** Replicates the current NAS
  config: `caddy_internal.import: secure *` plus `DOZZLE_AUTH_PROVIDER: forward-proxy`,
  so dozzle trusts the Authelia-provided identity headers.
- **App naming / domain.** `dozzle` (container, compose project, template). Domain
  is `dozzle.<host.data.domain>` (→ `dozzle.dv.zone`), proxied by caddy-internal.

## Implementation (done)

### 1. New package `deploys/docker_vm/apps/`

**`apps.py`** — accumulating app list. Dozzle is stateless: its only volume is
the docker socket, an absolute-path `BindMount` the helper treats as unmanaged
(no volume dir created):

```python
from deploys.common.docker_compose.models import ComposeApp, BindMount

DOCKER_SOCKET = BindMount(source="/var/run/docker.sock", mount_path="/var/run/docker.sock")

apps = [
    ComposeApp(
        name="dozzle",
        volumes=[DOCKER_SOCKET],
    ),
]
```

**`__init__.py`** — the deploy entry (mirrors `deploys/dns/__init__.py`, the
simplest existing example):

```python
from pathlib import Path
from pyinfra.api import deploy

from deploys.common.docker_compose import docker_compose
from deploys.docker_vm.apps.apps import apps

template_dir = Path(__file__).resolve().parent / "templates"


@deploy("Provision Docker apps")
def setup_apps():
    docker_compose(apps=apps, template_dir=template_dir)
```

> No `vars.py` / `secrets.py` yet — dozzle needs neither. They get added the
> first time an app needs a non-secret variable or a 1Password secret (follow the
> `deploys/dns/vars.py` + `secrets.py` pattern and pass `variables=vars` into
> `docker_compose`).

**`templates/dozzle.yaml.j2`** — ported from
`roles/docker-apps/templates/dozzle.yml.j2`, adapted to pyinfra conventions
(custom `[[ ]]` delimiters, `_volumes.j2` macros, `host.data.domain`, external
networks). The docker-compose-native `{{upstreams 8080}}` is preserved literally
because the jinja env uses `[[ ]]` for its own variables:

```yaml
[%- import '_volumes.j2' as vol with context -%]
services:
  dozzle:
    container_name: dozzle
    image: amir20/dozzle:latest
    volumes:[[ vol.service_volumes(app) ]]
    networks:
      - caddy-internal
    environment:
      DOZZLE_AUTH_PROVIDER: forward-proxy
    labels:
      caddy_internal: dozzle.[[ host.data.domain ]]
      caddy_internal.reverse_proxy: "{{upstreams 8080}}"
      caddy_internal.import: secure *
    expose:
      - 8080
    restart: unless-stopped

networks:
  caddy-internal:
    external: true
[[ vol.top_level_volumes(app) ]]
```

`top_level_volumes(app)` renders nothing for dozzle (no named volumes) but is
included so every app template stays uniform.

### 2. Re-export the deploy

`deploys/docker_vm/__init__.py` adds `from deploys.docker_vm.apps import setup_apps`.

### 3. Wire into the dispatcher

`deploy.py` imports `setup_apps` and calls it in the `docker_vm` block, **after**
`setup_caddy_proxies()` (so caddy/authelia/networks exist first) and before
`setup_technitium_dns()`.

## Out of scope

- **Removing dozzle from the NAS / Ansible `roles/docker-apps`.** Leave it running
  there until the docker_vm instance is verified; decommissioning is a follow-up.
- **Homepage labels (`homepage.*`).** *(Resolved — homepage has since landed;
  dozzle's labels were added with it. New apps add their own labels as they're
  ported — see the Migration tracker notes.)*
- **The other apps.** Tracked in the **Migration tracker** above. Stateful ones
  (named volumes, postgres DB users, secrets) exercise more of the scaffolding
  (`NamedVolume(external=True)`, `TemplateFile`, the postgres network, `secrets.py`).

## Verification

1. **Secrets env:** `OP_SERVICE_ACCOUNT_TOKEN` must be set (no new secrets here,
   but existing `secrets.py` modules resolve at import).
2. **Dry run** *(passed)*:
   `uv run pyinfra inventory.py --limit docker_vm deploy.py --dry` shows the
   `Provision Docker apps` operations — create `/srv/docker/compose/dozzle/`,
   render `compose.yaml`, `docker compose up` for project `dozzle` — with no
   import errors. The socket bind mount is correctly unmanaged (no volume dir).
3. **Apply:** `uv run pyinfra inventory.py --limit docker_vm deploy.py`.
4. **On the host:** `docker ps` shows `dozzle` running on `caddy-internal`;
   inspect `/srv/docker/compose/dozzle/compose.yaml` (socket mount present,
   `{{upstreams 8080}}` literal, labels correct).
5. **End-to-end:** browse `https://dozzle.dv.zone` → Authelia login → dozzle UI
   showing container logs. (Requires DNS for `dozzle.dv.zone` → internal
   reverse-proxy IP; caddy discovers the backend from the labels.)
6. **Idempotency:** re-run; second run reports no changes (or a no-op
   `docker compose up`).
