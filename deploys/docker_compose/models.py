from dataclasses import dataclass
from pathlib import Path


@dataclass
class DockerVolume:
    directory: str
    uid: int | None = None
    gid: int | None = None


@dataclass
class TemplateFile:
    src: str
    dest: str
    uid: int | None = None
    gid: int | None = None


@dataclass
class ComposeApp:
    name: str
    domain: str | None = None
    volumes: list[DockerVolume] | None = None
    files: list[TemplateFile] | None = None
    templates: list[TemplateFile] | None = None
    external: bool = False
