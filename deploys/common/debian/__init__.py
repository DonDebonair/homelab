from pyinfra.api import deploy
from pyinfra.operations import files, server, apt


@deploy("Common Debian Setup")
def common_debian_setup():
    server.locale(
        name="Ensure en_US.UTF-8 locale is enabled and generated",
        locale="en_US.UTF-8",
        _sudo=True,
    )
    files.replace(
        name="Set default locale to en_US.UTF-8",
        path="/etc/default/locale",
        text='LANG="C"',
        replace='LANG=en_US.UTF-8',
        _sudo=True,
    )
    files.replace(
        name="Allow agent forwarding in sshd_config",
        path="/etc/ssh/sshd_config",
        text="#AllowAgentForwarding yes",
        replace="AllowAgentForwarding yes",
        _sudo=True,
    )
    apt.packages(
        name="Install common packages",
        packages=[
            "curl",
            "wget",
            "net-tools",
            "htop",
            "unattended-upgrades",
            "zsh",
            "git",
            "atuin",
            "direnv",
        ],
        _sudo=True,
    )
    apt.deb(
        name="Ensure Chezmoi is installed",
        src="https://github.com/twpayne/chezmoi/releases/download/v2.65.0/chezmoi_2.65.0_linux_amd64.deb",
        _sudo=True,
    )
