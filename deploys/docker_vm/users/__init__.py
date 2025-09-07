from pyinfra.api import deploy

from deploys.common.users import default_user
from deploys.docker_vm.users import secrets


@deploy("Ensure users and groups exist")
def users():
    """
    Ensure necessary users and groups exist on the Docker VM.

    This deploy is run first, and it sets up the required users and groups. The operations do not use sudo, as they are
    intended to be run as root. After this deploy, subsequent deploys can use a non-root user with sudo privileges.
    """
    default_user(password=secrets.user_password, salt=secrets.user_password_salt)
