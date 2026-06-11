from deploys.common.docker_compose.models import ComposeApp, BindMount

DOCKER_SOCKET = BindMount(source="/var/run/docker.sock", mount_path="/var/run/docker.sock")

apps = [
    ComposeApp(
        name="dozzle",
        volumes=[DOCKER_SOCKET],
    ),
]
