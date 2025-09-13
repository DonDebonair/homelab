from dataclasses import dataclass

@dataclass
class DockerNetwork:
    name: str
    gateway: str
    subnet: str
    ip_range: str
    driver: str = "bridge"
    opts: list[str] | None = None
    aux_addresses: dict[str, str] | None = None
