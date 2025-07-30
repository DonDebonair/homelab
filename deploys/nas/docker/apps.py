from deploys.docker_compose.models import ComposeApp, DockerVolume, TemplateFile

apps = [
    ComposeApp(
        name="loki",
        volumes=[
            DockerVolume(directory="loki/config"),
            DockerVolume(directory="loki/data"),
            DockerVolume(directory="loki/rules"),
        ],
        templates=[
            TemplateFile(src="loki-config.yaml", dest="loki/config/loki-configzzz.yaml"),
        ]
    )
]