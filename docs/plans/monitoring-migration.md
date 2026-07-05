# Monitoring stack migration (NAS/Ansible → docker_vm/pyinfra)

Moves the monitoring stack off the Synology NAS (Ansible role `roles/monitoring/`
+ Loki bits in `roles/docker-setup/`) onto the `docker_vm` host under pyinfra,
following the established docker-apps migration pattern (`deploys/docker_vm/apps/`).

## Scope

- **Prometheus TSDB + Loki chunks: NOT migrated** — start clean. But the data
  collected from here on is considered important, so `prometheus-data` /
  `loki-data` are `external=True` named volumes (survive `docker compose down -v`).
- **Grafana data: migrated** — dump/restore the `grafana` PostgreSQL database
  (dashboards, users, datasources, etc. live there since `GF_DATABASE_TYPE=postgres`).
  The `/var/lib/grafana` volume holds only plugins/renders and is *not* migrated.
- **Loki logging: replicated** — `loki-docker-driver` plugin set as the docker
  daemon's default log driver so every container ships logs to the new Loki.
- **Exporters: ported as-is, retargeted locally** — node-exporter + cAdvisor now
  observe `docker_vm`; snmp-exporter keeps polling the Synology over SNMPv3.
- **Grafana bumped** 11.1.1 → 13.1.0 (schema auto-migrates on first start).

## What was built

New package `deploys/docker_vm/monitoring/`:

- `monitoring.py` — three `ComposeApp`s: `loki`, `prometheus` (with sidecars
  node-exporter / snmp-exporter / cadvisor, pinned inline), `grafana`.
- `secrets.py` — `SecretString`s (see **1Password prep** below).
- `templates/` — `loki.yaml.j2`, `prometheus.yaml.j2`, `grafana.yaml.j2` (compose),
  `loki-config.yaml.j2`, `prometheus-config.yml.j2`, `snmp.yml.j2` (rendered config
  files), `daemon.json.j2` (docker daemon log-driver config).
- `__init__.py` — `setup_monitoring()` (creates the `monitoring` network then
  composes the apps) and `setup_loki_log_driver()` (plugin + daemon.json + restart).

Wiring:
- `group_data/docker_vm.py` — `monitoring_network` (`172.105.0.0/16`) + `loki_ip`
  (`172.105.0.100`, the fixed IP Loki binds so the daemon log driver can reach it).
- `deploy.py` — `setup_monitoring()` then `setup_loki_log_driver()` in the
  `docker_vm` block (driver flip runs *after* Loki is up).

Already in place (no work): `grafana` DB+user on `postgres_lxc`
(`deploys/postgres_lxc/databases/`), Grafana Authelia OIDC client
(`deploys/docker_vm/proxies/vars.py`).

Image versions pinned: grafana 13.1.0, loki 3.7.3, loki-docker-driver 3.7.2-amd64,
prometheus v3.12.0, node-exporter v1.11.1, snmp-exporter v0.30.1, cadvisor v0.55.1.

## Migration sequence (end-to-end)

Run top to bottom **from the Mac**, with the repo checkout as the working dir and
`OP_SERVICE_ACCOUNT_TOKEN` exported. Hosts: NAS = `nas.dv.zone`, docker_vm =
`daan@192.168.50.10`, postgres_lxc = `192.168.1.41`. The DB move mirrors the Forgejo
runbook (`docs/plans/forgejo-migration.md`): every `ssh` hop originates on the Mac
(the NAS never reaches the postgres_lxc) and the restore borrows `pg_restore` from a
throwaway `postgres:17` container, so no Postgres client tools are needed locally.

Known NAS Postgres gotchas baked into the commands below: **no `docker exec -t`** for
`-Fc` dumps (a docker TTY translates `\n`→`\r\n` in the binary stream → empty TOC,
restore loads 0 rows and exits clean); **DSM ssh has no `docker` on PATH** (wrap
NAS-side docker in `bash -lc "..."`); **don't stream the dump over stdin** (a short
read truncates it silently → empty DB, no error) — transfer it as a file, restore
from a mount.

### Step 0 — Create the 1Password items

`deploys/docker_vm/monitoring/secrets.py` resolves these at import, so the deploy in
Step 2 fails fast at `populate_cache_sync()` if any are missing. Create them first:

