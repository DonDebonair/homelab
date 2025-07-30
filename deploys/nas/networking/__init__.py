from pathlib import Path
from typing import Any

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.hardware import NetworkDevices
from pyinfra.operations import files, server

files_dir = Path(__file__).resolve().parent / "files"

def has_key_starting_with(dictionary: dict[str, Any], prefix: str) -> bool:
    return any(key.startswith(prefix) for key in dictionary.keys())

@deploy("Setup networking")
def networking():
    macvlan_script = f"{host.data.home}/macvlan.sh"
    files.put(
        name="Copy macvlan script",
        src=files_dir / "macvlan.sh",
        dest=macvlan_script,
        mode=755,
        create_remote_dir=False
    )
    network_devices = host.get_fact(NetworkDevices)
    macvlan_created = has_key_starting_with(network_devices, "macvlan-shim")

    if not macvlan_created:
        # The script will create the macvlan interface if it doesn't exist
        server.shell(
            name="Create macvlan network interface",
            commands=f"sh {macvlan_script}",
            _sudo=True,
        )
