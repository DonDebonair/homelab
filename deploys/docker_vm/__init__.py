from deploys.docker_vm.users import users
from deploys.docker_vm.docker import docker_setup
from deploys.docker_vm.proxies import setup_caddy_proxies
from deploys.docker_vm.macvlan_shim import setup_macvlan_shim
from deploys.docker_vm.apps import setup_apps
from deploys.docker_vm.monitoring import setup_monitoring, setup_loki_log_driver
from deploys.docker_vm.samba import setup_samba
from deploys.docker_vm.guest_agent import setup_guest_agent
