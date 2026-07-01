import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Union, override

from pyinfra.api import FactBase

class SynologyGroupType(StrEnum):
    AUTH_LOCAL = "AUTH_LOCAL"
    AUTH_LDAP = "AUTH_LDAP"
    AUTH_DOM = "AUTH_DOMAIN"

class SynologyUserType(StrEnum):
    AUTH_LOCAL = "AUTH_LOCAL"
    AUTH_LDAP = "AUTH_LDAP"
    AUTH_DOM = "AUTH_DOMAIN"

@dataclass
class SynologyUserInfo:
    name: str
    uid: int
    gid: int
    type: SynologyUserType
    description: str
    home: str
    shell: str
    expired: bool
    mail: str


class SynologyUser(FactBase[Union[SynologyUserInfo, None]]):

    def requires_command(self, *args, **kwargs) -> str | None:
        return "/usr/syno/sbin/synouser"

    @override
    def command(self, user_name: str) -> str:
        return f"/usr/syno/sbin/synouser --get '{user_name}' || true"

    @override
    def process(self, output: str) -> Union[SynologyUserInfo, None]:
        output = '\n'.join(output)

        # A missing user prints "SYNOUserGet failed" / a "SynoErr" line and no
        # fields, so the absence of the name field is the reliable signal.
        name_match = re.search(r"User Name\s*:\s*\[(?P<name>.+?)\]", output)
        if not name_match:
            return None

        def field(label: str, pattern: str = r"(.*?)") -> str | None:
            match = re.search(rf"{label}\s*:\s*\[{pattern}\]", output)
            return match.group(1) if match else None

        return SynologyUserInfo(
            name=name_match.group("name"),
            uid=int(field("User uid", r"(\d+)")),
            gid=int(field("Primary gid", r"(\d+)")),
            type=SynologyUserType(field("User Type", r"(.+?)")),
            description=field("Fullname") or "",
            home=field("User Dir") or "",
            shell=field("User Shell") or "",
            expired=field("Expired", r"(.+?)") == "true",
            mail=field("User Mail") or "",
        )

@dataclass
class SynologyGroupInfo:
    name: str
    gid: int
    type: SynologyGroupType
    members: list[str]


class SynologyGroup(FactBase[Union[SynologyGroupInfo, None]]):

    def requires_command(self, *args, **kwargs) -> str | None:
        return "/usr/syno/sbin/synogroup"

    @override
    def command(self, group_name: str) -> str:
        return f"/usr/syno/sbin/synogroup --get '{group_name}' || true"

    @override
    def process(self, output: str) -> Union[SynologyGroupInfo, None]:

        output = '\n'.join(output)

        failure_pattern = r"SYNOGroupGet failed"

        if re.search(failure_pattern, output):
            return None

        # Extract all information with a single regex pattern using named groups
        pattern = r"Group Name: \[(?P<name>.+?)\].*?" \
                  r"Group Type: \[(?P<type>.+?)\].*?" \
                  r"Group ID:\s+\[(?P<gid>\d+)\].*?" \
                  r"Group Members:((?:\s+\d+:\[(?P<member>.+?)\])*)"

        match = re.search(pattern, output, re.DOTALL)
        if not match:
            return None

        # Extract basic information
        name = match.group('name')
        type_str = match.group('type')
        gid = int(match.group('gid'))

        # Extract members separately since they are multiple matches
        members = re.findall(r"\d+:\[(.+?)\]", output)

        # Convert string type to enum value
        group_type = SynologyGroupType(type_str)

        return SynologyGroupInfo(
            name=name,
            gid=gid,
            type=group_type,
            members=members
        )
