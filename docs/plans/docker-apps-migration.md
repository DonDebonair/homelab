# Plan: Port docker apps from the NAS to the Docker VM (Ansible → pyinfra)

## Context

The homelab runs ~20 docker apps on the Synology NAS via the legacy Ansible
`roles/docker-apps` role. We are migrating these onto the pyinfra-managed
`docker_vm` host, app by app. This document covers the **first step**: standing
up the **common scaffolding** for ordinary docker apps and porting **one** app —
`dozzle` (a stateless docker log viewer) — end-to-end as the proving case.

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
- **Homepage labels (`homepage.*`).** The NAS dozzle template carries them, but
  `homepage` isn't on docker_vm yet, so they'd be inert. Add when homepage lands.
- **The other ~17 apps.** Stateful ones (named volumes, postgres DB users,
  secrets) will exercise more of the scaffolding (`NamedVolume(external=True)`,
  `TemplateFile`, the postgres network, `secrets.py`).

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
