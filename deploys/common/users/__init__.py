from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, server

from op_secrets import SecretString


@deploy("Ensure default user exists")
def default_user(password: SecretString, salt: SecretString):
    """
    Ensure the default user exists
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
        password=password.encrypted(salt),
        shell="/usr/bin/zsh",
        public_keys=host.data.ssh_public_key,
        _sudo=True
    )
