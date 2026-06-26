import re
from typing import override

from pyinfra.api import FactBase

from models.iscsi import ISCSISession


class ISCSISessions(FactBase[dict[str, ISCSISession]]):
    """
    Active iSCSI sessions, keyed by target IQN, parsed from
    ``iscsiadm -m session -P 3``.

    The verbose (``-P 3``) output groups everything under a ``Target:`` line and
    lists, per session, the negotiated portal and the attached SCSI disk (e.g.
    ``sdb``) together with its running state. We extract just enough to decide
    whether a target is logged in and which block device it maps to.
    """

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "iscsiadm"

    @staticmethod
    @override
    def default() -> dict[str, ISCSISession]:
        return {}

    @override
    def command(self) -> str:
        # `iscsiadm -m session` exits 21 with "iscsiadm: No active sessions." on
        # stderr when nothing is logged in; swallow that so pyinfra sees an empty
        # (successful) fact rather than a load failure.
        return "iscsiadm -m session -P 3 2> /dev/null || true"

    @override
    def process(self, output: list[str]) -> dict[str, ISCSISession]:
        sessions: dict[str, ISCSISession] = {}
        current: ISCSISession | None = None

        for line in output:
            stripped = line.strip()

            target_match = re.match(r"Target:\s+(\S+)", stripped)
            if target_match:
                current = ISCSISession(
                    target_iqn=target_match.group(1),
                    portal=None,
                    state=None,
                    device=None,
                )
                sessions[current.target_iqn] = current
                continue

            if current is None:
                continue

            portal_match = re.match(r"Current Portal:\s+(\S+)", stripped)
            if portal_match:
                # Drop the trailing ",<tag>" portal group id, keeping host:port.
                current.portal = portal_match.group(1).split(",", 1)[0]
                continue

            disk_match = re.match(
                r"Attached scsi disk\s+(\S+)\s+State:\s+(\S+)", stripped
            )
            if disk_match:
                current.device = f"/dev/{disk_match.group(1)}"
                current.state = disk_match.group(2)

        return sessions
