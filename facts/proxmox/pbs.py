import json
from typing import override

from pyinfra.api import FactBase

from models.proxmox import (
    PBSUserInfo,
    PBSAclType,
    PBSAclInfo,
)


class PBSUsers(FactBase[dict[str, PBSUserInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "proxmox-backup-manager"

    @override
    def command(self) -> str:
        return "proxmox-backup-manager user list --output-format json"

    @override
    def process(self, output: list[str]) -> dict[str, PBSUserInfo]:
        users_data = json.loads("\n".join(output))

        users = {}
        for user in users_data:
            user_id = user["userid"]
            # PBS omits optional fields when unset (unlike PVE, which emits
            # explicit nulls). `enable` is only present when the user is
            # disabled, so an absent value means the user is enabled. There is
            # no `realm-type` field; the realm is the part after the `@`.
            realm = user_id.split("@", 1)[1] if "@" in user_id else None
            users[user_id] = PBSUserInfo(
                user_id=user_id,
                enabled=bool(user.get("enable", True)),
                expire=user.get("expire"),
                firstname=user.get("firstname"),
                lastname=user.get("lastname"),
                email=user.get("email"),
                comment=user.get("comment"),
                realm=realm,
            )
        return users


class PBSAcls(FactBase[dict[tuple[str, str, str], PBSAclInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "proxmox-backup-manager"

    @override
    def command(self) -> str:
        return "proxmox-backup-manager acl list --output-format json"

    @override
    def process(self, output: list[str]) -> dict[tuple[str, str, str], PBSAclInfo]:
        acls_data = json.loads("\n".join(output))

        acls = {}
        for acl in acls_data:
            key = (acl["path"], acl["ugid_type"], acl["ugid"])
            acls[key] = PBSAclInfo(
                path=acl["path"],
                propagate=bool(acl["propagate"]),
                role_id=acl["roleid"],
                subject=acl["ugid"],
                type=PBSAclType(acl["ugid_type"]),
            )
        return acls
