from pyinfra.api import deploy
from pyinfra.operations import files, server


@deploy("Setup Networking")
def setup_networking():
    # Add interface for VLAN 50
    add_vlan50_interface = files.block(
        name="Add VLAN 50 interface to /etc/network/interfaces if not present",
        path="/etc/network/interfaces",
        content="""
auto enp4s0.50
iface enp4s0.50 inet manual

auto vmbr50
iface vmbr50 inet manual
    bridge-ports enp4s0.50
    bridge-stp off
    bridge-fd 0
""",
        line="source \\/etc\\/network\\/interfaces.*",
        before=True,
        marker="# {mark} VLAN 50 interface - set by pyinfra",
        _sudo=True,
    )
    # Ensure the networking service is restarted if the interface file changes
    server.service(
        name="Restart networking service",
        service="networking",
        restarted=True,
        _sudo=True,
        _if=add_vlan50_interface.did_change,
    )