| op:// reference | value |
|---|---|
| `op://Homelab/PostgreSQL Grafana user/password` | already exists (no action) |
| `op://Homelab/Grafana OIDC client/password` | exists — plaintext must match the `grafana` client `secret_hash` in `proxies/vars.py`. If they don't match, regenerate both: `authelia crypto hash generate pbkdf2 --variant sha512 --random` → plaintext in 1Password, hash in `proxies/vars.py`. |
| `op://Homelab/Synology SNMP/username` | exists — SNMPv3 username (field id `username`; its display label is "rouser", but the op SDK resolves by id) |
| `op://Homelab/Synology SNMP/password` | exists — SNMPv3 auth password |
| `op://Homelab/Synology SNMP/SNMP privacy password` | exists — SNMPv3 privacy password |

All items above already exist. The `grafana` DB/user (on postgres_lxc) and the Grafana
Authelia OIDC client are also already provisioned — no action.

### Step 1 — Quiesce + dump the Grafana DB on the NAS

```bash
# Stop Grafana so the DB is a consistent snapshot (brief downtime; DNS stays on the NAS).
ssh nas.dv.zone 'sudo bash -lc "docker stop grafana"'

# Dump the `grafana` DB (container `postgres`) to a FILE on the NAS, then verify the
# TOC has TABLE DATA entries (> 0) BEFORE continuing -- the postgres container has pg_restore:
ssh nas.dv.zone 'sudo bash -lc "docker exec postgres pg_dump -U grafana -Fc grafana > /volume2/docker/grafana-db.dump \
  && docker cp /volume2/docker/grafana-db.dump postgres:/tmp/d.dump \
  && docker exec postgres pg_restore -l /tmp/d.dump | grep -ci \"TABLE DATA\""'

# Pull the dump to the Mac as a FILE.
ssh nas.dv.zone 'sudo bash -lc "cat /volume2/docker/grafana-db.dump"' > grafana-db.dump
ls -l grafana-db.dump   # sanity: not ~5 MB / 0 bytes
```

### Step 2 — Deploy the new stack, then stop Grafana

```bash
# Creates the monitoring network + external volumes, deploys loki/prometheus/grafana,
# and (after Loki is up) flips the docker daemon's default log driver to Loki.
uv run pyinfra inventory.py --limit docker_vm deploy.py

# Stop Grafana so it doesn't write to the DB mid-restore.
ssh daan@192.168.50.10 'docker stop grafana'
```

**After the deploy flips the default log driver to Loki, recreate the existing
containers once.** A container's log driver is fixed at *creation*, not on restart —
the daemon restart that the flip triggers does NOT move already-running containers
onto Loki (they stay `json-file`, so Loki stays empty). Recreate every stack once
(`docker info --format '{{.LoggingDriver}}'` should already read `loki`):

```bash
ssh daan@192.168.50.10 'for d in /srv/docker/compose/*/; do \
  docker compose --project-directory "$d" -p "$(basename "$d")" up -d --force-recreate; done'
# verify: every container now shows loki
ssh daan@192.168.50.10 "docker ps --format '{{.Names}}' | while read n; do \
  printf '%-18s %s\n' \"\$n\" \"\$(docker inspect -f '{{.HostConfig.LogConfig.Type}}' \$n)\"; done"
```

(One-time: future deploys create new containers with the `loki` default already. A
later option is to set `logging: driver: loki` per service so it's explicit and not
dependent on creation order.) Brief blip for caddy/authelia/dns during recreate.

### Step 3 — Transfer + restore the DB into postgres_lxc

```bash
# Hand the dump to the docker_vm as a FILE (never stream the archive into the restore).
ssh daan@192.168.50.10 'cat > ~/grafana-db.dump' < grafana-db.dump
ssh daan@192.168.50.10 'ls -l ~/grafana-db.dump'   # size MUST equal the local file

# Restore into the already-provisioned (empty) `grafana` DB using pg_restore from a
# throwaway postgres:17 container (reaches the LXC over the LAN). --clean --if-exists
# keeps it re-runnable.
PW=$(op read "op://Homelab/PostgreSQL Grafana user/password")   # on the Mac
ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD \
  -v ~/grafana-db.dump:/dump:ro postgres:17 \
  pg_restore -h 192.168.1.41 -U grafana -d grafana --clean --if-exists --no-owner --verbose /dump"
# $PW expands on the Mac; the literal single quotes reach the docker_vm shell so a
# password with shell metacharacters stays intact (assumes no single quote in it).
# NAS runs Postgres 14, so postgres:17 pg_restore reads the dump fine. If it errors
# "unsupported version ... in file header", bump the tag to match the NAS
# (ssh nas.dv.zone 'sudo bash -lc "docker exec postgres postgres --version"').
```

