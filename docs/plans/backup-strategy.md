# Plan: Backup strategy review — PBS chain vs. logical (Portabase-style) backups

**Status:** design / discussion doc. Nothing here is locked or implemented yet. Written
2026-07-27 from a review of the current setup against [Portabase](https://portabase.io/docs)
as an alternative. Read the *Recommendation* and *Open questions* sections before starting
implementation.

## Context: the current setup

1. **PBS** runs as a VM (`pbs_vm`, `192.168.1.51`) — see `deploys/pbs_vm/`.
2. PVE runs a nightly `vzdump` job (`deploys/proxmox_host/backups/`) backing up the
   **postgres_lxc** and the **docker_vm** to the PBS datastore, which lives on a **Synology
   iSCSI LUN** (`deploys/pbs_vm/datastore/`, CHAP-authenticated).
   Schedule/retention from `group_data/proxmox_host.py`:
   `backup_schedule = "02:00"`, `backup_mode = "snapshot"`,
   `backup_prune = "keep-last=3,keep-daily=7,keep-weekly=4,keep-monthly=2"`.
3. Synology Hyper Backup copies the **LUN → a local directory on the same NAS**.
4. Synology Hyper Backup copies that **directory → Backblaze B2**.

What's being protected: **11 Postgres databases** (`deploys/postgres_lxc/databases/vars.py`)
and **~39 external named Docker volumes** (`deploys/docker_vm/apps/apps.py`), plus whatever
lives on the NFS shares (`ENTERTAINMENT_NFS`, books, and per-app mounts).

## Two corrections to the premise

These materially change the comparison, so they come first.

### 1. PBS *can* already do granular restores

Both the PVE UI and `proxmox-backup-client` support **File Restore** on VM and LXC backups.
You can browse into the docker_vm's filesystem and extract a single named volume without
restoring the whole VM. So "restoring a single Docker volume isn't possible" is not accurate —
it's a few clicks, *provided you're restoring from the live PBS datastore*.

The gap that **is** real is **logical** granularity. File Restore hands you
`/var/lib/postgresql/…` as raw files, not a `pg_restore`-able dump. Getting "the vikunja
database as of Tuesday" means: restore the whole PGDATA → start it as a scratch cluster →
let it crash-recover → `pg_dump` the one database out → restore into the live cluster. That's
genuinely painful and it's the strongest argument for adding a logical layer.

### 2. The 3-2-1 claim is thinner than it looks

- **3 copies:** ✓ — production + PBS datastore + staging dir + B2 = 4, actually.
- **2 locations:** ✓ — home + B2.
- **2 media:** ✗ — the PBS datastore LUN, the staging directory, *and* the source of the B2
  upload all live on **the same NAS, the same disk pool**. A chassis, pool, or filesystem
  loss takes out every on-site backup copy at once and leaves only B2 — the slowest copy,
  and (see below) the one you can't verify. The Proxmox host's disks hold production only.

Effectively it's 3-2-1 with a "2" of about 1.2.

Also: **step 3 is not an independent copy.** LUN → directory on the same disks is a
format-conversion workaround (so Hyper Backup can reach a cloud target), at the cost of
double the space and zero additional resilience.

## Current setup: pros and cons

### Pros

- **Dedup + incremental.** Only changed 4 MB chunks move. Nightly backups of the docker_vm
  are near-free in space and time. **Portabase has no equivalent** — this is the single
  biggest thing PBS gives that a logical-dump tool does not.
- **Verification.** PBS `verify` jobs re-hash chunks and detect bit rot. Provable integrity —
  *for the local datastore*.
- **Bare-metal recovery.** The whole machine comes back, including any state that isn't
  captured in this repo.
- **Consistency.** `vzdump` snapshot mode + qemu-guest-agent fs-freeze — the PG data
  directory is snapshot-consistent, not a hot copy of a live tree.
- **Mature.** Backup software is the one category where boring wins outright.

### Cons

- **The offsite copy is unverified and unverifiable.** *This is the biggest weakness — bigger
  than the restore complexity.* `verify` only runs against the live datastore. B2 holds a
  copy-of-a-block-image-of-a-copy, and its validity is discovered at exactly the wrong moment.
- **Block-level copy of a live LUN.** PBS is writing chunks while Hyper Backup images the LUN.
  Crash-consistent at best; chunk-store corruption is a plausible failure mode.
- **Long restore chain with hard dependencies.**
  B2 → NAS → create new LUN → iSCSI + CHAP creds → re-attach PBS → restore.
  Requires the PBS encryption key and CHAP credentials to survive independently. They're in
  1Password, which is the right answer — but it makes **1Password a single point of failure
  for the entire plan**, and that should be stated out loud rather than assumed.
- **No logical granularity** (see correction 1).
- **Steps 3 and 4 are pure tax** — 2× on-site storage for no added resilience.

## Portabase: pros and cons

Findings from the docs and the GitHub org (checked 2026-07-27):

- Apache-2.0, self-hosted control plane (Next.js + its own Postgres) + lightweight agents
  deployed next to the data. Agents push out; databases are never exposed.
- Supports PostgreSQL 12–18, MySQL/MariaDB, MongoDB, SQLite, Redis/Valkey (backup only, no
  restore), MSSQL, Firebird, and **Docker volumes**.
- **Fan-out: "the same backup to multiple destinations simultaneously"** — on-prem storage,
  S3-compatible, Google Drive/GCS.
- Cron scheduling + manual triggers. AES-GCM encryption.
- Repo maturity: `Portabase/portabase` created 2024-10-19, ~1520 stars, actively pushed.
  **`Portabase/agent` (Rust) created 2026-01-03, ~30 stars** — it replaced the archived
  Python `old-agent`. **Docker volume support is only weeks old.**

### Pros

- **Exactly the granularity that's missing.** Per-database logical dumps → restore one DB
  into the running cluster. That's the 95% case ("n8n ate its own workflows"), not the 5%
  case ("the house burned down").
- **Kills the daisy chain.** One job fans out to NFS + B2. Both destinations are
  **first-class copies**, independently restorable — not copies-of-copies.
- **Short restore path.** Pull object from B2 → `pg_restore`. No LUN, no iSCSI, no PBS.
- **Decoupled from the machine.** Doesn't care that the VM was rebuilt — which matters
  because **the VMs are already reproducible from this repo**. That's the key asymmetry:
  whole-VM imaging is worth materially less here than to someone without pyinfra.
- Fits the repo idiom cleanly: a `ComposeApp` on docker_vm + agents, Caddy-internal +
  Authelia, Postgres in postgres_lxc, secrets via `SecretString`.

### Cons

- **It's young, and the parts needed here are the youngest.** The server has ~1.5 k stars and
  real activity, but the Rust agent is ~6 months old and **Docker volume support is brand
  new**. That would be betting 39 named volumes on a feature with weeks of production
  history. Backup failures are silent by nature.
- **Full backups, every time.** No dedup, no incremental. B2 storage and egress grow linearly
  with retention × dataset. Fine for 11 smallish Postgres DBs; **do not point it at the
  entertainment share**.
- **Volume consistency is an open question.** The docs don't state whether containers are
  quiesced. A hot tar of a SQLite/LevelDB/Mongo volume can be silently inconsistent. The
  practical answer is a **mixed model** — native connectors for DB-shaped state, volume
  backup only for genuinely static data — which is more config surface and easy to get
  subtly wrong.
- **No bare-metal recovery.** Only acceptable if the repo truly reproduces the hosts. Needs an
  explicit audit for state configured through app UIs rather than pyinfra.
  (`any-sync-bundle`'s first-run `INIT` state is baked into a volume, so a volume restore
  covers it — but that's the kind of thing that has to be checked, not assumed.)
- **Chicken-and-egg.** The control plane has its own Postgres. Keep its config fully
  declarative in this repo so its DB is disposable.
- **Verification is on you.** No documented equivalent to PBS `verify`.

## The gap neither setup covers

PBS backs up the **LXC and the VM — not the NAS's own shares**. `ENTERTAINMENT_NFS`, the
books share, and any per-app NFS mounts are outside both plans. Presumably a separate Hyper
Backup job covers them — **this needs confirming**, because Paperless / BookOrbit data living
there would be among the most painful things to lose.

## Recommendation: don't replace — rebalance, and simplify PBS

Split by **recovery objective**, not by tool. These solve different problems; keep both.

### Layer 1 — granular / logical (the 95 % case)

Portabase (or an equivalent, see alternative below) covering:

- the 11 Postgres databases in `deploys/postgres_lxc/databases/vars.py`, and
- the subset of the 39 named volumes that hold irreplaceable, non-DB state,

fanned out to **NFS share on the NAS + Backblaze B2**. This is the layer that actually gets
used day to day.

### Layer 2 — disaster recovery (the 5 % case)

Keep PBS, but **delete steps 3 and 4**:

- **PBS 4.2 (April 2026) made the S3 datastore backend officially supported** (out of tech
  preview), and **Backblaze B2 is explicitly listed** as a compatible provider.
- So: add a **second datastore backed directly by B2**, and use a PBS **sync job** to push
  local → B2.

This collapses LUN → dir → cloud into one native operation, and — crucially — **makes the
offsite copy verifiable**, because `verify` runs against an S3-backed datastore. It also
shortens the DR restore: attach the B2 datastore to a fresh PBS and restore directly, with no
LUN reconstruction.

**Caveats to model before committing:**

- B2 bills Class B/C transactions, and a chunk-based datastore is a *lot* of small objects.
  **Garbage collection in particular is API-call heavy** (it enumerates the bucket).
- S3-backed datastores still need a local cache directory — plan disk on the PBS VM.
- Estimate cost against the current dataset before flipping anything.

### Also worth doing

- **Move the primary datastore off the NAS iSCSI LUN** onto storage that isn't the NAS, if a
  genuine second on-site *medium* is wanted. This is what fixes the "2" in 3-2-1.
- **Confirm NAS share coverage** (see gap section above).

### Alternative to weigh before committing to Portabase

**restic or Kopia** gets granular + multi-destination + dedup + encryption + `check`
verification, with years of production history. The `pg_dump` / volume-tar step would be
scripted here instead — a modest pyinfra deploy, well within this repo's idiom.

- Portabase's advantage: UI, scheduling, per-engine connectors, less code to own.
- restic's advantage: **it will not surprise you**, and it *does* dedup — which removes the
  single biggest technical downside of the logical-backup layer.

Given how new Portabase's volume support is, this trade deserves an explicit decision rather
than defaulting to the shinier option.

## Non-negotiable, regardless of what gets chosen

**Schedule a real restore test.** Restore one database and one volume **from the B2 copy**,
not the local one. Put a recurring reminder on it. Every argument in this document is
theoretical until that has been done once successfully.

## Open questions (resolve before implementing)

1. Is there already a Hyper Backup job covering the NAS shares to B2? What's in scope?
2. Actual dataset sizes — total PG dump size, total size of the volumes worth backing up,
   and current PBS datastore size. Needed for the B2 cost model.
3. B2 cost estimate for a PBS S3 datastore (storage + Class B/C transactions + GC) vs. the
   current Hyper Backup arrangement.
4. Portabase vs. restic/Kopia for layer 1 — decide explicitly.
5. If Portabase: does the volume backup quiesce containers? (Test, don't trust the docs.)
   Which of the 39 volumes go through volume backup vs. a native connector vs. neither?
6. Audit: what state on docker_vm / postgres_lxc is **not** reproducible from this repo?
   That set defines how much layer 2 is really carrying.
7. Where does the PBS S3 datastore's local cache live, and how big?

## Order of operations (proposed — not approved)

Deliberately sequenced so the safest, highest-value change lands first and nothing is torn
down before its replacement is proven.

1. Answer the open questions above; in particular size the data and cost the B2 options.
2. **Add** the PBS S3 datastore on B2 + sync job. Model it in `deploys/pbs_vm/datastore/` and
   `group_data/pbs_vm.py`, in keeping with the existing `operations/proxmox/pbs.py` ops.
   Leave the Hyper Backup chain running in parallel.
3. Run a `verify` against the B2 datastore, then do a **test restore from it**. Only once
   that succeeds:
4. **Retire Hyper Backup steps 3 and 4.** Reclaim the staging space.
5. Decide layer 1 (Portabase vs. restic/Kopia) and implement it on docker_vm, fanning out to
   NFS + B2. New deploy package, `ComposeApp` with a pinned `image`/`version` per
   `CLAUDE.md`, secrets via `SecretString`.
6. Test-restore one database and one volume from the B2 destination.
7. Optionally relocate the primary PBS datastore off the NAS LUN for a true second medium.
8. Set up a recurring restore-test reminder.

## References

- [Proxmox Backup Server 4.2 release](https://proxmox.com/en/about/company-details/press-releases/proxmox-backup-server-4-2)
- [PBS backup storage documentation](https://pbs.proxmox.com/docs/storage.html)
- [PBS 4.2: S3 storage exits tech preview](https://wz-it.com/en/blog/proxmox-backup-server-4-2-s3-storage-stable/)
- [Portabase docs](https://portabase.io/docs)
- [Portabase Docker volume support announcement](https://lemmy.self-hosted.site/post/424334)
