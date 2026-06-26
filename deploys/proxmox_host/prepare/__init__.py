import re

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, files, server

PROXMOX_KEYRING = "/usr/share/keyrings/proxmox-archive-keyring.gpg"


@deploy("Prepare Proxmox Host")
def prepare_proxmox_host():
    apt.sources_file(
        name="Ensure Enterprise repository is removed",
        filename="pve-enterprise",
        present=False,
    )
    add_proxmox_repo = apt.sources_file(
        name="Add Proxmox VE no-subscription repository",
        filename="proxmox",
        uris="http://download.proxmox.com/debian/pve",
        suites="trixie",
        components="pve-no-subscription",
        signed_by=PROXMOX_KEYRING,
    )
    add_ceph_repo = apt.sources_file(
        name="Add Ceph no-subscription repository",
        filename="ceph",
        uris="http://download.proxmox.com/debian/ceph-squid",
        suites="trixie",
        components="no-subscription",
        signed_by=PROXMOX_KEYRING,
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