### Step 4 — Start Grafana + sanity-check the restore

```bash
ssh daan@192.168.50.10 'docker start grafana'
ssh daan@192.168.50.10 'docker logs -f grafana'   # clean startup + "HTTP Server Listen"

# Confirm rows landed (from the Mac, via the throwaway container):
ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD postgres:17 \
  psql -h 192.168.1.41 -U grafana -d grafana -c 'SELECT count(*) FROM dashboard;'"
```

**Known startup failure (cross-version schema bug) — what actually worked (2026-06-29).**
Migrating from the NAS's 11.1.1 to 13.1.0 hits Grafana issue #100709: the beta-era
`cloud_migration*` tables (from the "migrate to Grafana Cloud" assistant — no
dashboards/users/datasources in them, all empty and disposable) have a half-applied
schema, so the `copy <table> v1 to v2` migrations abort startup, e.g.
`copy cloud_migration_snapshot v1 to v2 → column "result"/"uid" does not exist`.

Two traps that wasted time, avoid them:
- **`docker stop grafana` first.** The container is `restart: unless-stopped`, so a
  crashing Grafana restart-loops and **recreates the tables + `migration_log` rows
  between your DB edit and your verify** (symptom: `DELETE 5` yet the verify still
  shows 5). Confirm `docker ps -a --filter name=^/grafana$` shows `Exited` and stays
  that way before any DB surgery.
- **The drop-all-tables + clear-`migration_log` "reset" does NOT fix this** — the
  rework is half-recorded (`create … v2` and the rename are in `migration_log`, the
  `copy …` is not), so a rebuild just reproduces the same broken intermediate and
  fails again on the next table. Don't go down that path.

**What worked — patch each `*_tmp_qwerty` (old v1) table to have the columns its copy
SELECTs, then restart; repeat per failing table.** The copy moves 0 rows (everything
is empty), so it just needs the columns to *exist*, with types matching the v2 table
so the 0-row INSERT…SELECT type-checks. For each failure, read the failing `sql=…` in
the log to see which columns the SELECT reads, compare `\d <table>_tmp_qwerty` to
`\d <table>` (the v2 table), and `ADD COLUMN IF NOT EXISTS` the missing ones. With
Grafana **stopped**:

```bash
# session copy needed region_slug/cluster_slug/uid/stack_id on the tmp table:
ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD postgres:17 \
  psql -h 192.168.1.41 -U grafana -d grafana -v ON_ERROR_STOP=1 \
  -c 'ALTER TABLE cloud_migration_session_tmp_qwerty \
        ADD COLUMN IF NOT EXISTS region_slug text, ADD COLUMN IF NOT EXISTS cluster_slug text, \
        ADD COLUMN IF NOT EXISTS uid varchar(40), ADD COLUMN IF NOT EXISTS stack_id bigint;'"

# start, watch; snapshot copy then needed uid on its tmp table:
ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD postgres:17 \
  psql -h 192.168.1.41 -U grafana -d grafana -v ON_ERROR_STOP=1 \
  -c 'ALTER TABLE cloud_migration_snapshot_tmp_qwerty ADD COLUMN IF NOT EXISTS uid varchar(40);'"

# docker start grafana between each; once the copies pass, the chain completes
# ("migrations completed performed=N", then "HTTP Server Listen") and Grafana boots.
```

(The exact missing columns may differ on a re-run; always read the log's `sql=…` and
diff the two `\d` outputs rather than copy these verbatim.)

### Step 4b — Re-import dashboards (Grafana 13 unified storage)

**The DB restore does NOT bring dashboards/folders across.** Grafana 13.1 serves
dashboards from *unified storage* (the `resource` table, "mode 5"), but `pg_restore`
loads them into the legacy `dashboard` table — which mode 5 ignores. After login the
UI shows **no dashboards** even though `SELECT count(*) FROM dashboard` is non-zero
and `SELECT count(*) FROM resource WHERE resource='dashboards'` is 0. (Users,
datasources, org, prefs live in legacy tables that *are* still read, so those migrate
fine — only dashboards/folders/playlists need this.)

Fix: re-import each dashboard *through Grafana* so it gets written to unified storage.
Pull the JSON from the legacy table and import via the UI (Dashboards → New → Import →
paste the JSON model → pick a folder → Import), or POST to the API:

