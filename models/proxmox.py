"""Proxmox data models and enums shared across facts and operations."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass
class PVEGroupInfo:
    group_id: str
    comment: str | None
    users: list[str]


@dataclass
class PVEUserInfo:
    user_id: str
    enabled: bool
    expire: int | None
    firstname: str | None
    lastname: str | None
    email: str | None
    comment: str | None
    groups: list[str]
    realm_type: str


class PVEAclType(StrEnum):
    USER = "user"
    GROUP = "group"
    TOKEN = "token"


@dataclass
class PVEAclInfo:
    path: str
    propagate: bool
    role_id: str
    subject: str
    type: PVEAclType


class PVEContainerArch(StrEnum):
    AMD64 = "amd64"
    ARM64 = "arm64"
    ARMHF = "armhf"
    I386 = "i386"
    RISCV32 = "riscv32"
    RISCV64 = "riscv64"


class PVEContainerOSType(StrEnum):
    ALPINE = "alpine"
    ARCHLINUX = "archlinux"
    CENTOS = "centos"
    DEBIAN = "debian"
    DEVUAN = "devuan"
    FEDORA = "fedora"
    GENTOO = "gentoo"
    NIXOS = "nixos"
    OPENSUSE = "opensuse"
    UBUNTU = "ubuntu"
    UNMANAGED = "unmanaged"


@dataclass
class PVEContainerNetworkInterface:
    name: str
    bridge: str | None = None
    firewall: bool | None = None
    gw: str | None = None
    gw6: str | None = None
    hwaddr: str | None = None
    ip: str | None = None
    ip6: str | None = None
    link_down: bool | None = None
    mtu: int | None = None
    rate: int | None = None
    tag: int | None = None
    trunks: list[int] | None = None
    type: str | None = None


@dataclass
class PVEContainerRootFS:
    volume: str
    acl: bool | None = None
    mountoptions: list[str] | None = None
    quota: bool | None = None
    replicate: bool | None = None
    ro: bool | None = None
    shared: bool | None = None
    size: str | None = None


@dataclass
class PVEContainerFeatures:
    force_rw_sys: bool | None = None
    fuse: bool | None = None
    keyctl: bool | None = None
    mknod: bool | None = None
    mount: list[str] | None = None
    nesting: bool | None = None


@dataclass
class PVEContainerConfig:
    arch: PVEContainerArch
    cores: int
    hostname: str
    memory: int
    ostype: PVEContainerOSType
    rootfs: PVEContainerRootFS
    swap: int
    unprivileged: bool
    features: PVEContainerFeatures | None = None
    network_interfaces: dict[int, PVEContainerNetworkInterface] | None = None


class PVEContainerStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class PVEContainerLock(StrEnum):
    BACKUP = "backup"
    CREATE = "create"
    DESTROYED = "destroyed"
    DISK = "disk"
    FSTRIM = "fstrim"
    MIGRATE = "migrate"
    MOUNTED = "mounted"
    ROLLBACK = "rollback"
    SNAPSHOT = "snapshot"
    SNAPSHOT_DELETE = "snapshot-delete"
    UNKNOWN = "unknown"


@dataclass
class PVEContainerSummary:
    vmid: int
    status: PVEContainerStatus
    lock: PVEContainerLock | None
    name: str


class PVEConsoleMode(StrEnum):
    CONSOLE = "console"
    SHELL = "shell"
    TTY = "tty"


# --- Proxmox Backup Server (PBS) ---------------------------------------------


@dataclass
class PBSUserInfo:
    user_id: str
    enabled: bool
    expire: int | None
    firstname: str | None
    lastname: str | None
    email: str | None
    comment: str | None
    realm: str | None


class PBSAclType(StrEnum):
    USER = "user"
    GROUP = "group"
    TOKEN = "token"


@dataclass
class PBSAclInfo:
    path: str
    propagate: bool
    role_id: str
    subject: str
    type: PBSAclType


@dataclass
class PBSDatastoreInfo:
    name: str
    path: str
    comment: str | None
