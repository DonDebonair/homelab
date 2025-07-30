from pathlib import Path
import re

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, files, server

files_dir = Path(__file__).resolve().parent / "files"


@deploy("Prepare Proxmox Host")
def prepare_proxmox_host():
    files.file(
        name="Ensure Enterprise repository is removed",
        path="/etc/apt/sources.list.d/pve-enterprise.sources",
        present=False,
    )
    add_proxmox_repo = files.put(
        name="Copy Proxmox VE no-subscription repository file",
        src=files_dir / "proxmox.sources",
        dest="/etc/apt/sources.list.d/proxmox.sources",
        mode=644,
        create_remote_dir=False,
    )
    add_ceph_repo = files.put(
        name="Copy Ceph no-subscription repository file",
        src=files_dir / "ceph.sources",
        dest="/etc/apt/sources.list.d/ceph.sources",
        mode=644,
        create_remote_dir=False
    )
    apt.update(
        name="Update APT package cache",
        _if=add_proxmox_repo.did_change or add_ceph_repo.did_change
    )
    server.hostname(
        name="Set the system hostname",
        hostname=host.data.hostname,
        _sudo=True
    )
    files.line(
        name="Ensure hostname is in /etc/hosts",
        path="/etc/hosts",
        line=fr"{re.escape(host.data.proxmox_ip)}.*",
        replace=f"{host.data.proxmox_ip} {host.data.hostname} {host.data.hostname_fqdn}",
        _sudo=True
    )
