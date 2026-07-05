from pyinfra.api import deploy
from pyinfra.operations import apt, server


@deploy("Install node-exporter")
def setup_node_exporter():
    """
    Install Prometheus node-exporter from the Debian archive and run it as a
    systemd service for the docker_vm Prometheus to scrape.

    This is the group-agnostic, bare-metal/LXC counterpart to the compose
    exporter on docker_vm. On these hosts there is no container namespace to work
    around, so the distro package's default collector set already reports true
    host metrics -- no `pid: host` / `network_mode: host` / `--path.rootfs`
    gymnastics. The upstream default binds `:9100` on all interfaces, so the
    docker_vm Prometheus reaches it over the LAN (see the `nodeexporter` job in
    deploys/docker_vm/monitoring/templates/prometheus-config.yml.j2).

    Do NOT call this for docker_vm: it is Debian too but already binds `:9100`
    via the host-networked compose exporter, so the apt service would collide.
    """
    apt.packages(
        name="Install prometheus-node-exporter",
        packages=["prometheus-node-exporter"],
        # Refresh lists if stale so the package resolves on a freshly-provisioned
        # host; cache_time keeps it from running apt-get update every deploy.
        update=True,
        cache_time=3600,
        _sudo=True,
    )
    server.service(
        name="Ensure prometheus-node-exporter is enabled and running",
        service="prometheus-node-exporter",
        running=True,
        enabled=True,
        _sudo=True,
    )
