import json
from typing import override

from pyinfra.api import FactBase

from models.proxmox import (
    PBSUserInfo,
    PBSAclType,
    PBSAclInfo,
    PBSDatastoreInfo,
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


class PBSAcls(FactBase[dict[tuple[str, PBSAclType, str, str], PBSAclInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "proxmox-backup-manager"

    @override
    def command(self) -> str:
        return "proxmox-backup-manager acl list --output-format json"

    @override
    def process(self, output: list[str]) -> dict[tuple[str, PBSAclType, str, str], PBSAclInfo]:
        acls_data = json.loads("\n".join(output))

        acls = {}
        for acl in acls_data:
            path = acl["path"]
            ugid = acl["ugid"]
            role_id = acl["roleid"]
            # PBS reports both users and API tokens with ugid_type "user"; a
            # token is distinguished only by the "!" in its id (e.g.
            # "pve@pbs!backup"). Derive TOKEN so it round-trips against the
            # acl_type callers pass to the operation.
            raw_type = acl["ugid_type"]
            if raw_type == "user" and "!" in ugid:
                acl_type = PBSAclType.TOKEN
            else:
                acl_type = PBSAclType(raw_type)
            # `acl update` is additive: one auth-id can hold several roles on the
            # same path, so the role is part of the key.
            key = (path, acl_type, ugid, role_id)
            acls[key] = PBSAclInfo(
                path=path,
                propagate=bool(acl["propagate"]),
                role_id=role_id,
                subject=ugid,
                type=acl_type,
            )
        return acls


class PBSDatastores(FactBase[dict[str, PBSDatastoreInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "proxmox-backup-manager"

    @override
    def command(self) -> str:
        return "proxmox-backup-manager datastore list --output-format json"

    @override
    def process(self, output: list[str]) -> dict[str, PBSDatastoreInfo]:
        datastores_data = json.loads("\n".join(output))

        datastores = {}
        for datastore in datastores_data:
            name = datastore["name"]
            datastores[name] = PBSDatastoreInfo(
                name=name,
                path=datastore["path"],
                comment=datastore.get("comment"),
            )
        return datastores
