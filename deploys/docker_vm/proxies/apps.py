from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume

DOCKER_SOCKET = BindMount(source="/var/run/docker.sock", mount_path="/var/run/docker.sock")

apps = [
    ComposeApp(
        name="caddy-internal",
        volumes=[
            DOCKER_SOCKET,
            NamedVolume(name="caddy-internal-data", mount_path="/data", external=True),
        ],
    ),
    ComposeApp(
        name="caddy-external",
        volumes=[
            DOCKER_SOCKET,
            NamedVolume(name="caddy-external-data", mount_path="/data", external=True),
        ],
    ),
]
