from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume, NfsVolume, TemplateFile
from group_data.all import nas_ip
from group_data.docker_vm import docker_volumes_base

DOCKER_SOCKET = BindMount(source="/var/run/docker.sock", mount_path="/var/run/docker.sock")

apps = [
    ComposeApp(
        name="homepage",
        image="ghcr.io/gethomepage/homepage",
        version="v1.13.2",
        domain="home.dv.zone",
        volumes=[
            # Config dir holds the rendered yaml below; bind-mounted so the
            # templates this deploy writes are what the container reads.
            BindMount(source="homepage", mount_path="/app/config"),
            # Read-only socket: homepage only discovers containers via labels.
            BindMount(source="/var/run/docker.sock", mount_path="/var/run/docker.sock", read_only=True),
        ],
        templates=[
            TemplateFile(src="homepage/settings.yaml", dest="homepage/settings.yaml"),
            TemplateFile(src="homepage/docker.yaml", dest="homepage/docker.yaml"),
            TemplateFile(src="homepage/services.yaml", dest="homepage/services.yaml"),
            TemplateFile(src="homepage/bookmarks.yaml", dest="homepage/bookmarks.yaml"),
        ],
    ),
    ComposeApp(
        name="dozzle",
        image="amir20/dozzle",
        version="v10.6.9",
        volumes=[DOCKER_SOCKET],
    ),
    ComposeApp(
        name="whoami",
        image="traefik/whoami",
        version="v1.11.0",
    ),
    ComposeApp(
        name="miniflux",
        image="miniflux/miniflux",
        version="2.3.2",
        domain="rss.dv.zone",
    ),
    ComposeApp(
        name="forgejo",
        image="codeberg.org/forgejo/forgejo",
        # Latest stable + LTS (supported to 2027-07). Upgraded from 8.0.3 in one
        # jump -- migrations are cumulative and 15.0.3 ships the fixed migrations.
        # See docs/plans/forgejo-migration.md "Upgrade to v15" for the runbook.
        version="15.0.3",
        domain="git.dv.zone",
        volumes=[
            # Git repositories + LFS + gitea/conf/app.ini (SECRET_KEY,
            # INTERNAL_TOKEN, OAUTH2_JWT_SECRET, LFS_JWT_SECRET) -- the
            # highest-recovery-cost state in the homelab, so external=True keeps
            # `down -v` from ever wiping it.
            NamedVolume(name="forgejo-data", mount_path="/data", external=True),
        ],
    ),
    ComposeApp(
        name="qbittorrent",
        image="lscr.io/linuxserver/qbittorrent",
        version="5.2.2_v2.0.13-ls464",
        domain="torrent.dv.zone",
        volumes=[
            # Config: settings + per-torrent session/.fastresume data. High
            # recovery cost (losing it means re-adding every torrent and
            # force-rechecking), so external=True keeps `down -v` from wiping it.
            NamedVolume(name="qbittorrent-config", mount_path="/config", external=True),
            # The whole media library lives on the NAS under
            # /volume1/entertainment; we mount that *root* (not just /torrents) at
            # /data so the download client and the *arr apps share one tree and
            # cross-directory hardlinks / instant moves work. Downloads land in
            # the `torrents/` subdir (qBittorrent's Session\DefaultSavePath is
            # /data/torrents). Access is via a Synology ACL entry for the
            # container's id (2000); see the template's PUID/PGID note.
            NfsVolume(
                name="qbittorrent-data",
                mount_path="/data",
                server=nas_ip,
                path="/volume1/entertainment",
            ),
        ],
    ),
    ComposeApp(
        name="sabnzbd",
        image="lscr.io/linuxserver/sabnzbd",
        version="5.0.4-ls261",
        domain="nzb.dv.zone",
        volumes=[
            # Config: sabnzbd.ini (servers, API key, categories, schedules) plus
            # the queue/history db. High recovery cost -- losing it means
            # re-adding every news server and losing queue/history -- so
            # external=True keeps `down -v` from wiping it.
            NamedVolume(name="sabnzbd-config", mount_path="/config", external=True),
            # Mount the whole /volume1/entertainment tree at /data (not just the
            # usenet/ subdir) so downloads share the media library with the *arr
            # apps for hardlinks. sabnzbd writes under the `usenet/` subdir
            # (download_dir=/data/usenet/incomplete, complete_dir=/data/usenet/complete).
            # Access is via a Synology ACL entry for the container's id (2000);
            # see the template's PUID/PGID note.
            NfsVolume(
                name="sabnzbd-data",
                mount_path="/data",
                server=nas_ip,
                path="/volume1/entertainment",
            ),
        ],
    ),
    ComposeApp(
        name="portainer",
        # Enterprise Edition (free tier) -- matches the NAS instance so the
        # migrated /data volume (users, OIDC login config, EE license) stays valid.
        image="portainer/portainer-ee",
        version="2.39.4",
        domain="docker.dv.zone",
        volumes=[
            # Portainer's state: local admin user, OIDC login config, EE license,
            # environment/endpoint definitions, stacks. Non-trivial recovery cost,
            # so external=True keeps `down -v` from wiping it. Data is bridged
            # over from the NAS bind mount (/volume2/docker/portainer).
            NamedVolume(name="portainer-data", mount_path="/data", external=True),
            # Manages the local docker_vm daemon via the socket.
            DOCKER_SOCKET,
        ],
    ),
    ComposeApp(
        name="tautulli",
        image="tautulli/tautulli",
        version="v2.17.2",
        domain="tautulli.dv.zone",
        volumes=[
            # tautulli.db holds all Plex watch history + stats -- irreplaceable
            # historical data that can't be reconstructed -- so external=True
            # keeps `down -v` from wiping it. Config (config.ini) lives here too.
            NamedVolume(name="tautulli-config", mount_path="/config", external=True),
        ],
    ),
    ComposeApp(
        name="pinchflat",
        image="ghcr.io/kieraneglin/pinchflat",
        # Newest dated tag published to ghcr (later builds ship only as
        # :latest/:dev, which we don't pin to). Bump when a new vYYYY.M.D lands.
        version="v2025.6.6",
        domain="pinchflat.dv.zone",
        volumes=[
            # SQLite db (db/) tracking sources, per-video download history, and
            # settings. High recovery cost -- losing it re-adds every channel /
            # playlist and re-downloads everything -- so external=True keeps
            # `down -v` from wiping it. Bridged from the NAS
            # (/volume2/docker/pinchflat/config). Local volume (not NFS), so
            # SQLite WAL is fine here -- no JOURNAL_MODE override needed.
            NamedVolume(name="pinchflat-config", mount_path="/config", external=True),
            # The YouTube library lives on the NAS under
            # /volume1/entertainment/media/youtube -- a subdir of the same
            # entertainment tree qbittorrent/sabnzbd/cwa mount, so the existing
            # dockervm (uid 2000) ACL already covers it. Plex serves these files,
            # so pinchflat writes them as 2000:100 (see the template's `user:`).
            NfsVolume(
                name="pinchflat-downloads",
                mount_path="/downloads",
                server=nas_ip,
                path="/volume1/entertainment/media/youtube",
            ),
        ],
    ),
    ComposeApp(
        name="cwa",
        # Calibre-Web-Automated. Pinned stable (no :latest); bump via the version
        # field and redeploy.
        image="crocodilestick/calibre-web-automated",
        version="v4.0.6",
        domain="books.dv.zone",
        volumes=[
            # App settings + app.db (users, ingest history, per-user shelves).
            # High recovery cost, so external=True keeps `down -v` from wiping it.
            # Migrated from the NAS bind dir (/volume2/docker/cwa/config).
            NamedVolume(name="cwa-config", mount_path="/config", external=True),
            # Ingest/watch dir -- transient (files are removed after CWA processes
            # them). Local bind so books can be dropped on the host fs (and shared
            # with cwa-dl once it lands here too). Resolves to
            # /srv/docker/volumes/cwa/ingest.
            BindMount(source="cwa/ingest", mount_path="/cwa-book-ingest"),
            # The calibre library lives on the NAS under /volume1/entertainment --
            # the same share qbittorrent/sabnzbd mount -- so the existing dockervm
            # (uid 2000) ACL already covers it. metadata.db is SQLite on a network
            # share, so the template sets NETWORK_SHARE_MODE=true to disable WAL.
            NfsVolume(
                name="cwa-library",
                mount_path="/calibre-library",
                server=nas_ip,
                path="/volume1/entertainment/calibre-library",
            ),
        ],
    ),
    ComposeApp(
        name="shelfmark",
        # Book search/request + downloader (github.com/calibrain/shelfmark).
        # Fresh stand-up replacing the NAS cwa-dl stack (superseded) -- no
        # config/state carried over. The full image bundles Cloudflare bypass
        # (USE_CF_BYPASS=true), so unlike cwa-dl there is no cloudflarebypass
        # sidecar. Pinned stable; project is frozen as of May 2026.
        image="ghcr.io/calibrain/shelfmark",
        version="v1.3.3",
        domain="shelfmark.dv.zone",
        volumes=[
            # App config + users + sources + the request queue + the OIDC
            # provider config (entered once in Shelfmark's UI, like CWA). Fresh
            # install, but non-trivial recovery cost, so external=True keeps
            # `down -v` from wiping it.
            NamedVolume(name="shelfmark-config", mount_path="/config", external=True),
            # Downloads land here (INGEST_DIR in the template) -- the SAME bind
            # CWA watches (/srv/docker/volumes/cwa/ingest), so completed books
            # flow straight into CWA's auto-ingest. Reuses cwa's dir; the helper
            # creates it idempotently.
            BindMount(source="cwa/ingest", mount_path="/cwa-book-ingest"),
        ],
    ),
    ComposeApp(
        name="seerr",
        # Overseerr/Jellyseerr successor (seerr.dev); replaces the short-lived
        # sctx/overseerr install. Keeps Overseerr's /api/v1 surface and the
        # /app/config layout. Pinned stable; bump the version field and redeploy.
        image="ghcr.io/seerr-team/seerr",
        version="v3.3.0",
        domain="requests.dv.zone",
        volumes=[
            # settings.json + the SQLite db (db.sqlite3) holding request history,
            # user accounts (Plex-linked), and service (Plex/Radarr/Sonarr)
            # config. Non-trivial recovery cost -- losing it re-does the whole
            # setup and loses request history -- so external=True keeps `down -v`
            # from wiping it. Fresh volume: clean install, no data migrated from
            # the overseerr instance (which itself carried nothing over).
            NamedVolume(name="seerr-config", mount_path="/app/config", external=True),
        ],
    ),
    ComposeApp(
        name="pgadmin",
        image="dpage/pgadmin4",
        version="9.16",
        domain="pgadmin.dv.zone",
        volumes=[
            # pgadmin4.db (server/connection definitions, users, prefs, saved
            # queries) + storage/ + sessions. High recovery cost, so external=True
            # keeps `down -v` from wiping it. Bridged from the NAS
            # (/volume2/docker/pgadmin/data). The dpage image runs as uid/gid 5050.
            NamedVolume(name="pgadmin-data", mount_path="/var/lib/pgadmin", external=True),
            # config_local.py (OAuth2/OIDC config) is a single file that lives in
            # /pgadmin4 alongside the image's own modules, so it can't be a
            # whole-dir mount. The TemplateFile below renders it under
            # docker_volumes_base; an *absolute* source (is_managed=False) mounts
            # just that file read-only without the helper mkdir-ing a dir over it.
            BindMount(
                source=f"{docker_volumes_base}/pgadmin/config_local.py",
                mount_path="/pgadmin4/config_local.py",
                read_only=True,
            ),
        ],
        templates=[
            TemplateFile(src="config_local.py", dest="pgadmin/config_local.py", uid=5050, gid=5050),
        ],
    ),
    ComposeApp(
        name="nocodb",
        image="nocodb/nocodb",
        # NocoDB uses calver; pin the current :latest (also what the NAS runs).
        version="2026.06.2",
        domain="nocodb.dv.zone",
        volumes=[
            # /usr/app/data holds uploaded attachments + local tool state (the
            # relational data itself lives in the postgres_lxc `nocodb` DB via
            # NC_DB). Fresh volume -- this is a clean install, the barely-used NAS
            # data is not migrated -- but external=True still protects attachments
            # going forward so `down -v` can't wipe them.
            NamedVolume(name="nocodb-data", mount_path="/usr/app/data", external=True),
        ],
    ),
    ComposeApp(
        name="n8n",
        image="docker.n8n.io/n8nio/n8n",
        # Pin the exact version the NAS runs (was the floating :latest) so n8n's
        # startup DB migrations are a no-op against the carried-over DB. Bump as a
        # separate, isolated change afterwards.
        version="2.28.6",
        domain="n8n.dv.zone",
        volumes=[
            # The ~/.n8n dir. Beyond logs/custom-nodes, it holds `config` -- the
            # instance ENCRYPTION KEY that decrypts every stored credential in the
            # Postgres DB. Lose it and the migrated DB's credentials are
            # unrecoverable, so external=True keeps `down -v` from wiping it.
            # Bridged from the NAS bind dir (/volume2/docker/n8n); the image runs
            # as node (uid/gid 1000), matching the migrated files.
            NamedVolume(name="n8n-data", mount_path="/home/node/.n8n", external=True),
        ],
    ),
    ComposeApp(
        name="paperless",
        image="ghcr.io/paperless-ngx/paperless-ngx",
        version="2.20.15",
        domain="docs.dv.zone",
        volumes=[
            # Documents (media) and the search index/ML models (data) are the
            # high-recovery-cost state -> external named volumes so `down -v`
            # can't wipe them.
            NamedVolume(name="paperless-data", mount_path="/usr/src/paperless/data", external=True),
            NamedVolume(name="paperless-media", mount_path="/usr/src/paperless/media", external=True),
            # Broker data is disposable -> plain (project-scoped) named volume.
            NamedVolume(name="paperless-redis", mount_path="/data"),
            # Host-accessible so the migration export can be dropped here and the
            # consume inbox is reachable on the host fs.
            BindMount(source="paperless/export", mount_path="/usr/src/paperless/export"),
            BindMount(source="paperless/consume", mount_path="/usr/src/paperless/consume"),
        ],
    ),
    # Forgejo Actions runner (+ its isolated docker-in-docker daemon). Ephemeral
    # CI jobs -- including the scheduled Renovate run in
    # .forgejo/workflows/renovate.yml -- execute inside `dind`, never on the host
    # docker daemon. The runner connects declaratively via server.connections in
    # its config.yaml (Forgejo runner >=12.7). See
    # docs/plans/renovate-forgejo-actions.md.
    ComposeApp(
        name="forgejo-runner",
        image="code.forgejo.org/forgejo/runner",
        version="12.7.3",
        volumes=[
            # Runner cache/state. External so `down -v` can't wipe it.
            NamedVolume(name="forgejo-runner-data", mount_path="/data", external=True),
            # dind's image/layer cache -- disposable (re-pulls), so project-scoped.
            NamedVolume(name="forgejo-runner-dind-data", mount_path="/var/lib/docker"),
        ],
        templates=[
            # Holds the server.connections block (url + uuid + token + labels).
            # restart_on_change so a token/label edit restarts the runner service.
            TemplateFile(
                src="forgejo-runner-config.yaml",
                dest="forgejo-runner/config.yaml",
                restart_on_change=True,
            ),
        ],
    ),
]
