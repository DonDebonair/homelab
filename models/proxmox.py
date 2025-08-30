"""Proxmox data models and enums shared across facts and operations."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass
class ProxmoxGroupInfo:
    group_id: str
    comment: str | None
    users: list[str]


@dataclass
class ProxmoxUserInfo:
    user_id: str
    enabled: bool
    expire: int | None
    firstname: str | None
    lastname: str | None
    email: str | None
    comment: str | None
    groups: list[str]
    realm_type: str


class ProxmoxAclType(StrEnum):
    USER = "user"
    GROUP = "group"
    TOKEN = "token"


@dataclass
class ProxmoxAclInfo:
    path: str
    propagate: bool
    role_id: str
    subject: str
    type: ProxmoxAclType


class ProxmoxContainerArch(StrEnum):
    AMD64 = "amd64"
    ARM64 = "arm64"
    ARMHF = "armhf"
    I386 = "i386"
    RISCV32 = "riscv32"
    RISCV64 = "riscv64"


class ProxmoxContainerOSType(StrEnum):
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
class ProxmoxContainerNetworkInterface:
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
class ProxmoxContainerRootFS:
    volume: str
    acl: bool | None = None
    mountoptions: list[str] | None = None
    quota: bool | None = None
    replicate: bool | None = None
    ro: bool | None = None
    shared: bool | None = None
    size: str | None = None


@dataclass
class ProxmoxContainerFeatures:
    force_rw_sys: bool | None = None
    fuse: bool | None = None
    keyctl: bool | None = None
    mknod: bool | None = None
    mount: list[str] | None = None
    nesting: bool | None = None


@dataclass
class ProxmoxContainerConfig:
    arch: ProxmoxContainerArch
    cores: int
    hostname: str
    memory: int
    ostype: ProxmoxContainerOSType
    rootfs: ProxmoxContainerRootFS
    swap: int
    unprivileged: bool
    features: ProxmoxContainerFeatures | None = None
    network_interfaces: dict[int, ProxmoxContainerNetworkInterface] | None = None


class ProxmoxContainerStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class ProxmoxContainerLock(StrEnum):
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
class ProxmoxContainerSummary:
    vmid: int
    status: ProxmoxContainerStatus
    lock: ProxmoxContainerLock | None
    name: str


class ProxmoxConsoleMode(StrEnum):
    CONSOLE = "console"
    SHELL = "shell"
    TTY = "tty"
