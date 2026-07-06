from pyinfra import host
from pyinfra.api import deploy

import operations.proxmox.pbs as pbs
from deploys.common.users import default_user
from deploys.pbs_vm.users import secrets


@deploy("Ensure users and groups exist")
def users():
    """
    Ensure necessary users and groups exist on the Proxmox Backup Server VM.

    This deploy is run first, as root, to set up the non-root user. After this
    deploy, subsequent deploys can use that user with sudo privileges.
    """
    default_user(password=secrets.user_password, salt=secrets.user_password_salt)

    # Allow web-UI / API login as the non-root PAM user. PBS authenticates the
    # `@pam` realm against the Linux account (created above), so no PBS-side
    # password is needed; an Admin ACL on `/` grants full access.
    admin_auth_id = f"{host.data.user}@pam"
    pbs.user(
        name=f"Ensure PBS user '{admin_auth_id}' exists",
        user_id=admin_auth_id,
        firstname=host.data.firstname,
        lastname=host.data.lastname,
        email=host.data.email,
        _sudo=True,
    )
    pbs.acl(
        name=f"Grant Admin on '/' to '{admin_auth_id}'",
        path="/",
        role_id="Admin",
        subject=admin_auth_id,
        _sudo=True,
    )

    # Read-only service identity for the Homepage `proxmoxbackupserver` widget. A
    # `@pbs`-realm user needs no password -- it authenticates only via an API
    # token. `Audit` is the built-in read-only role, enough for the widget's
    # datastore-usage / task / cpu / memory stats. The token is bootstrapped by
    # hand (PBS reveals a token secret only once; there is no pyinfra token op)
    # and stored in 1Password, mirroring `pve@pbs!backup`. Tokens are
    # privilege-separated by default (effective rights = user ACL ∩ token ACL),
    # so the same Audit role must be granted to `homepage@pbs!homepage` during
    # that bootstrap.
    widget_auth_id = "homepage@pbs"
    pbs.user(
        name=f"Ensure PBS user '{widget_auth_id}' exists",
        user_id=widget_auth_id,
        comment="Homepage proxmoxbackupserver widget (read-only)",
        _sudo=True,
    )
    pbs.acl(
        name=f"Grant Audit on '/' to '{widget_auth_id}'",
        path="/",
        role_id="Audit",
        subject=widget_auth_id,
        _sudo=True,
    )
