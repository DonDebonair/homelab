from pyinfra import host
from pyinfra.facts.server import LinuxName

from deploys.common.debian import common_debian_setup
from deploys.docker_vm import users as docker_vm_users, docker_setup, setup_caddy_proxies
from deploys.nas import docker_setup as nas_docker_setup, networking
from deploys.proxmox_host import prepare_proxmox_host, users_and_groups, setup_lxc_containers, setup_networking, \
    setup_vms
from deploys.postgres_lxc import users as postgres_users, setup_postgres, databases_and_users


if "nas" in host.groups:
    networking()
    nas_docker_setup()

if "proxmox_host" in host.groups:
    prepare_proxmox_host()
    users_and_groups()
    setup_networking()
    setup_lxc_containers()
    setup_vms()

if "postgres_lxc" in host.groups:
    postgres_users()

if "docker_vm" in host.groups:
    docker_vm_users()

if host.get_fact(LinuxName) == "Debian":
    common_debian_setup()

if "postgres_lxc" in host.groups:
    setup_postgres()
    databases_and_users()

if "docker_vm" in host.groups:
    docker_setup()
    setup_caddy_proxies()
