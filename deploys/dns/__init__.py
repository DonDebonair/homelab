from pathlib import Path

from pyinfra.api import deploy

from deploys.common.docker_compose import docker_compose
from deploys.dns.apps import apps
from deploys.dns import vars

template_dir = Path(__file__).resolve().parent / "templates"


@deploy("Provision Technitium DNS with Docker")
def setup_technitium_dns():
    docker_compose(apps=apps, template_dir=template_dir, variables=vars)
