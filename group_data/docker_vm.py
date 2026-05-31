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