```bash
# Export every dashboard's JSON model from the legacy table:
ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD postgres:17 \
  psql -h 192.168.1.41 -U grafana -d grafana -At \
  -c \"SELECT id FROM dashboard WHERE is_folder = false AND deleted IS NULL;\"" \
| while read id; do
    ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD postgres:17 \
      psql -h 192.168.1.41 -U grafana -d grafana -At \
      -c \"SELECT data FROM dashboard WHERE id=$id;\"" > "dash-$id.json"
  done
# Then import each via the UI, or via API with an Admin service-account token:
#   jq -c '{dashboard: (.+{id:null}), overwrite:false}' dash-N.json \
#     | curl -sS -X POST https://grafana.dv.zone/api/dashboards/db \
#         -H "Authorization: Bearer $SA" -H 'Content-Type: application/json' --data @-
```

Re-create any folders first (folders are `dashboard` rows with `is_folder=true`) so the
imports can target them; if there are none, everything lands in General. The orphaned
legacy `dashboard` rows are harmless — mode 5 never reads them.

### Step 5 — Verify the stack (before cutting DNS)

1. `docker ps` on docker_vm: loki, prometheus, node-exporter, snmp-exporter,
   cadvisor, grafana all healthy. Re-running the Step 2 deploy is idempotent (no
   spurious docker restart — `daemon.json` unchanged).
2. `prometheus.dv.zone` → Status ▸ Targets: `prometheus`, `nodeexporter`, `snmp`
   (the NAS, `192.168.1.21`), `cadvisor` all `UP` (page is gated by Authelia).
3. `grafana.dv.zone` → Authelia OIDC auto-login works; migrated dashboards/users
   present; Prometheus + Loki datasources test green (Explore returns data).
   - **OAuth login needs the `groups` claim in the ID token.** Authelia 4.39+ drops
     non-standard claims from the ID token by default, so Grafana's
     `role_attribute_path` (`contains(groups,'administrators')`) resolves to Viewer and
     the org-role sync aborts with `cannot remove last organization admin` — login
     fails. Fixed by the `default` claims policy on the `grafana` client
     (`proxies/templates/configuration.yml.j2` + `claims_policy` in `proxies/vars.py`).
     Authelia does NOT hot-reload its config, so after deploying run
     `ssh daan@192.168.50.10 'docker restart authelia'`.
4. Logs reach Loki: in Grafana Explore (Loki source) query e.g.
   `{container_name="grafana"}` → recent lines. (With the Loki driver as default,
   `docker logs` / Dozzle no longer show container logs — logs live only in Loki.
   This matches the NAS behaviour.)

### Step 6 — Cut over DNS

Point `grafana.dv.zone` and `prometheus.dv.zone` → `192.168.50.20` (caddy-internal)
in Technitium. Re-verify both load through the proxy.

### Step 7 — Decommission (later cleanup commit)

Remove `roles/monitoring/`, the Loki bits in `roles/docker-setup/`, and the NAS
`dockerd.json` log-driver override, then drop the stale NAS containers/volumes.

## Risks / follow-ups

- **snmp_exporter config compatibility:** `snmp.j2` is the NAS-generated config
  (auths/modules format). If snmp-exporter v0.30.1 rejects it, regenerate with the
  matching `generator`, or pin an older snmp-exporter. The 79 KB module block is
  Synology-specific and was copied verbatim.
- **node-exporter scope:** ✅ reports true host metrics (fixed 2026-07-05). Runs
  with `pid: host`, `network_mode: host`, a `/:/host:ro,rslave` bind and
  `--path.rootfs=/host` (the upstream single-mount pattern), and node-exporter's
  **default collector set** -- the same as the apt-installed exporters on the
  other hosts, so all four report a consistent metric set (incl. `node_uname_info`,
  which the Node Exporter Full dashboard needs for its host selector). The only
  docker_vm-specific tuning is `--collector.netdev.device-exclude` +
  `--collector.netclass.ignored-devices` to drop the ~48 container `veth*`/`br-*`
  NICs host networking exposes. Host networking takes it off the monitoring
  bridge, so Prometheus scrapes it by host IP (`host.data.docker_vm_ip`) rather
  than by service name, and the scrape-config template is `restart_on_change=True`
  so Prometheus reloads on change. (The original NAS-ported `--collector.disable-defaults`
  explicit list was dropped -- it kept missing collectors the dashboard expected.)
- **Loki volume ownership:** if Loki logs permission errors writing `/loki/chunks`
  on first start, `chown` the fresh `loki-data` volume to the image's loki uid.
- **Dozzle:** redundant once logs live in Loki; either drop it or override its
  service back to the `json-file` log driver if you still want `docker logs`.
