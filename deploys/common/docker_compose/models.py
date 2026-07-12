from dataclasses import dataclass
from typing import ClassVar


@dataclass
class BindMount:
    """Bind mount from host into container.

    If `source` is absolute (starts with '/'), it's a pre-existing system path
    (e.g. /var/run/docker.sock); the helper does not touch the host.
    If `source` is relative, it's resolved under host.data.docker_volumes_base
    and the helper creates that directory with the given uid/gid.
    """
    kind: ClassVar[str] = "bind"
    source: str
    mount_path: str
    uid: int | None = None
    gid: int | None = None
    read_only: bool = False

    @property
    def is_managed(self) -> bool:
        return not self.source.startswith("/")


@dataclass
class NamedVolume:
    """Docker named volume.

    external=False (default): compose creates the volume and project-scopes the name.
    Survives `docker compose down` but not `down -v`.
    external=True: the helper pre-creates the volume via docker.volume(present=True);
    compose marks it `external: true` and never tries to create or remove it. Survives
    `down -v`. Name is global (not project-scoped) so it must be unique.
    """
    kind: ClassVar[str] = "named"
    name: str
    mount_path: str
    external: bool = False
    read_only: bool = False


@dataclass
class NfsVolume:
    """NFS-backed docker named volume (local driver, type=nfs).

    Referenced in a service as `<name>:<mount_path>` like any named volume.
    `server` is the NFS host, `path` the exported path on it. NFS passes
    ownership by numeric uid/gid, so the container's PUID/PGID must match the
    ownership of the files on the NFS server -- not necessarily
    host.data.docker_uid/gid.

    external=False (default): rendered inline as a top-level volume with
    `driver_opts`; compose creates a project-scoped volume and the share is
    mounted lazily by the docker daemon when the first container using it starts.
    The helper does not pre-create anything.

    external=True: the helper pre-creates one global volume via
    docker.volume(driver="local", options=[...]) and compose marks it
    `external: true`, never touching driver_opts. Because the name is global (not
    project-scoped), several apps can reference the SAME NfsVolume to share one
    docker volume across compose projects -- e.g. qbittorrent and sabnzbd both
    mounting the `/volume1/entertainment` tree. The helper dedupes the
    pre-creation by name, so a shared volume is only created once. Survives
    `down -v`.
    """
    kind: ClassVar[str] = "nfs"
    name: str
    mount_path: str
    server: str
    path: str
    options: str = "rw,nfsvers=4,soft,timeo=100,retrans=3"
    read_only: bool = False
    external: bool = False


@dataclass
class TemplateFile:
    """A Jinja template rendered onto the host under docker_volumes_base.

    restart_on_change: when True, and this template's content actually changed on
    this run, the helper restarts the app's primary service (the compose service
    named after ``ComposeApp.name``) after the stack is (re)deployed. Needed for
    bind-mounted config that the container only reads at startup: `compose up -d`
    does NOT recreate a container when a bind-mounted file's *contents* change, so
    e.g. Authelia would otherwise keep serving stale OIDC config until a manual
    restart. Only the named service is restarted, not the whole project, so
    sidecars (e.g. authelia's session `redis`) are left untouched.
    """
    src: str
    dest: str
    uid: int | None = None
    gid: int | None = None
    restart_on_change: bool = False


@dataclass
class ComposeApp:
    name: str
    image: str
    version: str
    domain: str | None = None
    volumes: list[BindMount | NamedVolume | NfsVolume] | None = None
    files: list[TemplateFile] | None = None
    templates: list[TemplateFile] | None = None
    external: bool = False
