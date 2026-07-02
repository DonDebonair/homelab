from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, docker

from deploys.common.docker_compose import docker_compose
from deploys.nas.docker import vars
from deploys.nas.docker.apps import apps
from operations import synology

template_dir = Path(__file__).resolve().parent / "templates"


@deploy("Setup Docker")
def docker_setup():
    synology.group(
        name=f"Create '{host.data.docker_group}' group",
        group=host.data.docker_group,
        present=True,
        _sudo=True
    )
    synology.group_members(
        name=f"Add '{host.data.user}' to '{host.data.docker_group}'",
        group=host.data.docker_group,
        members=host.data.user,
        add=True,
        _sudo=True
    )
    files.directory(
        name="Create directory for Docker CLI plugins",
        path=f"{host.data.home}/.docker/cli-plugins",
        mode=755
    )
    files.download(
        name="Download Docker Compose CLI plugin",
        src=f"https://github.com/docker/compose/releases/download/"
            f"v{host.data.docker_compose_plugin_version}/docker-compose-linux-x86_64",
        dest=f"{host.data.home}/.docker/cli-plugins/docker-compose",
        mode=755,
        sha256sum=host.data.docker_compose_plugin_sha256sum,
    )
    docker.network(
        name="Create macvlan network",
        network="macvlan",
        driver="macvlan",
        subnet=host.data.macvlan_network.subnet,
        gateway=host.data.macvlan_network.gateway,
        ip_range=host.data.macvlan_network.ip_range,
        opts=host.data.macvlan_network.opts,
        aux_addresses=host.data.macvlan_network.aux_addresses,
    )
    files.directory(
        name="Create directory for compose files",
        path=host.data.docker_compose_base,
        mode=755
    )
    files.directory(
        name="Create directory for Docker builds",
        path=host.data.docker_build_base,
        mode=755
    )
    docker.plugin(
        name="Install Loki plugin",
        plugin="grafana/loki-docker-driver:3.7.2-amd64",
        alias="loki",
        enabled=True,
    )
    files.template(
        name="Configure Docker daemon default log driver",
        src=str(template_dir / "daemon.json.j2"),
        dest="/var/packages/ContainerManager/etc/dockerd.json",
        mode="0600",
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


@deploy("Setup Docker apps")
def setup_docker_apps():
    """Deploy the Docker Compose apps that remain on the NAS (currently just
    cAdvisor, scraped by the docker_vm Prometheus)."""
    docker_compose(apps=apps, template_dir=template_dir)