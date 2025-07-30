from pyinfra.api import operation
from pyinfra import host
from facts.proxmox import ProxmoxGroups, ProxmoxUsers, ProxmoxAcls, ProxmoxAclType


@operation()
def group(group_id: str, comment: str | None = None, present: bool = True):
    groups = host.get_fact(ProxmoxGroups, _sudo=True)
    group_info = groups.get(group_id) if groups else None
    is_present = group_info is not None
    cmd = ["pveum", "group"]

    if not present and is_present:
        cmd.extend(["delete", group_id])
    elif present and not is_present:
        cmd.extend(["add", group_id])
        if comment:
            cmd.extend(["--comment", f"'{comment}'"])
    elif present and is_present:
        if comment is not None and comment != group_info.comment:
            cmd.extend(["modify", group_id, "--comment", f"'{comment}'"])
        else:
            host.noop(f"Group '{group_id}' already exists with the same comment.")
            return
    else:
        host.noop(f"Group '{group_id}' does not exist and 'present' is False.")
        return
    yield " ".join(cmd)


@operation()
def acl(path: str, role_id: str, subject: str, acl_type: ProxmoxAclType, propagate: bool = True, present: bool = True):
    acls = host.get_fact(ProxmoxAcls, _sudo=True)
    acl_info = acls.get((path, acl_type, subject)) if acls else None
    is_present = acl_info is not None
    cmd = ["pveum", "acl"]

    if not present and is_present:
        cmd.extend(["delete", path, "--" + acl_type + "s", subject])
    elif present and not is_present:
        cmd.extend(["modify", path, "--roles", role_id, "--" + acl_type + "s", str(subject), "--propagate",
                    str(int(propagate))])
    elif present and is_present:
        if role_id != acl_info.role_id or propagate != acl_info.propagate:
            cmd.extend(["modify", path, "--roles", role_id, "--" + acl_type + "s", subject, "--propagate",
                        str(int(propagate))])
        else:
            host.noop(f"ACL for '{subject}' on '{path}' already exists with the '{role_id}' role and propagation.")
            return
    else:
        host.noop(f"ACL for '{subject}' on '{path}' does not exist and 'present' is False.")
        return
    yield " ".join(cmd)


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
        groups: list[str] | None = None,
        present: bool = True,
        append_groups: bool = False,
):
    users = host.get_fact(ProxmoxUsers, _sudo=True)
    user_info = users.get(user_id) if users else None
    is_present = user_info is not None
    cmd = ["pveum", "user"]

    if not present and is_present:
        cmd.extend(["delete", user_id])
    elif present and not is_present:
        cmd.extend(["add", user_id])
        if password:
            cmd.extend(["--password", f"'{password}'"])
        if expire is not None:
            cmd.extend(["--expire", str(expire)])
        if firstname:
            cmd.extend(["--firstname", f"'{firstname}'"])
        if lastname:
            cmd.extend(["--lastname", f"'{lastname}'"])
        if email:
            cmd.extend(["--email", f"'{email}'"])
        if comment:
            cmd.extend(["--comment", f"'{comment}'"])
        if groups:
            cmd.extend(["--groups", ",".join(groups)])
        cmd.extend(["--enable", str(int(enabled))])
    elif present and is_present:
        modified = False
        cmd.extend(["modify", user_id])
        if password:
            cmd.extend(["--password", f"'{password}'"])
            modified = True
        if enabled != user_info.enabled:
            cmd.extend(["--enable", str(int(enabled))])
            modified = True
        if expire != user_info.expire:
            cmd.extend(["--expire", str(expire) if expire is not None else "0"])
            modified = True
        if firstname != user_info.firstname and firstname is not None:
            cmd.extend(["--firstname", f"'{firstname}'"])
            modified = True
        if lastname != user_info.lastname and lastname is not None:
            cmd.extend(["--lastname", f"'{lastname}'"])
            modified = True
        if email != user_info.email and email is not None:
            cmd.extend(["--email", f"'{email}'"])
            modified = True
        if comment != user_info.comment and comment is not None:
            cmd.extend(["--comment", f"'{comment}'"])
            modified = True
        if groups is not None and set(groups) != set(user_info.groups):
            cmd.extend(["--groups", ",".join(groups)])
            if append_groups:
                cmd.extend(["--append", "1"])
            modified = True
        if not modified:
            host.noop(f"User '{user_id}' already exists with the same attributes.")
            return
    yield " ".join(cmd)
