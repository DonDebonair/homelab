# Plan: any-sync-bundle (self-hosted Anytype sync) on docker_vm

## Context

any-sync-bundle (grishy's all-in-one packaging of Anytype's any-sync server) lets Anytype
apps sync against self-hosted infrastructure. Goal: run it on `docker_vm` using our existing
**Garage** as S3 blob storage, with a **dedicated MongoDB + Redis** in the *same* compose
file. This is a combination of the upstream
[`compose.external.yml`](https://raw.githubusercontent.com/grishy/any-sync-bundle/refs/heads/main/compose.external.yml)
(the `-minimal` bundle image + external Mongo/Redis) and
[`compose.s3.yml`](https://raw.githubusercontent.com/grishy/any-sync-bundle/refs/heads/main/compose.s3.yml)
(S3 storage), with **MinIO replaced by Garage** and the deprecated `redis-stack-server`
replaced by official Redis.

Follows the standard `ComposeApp` + per-app template pattern
([[project_docker_apps_migration]]), reusing the live Garage store
([[project_garage_deploy]]).

**Decisions locked:**
- **Image:** `ghcr.io/grishy/any-sync-bundle:1.4.3-2026-04-21-minimal` (latest release; the
  `-minimal` variant expects external Mongo/Redis).
- **Mongo/Redis:** dedicated sidecars in the same compose file — `mongo:8.0.26` (latest 8.0)
  and `redis:8.8.0` (secondary images, pinned inline).
- **S3:** Garage (`http://garage:3900`, path-style, region `garage`, bucket `anytype-data`).
- **Access scope:** internet-reachable (user's choice) — see Networking.

## Why official Redis replaces redis-stack-server (verified)

Upstream loads RedisBloom via `--loadmodule /opt/redis-stack/lib/redisbloom.so` on the
now-deprecated `redis-stack-server`. **Redis 8 merged the former Redis Stack modules into
core**, so official `redis:8.8.0` (already the repo standard — authelia/outline/affine/
paperless) ships Bloom built in. Verified empirically on the running `outline-redis`
(`redis:8.8.0`): `BF.RESERVE`/`BF.ADD`/`BF.EXISTS` all work and `MODULE LIST` shows
`bf`, `search`, `timeseries`. **So we use `redis:8.8.0` and simply drop the `--loadmodule`
flag** — every other upstream redis flag is kept.

## Networking & access (internet-reachable)

any-sync speaks **raw TCP 33010 (DRPC) + UDP 33020 (QUIC)** — not HTTP — so it cannot go
through Caddy or the Cloudflare tunnel. Instead:
- **Publish** `33010:33010` and `33020:33020/udp` on the docker_vm host.
- **Advertise** both addresses via `ANY_SYNC_BUNDLE_INIT_EXTERNAL_ADDRS`: the LAN IP
  `192.168.50.10` (home clients) **and the public hostname** `anytype-sync.dv.zone` (internet
  clients). Both are baked into `client-config.yml`, so a client tries whichever is reachable.
- **Public DNS (done, outside this repo):** a **DNS-only** (grey-cloud, not Cloudflare-proxied)
  Cloudflare record `anytype-sync.dv.zone → 84.83.143.65` (home WAN IP), plus a router
  port-forward `33010/tcp` + `33020/udp` → `192.168.50.10`.
- **Split-horizon internal DNS (done, outside this repo):** an explicit A record
  `anytype-sync.dv.zone → 192.168.50.10` on **both** Technitium instances (dns1 `192.168.50.30`
  *and* dns2 `192.168.1.210` — cluster settings sync does **not** replicate this zone record,
  so add it to each). This specific record overrides the `*.dv.zone` wildcard (which points at
  the Caddy macvlan IP `.20`, a dead end for raw TCP/UDP — see [[project_wildcard_dns_dv_zone]]).
  Effect: at home the hostname resolves straight to the docker VM (no NAT hairpin); away it
  resolves via Cloudflare to the WAN IP. Verify both agree: `dig +short anytype-sync.dv.zone`
  → `192.168.50.10` on-LAN. Caveat: a client using its own DoH/DoT bypasses Technitium and
  would hairpin via the public IP even at home.

**S3 path:** the bundle reaches Garage container-direct at `http://garage:3900`. A bridge
container can't reach `s3.dv.zone` (macvlan .20), so the bundle joins the shared
`caddy-internal` network to resolve `garage` (same approach as prometheus→garage; Caddy
ignores it since it has no `caddy_*` labels). Mongo + Redis sit on a private `any-sync`
bridge only.

## Storage / volumes (all external named — on docker_vm NVMe)

Per [[feedback_named_volumes_external]], all state is `external=True`:
- `any-sync-mongo-data` → mongo `/data` (spaces DB / ACL — critical)
- `any-sync-redis-data` → redis `/data` (appendonly coordination state)
- `any-sync-data` → bundle `/data` (**network identity/keys + generated `client-config.yml`**
  — highest recovery cost)

All three go in `ComposeApp.volumes`; the template hand-writes each service's `volumes:`
list and ends with `[[ vol.top_level_volumes(app) ]]` (the outline/affine multi-service
pattern). Blob data itself lives in Garage, not these volumes.

## Secrets & Garage bucket

The bundle authenticates to Garage with an S3 access key. **I provision the Garage
bucket+key; you store the credentials in 1Password** (per [[feedback_user_creates_1password_items]]).

1. I run (one-time):
   ```bash
   docker exec garage /garage bucket create anytype-data
   docker exec garage /garage key create any-sync            # prints Key ID + Secret
   docker exec garage /garage bucket allow anytype-data --read --write --key any-sync
   ```
2. You create a 1Password item (Homelab vault) with the printed **Key ID** and **Secret**,
   then confirm the `op://` refs. I verify they resolve via the SDK ([[feedback_op_sdk_resolves_by_field_id]]).
3. `deploys/docker_vm/apps/secrets.py` gains (above `populate_cache_sync()`):
   ```python
   any_sync_s3_access_key = SecretString("op://Homelab/Garage any-sync key/access key id")
   any_sync_s3_secret_key = SecretString("op://Homelab/Garage any-sync key/secret access key")
   ```

## Files to create / change

1. **`deploys/docker_vm/apps/apps.py`** — add the `ComposeApp`:
   ```python
   ComposeApp(
       name="any-sync-bundle",
       image="ghcr.io/grishy/any-sync-bundle",
       version="1.4.3-2026-04-21-minimal",
       # No domain: raw TCP/UDP protocol, not proxied by Caddy.
       volumes=[
           NamedVolume(name="any-sync-mongo-data", mount_path="/data", external=True),
           NamedVolume(name="any-sync-redis-data", mount_path="/data", external=True),
           NamedVolume(name="any-sync-data", mount_path="/data", external=True),
       ],
   ),
   ```
2. **`deploys/docker_vm/apps/templates/any-sync-bundle.yaml.j2`** (NEW) — three services:
   - `mongo` (`mongo:8.0.26`, `--replSet rs0 --port 27017`, the upstream `mongosh`
     healthcheck that idempotently `rs.initiate`s `rs0`, vol `any-sync-mongo-data:/data`,
     private `any-sync` net).
   - `redis` (`redis:8.8.0`, upstream flags **minus** `--loadmodule`:
     `redis-server --port 6379 --dir /data/ --appendonly yes --maxmemory 256mb
     --maxmemory-policy noeviction --protected-mode no`, `redis-cli ping` healthcheck, vol
     `any-sync-redis-data:/data`, private net). No password — consistent with the
     outline/affine/paperless private-bridge redis sidecars.
   - `any-sync-bundle` (`[[ app.image ]]:[[ app.version ]]`, `depends_on` mongo+redis
     healthy, `ports: 33010:33010` + `33020:33020/udp`, nets `[any-sync, caddy-internal]`,
     vol `any-sync-data:/data`) with env:
     ```yaml
     ANY_SYNC_BUNDLE_INIT_EXTERNAL_ADDRS: "192.168.50.10,anytype-sync.dv.zone"
     ANY_SYNC_BUNDLE_INIT_MONGO_URI: "mongodb://mongo:27017/?replicaSet=rs0"
     ANY_SYNC_BUNDLE_INIT_REDIS_URI: "redis://redis:6379/"
     ANY_SYNC_BUNDLE_INIT_S3_BUCKET: "anytype-data"
     ANY_SYNC_BUNDLE_INIT_S3_ENDPOINT: "http://garage:3900"
     ANY_SYNC_BUNDLE_INIT_S3_FORCE_PATH_STYLE: "true"
     ANY_SYNC_BUNDLE_INIT_S3_REGION: "garage"
     ANY_SYNC_BUNDLE_INIT_FILENODE_DEFAULT_LIMIT: "10737418240"   # 10 GiB/space (Garage has ~30G total)
     AWS_ACCESS_KEY_ID: [[ any_sync_s3_access_key ]]
     AWS_SECRET_ACCESS_KEY: [[ any_sync_s3_secret_key ]]
     ```
   - Bottom: `networks: { any-sync: {driver: bridge}, caddy-internal: {external: true} }`
     then `[[ vol.top_level_volumes(app) ]]`.
   - ⚠️ The mongo healthcheck contains `$$(...)` (compose-escaped `$`) and JS with braces;
     I'll render-test it to confirm no `[[`/`]]`/`[%`/`%]` collision with the Jinja
     delimiters (the same class of bug caught in `garage.toml.j2`).
3. **`deploys/docker_vm/apps/secrets.py`** — the two refs above.
4. **`docs/plans/apps-to-try.md`** — any-sync-bundle ⬜→✅ once verified.

No `__init__.py` / `deploy.py` changes.

> **First-run caveat:** `ANY_SYNC_BUNDLE_INIT_*` values are consumed **only on first start**
> and baked into `/data` config. Changing `EXTERNAL_ADDRS` or the S3 creds later means
> editing the config in the `any-sync-data` volume, not just the env. So the bucket, key,
> and `<PUBLIC_ADDR>` must be correct before the first deploy.

## Order of operations
1. Provision Garage bucket + key (above); you create the 1Password item; I verify refs.
2. You give me `<PUBLIC_ADDR>` (and set up its public DNS + router forward when ready).
3. Write the code (files above); render-test the template; `git` on `main` (trunk-based,
   [[feedback_trunk_based]]).
4. Deploy: `uv run pyinfra inventory.py --limit docker_vm -y deploy.py`.
5. Retrieve `client-config.yml` from the bundle volume → import into Anytype apps:
   `docker exec any-sync-bundle cat /data/client-config.yml`.

## Verification
- **Containers:** `mongo` + `redis` healthy, `any-sync-bundle` up; bundle logs show it
  connected to Mongo (replica set `rs0`), Redis, and S3 with no errors.
- **Replica set:** `docker exec any-sync-mongo mongosh --quiet --eval 'rs.status().ok'` → `1`.
- **Bloom present:** `docker exec any-sync-redis redis-cli MODULE LIST` includes `bf`.
- **S3 wired:** after a sync (or a bundle self-check), `docker exec garage /garage bucket
  info anytype-data` shows object count/size > 0.
- **Reachability:** from a LAN host, TCP-connect to `192.168.50.10:33010`; once the router
  forward + public DNS are up, repeat from an external network.
- **End-to-end:** add the self-host config to an Anytype client via `client-config.yml` and
  confirm a space syncs.

## Follow-ups / out of scope
- Router port-forward + public DNS for `<PUBLIC_ADDR>` (your side).
- Optional: a dedicated `garage-data` network shared by Garage + its S3 consumers, instead
  of reusing `caddy-internal`, if more consumers appear.
- Optional: back up the `any-sync-data` volume (network identity) and Mongo — losing the
  bundle keys forces clients to re-add the network.
