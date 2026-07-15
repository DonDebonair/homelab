# Debian trixie only ships PostgreSQL 17, so 18 comes from the PGDG repository that
# deploys/postgres_lxc/postgres adds. Bumping this installs the new server packages, but it
# does NOT migrate the data: pg_upgrade is a stateful one-shot that pyinfra can't express
# idempotently. See docs/plans/postgres-18-upgrade.md for the procedure.
postgres_version = 18
