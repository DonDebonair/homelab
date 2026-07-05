from models.docker import DockerNetwork

docker_user = "dockerlimited"
docker_uid = 2000
docker_gid = 2000
default_group = docker_user
# This host's own LAN address (matches the inventory connection target). Used
# as the Prometheus scrape target for node-exporter, which runs with
# network_mode: host and so binds the host's :9100 instead of a bridge IP.
docker_vm_ip = "192.168.50.10"
docker_volumes_base = "/srv/docker/volumes"
docker_compose_base = "/srv/docker/compose"
docker_build_base = "/srv/docker/build"
main_network_interface = "ens18"

internal_reverse_proxy_ip = "192.168.50.20"
external_reverse_proxy_ip = "192.168.50.21"
dns_ip = "192.168.50.30"
# Technitium console subdomain for this host (dns1.dv.zone) -- used for the
# server's own DNS_SERVER_DOMAIN. The NAS runs the secondary on dns2 -- see
# group_data/nas.py.
dns_console_subdomain = "dns1"
# All domains caddy should serve for this node's Technitium web console (each
# gets its own LE cert; all reverse-proxy to the same :5380 upstream because
# Technitium's HTTP service ignores the Host header). Besides the normal console
# name this includes the cluster node FQDN under `cluster.dv.zone`: Technitium
# clustering needs a cluster domain with no existing primary zone (so not
# dv.zone), and the nodes -- dns1/dns2.cluster.dv.zone -- need real certs for
# node-to-node HTTPS. See docs/plans/technitium-dns.md (Phase 2, clustering).
dns_console_domains = ["dns1.dv.zone", "dns1.cluster.dv.zone"]
# This host runs caddy-internal, so the Technitium console is proxied via
# caddy-docker-proxy labels on the container. The NAS has no local caddy, so its
# console is proxied from *this* host's caddy via extra_proxied_domains instead.
dns_console_via_caddy_labels = True
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
    # Secondary Technitium console lives on the NAS macvlan; proxy to it directly
    # (caddy-docker-proxy labels only cover containers on this host). Serves both
    # the console name and the cluster node FQDN -- a proxied entry may carry a
    # `domains` list (rendered comma-separated, one caddy site per name) instead
    # of a single `domain`; both share the one reverse_proxy upstream.
    {"domains": ["dns2.dv.zone", "dns2.cluster.dv.zone"], "ip": "192.168.1.210", "port": 5380},
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

