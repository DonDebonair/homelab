from pyinfra.api import deploy
from pyinfra.operations import apt, files, postgres, server

from deploys.postgres_lxc.postgres.secrets import postgres_password

@deploy("Setup PostgreSQL")
def setup_postgres():
    apt.packages(
        name="Install PostgreSQL server",
        packages=["postgresql", "postgresql-contrib"],
        _sudo=True,
    )
    postgres.role(
        name="Set password for postgres user",
        role="postgres",
        password=str(postgres_password),
        psql_user="postgres",
        _sudo=True,
        _sudo_user="postgres",
    )
    pg_hba_changed = files.replace(
        name="Allow password authentication on current subnet",
        path="/etc/postgresql/17/main/pg_hba.conf",
        text=r"host\s*all\s*all\s*127.0.0.1/32\s*scram-sha-256",
        replace="host    all             all             192.168.0.0/16          scram-sha-256",
        _sudo=True,
    )
    postgresql_conf_changed = files.replace(
        name="Listen on all interfaces",
        path="/etc/postgresql/17/main/postgresql.conf",
        text=r"#listen_addresses = 'localhost'",
        replace="listen_addresses = '*'",
        _sudo=True,
    )
    server.service(
        name="Restart PostgreSQL service",
        service="postgresql",
        running=True,
        restarted=True,
        _if=lambda: pg_hba_changed.did_change() or postgresql_conf_changed.did_change(),
        _sudo=True,
    )
