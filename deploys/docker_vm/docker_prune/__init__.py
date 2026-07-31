from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server, systemd

templates_dir = Path(__file__).resolve().parent / "templates"


@deploy("Setup weekly Docker prune")
def setup_docker_prune():
    """
    Weekly housekeeping for Docker's image store.

    Every image on this host is pinned to an explicit version (enforced by
    ComposeApp.image/version), so each Renovate bump + redeploy leaves the
    previous tag behind: still tagged, but referenced by no container. Plain
    `docker image prune` only removes *dangling* layers, so it never reaches
    them and they accumulate -- tens of GB per quarter across ~40 images.
    `docker image prune -a` is what reclaims them.

    Images labelled `docker_prune_keep_label` are exempt; that label is set on
    the locally built caddy-custom image, which has no registry to re-pull from.
    Volumes are deliberately not pruned -- see the unit template.
    """
    # `--filter label!=` takes a single key=value pair, so unpack it as one: a
    # second entry in group_data would raise here rather than be silently
    # dropped, leaving an image that thinks it is protected but is not.
    ((keep_key, keep_value),) = host.data.docker_prune_keep_label.items()

    service = files.template(
        name="Install docker-prune systemd unit",
        src=str(templates_dir / "docker-prune.service.j2"),
        dest="/etc/systemd/system/docker-prune.service",
        until=host.data.docker_prune_until,
        keep_label=f"{keep_key}={keep_value}",
        _sudo=True,
    )
    timer = files.template(
        name="Install docker-prune systemd timer",
        src=str(templates_dir / "docker-prune.timer.j2"),
        dest="/etc/systemd/system/docker-prune.timer",
        on_calendar=host.data.docker_prune_on_calendar,
        _sudo=True,
    )
    server.shell(
        name="Reload systemd after writing docker-prune units",
        commands=["systemctl daemon-reload"],
        _sudo=True,
        _if=lambda: service.did_change() or timer.did_change(),
    )
    systemd.service(
        name="Enable docker-prune timer on boot",
        service="docker-prune.timer",
        running=True,
        enabled=True,
        _sudo=True,
    )
    server.shell(
        name="Restart docker-prune timer to apply schedule changes",
        commands=["systemctl restart docker-prune.timer"],
        _sudo=True,
        _if=timer.did_change,
    )
