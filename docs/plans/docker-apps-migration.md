# Plan: Port docker apps from the NAS to the Docker VM (Ansible → pyinfra)

## Context

The homelab runs 20 docker apps on the Synology NAS via the legacy Ansible
`roles/docker-apps` role. We are migrating these onto the pyinfra-managed
`docker_vm` host, app by app. The section below tracks **overall progress**; the
rest of this document is the original write-up of the **first step** — standing
up the **common scaffolding** for ordinary docker apps and porting `dozzle` (a
stateless docker log viewer) end-to-end as the proving case.

## Migration tracker

19 apps in the Ansible `roles/docker-apps` role (source of truth:
`roles/docker-apps/vars/main.yml`). **16 ported (all migratable apps done), 3
won't be ported** (superseded/dropped). Ported apps live in
`deploys/docker_vm/apps/apps.py` with a `templates/<app>.yaml.j2` each.

| App | Domain | Homepage group | Exposure | State / dependencies | Status |
|-----|--------|----------------|----------|----------------------|--------|
| dozzle | dozzle.dv.zone | Admin | internal | docker socket only (stateless) | ✅ Ported |
| whoami | whoami.dv.zone | — | external | none (stateless) | ✅ Ported |
| miniflux | rss.dv.zone | Bookmarks | external | postgres `miniflux`, OIDC | ✅ Ported |
| paperless | docs.dv.zone | Office | internal | postgres `paperless`, redis/tika/gotenberg sidecars, external named vols, OIDC, secrets | ✅ Ported |
| homepage | home.dv.zone | — | internal | bind-mount config + docker socket; `homepage.*` labels drive the dashboard | ✅ Ported |
| pgadmin | pgadmin.dv.zone | Databases | internal | `pgadmin-data` vol (external, uid/gid 5050), single-file `config_local.py` bind, OIDC (self-auth, no `import secure`); data bridged from NAS — see runbook below | ✅ Ported |
| portainer | docker.dv.zone | Admin | internal | `portainer-data` vol (external), docker socket; EE, `/data` bridged from NAS | ✅ Ported |
| tautulli | tautulli.dv.zone | Entertainment | internal | `tautulli/config` vol (external), config migrated from NAS | ✅ Ported |
| seerr | requests.dv.zone | Entertainment | internal | `seerr-config` vol (external); **fresh install, no data migrated**; self-auths via Plex (no `import secure`); `init: true`; replaced `sctx/overseerr` 2026-07-06 | ✅ Ported |
| sabnzbd | nzb.dv.zone | Downloaders | internal | `sabnzbd/config` vol + NAS usenet library over NFS | ✅ Ported |
| qbittorrent | torrent.dv.zone | Downloaders | internal | `qbittorrent/config` vol + NAS torrent library over NFS | ✅ Ported |
| forgejo | git.dv.zone | Development | internal | postgres `forgejo`, external `forgejo-data` vol, git-over-SSH via caddy-internal layer4; upgraded 8→15.0.3 (LTS) | ✅ Ported |
| nocodb | nocodb.dv.zone | Databases | internal | postgres `nocodb`, `nocodb-data` vol (external); **fresh install, no data migrated** (barely used); self-auth (no `import secure`) | ✅ Ported |
| n8n | n8n.dv.zone | Automation | internal | postgres `n8n`, `n8n-data` vol (external, uid/gid 1000) holding the encryption key; DB + vol bridged from NAS — see runbook below | ✅ Ported |
| pinchflat | pinchflat.dv.zone | Entertainment | internal | `pinchflat-config` vol (external) + NAS youtube library over NFS; runs `2000:100`, config bridged from NAS | ✅ Ported |
| cwa (calibre-web-automated) | books.dv.zone | Entertainment | internal | `cwa-config` vol (external), `cwa/ingest` bind, NAS `calibre-library` over NFS + `NETWORK_SHARE_MODE`; see [cwa-migration.md](cwa-migration.md) | ✅ Ported |
| cwa-dl | books-dl.dv.zone | Entertainment | internal | **superseded** by [Shelfmark](https://github.com/calibrain/shelfmark) — deploy fresh on docker_vm (clean slate), don't migrate cwa-dl or its data; see [cwa-migration.md](cwa-migration.md) follow-ups | 🚫 Won't port |
| pihole | — | Admin | — | **superseded** by the Technitium DNS migration (already on docker_vm) — not ported | 🚫 Won't port |
| watchtower | — | — | — | auto-updater; to be dropped in favour of Renovate-driven version bumps | 🚫 Won't port |

Notes:
- **NFS-mounted shares** — `qbittorrent` and `sabnzbd` both mount the **whole
  `/volume1/entertainment` tree** at `/data` (not just their `torrents/` /
  `usenet/` subdir), so the download clients and the future *arr apps share one
  filesystem and cross-directory hardlinks / instant moves work (trash-guides
  single-mount layout; the tree holds `torrents/`, `usenet/`, `media/`). Both
  clients now **share a single external NFS volume** (`ENTERTAINMENT_NFS`, name
  `entertainment`, in `apps.py`) rather than each inlining its own `NfsVolume`:
  `NfsVolume(external=True)` makes the `docker_compose` helper pre-create the
  volume once via `docker.volume(driver="local", options=[…])` (now that pyinfra's
  `docker.volume` supports `--opt`) and the compose file marks it `external: true`.
  Downloads
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
  `local`/`type=nfs` docker volume, mounted lazily by the daemon on `up`. (cwa and
  pinchflat mount distinct **subdirs** of the same tree, so they keep their own
  inline non-external `NfsVolume` — nothing to share there.)
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

## tautulli — config migration (done 2026-07-02)

Plex activity/stats monitor. Simplest kind of stateful port: no postgres, no
OIDC, no NFS — just one high-recovery-cost config volume whose live SQLite db
(`tautulli.db`, all Plex watch history) is bridged from the NAS. Internal on
`caddy-internal` (`tautulli.dv.zone`, `import secure *`), Entertainment homepage
widget, `tautulli/tautulli:v2.17.2`.

- **State — `tautulli-config`, `external=True`** at `/config`. `tautulli.db` is
  irreplaceable historical data, so external keeps `down -v` from wiping it.
- **Runs as PUID/PGID `2000`/`2000`** (`host.data.docker_{uid,gid}`) — matches
  the Ansible original. No NFS, so no NAS-ACL reason to force PGID 100 (contrast
  qbittorrent/sabnzbd). Migrated files were `1029:100` on the NAS → chowned
  `2000:2000` on the way in.
- **Homepage widget key → 1Password.** The Ansible template hardcoded the
  Tautulli API key inline; moved to `tautulli_api_token`
  (`op://Homelab/Tautulli/api key`) rendered via `[[ tautulli_api_token ]]`,
  matching the portainer widget-key pattern. (User creates the 1Password item;
  the field label is `api key` — verify the ref resolves via the SDK, not
  `op read`.)
- **Config migration** — same bridge-through-workstation pattern as sabnzbd
  (NAS and docker_vm can't reach each other). **Stop the NAS tautulli first** to
  quiesce the SQLite db (clean checkpoint, no lingering `-wal`), then:
  ```
  ssh <docker_vm> 'docker volume create tautulli-config'
  ssh -p 22910 daanadmin@192.168.1.21 'tar -C /volume2/docker/tautulli/config -cf - .' \
    | ssh <docker_vm> 'docker run --rm -i -v tautulli-config:/dest alpine tar --numeric-owner -xf - -C /dest'
  ssh <docker_vm> 'docker run --rm -v tautulli-config:/dest alpine chown -R 2000:2000 /dest'
  ```
  Domain unchanged (`tautulli.dv.zone`), so no `config.ini` edit needed.
- **Verified:** container healthy on `caddy-internal`; logs show the migrated db
  loaded (`Database File: /config/tautulli.db`) and reconnected to Plex server
  `NASty` from the carried-over `config.ini` (not a first-run); 884 history rows
  in the volume; `tautulli.dv.zone` → 302 Authelia; file-mgmt ops idempotent.
  NAS tautulli left stopped-but-present; Ansible decommission is the follow-up.

## pgadmin — config + data migration (done 2026-07-03)

Postgres admin UI. Stateful, **self-auths via Authelia OIDC** (like miniflux /
forgejo — **not** behind `import secure`), Databases homepage tile,
`dpage/pgadmin4:9.16` (NAS ran `:latest`). Runs as the image's built-in
**uid/gid 5050**. Internal on `caddy-internal` (`pgadmin.dv.zone`, container port
**80**). The Authelia `pgadmin` OIDC client was already staged in
`deploys/docker_vm/proxies/vars.py` (redirect `…/oauth2/authorize`,
`client_secret_basic`), so no proxy change was needed.

- **State — `pgadmin-data`, `external=True`** at `/var/lib/pgadmin`. Holds
  `pgadmin4.db` (server/connection definitions, users, prefs, saved queries) +
  `storage/`/`sessions/` — high recovery cost, so external keeps `down -v` from
  wiping it. Bridged from the NAS `/volume2/docker/pgadmin/data`.
- **`config_local.py` — single-file bind (the one novel bit).** It must land at
  `/pgadmin4/config_local.py`, *inside* the image's own module dir, so it can't
  be a whole-dir mount. It's rendered by `TemplateFile(src="config_local.py",
  dest="pgadmin/config_local.py", uid/gid 5050)` under `docker_volumes_base`, then
  mounted read-only via an **absolute-source** `BindMount`
  (`/srv/docker/volumes/pgadmin/config_local.py` → `/pgadmin4/config_local.py:ro`).
  Absolute source ⇒ `is_managed=False`, so the helper doesn't mkdir a directory
  over the file. Template is `deploys/docker_vm/apps/templates/config_local.py.j2`
  (OAuth2 → Authelia; fixed the original's `OAUTH2_BUTTON_COLOR: <button-color>`
  placeholder → `#2c3e50`).
- **Secrets → 1Password** (was Ansible-Vault). Two new refs in
  `deploys/docker_vm/apps/secrets.py`:
  - `pgadmin_oidc_client_secret` = `op://Homelab/pgAdmin OIDC client/password` —
    **must be the same plaintext** whose pbkdf2 hash is registered for the
    `pgadmin` client in `proxies/vars.py` (carry over the Ansible
    `pgadmin.oidc.secret` value) or Authelia rejects the token exchange.
  - `pgadmin_default_password` = `op://Homelab/pgAdmin/password` — only satisfies
    the image's first-init env check; internal login is disabled by OIDC-only auth.
  - **Dropped** the NAS SendGrid `PGADMIN_CONFIG_MAIL_*` env — password-recovery
    mail is unused under OIDC-only auth (kept `PGADMIN_DISABLE_POSTFIX=True`).
  - User creates the 1Password items ([[feedback_user_creates_1password_items]]);
    both must exist before *any* app deploys or `populate_cache_sync()` fails for
    all of them. Verify the refs resolve via the SDK, not `op read`
    ([[feedback_op_sdk_resolves_by_field_id]]).
- **Data migration** — bridge NAS → workstation → docker_vm volume. **Stopped the
  NAS pgadmin first** (`docker stop pgadmin`) to quiesce `pgadmin4.db`.
  `pgadmin4.db` is mode `600` owned `5050`, which the ssh user can't read, so the
  tar ran inside a **root container** on each end (also sidesteps NAS sudo; DSM
  docker is at `/usr/local/bin/docker`, not on the non-interactive ssh PATH):
  ```
  ssh dockervm.dv.zone 'docker volume create pgadmin-data'
  ssh nas.dv.zone '/usr/local/bin/docker run --rm -v /volume2/docker/pgadmin/data:/src alpine tar -C /src --numeric-owner -cf - .' \
    | ssh dockervm.dv.zone 'docker run --rm -i -v pgadmin-data:/dest alpine tar --numeric-owner -xf - -C /dest'
  ssh dockervm.dv.zone 'docker run --rm -v pgadmin-data:/dest alpine chown -R 5050:5050 /dest'
  ```
- **Server-definition repoint (remaining UI step).** The one carried-over server
  in `pgadmin4.db` (`PostgreSQL Main`) references host **`postgres-db`** (the NAS
  in-compose Postgres, macvlan `192.168.1.195`), which doesn't resolve on
  docker_vm. After login, edit its host to an IP the VM can reach
  (`192.168.1.195` for the NAS postgres, or `192.168.1.41` for the postgres_lxc).
- **Deployed:** `uv run pyinfra inventory.py --limit docker_vm deploy.py -y`.
- **Verified 2026-07-03:** `pgadmin` up on `dpage/pgadmin4:9.16`, `caddy-internal`;
  `config_local.py` mounted `:ro`; gunicorn on :80; migrated `pgadmin4.db` loaded
  (user `daan@dv.email`, 1 server def present, not a first-run);
  `pgadmin.dv.zone` → 302 Authelia with the OAuth2 login button. NAS pgadmin left
  stopped-but-present; Ansible decommission is the follow-up.

## pinchflat — config migration + NFS library (done 2026-07-03)

YouTube channel/playlist downloader. Stateful config + an NFS-mounted media
library — the qbittorrent/sabnzbd shape without the whole-tree mount. Internal on
`caddy-internal` (`pinchflat.dv.zone`, container port **8945**, behind
`import secure *` Authelia SSO like the other download UIs), Entertainment
homepage tile, `ghcr.io/kieraneglin/pinchflat:v2025.6.6` — the newest **dated**
tag on ghcr (upstream stopped publishing `vYYYY.M.D` tags after it and ships
newer builds only as `:latest`/`:dev`; NAS ran `:latest`).

- **State — `pinchflat-config`, `external=True`** at `/config`. Holds the SQLite
  db (`db/pinchflat.db`) tracking sources + per-video download history, plus
  `metadata/`/`extras/`/`logs/`. High recovery cost (losing it re-adds every
  channel/playlist and re-downloads everything), so external keeps `down -v`
  from wiping it. It's a **local** volume, so SQLite WAL is fine — no
  `JOURNAL_MODE=delete` override (contrast the NFS-hosted SQLite in cwa).
- **Library — `pinchflat-downloads` (`NfsVolume`)** at `/downloads`, backed by
  the NAS `/volume1/entertainment/media/youtube`. That's a subdir of the same
  `/volume1/entertainment` tree qbittorrent/sabnzbd/cwa mount, so the existing
  `dockervm` (uid 2000) Synology ACL already covers it — **no new NAS-side
  setup**. The library files stay in place on the NAS; only the config is
  migrated.
- **Runs as `2000:100` via the compose `user:` directive** (not PUID/PGID —
  pinchflat has no such env; it uses docker's `user`). NFS maps by numeric id,
  so writes to the shared youtube tree need uid 2000 / gid 100 (the NAS `users`
  group), matching qbittorrent/sabnzbd/cwa. Pinchflat's own docs also recommend
  against root so Plex/other apps can read the media. The bridged `/config`
  volume is chowned `2000:100` so this user owns its db.
- **Config migration** — same bridge-through-workstation pattern as tautulli
  (NAS and docker_vm can't reach each other). **Stop the NAS pinchflat first**
  (DSM docker is `/usr/local/bin/docker`, not on the ssh PATH) to quiesce the
  SQLite db (clean checkpoint — no lingering `-wal`), then:
  ```
  ssh nas.dv.zone 'sudo /usr/local/bin/docker stop pinchflat'
  ssh dockervm.dv.zone 'docker volume create pinchflat-config'
  ssh nas.dv.zone 'sudo tar -C /volume2/docker/pinchflat/config -cf - .' \
    | ssh dockervm.dv.zone 'docker run --rm -i -v pinchflat-config:/dest alpine tar --numeric-owner -xf - -C /dest'
  ssh dockervm.dv.zone 'docker run --rm -v pinchflat-config:/dest alpine chown -R 2000:100 /dest'
  ```
  Domain unchanged (`pinchflat.dv.zone`), so no in-config edit needed.
- **Deployed:** `uv run pyinfra inventory.py --limit docker_vm deploy.py -y`.
  (First attempt pinned `v2025.9.26` — the GitHub *release* tag — which ghcr
  returned `manifest unknown` for; upstream's newest *ghcr* dated tag is
  `v2025.6.6`. Corrected and redeployed.)
- **Verified 2026-07-03:** container healthy on `caddy-internal`, running
  `2000:100` (`id` → `uid=2000 gid=100(users)`); migrated `pinchflat.db` loaded
  (Oban queue processing existing media_items #51xxxx — not a first-run);
  `/downloads` NFS mount writable as the container user and the carried-over
  library (`channels/Veritasium`, `playlists/…`) visible; `pinchflat.dv.zone` →
  302 `auth.dv.zone` (Authelia). The yt-dlp "Sign in to confirm your age" /
  "No JS runtime" errors in the log are pre-existing upstream YouTube issues,
  not migration-related. NAS pinchflat left stopped-but-present; Ansible
  decommission is the follow-up.

## overseerr — fresh install, no data migration (done 2026-07-03)

Plex media request/discovery app. The **simplest kind of port**: no data is
migrated — this is a clean install, so no bridge-through-workstation step and no
NAS quiesce. Internal on `caddy-internal` (`requests.dv.zone`, container port
**5055**), Entertainment homepage tile, `sctx/overseerr:1.35.0` (NAS ran
`:latest`).

- **State — `overseerr-config`, `external=True`** at `/app/config`. Holds
  `settings.json` + `db/db.sqlite3` (request history, Plex-linked user accounts,
  Plex/Radarr/Sonarr service config). Non-trivial recovery cost, so external=True
  keeps `down -v` from wiping it — even for a fresh volume it protects the state
  going forward ([[feedback_named_volumes_external]]).
- **Self-auths via Plex — NOT behind Authelia.** Overseerr has its own Plex-OAuth
  login, and the request UI must be reachable for users to sign in, so the
  template carries **no `import secure *`** (contrast the download UIs). Verified:
  `https://requests.dv.zone` → **307** to overseerr's own `/login` (not a 302 to
  `auth.dv.zone`).
- **No PUID/PGID.** The `sctx/overseerr` image runs as root and doesn't read
  PUID/PGID env (contrast the linuxserver images); the NAS template set none
  either. Fresh named volume, so no ownership migration.
- **Homepage widget.** The Ansible template hardcoded an inline
  `homepage.widget.key` (the old instance's API key), which was useless here —
  a fresh install generates a **new** API key on first setup. Initially shipped
  with group/name/icon/href only; once the user set up Overseerr and provided the
  new key's 1Password ref, `overseerr_api_token` =
  `op://Homelab/Overseerr/password` was added to `secrets.py` and
  `homepage.widget.{type,url,key}` wired into the template (tautulli's shape).
- **Deployed:** `uv run pyinfra inventory.py --limit docker_vm deploy.py -y`.
- **Verified 2026-07-03:** `overseerr` up on `sctx/overseerr:1.35.0`,
  `caddy-internal`; clean first-run init in the logs (built-in discovery sliders
  created, scheduled jobs loaded, `Server ready on port 5055`); external
  `overseerr-config` volume created; `requests.dv.zone` → 307 to overseerr's
  Plex login. No NAS instance to decommission beyond the usual Ansible cleanup.
  **First-run setup completed 2026-07-03** — Overseerr is fully configured (Plex +
  Radarr/Sonarr connections); the homepage widget key was then wired in (see above).
### Replaced with Seerr (done 2026-07-06)

`requests.dv.zone` was swapped off `sctx/overseerr:1.35.0` onto
`ghcr.io/seerr-team/seerr:v3.3.0` — [Seerr](https://seerr.dev/), the maintained
Overseerr/Jellyseerr successor. A **fresh install, no data migrated** (overseerr
itself carried nothing over, and no migration was wanted).

- The overseerr `ComposeApp` + `overseerr.yaml.j2` were removed; a new `seerr`
  `ComposeApp` + `seerr.yaml.j2` take over the same domain, port (**5055**),
  Entertainment tile, and internal-only (`caddy-internal`, no `import secure`)
  posture — Seerr self-auths via Plex just like overseerr.
- **State — `seerr-config`, `external=True`** at `/app/config` (fresh volume;
  same `settings.json` + `db/db.sqlite3` layout Overseerr used).
- **`init: true`.** The Seerr image ships **no init process** upstream (unlike
  `sctx/overseerr`), so the template sets `init: true` to reap zombies.
- **Runs as `node` (UID 1000)** with a named volume — no PUID/PGID needed.
- **Homepage widget.** Seerr keeps Overseerr's `/api/v1` surface, so the
  `overseerr` widget type/icon are reused. Fresh API key (generated at first-run
  setup) stored at `op://Homelab/Seerr/password`; `seerr_api_token` in
  `secrets.py` replaced `overseerr_api_token`.
- **Deploy:** `uv run pyinfra inventory.py --limit docker_vm deploy.py -y` — but
  the 1Password `Seerr` item must exist first (secret resolution happens at
  import; a missing item fails the run). Do first-run setup (Plex + Radarr/Sonarr
  connections), generate the API key, store it in the `Seerr` item, then redeploy
  so the homepage widget resolves.

## n8n — DB + volume migration (done 2026-07-03)

Workflow automation platform. The **forgejo shape**: Postgres-backed + one
high-recovery-cost external volume, and **both** the DB *and* the volume must be
migrated together. Internal on `caddy-internal` (`n8n.dv.zone`, container port
**5678**), Automation homepage tile, `docker.n8n.io/n8nio/n8n:2.28.6` (the exact
version the NAS currently runs as the floating `:latest`, so n8n's startup schema
migration is a no-op against the carried-over DB — bump as a separate change
later, matching the forgejo "migrate on same version" rule).

- **DB → postgres_lxc.** The `n8n` DB + user are **already provisioned** on
  `postgres_lxc` (`deploys/postgres_lxc/databases/vars.py`; secret
  `n8n_password` at `op://Homelab/PostgreSQL n8n user/password`). The live data
  still lives in the NAS in-compose `postgres` container (**postgres:14**,
  database `n8n`) and must be dumped → restored into the LXC (PostgreSQL 17).
  App side reads the same password ref via the new `n8n_db_password` in
  `deploys/docker_vm/apps/secrets.py`.
- **State — `n8n-data`, `external=True`** at `/home/node/.n8n`. Besides logs and
  custom nodes, this dir holds **`config` — the instance encryption key** that
  decrypts *every* stored credential in the Postgres DB. **The DB alone is
  useless without this key**, so the volume and the DB must move together, and
  `external=True` keeps `down -v` from ever wiping the key. `N8N_ENCRYPTION_KEY`
  is deliberately **not** set in the compose env so n8n reads the migrated key
  from the file (matches the NAS, which never set it).
- **Self-auth, NOT behind Authelia.** n8n has its own user management, and its
  webhook endpoints must be reachable without an SSO round-trip, so the template
  carries **no `import secure *`** (matches the NAS `exposure: internal`).
- **Runs as the image's built-in `node` (uid/gid 1000).** The NAS set no
  PUID/PGID and the volume files are already `1000:1000`, so no `user:` override;
  migrated files are chowned `1000:1000` on the way in.

**Cutover runbook** (mirrors the forgejo DB + `/data` bridge — NAS and docker_vm
can't reach each other, so every hop originates from the Mac; all three
NAS-postgres dump traps apply, see [[feedback_nas_postgres_dump_restore]]):

```bash
# 1. Quiesce — on the NAS, stop n8n so the DB + .n8n dir are a consistent snapshot.
ssh nas.dv.zone 'sudo /usr/local/bin/docker stop n8n'

# 2. Dump the DB — ON THE NAS (postgres container is named `postgres`, v14).
#    NO `-t` (corrupts the -Fc archive) and NO `-i`; just redirect stdout.
ssh nas.dv.zone 'sudo /usr/local/bin/docker exec postgres pg_dump -U n8n -Fc n8n > /volume2/docker/n8n-db.dump'
#    Verify the dump has row data BEFORE trusting it (must be > 0):
ssh nas.dv.zone 'sudo /usr/local/bin/docker cp /volume2/docker/n8n-db.dump postgres:/tmp/d.dump \
  && sudo /usr/local/bin/docker exec postgres pg_restore -l /tmp/d.dump | grep -ci "TABLE DATA"'

# 3. Restore into postgres_lxc (192.168.1.41, PG17), into the empty n8n DB.
#    Transfer to a FILE (never stream over stdin -> silent truncation); docker_vm
#    has no pg_restore so borrow a throwaway postgres:17 (reaches the LXC like
#    miniflux/paperless). --clean --if-exists keeps it re-runnable.
ssh nas.dv.zone 'sudo cat /volume2/docker/n8n-db.dump' | ssh dockervm.dv.zone 'cat > ~/n8n-db.dump'
ssh dockervm.dv.zone 'ls -l ~/n8n-db.dump'   # size MUST match the NAS dump
PW=$(op read "op://Homelab/PostgreSQL n8n user/password")   # on the Mac
ssh dockervm.dv.zone "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD \
  -v ~/n8n-db.dump:/dump:ro postgres:17 \
  pg_restore -h 192.168.1.41 -U n8n -d n8n --clean --if-exists --no-owner --verbose /dump"

# 4. Bridge the .n8n dir -> the n8n-data named volume. `config` is mode 600 owned
#    uid 1000, so tar as ROOT on the NAS (the ssh user can't read it). Create the
#    volume first, then extract as root and chown to the container user (1000).
ssh dockervm.dv.zone 'docker volume create n8n-data'
ssh nas.dv.zone 'sudo tar -C /volume2/docker/n8n --numeric-owner -cf - .' \
  | ssh dockervm.dv.zone 'docker run --rm -i -v n8n-data:/dest alpine tar --numeric-owner -xf - -C /dest'
ssh dockervm.dv.zone 'docker run --rm -v n8n-data:/dest alpine chown -R 1000:1000 /dest'

# 5. Deploy — brings up n8n on the migrated key + restored DB (domain unchanged,
#    so WEBHOOK_URL/n8n.dv.zone need no edit).
uv run pyinfra inventory.py --limit docker_vm deploy.py -y
ssh dockervm.dv.zone 'docker logs -f n8n'   # expect clean start, migrations no-op
```

**Verified 2026-07-03** — container healthy on `caddy-internal` running
`node` (uid/gid 1000), `docker.n8n.io/n8nio/n8n:2.28.6`, `n8n ready on ::, port
5678` with no migration/DB/encryption errors (same version → schema migration a
no-op). DB restore landed 1 workflow / 2 credentials / 1 user (110 `TABLE DATA`
entries in the dump). **Decisive check: `n8n export:credentials --all
--decrypted` succeeded for both credentials** (`redditOAuth2Api`, `pushoverApi`)
— the migrated `/home/node/.n8n/config` encryption key matches the restored DB,
which is the whole point of bridging the volume with the DB. `https://n8n.dv.zone/`
→ **200** serving n8n's own login (not an Authelia 302). NAS n8n left
stopped-but-present (`Exited (0)`); Ansible decommission is the follow-up.

## nocodb — fresh install, no data migration (done 2026-07-03)

**The last migratable app.** No-code database/spreadsheet app. Postgres-backed
but a **clean install** — the NAS instance was barely used, so no data is
migrated (no DB dump, no volume bridge, no NAS quiesce): the overseerr "fresh
install" shape with a Postgres DB. Internal on `caddy-internal`
(`nocodb.dv.zone`, container port **8080**), Databases homepage tile,
`nocodb/nocodb:2026.06.2` (NocoDB uses calver; pinned the current `:latest`,
verified the tag exists on Docker Hub).

- **DB → postgres_lxc.** The `nocodb` DB + user are **already provisioned**
  (`deploys/postgres_lxc/databases/vars.py`; secret `nocodb_password` at
  `op://Homelab/PostgreSQL NocoDB user/password`). NocoDB reads its whole DB from
  a single `NC_DB` connection string, repointed from the NAS `postgres-db` to
  `host.data.postgres_lxc_ip`. App-side secret `nocodb_db_password` (same ref) in
  `apps/secrets.py`. NocoDB creates its own schema on first start.
- **State — `nocodb-data`, `external=True`** at `/usr/app/data`. Holds uploaded
  attachments + local tool state (not the relational data). Fresh volume, but
  `external=True` still protects attachments going forward so `down -v` can't
  wipe them ([[feedback_named_volumes_external]]).
- **Self-auth, NOT behind Authelia.** NocoDB has its own user management and its
  public shared views / API must be reachable without an SSO round-trip, so the
  template carries **no `import secure *`** (matches the NAS `exposure: internal`;
  same reasoning as n8n).
- **Deployed:** `uv run pyinfra inventory.py --limit docker_vm deploy.py -y`.
- **Verified 2026-07-03:** container healthy on `caddy-internal`,
  `nocodb/nocodb:2026.06.2`; clean first-run init against the empty `nocodb` DB
  (schema migrations ran, **129 tables** created, `App started successfully`, no
  DB/connection errors); external `nocodb-data` volume created; `nocodb.dv.zone`
  → **200** serving NocoDB's own UI (not an Authelia 302). NAS nocodb left
  running (barely used, no state to lose); Ansible decommission is the follow-up.

---

**🎉 All 16 migratable docker apps are now on `docker_vm`.** What's left is
cleanup, not migration: NAS/Ansible decommissioning (`docs/plans/open-todos.md`
§1), the remaining fresh-app stand-up that supersedes a migrated app
(Shelfmark ← cwa-dl; Seerr ← overseerr done 2026-07-06), and Renovate for
version bumps.
