from pyinfra import host
from pyinfra.facts.server import LinuxName

from deploys.nas import docker_setup, networking
from deploys.proxmox_host import prepare_proxmox_host, users_and_groups, setup_lxc_containers
from deploys.postgres_lxc import users, setup_postgres
from deploys.common.debian import common_debian_setup


if "nas" in host.groups:
    networking()
    docker_setup()

if "proxmox_host" in host.groups:
    prepare_proxmox_host()
    users_and_groups()
    setup_lxc_containers()

if "postgres_lxc" in host.groups:
    users()

if host.get_fact(LinuxName) == "Debian":
    common_debian_setup()

if "postgres_lxc" in host.groups:
    setup_postgres()
