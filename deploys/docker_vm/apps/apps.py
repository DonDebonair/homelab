from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume, TemplateFile

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
            TemplateFile(src="homepage/settings", dest="homepage/settings.yaml"),
            TemplateFile(src="homepage/docker", dest="homepage/docker.yaml"),
            TemplateFile(src="homepage/services", dest="homepage/services.yaml"),
            TemplateFile(src="homepage/bookmarks", dest="homepage/bookmarks.yaml"),
        ],
    ),
    ComposeApp(
        name="dozzle",
        image="amir20/dozzle",
        version="v10.6.6",
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
        # Latest 8.x patch: migrate on the same major as the NAS (`:8`) so the
        # startup schema migration is a no-op against the carried-over DB. A
        # major bump is a separate change -- see docs/plans/forgejo-migration.md.
        version="8.0.3",
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
]
