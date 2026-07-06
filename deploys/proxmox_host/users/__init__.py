from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, server

from deploys.proxmox_host.users import secrets
from facts.proxmox.pve import PVEAclType
from operations.proxmox import pve


@deploy("Ensure users and groups exist")
def users_and_groups():
    """
    Ensure necessary users and groups exist on the Proxmox host.

    This deploy is run first, and it sets up the required users and groups. The operations do not use sudo, as they are
    intended to be run as root. After this deploy, subsequent deploys can use a non-root user with sudo privileges.
    """
    apt.packages(
        name="Ensure 'sudo' is installed",
        packages=["sudo", "zsh"],
        _sudo=True
    )
    server.user(
        name=f"Ensure '{host.data.user}' user exists",
        user=host.data.user,
        groups=["sudo"],
        create_home=True,
        password=secrets.user_password.encrypted(secrets.user_password_salt),
        shell="/usr/bin/zsh",
        public_keys=host.data.ssh_public_key,
        _sudo=True
    )

    pve.group(
        name="Ensure 'admins' group exists",
        group_id="admins",
        comment="System Administrators",
        _sudo=True
    )
    pve.acl(
        name="Ensure 'admins' group has 'Administrator' role on root path",
        path="/",
        role_id="Administrator",
        subject="admins",
        acl_type=PVEAclType.GROUP,
        propagate=True,
        _sudo=True
    )
    pve.user(
        name=f"Ensure '{host.data.user}' user exists in Proxmox",
        user_id=f"{host.data.user}@pam",
        enabled=True,
        firstname=host.data.firstname,
        lastname=host.data.lastname,
        email=host.data.email,
        groups=["admins"],
        _sudo=True
    )

    # Read-only service identity for the Homepage `proxmox` widget. A `@pve`-realm
    # user needs no Linux/PAM account and no password -- it authenticates only via
    # an API token. `PVEAuditor` is the built-in read-only role (grants
    # {Sys,VM,Datastore}.Audit), enough for the widget's cluster/VM/CPU/memory
    # stats. The token itself is bootstrapped by hand (PVE reveals a token secret
    # only once; there is no pyinfra token op) and stored in 1Password, mirroring
    # the `pve@pbs!backup` flow. Because tokens are privilege-separated by default
    # (effective rights = user ACL ∩ token ACL), the same PVEAuditor role must be
    # granted to the token `homepage@pve!homepage` during that bootstrap.
    pve.user(
        name="Ensure 'homepage@pve' read-only widget user exists",
        user_id="homepage@pve",
        enabled=True,
        comment="Homepage proxmox widget (read-only)",
        _sudo=True,
    )
    pve.acl(
        name="Grant PVEAuditor on '/' to 'homepage@pve'",
        path="/",
        role_id="PVEAuditor",
        subject="homepage@pve",
        acl_type=PVEAclType.USER,
        propagate=True,
        _sudo=True,
    )
