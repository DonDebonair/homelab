from pyinfra.api import operation
from pyinfra import host
from facts.synology import SynologyGroup, SynologyUser

@operation()
def user(user: str, uid: int | None = None, password: str | None = None, present: bool = True):
    """Manage a Synology local user.

    (Named `user`, not `name` -- pyinfra reserves `name` for the operation's
    display label.)

    `synouser` auto-assigns the uid on creation, so pinning a specific `uid`
    (needed to match a numeric identity across NFS) is done by editing
    /etc/passwd and running `synouser --rebuild all` -- which, verified on DSM,
    persists the change into the user DB rather than clobbering it. Idempotent:
    once the uid matches, this is a no-op.

    `password` is only used on creation (accounts here are nologin NFS
    identities); when omitted a throwaway random one is generated on the host so
    no secret is embedded in the yielded command.
    """
    info = host.get_fact(SynologyUser, user, _sudo=True)
    exists = info is not None

    if not present:
        if exists:
            yield f"/usr/syno/sbin/synouser --del '{user}'"
        else:
            host.noop(f"Synology user {user} is absent")
        return

    changed = False
    if not exists:
        # synouser --add <name> <pwd> <fullname> <expired 0|1> <mail> <AppPrivilege>
        pwd = f'"{password}"' if password is not None else '"$(openssl rand -base64 24)"'
        yield f'/usr/syno/sbin/synouser --add \'{user}\' {pwd} "" 0 "" ""'
        changed = True

    if uid is not None and (not exists or info.uid != uid):
        yield f"sed -i 's/^{user}:x:[0-9]*:/{user}:x:{uid}:/' /etc/passwd"
        yield "/usr/syno/sbin/synouser --rebuild all"
        changed = True

    if not changed:
        host.noop(f"Synology user {user} already present with uid {uid}")

@operation()
def group(group: str, present: bool = True):
    group_info = host.get_fact(SynologyGroup, group, _sudo=True)
    is_present = group_info is not None
    if not present and is_present:
        yield f"/usr/syno/sbin/synogroup --del '{group}'"
    elif present and not is_present:
        yield f"/usr/syno/sbin/synogroup --add '{group}'"

@operation()
def group_members(
        group: str,
        members: str | list[str],
        add: bool = True,
):
    if isinstance(members, str):
        members = [members]

    group_info = host.get_fact(SynologyGroup, group, _sudo=True)
    if group_info is None:
        raise ValueError(f"Group '{group}' does not exist.")

    if not set(members).issubset(set(group_info.members)):
        if add:
            new_member_list = list(set(group_info.members) | set(members))
        else:
            new_member_list = members

        yield f"/usr/syno/sbin/synogroup --member '{group}' {' '.join(new_member_list)}"
