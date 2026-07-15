# Debian trixie only ships PostgreSQL 17, so 18 comes from the PGDG repository that
# deploys/postgres_lxc/postgres adds.
#
# Bumping this installs the new server packages, but it does NOT migrate the data: pg_upgrade
# is a stateful one-shot that pyinfra can't express idempotently. A major upgrade is therefore:
#
#   1. back up          — vzdump the LXC to PBS, plus `pg_dumpall -f <file>` as a logical net
#   2. apply this deploy — adds the repo and installs postgresql-<new>. It fails at the
#                          files.replace ops because no cluster exists yet; that is expected,
#                          the repo and packages still land.
#   3. migrate          — `pg_upgradecluster -m upgrade <old> main`. The `-m upgrade` is not
#                          optional: pg_upgradecluster defaults to -m dump. It copies the old
#                          cluster's config over, swaps the new cluster onto 5432, and matches
#                          the old cluster's data_checksums setting (PG18+ initdb turns them on
#                          by default, and pg_upgrade refuses to run on a mismatch).
#   4. re-apply         — this deploy now converges to a clean no-op.
#   5. retire           — `pg_dropcluster --stop <old> main`, then purge postgresql-<old>.
postgres_version = 18
