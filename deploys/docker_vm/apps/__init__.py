from pathlib import Path
from pyinfra.api import deploy

from deploys.common.docker_compose import docker_compose
from deploys.docker_vm.apps.apps import apps
from deploys.docker_vm.apps import secrets

template_dir = Path(__file__).resolve().parent / "templates"


@deploy("Provision Docker apps")
def setup_apps():
    docker_compose(apps=apps, template_dir=template_dir, variables=secrets)
