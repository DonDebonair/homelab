import re

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, files, server

PROXMOX_KEYRING = "/usr/share/keyrings/proxmox-archive-keyring.gpg"


@deploy("Prepare Proxmox Backup Server")
def prepare_pbs():
    apt.sources_file(
        name="Ensure Enterprise repository is removed",
        filename="pbs-enterprise",
        present=False,
        _sudo=True,
    )
    add_pbs_repo = apt.sources_file(
        name="Add Proxmox Backup Server no-subscription repository",
        filename="proxmox",
        uris="http://download.proxmox.com/debian/pbs",
        suites="trixie",
        components="pbs-no-subscription",
        signed_by=PROXMOX_KEYRING,
        _sudo=True,
    )
    apt.update(
        name="Update APT package cache",
        _if=add_pbs_repo.did_change,
        _sudo=True,
    )
    server.hostname(
        name="Set the system hostname",
        hostname=host.data.hostname,
        _sudo=True,
    )
    files.line(
        name="Ensure hostname is in /etc/hosts",
        path="/etc/hosts",
        line=fr"{re.escape(host.data.pbs_ip)}.*",
        replace=f"{host.data.pbs_ip} {host.data.hostname} {host.data.hostname_fqdn}",
        _sudo=True,
    )
