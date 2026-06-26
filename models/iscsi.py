"""iSCSI data models shared across facts and operations."""

from dataclasses import dataclass


@dataclass
class ISCSISession:
    target_iqn: str
    portal: str | None
    state: str | None
    device: str | None
