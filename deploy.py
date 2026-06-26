from pyinfra import host
from pyinfra.facts.server import LinuxName

from deploys.common.debian import common_debian_setup
from deploys.docker_vm import users as docker_vm_users, docker_setup, setup_caddy_proxies, setup_apps, \
    setup_guest_agent
from deploys.dns import setup_technitium_dns
from deploys.nas import docker_setup as nas_docker_setup, networking
from deploys.proxmox_host import prepare_proxmox_host, users_and_groups, setup_lxc_containers, setup_networking, \
    setup_vms, configure_backups
from deploys.postgres_lxc import users as postgres_users, setup_postgres, databases_and_users
from deploys.pbs_vm import prepare_pbs, users as pbs_vm_users, configure_datastore, configure_backup_access


if "nas" in host.groups:
    networking()
    nas_docker_setup()

if "proxmox_host" in host.groups:
    prepare_proxmox_host()
    users_and_groups()
    setup_networking()
    setup_lxc_containers()
    setup_vms()
    configure_backups()

if "postgres_lxc" in host.groups:
    postgres_users()

if "docker_vm" in host.groups:
    docker_vm_users()

if "pbs_vm" in host.groups:
    prepare_pbs()
    pbs_vm_users()
    configure_datastore()
    configure_backup_access()

if host.get_fact(LinuxName) == "Debian":
    common_debian_setup()

if "postgres_lxc" in host.groups:
    setup_postgres()
    databases_and_users()

if "docker_vm" in host.groups:
    docker_setup()
    setup_caddy_proxies()
    setup_apps()
    setup_technitium_dns()
    setup_guest_agent()
