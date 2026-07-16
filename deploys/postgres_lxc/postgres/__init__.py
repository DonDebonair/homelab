from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.files import Directory
from pyinfra.operations import apt, files, postgres, server

from deploys.postgres_lxc.postgres.secrets import postgres_password

PGDG_KEYRING_DIR = "/usr/share/postgresql-common/pgdg"
PGDG_KEYRING = f"{PGDG_KEYRING_DIR}/apt.postgresql.org.asc"


@deploy("Setup PostgreSQL")
def setup_postgres():
    version = host.data.postgres_version
    config_dir = f"/etc/postgresql/{version}/main"

    files.directory(
        name="Ensure PGDG keyring directory exists",
        path=PGDG_KEYRING_DIR,
        user="root",
        group="root",
        mode="755",
        _sudo=True,
    )
    files.download(
        name="Download PGDG repository signing key",
        src="https://www.postgresql.org/media/keys/ACCC4CF8.asc",
        dest=PGDG_KEYRING,
        sha256sum="0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76",
        user="root",
        group="root",
        mode="644",
        _sudo=True,
    )
    # Debian trixie only carries PostgreSQL 17, so the major version comes from PGDG.
    add_pgdg_repo = apt.sources_file(
        name="Add PGDG repository",
        filename="pgdg",
        uris="https://apt.postgresql.org/pub/repos/apt",
        suites="trixie-pgdg",
        components="main",
        signed_by=PGDG_KEYRING,
        _sudo=True,
    )
    apt.update(
        name="Update APT package cache",
        _if=add_pgdg_repo.did_change,
        _sudo=True,
    )
    # Pin the major version explicitly: the unversioned `postgresql` metapackage tracks PGDG's
    # newest major, so it would pull the next release in on a routine apt upgrade. The contrib
    # extensions (uuid-ossp, pg_trgm, unaccent) ship inside this package.
    apt.packages(
        name=f"Install PostgreSQL {version} server",
        packages=[f"postgresql-{version}"],
        _sudo=True,
    )
    # pgvector ships outside the server package (AFFiNE's copilot module needs the `vector`
    # extension). Unlike pgcrypto it is not a *trusted* extension, so a plain database owner
    # cannot CREATE EXTENSION it -- databases/__init__.py does that as the postgres superuser.
    # Versioned to match the server: the extension is built against a specific major.
    apt.packages(
        name=f"Install pgvector for PostgreSQL {version}",
        packages=[f"postgresql-{version}-pgvector"],
        _sudo=True,
    )
    # The versioned package never creates a cluster: on Debian that is done by the unversioned
    # `postgresql` metapackage's postinst, which we deliberately don't install (see above). So
    # create it here. This only fires when bootstrapping a fresh host — on a major upgrade
    # pg_upgradecluster creates the cluster from the old one, and this no-ops.
    server.shell(
        name=f"Create the {version}/main cluster",
        commands=[f"pg_createcluster {version} main --start"],
        _if=lambda: not host.get_fact(Directory, path=config_dir),
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
        path=f"{config_dir}/pg_hba.conf",
        text=r"host\s*all\s*all\s*127.0.0.1/32\s*scram-sha-256",
        replace="host    all             all             192.168.0.0/16          scram-sha-256",
        _sudo=True,
    )
    postgresql_conf_changed = files.replace(
        name="Listen on all interfaces",
        path=f"{config_dir}/postgresql.conf",
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
