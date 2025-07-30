import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Union, override

from pyinfra.api import FactBase

class SynologyGroupType(StrEnum):
    AUTH_LOCAL = "AUTH_LOCAL"
    AUTH_LDAP = "AUTH_LDAP"
    AUTH_DOM = "AUTH_DOMAIN"

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
