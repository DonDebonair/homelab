from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, server

from deploys.proxmox_host.users import secrets
from facts.proxmox import ProxmoxGroups, ProxmoxUsers, ProxmoxAcls, ProxmoxAclType
from operations import proxmox


@deploy("Ensure users and groups exist")
def users_and_groups():
    """
    Ensure necessary users and groups exist on the Proxmox host.

    This deploy is run first, and it sets up the required users and groups. The operations do not use sudo, as they are
    intended to be run as root. After this deploy, subsequent deploys can use a non-root user with sudo privileges.
    """
    apt.packages(
        name="Ensure 'sudo' is installed",
        packages=["sudo"],
        _sudo=True
    )
    server.user(
        name=f"Ensure '{host.data.user}' user exists",
        user=host.data.user,
        groups=["sudo"],
        create_home=True,
        password=secrets.user_password.encrypted(secrets.user_password_salt),
        shell="/bin/bash",
        public_keys=host.data.ssh_public_key,
        _sudo=True
    )
    groups = host.get_fact(ProxmoxGroups, _sudo=True)
    print(f"Existing groups: {groups}")
    users = host.get_fact(ProxmoxUsers, _sudo=True)
    print(f"Existing users: {users}")
    acls = host.get_fact(ProxmoxAcls, _sudo=True)
    print(f"Existing ACLs: {acls}")

    proxmox.group(
        name="Ensure 'admins' group exists",
        group_id="admins",
        comment="System Administrators",
        _sudo=True
    )
    proxmox.acl(
        name="Ensure 'admins' group has 'Administrator' role on root path",
        path="/",
        role_id="Administrator",
        subject="admins",
        acl_type=ProxmoxAclType.GROUP,
        propagate=True,
        _sudo=True
    )
    proxmox.user(
        name=f"Ensure '{host.data.user}' user exists in Proxmox",
        user_id=f"{host.data.user}@pam",
        enabled=True,
        firstname=host.data.firstname,
        lastname=host.data.lastname,
        email=host.data.email,
        groups=["admins"],
        _sudo=True
    )
