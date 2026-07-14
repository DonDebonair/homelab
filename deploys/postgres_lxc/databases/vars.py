from dataclasses import dataclass

from deploys.postgres_lxc.databases import secrets

@dataclass
class PostgresDBConfig:
    name: str
    user: str
    password: str

databases = [
    PostgresDBConfig(name="authelia", user="authelia", password=str(secrets.authelia_password)),
    PostgresDBConfig(name="miniflux", user="miniflux", password=str(secrets.miniflux_password)),
    PostgresDBConfig(name="grafana", user="grafana", password=str(secrets.grafana_password)),
    PostgresDBConfig(name="forgejo", user="forgejo", password=str(secrets.forejo_password)),
    PostgresDBConfig(name="nocodb", user="nocodb", password=str(secrets.nocodb_password)),
    PostgresDBConfig(name="n8n", user="n8n", password=str(secrets.n8n_password)),
    PostgresDBConfig(name="paperless", user="paperless", password=str(secrets.paperless_password)),
    PostgresDBConfig(name="outline", user="outline", password=str(secrets.outline_password)),
]
