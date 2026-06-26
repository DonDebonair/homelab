from pyinfra.api import deploy

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
