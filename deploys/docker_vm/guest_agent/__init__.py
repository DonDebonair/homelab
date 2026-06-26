from pyinfra.api import deploy
from pyinfra.operations import apt, server


@deploy("Install QEMU guest agent")
def setup_guest_agent():
    """
    Install the QEMU guest agent so PVE can fs-freeze the VM during vzdump,
    yielding application-consistent backups. Note: the VM must also have
    `agent: 1` set in its PVE config (`qm set <vmid> --agent 1`) — a one-time
    step done on the Proxmox host since the VM is created manually.
    """
    apt.packages(
        name="Install qemu-guest-agent",
        packages=["qemu-guest-agent"],
        _sudo=True,
    )
    server.service(
        name="Ensure qemu-guest-agent is enabled and running",
        service="qemu-guest-agent",
        running=True,
        enabled=True,
        _sudo=True,
    )
