from pyinfra.api import deploy
from pyinfra.operations import postgres

from deploys.postgres_lxc.databases.vars import databases


@deploy("Setup PostgreSQL databases and users")
def databases_and_users():
    create_users()
    create_databases()


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
