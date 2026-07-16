from dataclasses import dataclass, field

from deploys.postgres_lxc.databases import secrets

@dataclass
class PostgresDBConfig:
    name: str
    user: str
    password: str
    # Extensions to create in this database, as the postgres superuser. Needed for any
    # extension that isn't `trusted` (pgvector), since the database owner can't create
    # those itself -- the app's own migration would silently skip it and run degraded.
    extensions: list[str] = field(default_factory=list)

databases = [
    PostgresDBConfig(name="authelia", user="authelia", password=str(secrets.authelia_password)),
    PostgresDBConfig(name="miniflux", user="miniflux", password=str(secrets.miniflux_password)),
    PostgresDBConfig(name="grafana", user="grafana", password=str(secrets.grafana_password)),
    PostgresDBConfig(name="forgejo", user="forgejo", password=str(secrets.forejo_password)),
    PostgresDBConfig(name="nocodb", user="nocodb", password=str(secrets.nocodb_password)),
    PostgresDBConfig(name="n8n", user="n8n", password=str(secrets.n8n_password)),
    PostgresDBConfig(name="paperless", user="paperless", password=str(secrets.paperless_password)),
    PostgresDBConfig(name="outline", user="outline", password=str(secrets.outline_password)),
    # AFFiNE's migrations CREATE EXTENSION both of these themselves, but only warn and carry on
    # when it fails -- and it does fail for `vector`, which isn't trusted and so is out of reach
    # of the `affine` role. Create both up front instead of booting a half-migrated server.
    PostgresDBConfig(
        name="affine",
        user="affine",
        password=str(secrets.affine_password),
        extensions=["vector", "pgcrypto"],
    ),
]
