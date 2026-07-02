from deploys.common.docker_compose.models import ComposeApp

apps = [
    # cAdvisor for the handful of Docker containers still running on the NAS.
    # It publishes a host port (see cadvisor.yaml.j2) so the docker_vm Prometheus
    # can scrape it over the LAN. Version matches the docker_vm cadvisor.
    ComposeApp(
        name="cadvisor",
        image="gcr.io/cadvisor/cadvisor",
        version="v0.55.1",
    ),
]
