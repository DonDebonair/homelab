from dataclasses import dataclass
from enum import StrEnum
import json
from typing import override

from pyinfra.api import FactBase


@dataclass
class ProxmoxGroupInfo:
    group_id: str
    comment: str | None
    users: list[str]

@dataclass
class ProxmoxUserInfo:
    user_id: str
    enabled: bool
    expire: int | None
    firstname: str | None
    lastname: str | None
    email: str | None
    comment: str | None
    groups: list[str]
    realm_type: str


class ProxmoxAclType(StrEnum):
    USER = "user"
    GROUP = "group"
    TOKEN = "token"


@dataclass
class ProxmoxAclInfo:
    path: str
    propagate: bool
    role_id: str
    subject: str
    type: ProxmoxAclType  # 'user' or 'group'


class ProxmoxGroups(FactBase[dict[str, ProxmoxGroupInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pveum"

    @override
    def command(self) -> str:
        return "pveum group list --output-format json"

    @override
    def process(self, output: str) -> dict[str, ProxmoxGroupInfo]:
        groups_data = json.loads("\n".join(output))

        groups = {}
        for group in groups_data:
            groups[group["groupid"]] = ProxmoxGroupInfo(
                group_id=group["groupid"],
                comment=group.get("comment"),
                users=group["users"].split(",") if group["users"] else [],
            )
        return groups


class ProxmoxUsers(FactBase[dict[str, ProxmoxUserInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pveum"

    @override
    def command(self) -> str:
        return "pveum user list --full --output-format json"

    @override
    def process(self, output: str) -> dict[str, ProxmoxUserInfo]:
        users_data = json.loads("\n".join(output))

        users = {}
        for user in users_data:
            users[user["userid"]] = ProxmoxUserInfo(
                user_id=user["userid"],
                enabled=bool(user["enable"]),
                expire=user["expire"] if user["expire"] != 0 else None,
                firstname=user.get("firstname"),
                lastname=user.get("lastname"),
                email=user.get("email"),
                comment=user.get("comment"),
                groups=user["groups"].split(",") if user["groups"] else [],
                realm_type=user["realm-type"],
            )
        return users


class ProxmoxAcls(FactBase[dict[tuple[str, str, str], ProxmoxAclInfo]]):
    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pveum"

    @override
    def command(self) -> str:
        return "pveum acl list --output-format json"

    @override
    def process(self, output: str) -> dict[tuple[str, str, str], ProxmoxAclInfo]:
        acls_data = json.loads("\n".join(output))

        acls = {}
        for acl in acls_data:
            key = (acl["path"], acl["type"], acl["ugid"])
            acls[key] = ProxmoxAclInfo(
                path=acl["path"],
                propagate=bool(acl["propagate"]),
                role_id=acl["roleid"],
                subject=acl["ugid"],
                type=ProxmoxAclType(acl["type"]),
            )
        return acls
