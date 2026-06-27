from pyinfra import host
from pyinfra.api import HiddenValue, QuoteString, StringCommand, operation

from facts.proxmox.pbs import PBSUsers, PBSAcls, PBSDatastores
from models.proxmox import PBSAclType


@operation()
def user(
        user_id: str,
        password: str | None = None,
        enabled: bool = True,
        expire: int | None = None,
        firstname: str | None = None,
        lastname: str | None = None,
        email: str | None = None,
        comment: str | None = None,
        present: bool = True,
):
    """
    Create, update or remove a Proxmox Backup Server user via
    ``proxmox-backup-manager``.

    Args:
        user_id: The user id including realm, e.g. ``backup@pbs`` or ``root@pam``
        password: Password to set (only meaningful for ``@pbs`` realm users)
        enabled: Whether the user account is enabled
        expire: Account expiry as a unix epoch timestamp (``None``/``0`` = never)
        firstname, lastname, email, comment: Optional user attributes
        present: Whether the user should exist (True) or not (False)
    """
    users = host.get_fact(PBSUsers, _sudo=True)
    user_info = users.get(user_id) if users else None
    is_present = user_info is not None
    cmd: list[str | QuoteString] = ["proxmox-backup-manager", "user"]

    if not present and is_present:
        cmd.extend(["remove", QuoteString(user_id)])
    elif present and not is_present:
        cmd.extend(["create", QuoteString(user_id)])
        if password:
            cmd.extend(["--password", QuoteString(HiddenValue(str(password)))])
        if expire is not None:
            cmd.extend(["--expire", str(expire)])
        if firstname:
            cmd.extend(["--firstname", QuoteString(firstname)])
        if lastname:
            cmd.extend(["--lastname", QuoteString(lastname)])
        if email:
            cmd.extend(["--email", QuoteString(email)])
        if comment:
            cmd.extend(["--comment", QuoteString(comment)])
        cmd.extend(["--enable", str(int(enabled))])
    elif present and is_present:
        modified = False
        cmd.extend(["update", QuoteString(user_id)])
        if password:
            cmd.extend(["--password", QuoteString(HiddenValue(str(password)))])
            modified = True
        if enabled != user_info.enabled:
            cmd.extend(["--enable", str(int(enabled))])
            modified = True
        if expire != user_info.expire:
            # PBS treats an expiry of 0 as "never", so reset to 0 to clear it.
            cmd.extend(["--expire", str(expire) if expire is not None else "0"])
            modified = True
        if firstname != user_info.firstname and firstname is not None:
            cmd.extend(["--firstname", QuoteString(firstname)])
            modified = True
        if lastname != user_info.lastname and lastname is not None:
            cmd.extend(["--lastname", QuoteString(lastname)])
            modified = True
        if email != user_info.email and email is not None:
            cmd.extend(["--email", QuoteString(email)])
            modified = True
        if comment != user_info.comment and comment is not None:
            cmd.extend(["--comment", QuoteString(comment)])
            modified = True
        if not modified:
            host.noop(f"User '{user_id}' already exists with the same attributes.")
            return
    else:
        host.noop(f"User '{user_id}' does not exist and 'present' is False.")
        return
    yield StringCommand(*cmd)


@operation()
def acl(
        path: str,
        role_id: str,
        subject: str,
        acl_type: PBSAclType = PBSAclType.USER,
        propagate: bool = True,
        present: bool = True,
):
    """
    Set or remove an ACL entry on Proxmox Backup Server via
    ``proxmox-backup-manager acl update``.

    Args:
        path: The ACL path, e.g. ``/`` or ``/datastore/store1``
        role_id: The role to grant, e.g. ``DatastoreAdmin``
        subject: The auth-id (user/token) or group name the ACL applies to
        acl_type: Whether ``subject`` is a user, token or group
        propagate: Whether the ACL propagates to sub-paths
        present: Whether the ACL should exist (True) or not (False)
    """
    acls = host.get_fact(PBSAcls, _sudo=True)
    # `acl update` is additive (a role is added alongside any existing roles for
    # the auth-id on that path; PBS has no in-place role swap), so an ACL entry
    # is identified by role too. A role change is therefore a delete of the old
    # role plus a create of the new one, expressed as two operation calls.
    acl_info = acls.get((path, acl_type, subject, role_id)) if acls else None
    is_present = acl_info is not None
    cmd: list[str | QuoteString] = ["proxmox-backup-manager", "acl", "update"]
    # PBS addresses users/tokens via --auth-id and groups via --group. acl_type
    # is a PBSAclType enum member (fixed set), so the flag is safe to build; the
    # subject it refers to is quoted.
    subject_flag = "--group" if acl_type == PBSAclType.GROUP else "--auth-id"

    if not present and is_present:
        cmd.extend([QuoteString(path), QuoteString(role_id), subject_flag, QuoteString(subject), "--delete"])
    elif present and not is_present:
        cmd.extend([QuoteString(path), QuoteString(role_id), subject_flag, QuoteString(subject),
                    "--propagate", str(int(propagate))])
    elif present and is_present:
        # Same path/subject/role already present; only propagation can differ.
        if propagate != acl_info.propagate:
            cmd.extend([QuoteString(path), QuoteString(role_id), subject_flag, QuoteString(subject),
                        "--propagate", str(int(propagate))])
        else:
            host.noop(f"ACL for '{subject}' on '{path}' already exists with the '{role_id}' role and propagation.")
            return
    else:
        host.noop(f"ACL for '{subject}' on '{path}' does not exist and 'present' is False.")
        return
    yield StringCommand(*cmd)


@operation()
def datastore(
        datastore_name: str,
        path: str,
        comment: str | None = None,
        present: bool = True,
):
    """
    Create or remove a Proxmox Backup Server datastore via
    ``proxmox-backup-manager``.

    Args:
        datastore_name: The datastore name, e.g. ``synology``
        path: The absolute path backing the datastore, e.g. ``/mnt/synology``
        comment: Optional datastore comment (only set on creation)
        present: Whether the datastore should exist (True) or not (False)
    """
    datastores = host.get_fact(PBSDatastores, _sudo=True)
    datastore_info = datastores.get(datastore_name) if datastores else None
    is_present = datastore_info is not None
    cmd: list[str | QuoteString] = ["proxmox-backup-manager", "datastore"]

    if not present and is_present:
        cmd.extend(["remove", QuoteString(datastore_name)])
    elif present and not is_present:
        cmd.extend(["create", QuoteString(datastore_name), QuoteString(path)])
        if comment:
            cmd.extend(["--comment", QuoteString(comment)])
    elif present and is_present:
        # PBS does not support relocating a datastore in place; flag a mismatch
        # rather than silently ignoring it.
        if datastore_info.path != path:
            raise ValueError(
                f"Datastore '{datastore_name}' already exists at '{datastore_info.path}', "
                f"which differs from the requested path '{path}'."
            )
        host.noop(f"Datastore '{datastore_name}' already exists at '{path}'.")
        return
    else:
        host.noop(f"Datastore '{datastore_name}' does not exist and 'present' is False.")
        return
    yield StringCommand(*cmd)
