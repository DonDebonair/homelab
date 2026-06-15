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
            # ip6 is static because setting it as dhcp causes the container to loose its ipv4 address after while
            # see: https://forum.proxmox.com/threads/debian-lxc-container-not-getting-an-ip.65719/
            PVEContainerNetworkInterface(name="eth0", bridge="vmbr0", ip="dhcp", ip6="static", firewall=True)
        ],
        rootfs="vm-pool:8",
        features=PVEContainerFeatures(nesting=True),
        ssh_public_keys="/home/daan/.ssh/authorized_keys",
        start=True,
        on_boot=True,
        _sudo=True,
    )
