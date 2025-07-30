from pyinfra import host

from deploys.nas import docker_setup, networking
from deploys.proxmox_host import prepare_proxmox_host, users_and_groups


if "nas" in host.groups:
    networking()
    docker_setup()

if "proxmox_host" in host.groups:
    prepare_proxmox_host()
    users_and_groups()
