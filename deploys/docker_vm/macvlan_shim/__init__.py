from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server, systemd

templates_dir = Path(__file__).resolve().parent / "templates"


@deploy("Setup macvlan shim")
def setup_macvlan_shim():
    """
    Install a host-side macvlan "shim" so the docker_vm host -- and any
    bridge-network container that forwards DNS through the host resolver, such as
    cloudflared -- can reach the Technitium DNS container, which lives on a
    macvlan network. macvlan deliberately isolates a host from its own
    macvlan-attached containers; this shim is the standard workaround.

    The interface and its per-container /32 route are declared directly in a
    systemd oneshot unit (parameterised from group_data), so systemd recreates
    them on every boot and there is no separate script to keep in sync.
    """
    unit = files.template(
        name="Install macvlan-shim systemd unit",
        src=str(templates_dir / "macvlan-shim.service.j2"),
        dest="/etc/systemd/system/macvlan-shim.service",
        parent=host.data.main_network_interface,
        shim_ip=host.data.macvlan_shim_ip,
        routes=host.data.macvlan_shim_routes,
        _sudo=True,
    )
    server.shell(
        name="Reload systemd after writing macvlan-shim unit",
        commands=["systemctl daemon-reload"],
        _sudo=True,
        _if=unit.did_change,
    )
    systemd.service(
        name="Enable and start macvlan-shim on boot",
        service="macvlan-shim.service",
        running=True,
        enabled=True,
        _sudo=True,
    )
    server.shell(
        name="Restart macvlan-shim to apply changes",
        commands=["systemctl restart macvlan-shim.service"],
        _sudo=True,
        _if=unit.did_change,
    )
