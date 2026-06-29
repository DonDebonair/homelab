from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, docker, systemd

from deploys.common.docker_compose import docker_compose
from deploys.docker_vm.monitoring.monitoring import apps
from deploys.docker_vm.monitoring import secrets

template_dir = Path(__file__).resolve().parent / "templates"


@deploy("Provision monitoring stack")
def setup_monitoring():
    net = host.data.monitoring_network
    docker.network(
        name="Create monitoring network",
        network=net.name,
        driver=net.driver,
        subnet=net.subnet,
        ip_range=net.ip_range,
        gateway=net.gateway,
    )
    docker_compose(apps=apps, template_dir=template_dir, variables=secrets)


@deploy("Configure Loki Docker log driver")
def setup_loki_log_driver():
    """Ship every container's logs to Loki via the daemon's default log driver.

    Runs *after* setup_monitoring so Loki is already up before the daemon
    restart flips the default driver. The driver tag is arch-suffixed because
    grafana publishes no multi-arch tag for the plugin (see CLAUDE.md).
    """
    docker.plugin(
        name="Install Loki Docker log driver plugin",
        plugin="grafana/loki-docker-driver:3.7.2-amd64",
        alias="loki",
        present=True,
        enabled=True,
    )
    daemon_json = files.template(
        name="Configure Docker daemon default log driver",
        src=str(template_dir / "daemon.json.j2"),
        dest="/etc/docker/daemon.json",
        mode="0644",
        user="root",
        group="root",
        jinja_env_kwargs={
            "variable_start_string": "[[",
            "variable_end_string": "]]",
            "block_start_string": "[%",
            "block_end_string": "%]",
        },
        _sudo=True,
    )
    # Restarting the daemon restarts every container so they re-attach to the
    # Loki driver. Only when daemon.json actually changed.
    systemd.service(
        name="Restart Docker to apply log driver",
        service="docker",
        restarted=True,
        _sudo=True,
        _if=daemon_json.did_change,
    )
