from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume, TemplateFile
from deploys.docker_vm.proxies.vars import (
    cloudflare_tunnel_id,
    CLOUDFLARE_UID,
    CLOUDFLARE_GID,
)

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
    ComposeApp(
        name="authelia",
        volumes=[
            BindMount(source="authelia/config", mount_path="/config"),
            NamedVolume(name="redis-data", mount_path="/data"),
        ],
        templates=[
            TemplateFile(src="configuration.yml", dest="authelia/config/configuration.yml"),
            TemplateFile(src="STORAGE_PASSWORD", dest="authelia/config/secrets/STORAGE_PASSWORD"),
            TemplateFile(src="REDIS_PASSWORD", dest="authelia/config/secrets/REDIS_PASSWORD"),
            TemplateFile(src="SMTP_PASSWORD", dest="authelia/config/secrets/SMTP_PASSWORD"),
            TemplateFile(src="LDAP_PASSWORD", dest="authelia/config/secrets/LDAP_PASSWORD"),
            TemplateFile(src="JWT_SECRET", dest="authelia/config/secrets/JWT_SECRET"),
            TemplateFile(src="SESSION_SECRET", dest="authelia/config/secrets/SESSION_SECRET"),
            TemplateFile(src="STORAGE_ENCRYPTION_KEY", dest="authelia/config/secrets/STORAGE_ENCRYPTION_KEY"),
            TemplateFile(src="HMAC_SECRET", dest="authelia/config/secrets/HMAC_SECRET"),
            TemplateFile(src="jwks/private.pem", dest="authelia/config/secrets/jwks/private.pem"),
            TemplateFile(src="jwks/public.pem", dest="authelia/config/secrets/jwks/public.pem"),
        ],
    ),
    ComposeApp(
        name="cloudflared",
        volumes=[
            BindMount(
                source="cloudflared",
                mount_path="/etc/cloudflared",
                uid=CLOUDFLARE_UID,
                gid=CLOUDFLARE_GID,
            ),
        ],
        templates=[
            TemplateFile(
                src="cloudflared-config.yml",
                dest="cloudflared/config.yml",
                uid=CLOUDFLARE_UID,
                gid=CLOUDFLARE_GID,
            ),
            TemplateFile(
                src="cloudflared-credentials.json",
                dest=f"cloudflared/{cloudflare_tunnel_id}.json",
                uid=CLOUDFLARE_UID,
                gid=CLOUDFLARE_GID,
            ),
        ],
    ),
]
