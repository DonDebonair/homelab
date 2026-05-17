from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, docker

from deploys.common.docker_compose import docker_compose
from deploys.docker_vm.proxies.apps import apps
from deploys.docker_vm.proxies import vars

template_dir = Path(__file__).resolve().parent / "templates"


@deploy("Provision Caddy proxies with Docker")
def setup_caddy_proxies():
    build_dir = f"{host.data.docker_build_base}/caddy"
    files.directory(
        name="Create Caddy build directory",
        path=build_dir,
        mode=755,
        _sudo=True,
    )
    files.put(
        name="Upload Caddy Dockerfile",
        src=str(template_dir / "Dockerfile"),
        dest=f"{build_dir}/Dockerfile",
        mode=644,
        _sudo=True,
    )
    docker.build(
        name=f"Build custom Caddy image {vars.caddy_version}",
        path=build_dir,
        tags=[f"caddy-custom:{vars.caddy_version}"],
        build_args={"CADDY_VERSION": vars.caddy_version},
    )
    docker.network(
        name="Create caddy-internal network",
        network="caddy-internal",
        driver="bridge",
        subnet="172.101.0.0/16",
        ip_range="172.101.0.0/24",
        gateway="172.101.0.1",
    )
    docker.network(
        name="Create caddy-external network",
        network="caddy-external",
        driver="bridge",
        subnet="172.102.0.0/16",
        ip_range="172.102.0.0/24",
        gateway="172.102.0.1",
    )
    docker.network(
        name="Create authelia network",
        network="authelia",
        driver="bridge",
        subnet="172.103.0.0/16",
        ip_range="172.103.0.0/24",
        gateway="172.103.0.1",
    )
    docker_compose(apps=apps, template_dir=template_dir, variables=vars)
