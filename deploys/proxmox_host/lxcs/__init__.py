from pyinfra.api import deploy
from pyinfra.operations import files

from models.proxmox import PVEContainerArch, PVEContainerNetworkInterface, PVEContainerFeatures
from operations.proxmox import pve


@deploy("Setup LXC Containers")
def setup_lxc_containers():
    # Download the LXC template if it doesn't exist in /var/lib/vz/template/cache
    # Template URL: https://cdn.gyptazy.com/proxmox/debian-13-standard_13.0-0_amd64.tar.zst
    # SHA256: a543bb56db53200c81649a92cd385164d51df6c8d9ac5393b8bf15bed890d9aa
    files.download(
        name="Download LXC template for Debian 13 if not present",
        src="https://cdn.gyptazy.com/proxmox/debian-13-standard_13.0-0_amd64.tar.zst",
        dest="/var/lib/vz/template/cache/debian-13-standard_13.0-0_amd64.tar.zst",
        sha256sum="a543bb56db53200c81649a92cd385164d51df6c8d9ac5393b8bf15bed890d9aa",
        user="root",
        group="root",
        mode="644",
        _sudo=True,
    )
    pve.container(
        name="Create LXC container for PostgreSQL",
        vmid=100,
        os_template="local:vztmpl/debian-13-standard_13.0-0_amd64.tar.zst",
        hostname="postgres",
        arch=PVEContainerArch.AMD64,
        memory=4096,
        swap=2048,
        cores=2,
        networks=[
            # ip6 is manual (i.e. no autoconfiguration) because setting it to dhcp causes the container
            # to loose its ipv4 address after a while
            # see: https://forum.proxmox.com/threads/debian-lxc-container-not-getting-an-ip.65719/
            # NB: this used to read ip6="static", which pct rejects ("value does not look like a valid
            # ipv6 network configuration") -- it only accepts an address, auto, dhcp or manual. It went
            # unnoticed because the op no-ops while the container exists; it would have failed the day
            # this container had to be recreated.
            PVEContainerNetworkInterface(name="eth0", bridge="vmbr0", ip="dhcp", ip6="manual", firewall=True)
        ],
        rootfs="vm-pool:8",
        features=PVEContainerFeatures(nesting=True),
        ssh_public_keys="/home/daan/.ssh/authorized_keys",
        start=True,
        on_boot=True,
        _sudo=True,
    )
    # Palworld dedicated server.
    #
    # Sizing follows Pocketpair's published requirements
    # (https://docs.palworldgame.com/getting-started/requirements): 4+ cores and
    # 16 GB of RAM. 8 GB is documented as "bootable", but the server process has a
    # well-known memory leak -- RSS climbs for as long as the world stays up and is
    # only released by a restart -- so an 8 GB box tends to get OOM-killed mid
    # session. 16 GB plus a small swap buffer gives that leak somewhere to go until
    # the next restart. The host has 128 GB, so this is cheap.
    #
    # The rootfs lives on the NVMe-backed vm-pool, which the docs explicitly ask for
    # ("faster SSD strongly advised, as suboptimal performance may lead to data
    # corruption"). 32 GB covers the ~9 GB SteamCMD download plus save data and room
    # for in-place save backups.
    #
    # Unprivileged, unlike the PostgreSQL container above: SteamCMD and the server
    # binary need nothing from the host, so there is no reason to hand them root.
    # nesting=1 is the usual companion to that for a systemd-based Debian guest.
    #
    # One thing still has to happen outside this repo: the game is only reachable
    # over UDP 8211 from the internet, so the router has to forward UDP 8211 to
    # the static address configured below.
    pve.container(
        name="Create LXC container for the Palworld dedicated server",
        vmid=101,
        os_template="local:vztmpl/debian-13-standard_13.0-0_amd64.tar.zst",
        hostname="palworld",
        arch=PVEContainerArch.AMD64,
        memory=16384,
        swap=2048,
        cores=4,
        networks=[
            # Static, unlike the PostgreSQL container: the router has to forward UDP 8211 here, and a
            # forward pointed at an address that can move is a footgun. Keeping the address in this
            # repo means the router only has to know about the port, not about lease reservations.
            # ip6 manual for the same reason as the PostgreSQL container above.
            PVEContainerNetworkInterface(
                name="eth0", bridge="vmbr0", ip="192.168.1.42/24", gw="192.168.1.1", ip6="manual", firewall=True
            )
        ],
        rootfs="vm-pool:32",
        unprivileged=True,
        features=PVEContainerFeatures(nesting=True),
        ssh_public_keys="/home/daan/.ssh/authorized_keys",
        start=True,
        on_boot=True,
        _sudo=True,
    )
