from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume, TemplateFile

apps = [
    ComposeApp(
        name="technitium-dns",
        image="technitium/dns-server",
        version="15.4.0",
        volumes=[
            NamedVolume(name="technitium-dns-config", mount_path="/etc/dns", external=True),
            NamedVolume(name="technitium-dns-logs", mount_path="/var/log/technitium/dns"),
            BindMount(source="technitium-dns/secrets", mount_path="/run/secrets", read_only=True),
        ],
        templates=[
            TemplateFile(src="ADMIN_PASSWORD", dest="technitium-dns/secrets/ADMIN_PASSWORD"),
            TemplateFile(src="SSO_CLIENT_SECRET", dest="technitium-dns/secrets/SSO_CLIENT_SECRET"),
        ],
    ),
]
