from pyinfra import host
from pyinfra.api import deploy, DeployError
from pyinfra.facts.server import Kernel, KernelVersion, Arch, OsRelease
from pyinfra.operations import apt, files, server, docker


@deploy("Install and configure Docker")
def docker_setup():
    apt.packages(
        name="Install ca-certificates package",
        packages=[
            "ca-certificates",
            "gnupg",
        ],
        _sudo=True,
    )
    files.directory(
        name="Create /etc/apt/keyrings directory",
        path="/etc/apt/keyrings",
        mode="0755",
        user="root",
        group="root",
        _sudo=True,
    )
    files.download(
        name="Download Docker GPG key",
        src="https://download.docker.com/linux/debian/gpg",
        dest="/etc/apt/keyrings/docker.asc",
        mode="0644",
        user="root",
        group="root",
        _sudo=True,
    )
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armhf",
        "armv6l": "armhf",
        "ppc64le": "ppc64el",
        "s390x": "s390x",
    }
    arch = host.get_fact(Arch)
    apt_arch = arch_map.get(arch)
    if not apt_arch:
        raise DeployError(f"Unsupported architecture: {arch}")
    os_release = host.get_fact(OsRelease)
    version_codename = os_release["version_codename"]
    if not version_codename:
        raise DeployError("Could not determine OS version codename")
    docker_repo_line = (
        f"deb [arch={apt_arch} signed-by=/etc/apt/keyrings/docker.asc] "
        f"https://download.docker.com/linux/debian {version_codename} stable"
    )
    add_docker_repo = apt.repo(
        name="Add Docker APT repository",
        src=docker_repo_line,
        filename="docker",
        _sudo=True,
    )
    apt.update(
        name="Update APT package index",
        _sudo=True,
        _if=add_docker_repo.did_change,
    )
    apt.packages(
        name="Install Docker packages",
        packages=[
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "docker-buildx-plugin",
            "docker-compose-plugin",
        ],
        _sudo=True,
    )
    server.user(
        name=f"Add user '{host.data.user}' to 'docker' group",
        user=host.data.user,
        groups=["docker"],
        append=True,
        _sudo=True,
    )
    server.user(
        name=f"Create user '{host.data.docker_user}' with UID {host.data.docker_uid} and GID {host.data.docker_gid}",
        user=host.data.docker_user,
        uid=host.data.docker_uid,
        groups=["docker"],
        create_home=True,
        _sudo=True
    )
    docker.network(
        name="Create macvlan network",
        network="macvlan",
        driver="macvlan",
        subnet=host.data.macvlan_network.subnet,
        gateway=host.data.macvlan_network.gateway,
        ip_range=host.data.macvlan_network.ip_range,
        opts=host.data.macvlan_network.opts,
    )
