# PostgreSQL 17 → 18 upgrade (postgres_lxc)

## Starting state (verified on 192.168.1.41, 2026-07-15)

- Debian 13 (trixie), PostgreSQL **17.10** from **Debian's own repos** — no PGDG configured.
- Cluster `17/main`, port 5432, data dir `/var/lib/postgresql/17/main`.
- Root disk `vm-pool:8` — 8 GB total, **6.2 GB free**. Total DB data **~825 MB**
  (miniflux 621 MB, forgejo 89 MB, paperless 33 MB, outline 21 MB, grafana 16 MB,
  nocodb 15 MB, n8n 13 MB, authelia 12 MB). Space is a non-issue.
- Extensions in use: `plpgsql`, `uuid-ossp`, `unaccent`, `pg_trgm` — all stock, all ship
  inside the `postgresql-18` package. No third-party extensions.
- `data_checksums = off`.
- 8 consumer apps on `docker_vm` connect over the LAN to `192.168.1.41:5432`.

## Key findings that shape the plan

1. **PG18 is not in trixie.** Debian trixie ships PG17 only. PG18 requires the PGDG repo
   (`apt.postgresql.org`, suite `trixie-pgdg`), which currently has `postgresql-18` at
   `18.4-1.pgdg13+1`. Without PGDG, `apt.packages(["postgresql"])` can never yield 18.

2. **The PG18 checksum trap is handled for us.** PG18's `initdb` enables data checksums by
   default, and `pg_upgrade` refuses to run when old/new checksum settings differ. Debian's
   `pg_upgradecluster` (postgresql-common 278) already handles this — `/usr/bin/pg_upgradecluster`
   lines 568-574 pass `--no-data-checksums` when the old cluster has them off and the method is
   `upgrade`. Nothing to do manually; just don't hand-roll `pg_upgrade`.

3. **`pg_upgradecluster` defaults to `--method=dump`**, not `upgrade` (line 410:
   `my $method = 'dump';`). Must pass `-m upgrade` explicitly.

4. **Config is migrated automatically.** `pg_upgradecluster` copies the old cluster's
   `postgresql.conf` / `pg_hba.conf` to the new cluster ("Copying old configuration files...",
   line 253). The `listen_addresses = '*'` and the `192.168.0.0/16 scram-sha-256` pg_hba line
   carry over — so the pyinfra `files.replace` ops become no-ops on the new paths, which is correct.

5. **Ports swap automatically.** Lines 829-833: the new cluster takes the old cluster's port
   (5432) and the old cluster is moved to a free port. Apps need no reconfiguration.

6. **`postgresql-contrib` is a phantom.** It has *no candidate* on trixie — it's a virtual
   package provided by the `postgresql` metapackage, so the current
   `apt.packages(["postgresql", "postgresql-contrib"])` silently resolves to just `postgresql`.
   PGDG's `postgresql-18` declares `Provides: postgresql-contrib-18`, and the contrib
   extensions (`uuid-ossp`, `pg_trgm`, `unaccent`) ship inside it. Drop `postgresql-contrib`.

7. **Don't install the unversioned `postgresql` metapackage once PGDG is enabled.** PGDG's
   `postgresql` depends on `postgresql-18` today and will depend on `postgresql-19` when PG19
   releases (~Sept 2026), which would pull a second major version in on a routine `apt upgrade`.
   Pin `postgresql-18` explicitly. (`unattended-upgrades` is installed on this LXC by
   `common_debian_setup`, but its default origins only cover Debian security, not PGDG.)

8. **There are no PostgreSQL-level backups** — only crash-consistent `vzdump` of the whole LXC
   to PBS (`pve-to-pbs`, vmid 100, daily 02:00). Take a fresh vzdump *and* a logical dump first.

9. **The versioned package doesn't create a cluster — the metapackage does.** Confirmed the
   hard way: `postgresql-18.postinst` contains no `pg_createcluster` call at all. Cluster
   creation lives in the unversioned `postgresql` metapackage's postinst, which also carries a
   `try_upgrade` routine that auto-runs `pg_upgradecluster` via debconf when it sees an older
   main cluster. That implicit auto-upgrade is a second good reason to pin the versioned
   package (finding 7) — but it means the deploy must create the cluster itself, or a
   from-scratch rebuild installs PG18 and never gets a `18/main`.

## Upgrade procedure

The repo, the keyring and the package pin are declarative steady state, so pyinfra owns them.
The *data migration* is not: `pg_upgrade` is a stateful, ordering-sensitive one-shot that can't
be expressed idempotently. So pyinfra installs PG18, the migration is run by hand, and pyinfra
then converges on the result.

### 0. Back up

From the Proxmox host — on-demand snapshot of the LXC to PBS:

```bash
ssh 192.168.1.22
sudo vzdump 100 --storage pbs --mode snapshot --notes-template 'pre-pg18-upgrade'
```

On the LXC — a logical safety net independent of the VM image:

```bash
ssh 192.168.1.41
sudo -u postgres pg_dumpall --clean --if-exists -f /var/lib/postgresql/pre-pg18-dumpall.sql
ls -lh /var/lib/postgresql/pre-pg18-dumpall.sql
```

### 1. Add the PGDG repo and install PG18 — via pyinfra

