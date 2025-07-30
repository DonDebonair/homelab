import types
from pathlib import Path
from typing import Any

from pyinfra.api import deploy
from pyinfra import host
from pyinfra.operations import files

from .models import ComposeApp
from utils.variables import normalize_vars


@deploy("Run Docker Compose")
def docker_compose(
        apps: list[ComposeApp],
        template_dir: Path,
        variables: dict[str, Any] | types.ModuleType | None = None,
):
    cleaned_vars = normalize_vars(variables) if variables else {}
    create_docker_volume_dirs(apps)
    # copy_templates(apps, template_dir, cleaned_vars)
    copy_files(apps)
    copy_compose_files(apps, template_dir, cleaned_vars)


def create_docker_volume_dirs(apps: list[ComposeApp]):
    for app in apps:
        if app.volumes:
            for volume in app.volumes:
                files.directory(
                    name=f"Create directory for Docker volume {app.name} - {volume.directory}",
                    path=f"{host.data.docker_volumes_base}/{volume.directory}",
                    user=volume.uid if volume.uid is not None else host.data.docker_user,
                    group=volume.gid if volume.gid is not None else host.data.default_group,
                    _sudo=True
                )


def copy_templates(apps: list[ComposeApp], template_dir: Path, variables: dict[str, Any] | None = None):
    for app in apps:
        if app.templates:
            for template in app.templates:
                src = template_dir / f"{template.src}.j2"
                dest = f"{host.data.docker_volumes_base}/{template.dest}"
                files.template(
                    name=f"Copy template {src} to {dest} for app {app.name}",
                    src=src,
                    dest=dest,
                    user=template.uid if template.uid is not None else host.data.docker_user,
                    group=template.gid if template.gid is not None else host.data.default_group,
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
        path=f"{host.data.home}/docker/compose",
        mode=755,
        _sudo=True
    )
    files.directory(
        name="Create directory for Docker builds",
        path=f"{host.data.home}/docker/build",
        mode=755,
        _sudo=True
    )
    for app in apps:
        files.directory(
            name=f"Create directory for app {app.name} compose file",
            path=f"{host.data.home}/docker/compose/{app.name}",
            mode=755,
            _sudo=True
        )


def copy_compose_files(apps: list[ComposeApp], template_dir: Path, variables: dict[str, Any] | None = None):
    for app in apps:
        files.template(
            name=f"Copy Docker Compose file for app {app.name}",
            src=template_dir / f"{app.name}.yaml.j2",
            dest=f"{host.data.home}/docker/compose/{app.name}/compose.yaml",
            user=host.data.docker_user,
            group=host.data.default_group,
            jinja_env_kwargs={
                "variable_start_string": "[[",
                "variable_end_string": "]]",
                "block_start_string": "[%",
                "block_end_string": "%]",
            },
            **variables,
            _sudo=True
        )
