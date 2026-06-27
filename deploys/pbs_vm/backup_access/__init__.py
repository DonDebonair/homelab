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
    token-owning user exists and that the datastore role is granted. The token
    itself is created during bootstrap.

    Role is `DatastorePowerUser`, the least-privilege built-in PBS role that
    grants Datastore.Prune (on top of Backup + Read). `DatastoreBackup` is not
    enough: vzdump's retention pruning (`prune-backups`) needs Datastore.Prune,
    otherwise the backup fails with "missing Datastore.Modify|Datastore.Prune".

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
    # Remove the earlier, insufficient DatastoreBackup grants. PBS `acl update`
    # is additive (it adds a role, it does not replace), so without an explicit
    # removal the old DatastoreBackup entry would linger alongside the new one.
    pbs.acl(
        name="Remove stale DatastoreBackup from user 'pve@pbs'",
        path=datastore_path,
        role_id="DatastoreBackup",
        subject="pve@pbs",
        acl_type=PBSAclType.USER,
        present=False,
        _sudo=True,
    )
    pbs.acl(
        name="Remove stale DatastoreBackup from token 'pve@pbs!backup'",
        path=datastore_path,
        role_id="DatastoreBackup",
        subject="pve@pbs!backup",
        acl_type=PBSAclType.TOKEN,
        present=False,
        _sudo=True,
    )
    pbs.acl(
        name="Grant DatastorePowerUser to user 'pve@pbs' (privsep base)",
        path=datastore_path,
        role_id="DatastorePowerUser",
        subject="pve@pbs",
        acl_type=PBSAclType.USER,
        _sudo=True,
    )
    pbs.acl(
        name="Grant DatastorePowerUser to token 'pve@pbs!backup'",
        path=datastore_path,
        role_id="DatastorePowerUser",
        subject="pve@pbs!backup",
        acl_type=PBSAclType.TOKEN,
        _sudo=True,
    )