The repo and the package pin are ordinary declarative state, so they live in the code (see
[Code changes](#code-changes)), not in hand-run `curl`/`tee`. Apply them first:

```bash
uv run pyinfra inventory.py deploy.py --limit postgres_lxc --dry
uv run pyinfra inventory.py deploy.py --limit postgres_lxc -y
```

This adds `/etc/apt/sources.list.d/pgdg.sources` + the sha256-pinned keyring, refreshes the
apt cache, and installs `postgresql-18`.

Verified dry-run output (2026-07-15) — `Add PGDG repository` and `Install PostgreSQL 18 server`
under *Change*, `Update APT package cache` under *Conditional Change* (correctly gated on the
repo's `did_change`). The two `files.replace` ops also show as *Change*: they target
`/etc/postgresql/18/main/*`, which doesn't exist yet at plan time, so pyinfra assumes a change.
The real (`-y`) run installs the package first, so the paths exist by the time they run.

**This run stops with an error, and that is expected on the upgrade path:**

```
--> Starting operation: Setup PostgreSQL | Allow password authentication on current subnet
    [192.168.1.41]  sed: can't read /etc/postgresql/18/main/pg_hba.conf: No such file or directory
```

Installing `postgresql-18` does **not** create a cluster (see finding 9), so there is no
`/etc/postgresql/18/main` for the `files.replace` ops to edit until step 2 makes one. The
`pg_createcluster` op in the deploy is `_if`-gated on that directory and is only for
bootstrapping a fresh host — on this host it must *not* fire, because an existing `18/main`
would make `pg_upgradecluster` refuse to run.

Everything before the error succeeded, which is the part we needed: the PGDG repo, the keyring
and `postgresql-18` are installed, and `17/main` is untouched and still serving. Confirm, then
continue to step 2:

```bash
ssh 192.168.1.41
apt-cache policy postgresql-18   # 18.4-1.pgdg13+1, Installed
pg_lsclusters                    # only 17/main online 5432 — no 18/main
```

> **Do not re-run pyinfra before step 2.** With PG18 installed and no `18/main`, the
> `pg_createcluster` op *would* fire and create an empty cluster, which blocks
> `pg_upgradecluster`. (If that happens: `sudo pg_dropcluster --stop 18 main`.)

### 2. Run the upgrade

```bash
sudo pg_upgradecluster -m upgrade 17 main
```

This stops `17/main`, creates `18/main` with matching (disabled) checksums, copies the old
config across, runs `pg_upgrade`, swaps `18/main` onto port 5432, and starts it.
Expect a couple of minutes at this data size. Old cluster stays intact on a spare port for
rollback — don't use `--link`, the speed gain is meaningless at 825 MB and it destroys that
rollback path.

### 3. Verify

```bash
pg_lsclusters                                    # 18/main online 5432; 17/main down
sudo -u postgres psql -c 'SELECT version()'
sudo -u postgres psql -c '\l'
for db in authelia miniflux grafana forgejo nocodb n8n paperless outline; do
  echo "-- $db"; sudo -u postgres psql -d "$db" -tAc \
    "SELECT extname||' '||extversion FROM pg_extension"
done
```

Refresh planner statistics (PG18's `pg_upgrade` carries most stats over, but this is cheap):

```bash
sudo -u postgres vacuumdb --all --analyze-in-stages
```

### 4. Restart the consumer apps

The 8 apps on `docker_vm` dropped their connections when `17/main` stopped. Most reconnect on
their own; restart any that are stuck.

### 5. Retire PG17 (only once the apps are confirmed healthy)

Leave this for a day or so — the old cluster is the fastest rollback.

```bash
sudo pg_dropcluster --stop 17 main
sudo apt-get purge -y postgresql-17 postgresql-client-17
sudo apt-get autoremove --purge -y
sudo rm -f /var/lib/postgresql/pre-pg18-dumpall.sql
```

Purging `postgresql-17` also removes Debian's `postgresql` metapackage (it depends on it),
which is what we want per finding 7.

### 6. Converge pyinfra

```bash
uv run pyinfra inventory.py deploy.py --limit postgres_lxc --dry
```

Should report no changes against the hand-upgraded host — that no-op is the sign the code and
the machine agree.

## Code changes

- **`group_data/postgres_lxc.py`** (new) — `postgres_version = 18`. This group had no
  group_data file at all; the version was previously implicit in the distro default.
- **`deploys/postgres_lxc/postgres/__init__.py`** —
  - add the PGDG keyring (`files.download`, sha256-pinned) + repo (`apt.sources_file`) +
    guarded `apt.update`, mirroring the `deploys/proxmox_host/prepare` pattern;
  - pin `packages=[f"postgresql-{version}"]`, dropping the phantom `postgresql-contrib`
    and the unversioned `postgresql` metapackage;
  - add a `pg_createcluster` op gated on `_if=lambda: not host.get_fact(Directory, ...)`,
    which replaces the cluster creation the dropped metapackage used to do (finding 9).
    `_if` callables are only evaluated when `state.is_executing`
    (`pyinfra/api/operation.py:327-332`), so the fact is read *after* apt has installed the
    package in the same run — which is what makes the fresh-host bootstrap work;
  - derive both `files.replace` paths from `host.data.postgres_version` instead of
    hardcoding `17`.

## Rollback

Before step 7, rollback is: `sudo pg_dropcluster --stop 18 main` then
`sudo pg_ctlcluster 17 main start` after resetting its port to 5432
(`sudo pg_conftool 17 main set port 5432`). After step 7, restore the vzdump from PBS.
