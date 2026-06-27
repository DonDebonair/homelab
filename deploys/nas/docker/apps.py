from deploys.common.docker_compose.models import ComposeApp, BindMount, TemplateFile

apps = [
    ComposeApp(
        name="loki",
        image="grafana/loki",
        version="3.1.0",
        volumes=[
            BindMount(source="loki/config", mount_path="/etc/loki"),
            BindMount(source="loki/data", mount_path="/loki/chunks"),
            BindMount(source="loki/rules", mount_path="/loki/rules"),
        ],
        templates=[
            TemplateFile(src="loki-config.yaml", dest="loki/config/loki-config.yaml"),
        ]
    )
]
