from pyinfra import host
from pyinfra.api import deploy

import operations.proxmox.pbs as pbs
from models.proxmox import PBSAclType


@deploy("Configure PBS access for PVE backups")
def configure_backup_access():
    """
    Grant the Proxmox VE host least-privilege access to the backup datastore.

    The `pve@pbs!backup` API token's secret is bootstrapped manually into
    1Password (PBS only reveals it once), so this deploy just ensures the
    token-owning user exists and that DatastoreBackup is granted on the
    datastore. The token itself is created during bootstrap.

    With token privilege separation (the default), a token's effective rights
    are the intersection of the token's ACLs and its base user's ACLs — so the
    user `pve@pbs` must hold the role too, otherwise PVE cannot even see the
    datastore ("Cannot find datastore ...").
    """
    pbs.user(
        name="Ensure PBS user 'pve@pbs' exists",
        user_id="pve@pbs",
        _sudo=True,
    )
    datastore_path = f"/datastore/{host.data.iscsi_datastore_name}"
    pbs.acl(
        name="Grant DatastoreBackup to user 'pve@pbs' (privsep base)",
        path=datastore_path,
        role_id="DatastoreBackup",
        subject="pve@pbs",
        acl_type=PBSAclType.USER,
        _sudo=True,
    )
    pbs.acl(
        name="Grant DatastoreBackup to token 'pve@pbs!backup'",
        path=datastore_path,
        role_id="DatastoreBackup",
        subject="pve@pbs!backup",
        acl_type=PBSAclType.TOKEN,
        _sudo=True,
    )
