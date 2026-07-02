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
    # Portainer agent so the docker_vm Portainer server can manage the handful of
    # containers still on the NAS. Publishes host port 9001; the server connects
    # in over the LAN (the two hosts route to each other) authenticated by the
    # shared AGENT_SECRET. Version matches the docker_vm portainer server.
    ComposeApp(
        name="portainer-agent",
        image="portainer/agent",
        version="2.39.4",
    ),
]
