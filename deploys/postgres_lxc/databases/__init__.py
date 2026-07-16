from pyinfra.api import deploy
from pyinfra.operations import postgres

from deploys.postgres_lxc.databases.vars import databases


@deploy("Setup PostgreSQL databases and users")
def databases_and_users():
    create_users()
    create_databases()
    create_extensions()


def create_users():
    for db in databases:
        postgres.role(
            name=f"Create postgres user {db.user}",
            role=db.user,
            password=db.password,
            psql_user="postgres",
            _sudo=True,
            _sudo_user="postgres",
        )


def create_databases():
    for db in databases:
        postgres.database(
            name=f"Create database {db.name}",
            database=db.name,
            owner=db.user,
            psql_user="postgres",
            _sudo=True,
            _sudo_user="postgres",
        )


def create_extensions():
    for db in databases:
        for extension in db.extensions:
            # postgres.sql is not idempotent, so this reports a change on every run even
            # though IF NOT EXISTS makes it a server-side no-op. Living with the noise beats
            # adding a custom fact + operation (and its harness cases) for one statement.
            postgres.sql(
                name=f"Create extension {extension} in database {db.name}",
                sql=f'CREATE EXTENSION IF NOT EXISTS "{extension}"',
                psql_user="postgres",
                psql_database=db.name,
                _sudo=True,
                _sudo_user="postgres",
            )
