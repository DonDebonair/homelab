from pyinfra.api import operation
from pyinfra import host
from facts.synology import SynologyGroup

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
