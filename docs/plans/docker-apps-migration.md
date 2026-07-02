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
`roles/docker-apps/vars/main.yml`). **8 ported, 10 left to port, 2 won't be
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
| sabnzbd | nzb.dv.zone | Downloaders | internal | `sabnzbd/config` vol + NAS usenet library over NFS | ✅ Ported |
| qbittorrent | torrent.dv.zone | Downloaders | internal | `qbittorrent/config` vol + NAS torrent library over NFS | ✅ Ported |
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
- **NFS-mounted shares** — `qbittorrent` and `sabnzbd` both mount the **whole
  `/volume1/entertainment` tree** at `/data` (not just their `torrents/` /
  `usenet/` subdir), so the download clients and the future *arr apps share one
  filesystem and cross-directory hardlinks / instant moves work (trash-guides
  single-mount layout; the tree holds `torrents/`, `usenet/`, `media/`). Each app
  keeps its **own inline `NfsVolume`** with `path=/volume1/entertainment` (a
  shared *external* NFS volume would be tidier but needs a custom op — pyinfra's
  built-in `docker.volume` can't set `--opt` driver options; deferred). Downloads
  are pinned into the right subdir **inside each app's config**, not via the
  mount: qbittorrent `Session\DefaultSavePath=/data/torrents` (categories relative:
  `/data/torrents/{movies,tv,music,books}`); sabnzbd `download_dir=/data/usenet/incomplete`,
  `complete_dir=/data/usenet/complete`. **Gotcha:** an existing qbittorrent torrent
  bakes its absolute save path into `.fastresume`; widening the mount orphans it
  (`missingFiles`) even though AutoTMM recomputes `save_path` correctly — fix with
  a one-time **force-recheck** (`POST /api/v2/torrents/recheck`; `LocalHostAuth=false`
  lets you call the API from inside the container without login) once the files
  are visible at the new path.
  Expressed with the `NfsVolume` model (`deploys/common/docker_compose/models.py`) — a
  compose `local`/`type=nfs` named volume, mounted lazily by the daemon on `up`.
  The container runs as the docker_vm docker user (`PUID` = `host.data.docker_uid`
  = `2000`, `PGID` = `100`). NFS maps access by numeric id and the NAS folder's
  access is Synology-ACL based (keyed on named accounts:
  `dockerlimited`/`sc-radarr`/`sc-sonarr`/`PlexMediaServer`), so we give the NAS a
  matching **named `dockervm` account pinned to uid 2000** — provisioned by the
  new `synology.user()` operation (`deploys/nas/users`) — and grant *it* the ACL.
  NAS side needs the user (automated) + ACL + export rule + routing — see below.
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

## qbittorrent — NAS-side NFS setup (prerequisite)

The torrent library stays on the NAS (`/volume1/entertainment/torrents`); the
docker_vm container mounts it over NFS. Do all of this **before** deploying
qbittorrent, or `docker compose up` will hang trying to mount the volume. Step 4
(the `dockervm` user) is automated — run `uv run pyinfra inventory.py --limit nas
deploy.py`; the rest (NFS/export/routing/ACL) is DSM GUI + firewall.

1. **Enable NFS.** Control Panel → File Services → NFS → *Enable NFS service*
   and *Enable NFSv4.1* support.
2. **Export rule on the `entertainment` shared folder.** Control Panel → Shared
   Folder → `entertainment` → Edit → NFS Permissions → Create:
   - **Hostname/IP:** `192.168.50.0/24` (the docker_vm subnet) or just the VM,
     `192.168.50.10`.
   - **Privilege:** Read/Write.
   - **Squash:** *No mapping* — so the container's numeric uid/gid (`2000`) pass
     through unchanged and are evaluated against the folder ACL (below).
   - **Security:** sys.
   - Tick **Allow connections from non-privileged ports** (Docker's NFS client
     uses a high source port) and **Allow users to access mounted subfolders**.
   - DSM shows the mount path (`/volume1/entertainment`); the VM mounts the
     `/torrents` subdir via the `device: ":/volume1/entertainment/torrents"` in
     the compose volume.
3. **Routing / firewall.** docker_vm (`192.168.50.10`) is on a different subnet
   from the NAS (`192.168.1.21`); confirm the two route to each other and, if the
   DSM firewall is on, allow NFS (tcp/udp **2049**) from `192.168.50.0/24`.
4. **Named `dockervm` user (uid 2000) — automated.** Access to
   `/volume1/entertainment/torrents` is Synology-ACL based (entries for
   `dockerlimited` uid 1029, `sc-radarr`/`sc-readarr`/`sc-sonarr`,
   `PlexMediaServer`), **not** POSIX ownership. The docker_vm qbittorrent runs as
   uid `2000`, so the NAS needs a matching account. The `synology.user()`
   operation (run via `nas_setup_users()` in the `nas` deploy) creates a
   `dockervm` user and pins it to uid `2000` — `synouser` auto-assigns a uid, so
   the op edits `/etc/passwd` and runs `synouser --rebuild all`, which (verified
   on this DSM by controlled test) *persists* the change into the user DB rather
   than reverting it. Primary group stays `users` (gid 100), hence `PGID: 100`.
5. **ACL grant to `dockervm`.** Once the user exists, grant it **Read & Write**
   (incl. delete/rename) on `/volume1/entertainment/torrents`, **applied to this
   folder + sub-folders + files** (covers existing downloads — no chown) and
   **inheritable** (new files from qbittorrent *and* the `sc-*` users carry the
   grant both ways). Because `dockervm` is now a real named account, this is
   doable straight from the DSM **Shared Folder → Edit → Permissions** ACL editor
   (no `synoacltool` needed).

Quick client-side verification from the VM once the rule is in place:
`showmount -e 192.168.1.21` should list the export; `sudo mount -t nfs4
192.168.1.21:/volume1/entertainment/torrents /mnt` should succeed.

## sabnzbd — NAS-side + config migration (prerequisite)

sabnzbd is the structural twin of qbittorrent: `sabnzbd-config` (external named
volume, high recovery cost) + the NAS usenet download area
(`/volume1/entertainment/usenet`) mounted over NFS as `sabnzbd-usenet`. Runs as
`PUID` = `host.data.docker_uid` = `2000`, `PGID` = `100`. Because usenet is a
subfolder of the same `entertainment` share qbittorrent already uses, **the NFS
enable / export rule / routing from the qbittorrent runbook (steps 1–3) already
cover it** — the only new NAS-side step is the ACL grant.

1. **ACL grant to `dockervm` on the usenet folder.** Grant the existing
   `dockervm` account (uid 2000, provisioned by `nas_setup_users()`) **Read &
   Write** (incl. delete/rename) on `/volume1/entertainment/usenet`, **applied to
   this folder + sub-folders + files** (covers existing downloads — no chown) and
   **inheritable**. DSM **Shared Folder → `entertainment` → Edit → Permissions**
   ACL editor. (No new export rule / firewall change — already done for torrents.)

2. **Migrate the config — via the workstation.** The current config lives on the
   NAS bind mount at `/volume2/docker/sabnzbd/config`; it must land in the new
   `sabnzbd-config` named volume on docker_vm
   (`/var/lib/docker/volumes/sabnzbd-config/_data`). **The NAS and docker_vm
   cannot reach each other on the network**, so the copy must be bridged by the
   workstation — never a direct `rsync nas:… docker_vm:…`.
   - Stop the NAS sabnzbd container first (quiesce `sabnzbd.ini` + the queue db).
   - Populate the volume through a **helper container**, not host-path sudo: the
     `daan` user is in the `docker` group on docker_vm so `docker` needs no sudo,
     and a throwaway container writes into the named volume as root internally.
     This dodges the tar-pipe/sudo tty problem (`sudo` can't prompt when stdin is
     the tar stream). Both SSH sessions originate from the workstation, so data
     flows NAS → workstation → docker_vm with no direct host-to-host connection:
     ```
     ssh <docker_vm> 'docker volume create sabnzbd-config'
     ssh <nas> 'tar -C /volume2/docker/sabnzbd/config -cf - .' \
       | ssh <docker_vm> 'docker run --rm -i -v sabnzbd-config:/dest alpine tar --numeric-owner -xf - -C /dest'
     ```
     Do this *before* the deploy's `docker compose up` so sabnzbd starts on the
     migrated config. (Staging alternative: `rsync -aH <nas>:/volume2/docker/sabnzbd/config/ /tmp/sab/`
     on the workstation, then `rsync -aH /tmp/sab/ <docker_vm>:/tmp/sab/` and load
     it in via the same helper-container pattern.)
   - Fix ownership for the container's ids, again via a helper container:
     `ssh <docker_vm> 'docker run --rm -v sabnzbd-config:/dest alpine chown -R 2000:100 /dest'`.
   - **Domain is unchanged** (`nzb.dv.zone`), so `sabnzbd.ini`'s `host_whitelist`
     needs no edit. The download paths in the config are `/data/...` and the
     `/data` mount point is preserved, so category/completed/incomplete paths stay
     valid over NFS.

3. **Deploy & verify.** `uv run pyinfra inventory.py --limit docker_vm deploy.py`;
   then `https://nzb.dv.zone` → Authelia → sabnzbd UI with servers, queue, and
   history intact; confirm a test download completes into the NFS `/data` area and
   is visible to the *arr stack. Then decommission the NAS sabnzbd (Ansible).
