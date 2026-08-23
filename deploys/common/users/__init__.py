from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, server

from op_secrets import SecretString


@deploy("Ensure default user exists")
def default_user(password: SecretString, salt: SecretString, sudo: bool | None = None):
    """
    Ensure the default user exists
    This deploy is run first, and it sets up the required users and groups. On the bootstrap run it is
    reached as root, and only afterwards can subsequent deploys use a non-root user with sudo privileges.

    Args:
        password: the user's password
        salt: the salt to hash the password with
        sudo: whether to run the operations through sudo. Defaults to "only when we aren't already root",
            derived from the inventory's ssh_user. This matters because the Debian LXC template ships
            *without* a sudo binary: on the bootstrap run, `apt.packages(_sudo=True)` would fail trying
            to sudo its way into installing the very sudo it needs. Connecting as root, we don't need it;
            connecting as the unprivileged user afterwards, we do.
    """
    if sudo is None:
        sudo = host.data.get("ssh_user") != "root"

    apt.packages(
        name="Ensure 'sudo' is installed",
        packages=["sudo", "zsh"],
        # A freshly created LXC carries the template's package index, which is old enough that the
        # pool URLs in it 404. Refresh first; cache_time keeps this from running apt-get update on
        # every deploy of an already-bootstrapped host (same idiom as common/node_exporter).
        update=True,
        cache_time=3600,
        _sudo=sudo
    )
    server.user(
        name=f"Ensure '{host.data.user}' user exists",
        user=host.data.user,
        groups=["sudo"],
        create_home=True,
        password=password.encrypted(salt),
        shell="/usr/bin/zsh",
        public_keys=host.data.ssh_public_key,
        _sudo=sudo
    )
