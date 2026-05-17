import types
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, FileSystemLoader
from pyinfra.api import deploy
from pyinfra import host
from pyinfra.operations import files, docker

from .models import ComposeApp, BindMount, NamedVolume
from utils.variables import normalize_vars

COMMON_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@deploy("Run Docker Compose")
def docker_compose(
        apps: list[ComposeApp],
        template_dir: Path,
        variables: dict[str, Any] | types.ModuleType | None = None,
):
    cleaned_vars = normalize_vars(variables) if variables else {}
    create_docker_volume_dirs(apps)
    create_external_named_volumes(apps)
    copy_templates(apps, template_dir, cleaned_vars)
    copy_files(apps)
    create_compose_dirs(apps)
    copy_compose_files(apps, template_dir, cleaned_vars)
    deploy_compose_files(apps)


def create_docker_volume_dirs(apps: list[ComposeApp]):
    for app in apps:
        if app.volumes:
            for volume in app.volumes:
                if isinstance(volume, BindMount) and volume.is_managed:
                    files.directory(
                        name=f"Create directory for Docker volume {app.name} - {volume.source}",
                        path=f"{host.data.docker_volumes_base}/{volume.source}",
                        user=str(volume.uid) if volume.uid is not None else host.data.docker_user,
                        group=str(volume.gid) if volume.gid is not None else host.data.default_group,
                        _sudo=True
                    )


def create_external_named_volumes(apps: list[ComposeApp]):
    for app in apps:
        if app.volumes:
            for volume in app.volumes:
                if isinstance(volume, NamedVolume) and volume.external:
                    docker.volume(
                        name=f"Ensure external named volume {volume.name} exists for {app.name}",
                        volume=volume.name,
                        present=True,
                    )


def copy_templates(apps: list[ComposeApp], template_dir: Path, variables: dict[str, Any] | None = None):
    for app in apps:
        if app.templates:
            for template in app.templates:
                src = str(template_dir / f"{template.src}.j2")
                dest = f"{host.data.docker_volumes_base}/{template.dest}"
                files.template(
                    name=f"Copy template {src} to {dest} for app {app.name}",
                    src=src,
                    dest=dest,
                    user=str(template.uid) if template.uid is not None else host.data.docker_user,
                    group=str(template.gid) if template.gid is not None else host.data.default_group,
                    jinja_env_kwargs={
                        "variable_start_string": "[[",
                        "variable_end_string": "]]",
                        "block_start_string": "[%",
                        "block_end_string": "%]",
                    },
                    **variables,
                    _sudo=True
                )


def copy_files(apps: list[ComposeApp]):
    for app in apps:
        if app.files:
            for file in app.files:
                files.put(
                    name=f"Copy file {file.src} to {file.dest} for app {app.name}",
                    src=file.src,
                    dest=f"{host.data.docker_volumes_base}/{file.dest}",
                    user=file.uid if file.uid is not None else host.data.docker_user,
                    group=file.gid if file.gid is not None else host.data.default_group,
                    _sudo=True
                )


def create_compose_dirs(apps: list[ComposeApp]):
    files.directory(
        name="Create directory for Docker Compose files",
        path=host.data.docker_compose_base,
        mode=755,
        _sudo=True
    )
    files.directory(
        name="Create directory for Docker builds",
        path=host.data.docker_build_base,
        mode=755,
        _sudo=True
    )
    for app in apps:
        files.directory(
            name=f"Create directory for app {app.name} compose file",
            path=f"{host.data.docker_compose_base}/{app.name}",
            mode=755,
            _sudo=True
        )


def copy_compose_files(apps: list[ComposeApp], template_dir: Path, variables: dict[str, Any] | None = None):
    loader = ChoiceLoader([
        FileSystemLoader(str(template_dir)),
        FileSystemLoader(str(COMMON_TEMPLATE_DIR)),
    ])
    for app in apps:
        files.template(
            name=f"Copy Docker Compose file for app {app.name}",
            src=str(template_dir / f"{app.name}.yaml.j2"),
            dest=f"{host.data.docker_compose_base}/{app.name}/compose.yaml",
            user=host.data.docker_user,
            group=host.data.default_group,
            jinja_env_kwargs={
                "variable_start_string": "[[",
                "variable_end_string": "]]",
                "block_start_string": "[%",
                "block_end_string": "%]",
                "loader": loader,
            },
            app=app,
            **variables,
            _sudo=True
        )


def deploy_compose_files(apps: list[ComposeApp]):
    for app in apps:
        docker.compose(
            name=f"Deploy {app.name} compose stack",
            project_directory=f"{host.data.docker_compose_base}/{app.name}",
            project_name=app.name,
        )
