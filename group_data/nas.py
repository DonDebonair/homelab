from models.docker import DockerNetwork

user = "daanadmin"
home = f"/var/services/homes/{user}"
docker_volumes_base = "/volume2/docker"
docker_compose_base = f"{home}/docker/compose"
docker_build_base = f"{home}/docker/build"
docker_user = "dockerlimited"
docker_group = "docker"
default_group = "users"
docker_compose_plugin_version = "2.39.1"
docker_compose_plugin_sha256sum = "a5ea28722d5da628b59226626f7d6c33c89a7ed19e39f750645925242044c9d2"
main_network_interface = "eth0"
host_aux_address = "192.168.1.223"

# Docker network configuration
macvlan_network = DockerNetwork(
    name="macvlan",
    driver="macvlan",
    gateway="192.168.1.1",
    subnet="192.168.1.1/24",
    ip_range="192.168.1.192/27",
    opts=[f"parent={main_network_interface}"],
    aux_addresses={
        "host": host_aux_address,
    }
)
monitoring_network = DockerNetwork(
    name="monitoring",
    driver="bridge",
    gateway="172.105.0.1",
    subnet="172.105.0.0/16",
    ip_range="172.105.0.0/24"
)
