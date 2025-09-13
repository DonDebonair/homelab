from models.docker import DockerNetwork

docker_user = "dockerlimited"
docker_uid = 2000
docker_gid = 2000
main_network_interface = "ens18"

# Docker network configuration
macvlan_network = DockerNetwork(
    name="macvlan",
    driver="macvlan",
    gateway="192.168.50.1",
    subnet="192.168.50.0/24",
    ip_range="192.168.50.0/24",
    opts=[f"parent={main_network_interface}"],
)
