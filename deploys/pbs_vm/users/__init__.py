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
