from pyinfra import host
from pyinfra.facts.server import LinuxName

from deploys.common.debian import common_debian_setup
from deploys.common.node_exporter import setup_node_exporter
from deploys.docker_vm import users as docker_vm_users, docker_setup, setup_caddy_proxies, setup_apps, \
    setup_guest_agent, setup_macvlan_shim, setup_samba, setup_monitoring, setup_loki_log_driver
from deploys.dns import setup_technitium_dns
from deploys.nas import docker_setup as nas_docker_setup, setup_docker_apps as nas_setup_docker_apps, \
    networking, setup_users as nas_setup_users
from deploys.proxmox_host import prepare_proxmox_host, users_and_groups, setup_lxc_containers, setup_networking, \
    setup_vms, configure_backups
from deploys.postgres_lxc import users as postgres_users, setup_postgres, databases_and_users
from deploys.pbs_vm import prepare_pbs, users as pbs_vm_users, configure_datastore, configure_backup_access


if "nas" in host.groups:
    nas_setup_users()
    networking()
    nas_docker_setup()
    nas_setup_docker_apps()
    # Secondary Technitium DNS instance (clusters with the docker_vm primary).
    # Runs after nas_docker_setup(), which creates the macvlan network + compose
    # dirs the stack references. Same group-agnostic deploys/dns/ code.
    setup_technitium_dns()

if "proxmox_host" in host.groups:
    prepare_proxmox_host()
    users_and_groups()
    setup_networking()
    setup_lxc_containers()
    setup_vms()
    configure_backups()
    setup_node_exporter()

if "postgres_lxc" in host.groups:
    postgres_users()

if "docker_vm" in host.groups:
    docker_vm_users()

if "pbs_vm" in host.groups:
    prepare_pbs()
    pbs_vm_users()
    configure_datastore()
    configure_backup_access()
    setup_node_exporter()

if host.get_fact(LinuxName) == "Debian":
    common_debian_setup()

if "postgres_lxc" in host.groups:
    setup_postgres()
    databases_and_users()
    setup_node_exporter()

if "docker_vm" in host.groups:
    docker_setup()
    setup_macvlan_shim()
    setup_caddy_proxies()
    setup_apps()
    setup_samba()
    setup_technitium_dns()
    setup_monitoring()
    # Flip the daemon's default log driver to Loki only after Loki is up.
    setup_loki_log_driver()
    setup_guest_agent()
