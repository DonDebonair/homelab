from models.docker import DockerNetwork

docker_user = "dockerlimited"
docker_uid = 2000
docker_gid = 2000
default_group = docker_user
docker_volumes_base = "/srv/docker/volumes"
docker_compose_base = "/srv/docker/compose"
docker_build_base = "/srv/docker/build"
main_network_interface = "ens18"

internal_reverse_proxy_ip = "192.168.50.20"
external_reverse_proxy_ip = "192.168.50.21"
dns_ip = "192.168.50.30"
# Host's address on the macvlan-shim interface (lets the host reach the
# macvlan-only containers). Must be a free LAN IP, ideally outside the router's
# DHCP pool.
macvlan_shim_ip = "192.168.50.11"
# macvlan container IPs the host must reach via the shim (host-side /32 routes).
# These services live only on the macvlan network, so without the shim the host
# -- and bridge containers routing through it -- get "no route to host" when an
# internal name (e.g. auth.dv.zone -> .21) resolves to one of them.
macvlan_shim_routes = [internal_reverse_proxy_ip, external_reverse_proxy_ip, dns_ip]

extra_proxied_domains = [
    {"domain": "tv.dv.zone",       "port": 8989},
    {"domain": "movies.dv.zone",   "port": 8310},
    {"domain": "plex.dv.zone",     "port": 32400},
    {"domain": "indexers.dv.zone", "port": 9696},
    {"domain": "cmd.dv.zone",      "port": 1337},
]

# Docker network configuration
macvlan_network = DockerNetwork(
    name="macvlan",
    driver="macvlan",
    gateway="192.168.50.1",
    subnet="192.168.50.0/24",
    ip_range="192.168.50.0/24",
    opts=[f"parent={main_network_interface}"],
)

# Monitoring bridge network (prometheus/loki/grafana/exporters). Loki pins a
# fixed IP here so the daemon-level Loki log driver can push to it; see loki_ip
# below. Subnet picks the next free block after the caddy networks (172.101-104
# are taken in deploys/docker_vm/proxies/__init__.py).
monitoring_network = DockerNetwork(
    name="monitoring",
    driver="bridge",
    gateway="172.105.0.1",
    subnet="172.105.0.0/16",
    ip_range="172.105.0.0/24",
)
# Fixed address Loki binds on the monitoring network; the Docker daemon's
# default log driver ships every container's logs here. The host reaches this
# via the bridge, so it needs no macvlan-shim route.
loki_ip = "172.105.0.100"

