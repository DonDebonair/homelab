from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, server

from deploys.postgres_lxc.users import secrets


@deploy("Ensure users and groups exist")
def users():
    """
    Ensure necessary users and groups exist on the PostgreSQL LXC.

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
