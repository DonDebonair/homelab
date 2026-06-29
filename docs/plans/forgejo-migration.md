# Plan: Port Forgejo from the NAS to the Docker VM (Ansible → pyinfra)

## Context

Next app in the `docker-apps` migration ([docker-apps-migration.md](docker-apps-migration.md)),
and the first **git forge** (stateful repos + Postgres + an in-DB OAuth source +
git-over-SSH). Forgejo currently runs on the Synology NAS via the Ansible
`roles/docker-apps` role (`forgejo.yml.j2`): a single `codeberg.org/forgejo/forgejo:8`
container, the Postgres DB living in the NAS `postgres` container, all repo/LFS
state in the bind mount `/volume2/docker/forgejo:/data`, exposed HTTP-only on
`git.dv.zone` (port 3000) behind caddy-internal. The NAS compose configured **no**
OIDC and **no** git-over-SSH.

Three things are **already provisioned** on the pyinfra side before this work:

- the `forgejo` Postgres DB + user on `postgres_lxc`
  (`deploys/postgres_lxc/databases/vars.py`; secret var `forejo_password` —
  note the existing typo — at `op://Homelab/PostgreSQL Forgejo user/password`);
- the `forgejo` Authelia OIDC client (`deploys/docker_vm/proxies/vars.py`):
  `two_factor`, redirect `https://git.dv.zone/user/oauth2/authelia/callback`,
  scopes `openid groups email profile`, `client_secret_basic`;
- the **git-over-SSH path** in `caddy-internal.yaml.j2`: the container exposes port
  `22` and a Caddy `layer4` route matches SSH and proxies it to `forgejo:22`
  (lines 19, 31–33). caddy-internal is on the macvlan at
  `host.data.internal_reverse_proxy_ip` (`192.168.50.20` = `git.dv.zone`), so
  `git@git.dv.zone` reaches Forgejo's built-in SSH with **no host port publish**.

So the work is: the compose stack + `ComposeApp`/secrets wiring, and a clean data
migration (the `/data` volume **and** the Postgres DB), then cutover.

## Decisions

- **Pin Forgejo 8.x, upgrade major later.** Migrate on the same major (latest 8.x
  patch — look up the exact tag live, don't guess) so Forgejo's startup schema
  migration is a no-op against the carried-over DB. A major bump (9 → 10 → 11 → …)
  is a separate, isolated change afterwards. The NAS ran the floating `:8` tag; we
  replace it with an explicit patch per the repo's image-pinning rule
  ([feedback: pin docker image versions]).
- **Internal-only, self-auth (not Authelia forward-auth).** Webserver on
  `caddy-internal` (`git.dv.zone`, matching the NAS `exposure: internal`), plus a
  private compose bridge for the DB route is **not** needed — Forgejo reaches the
  `postgres_lxc` over the LAN like miniflux/paperless. Forgejo authenticates users
  itself via its **in-DB Authelia OAuth source** (carried over by the DB dump), so
  it does **not** get the caddy `import secure` / forward-auth wrapper. (Reaching
  `auth.dv.zone` for the OIDC round-trip works via the macvlan-shim host route.)
- **`/data` as one external named volume `forgejo-data`** ([feedback: external
  named volumes]). Git repositories + LFS are the highest-recovery-cost state in
  the homelab, so `external=True` keeps `down -v` from ever wiping them. This single
  volume also carries `gitea/conf/app.ini`, which holds Forgejo's `SECRET_KEY`,
  `INTERNAL_TOKEN`, `OAUTH2_JWT_SECRET` and `LFS_JWT_SECRET` — preserving the
  whole `/data` dir keeps existing sessions, 2FA enrolments and LFS objects valid.
- **git-over-SSH enabled** (improvement over the NAS). The container is named
  `forgejo` and joins `caddy-internal` so the pre-wired layer4 route (`forgejo:22`)
  resolves. We use the image's built-in **OpenSSH passthrough** (its sshd already
  listens on container port 22; Forgejo manages the `git` user's `authorized_keys`),
  with `FORGEJO__server__SSH_DOMAIN=git.dv.zone` and `SSH_PORT=22` so clone URLs
  render as `git@git.dv.zone:user/repo.git`. No host port mapping (caddy-internal
  owns `192.168.50.20:22` on the macvlan; the docker_vm host's own SSH is on a
  different IP, so no conflict).
- **DB host via env override.** `FORGEJO__database__HOST=host.data.postgres_lxc_ip:5432`,
  `NAME/USER=forgejo`, `PASSWD=[[ forgejo_db_password ]]`, `SSL_MODE=disable` —
  matching miniflux/paperless. Env vars override `app.ini`, so the migrated config's
  old NAS DB host is harmlessly superseded.
- **UID/GID 2000.** `USER_UID`/`USER_GID = host.data.docker_uid`/`docker_gid`
  (2000) — same values the NAS used, so the copied repo files' ownership maps
  cleanly.

## Implementation

- `deploys/docker_vm/apps/apps.py` — add the `forgejo` `ComposeApp`:
  ```python
  ComposeApp(
      name="forgejo",
      image="codeberg.org/forgejo/forgejo",
      version="8.0.3",  # latest 8.x patch at implementation time
      domain="git.dv.zone",
      volumes=[
          NamedVolume(name="forgejo-data", mount_path="/data", external=True),
      ],
  ),
  ```
- `deploys/docker_vm/apps/templates/forgejo.yaml.j2` — single service, ported from
  `roles/docker-apps/templates/forgejo.yml.j2` to pyinfra conventions (`[[ ]]`
  delimiters, `_volumes.j2` macros, `app.image`/`app.version`,
  `host.data.postgres_lxc_ip`, external `caddy-internal` network), adding the SSH
  env block and the `homepage.*` labels (Development group, `gitea` widget). Skeleton:
  ```yaml
  [%- import '_volumes.j2' as vol with context -%]
  services:
    forgejo:
      container_name: forgejo
      image: [[ app.image ]]:[[ app.version ]]
      networks:
        - caddy-internal
      volumes:[[ vol.service_volumes(app) ]]
      environment:
        USER_UID: [[ host.data.docker_uid ]]
        USER_GID: [[ host.data.docker_gid ]]
        FORGEJO__database__DB_TYPE: postgres
        FORGEJO__database__HOST: [[ host.data.postgres_lxc_ip ]]:5432
        FORGEJO__database__NAME: forgejo
        FORGEJO__database__USER: forgejo
        FORGEJO__database__PASSWD: [[ forgejo_db_password ]]
        FORGEJO__database__SSL_MODE: disable
        FORGEJO__server__ROOT_URL: https://[[ app.domain ]]/
        FORGEJO__server__DOMAIN: [[ app.domain ]]
        FORGEJO__server__SSH_DOMAIN: [[ app.domain ]]
        FORGEJO__server__SSH_PORT: "22"
      labels:
        caddy_internal: [[ app.domain ]]
        caddy_internal.reverse_proxy: "{{upstreams 3000}}"
        homepage.group: Development
        homepage.name: Forgejo
        homepage.icon: forgejo
        homepage.href: https://[[ app.domain ]]
        homepage.weight: 1000
      expose:
        - 3000
        - 22
      restart: unless-stopped

  networks:
    caddy-internal:
      external: true
  [[ vol.top_level_volumes(app) ]]
  ```
- `deploys/docker_vm/apps/secrets.py` — add
  `forgejo_db_password = SecretString("op://Homelab/PostgreSQL Forgejo user/password")`
  (same item the `postgres_lxc` side reads). **Every referenced 1Password item must
  exist before any apps deploy** — `populate_cache_sync()` fails the whole module
  otherwise. The homepage gitea widget is omitted for now (it needs an API token;
  regenerate one post-migration and add `homepage.widget.{type,url,key}` if wanted).

`setup_apps()` picks the app up from the list automatically; no `deploy.py` change.

> **No new Authelia secret needed.** Forgejo's OAuth *client secret* lives in its
> own DB (`login_source` / `oauth2` table), carried by the dump — not in env. The
> only requirement is that the **new** Authelia issues the client secret whose hash
> is in `proxies/vars.py`; if that secret was rotated from the NAS Authelia,
> Forgejo's stored copy must be updated (see Verification).

## Data migration runbook

Forgejo's clean same-version move = **copy `/data` + dump/restore the DB**. (The
`forgejo dump` zip exists but is awkward to restore; a direct copy + `pg_dump` is
what the Forgejo docs recommend for a host move and preserves `app.ini` secrets.)
Key invariant: **stop the NAS Forgejo before the copy** so repos + DB are a
consistent snapshot, and keep DNS on the NAS until import is verified.

```bash
# 1. Quiesce — on the NAS, stop Forgejo (repos + DB consistent; brief downtime)
docker stop forgejo

# 2. Dump the DB — run ON THE NAS (the postgres container is named `postgres`).
#    NEVER pass `-t`: a docker TTY translates \n->\r\n in the binary -Fc stream and
#    silently produces an archive with an EMPTY TOC -- the magic bytes survive (so
#    `head -c5` shows PGDMP) but pg_restore loads 0 rows and exits clean. No `-i`
#    either (pg_dump reads no stdin); just redirect stdout.
docker exec postgres pg_dump -U forgejo -Fc forgejo > /volume2/docker/forgejo-db.dump
#    Verify the dump actually contains row data BEFORE going further (must be > 0;
#    file should be tens of MB, not ~5 MB):
docker cp /volume2/docker/forgejo-db.dump postgres:/tmp/d.dump \
  && docker exec postgres pg_restore -l /tmp/d.dump | grep -ci 'TABLE DATA'
# NB: over `ssh nas.dv.zone '...'` (non-interactive) `docker` is NOT on PATH on DSM
#    -- wrap any NAS-side docker call in `bash -lc "..."` or use /usr/local/bin/docker.

# 3. Deploy the new stack — from the repo (OP_SERVICE_ACCOUNT_TOKEN set)
#    Creates the external `forgejo-data` volume + the (stopped-OK) container.
uv run pyinfra inventory.py --limit docker_vm deploy.py
#    Stop it before loading data so nothing writes mid-restore:
ssh daan@192.168.50.10 'docker stop forgejo'

# 4. Restore into postgres_lxc (192.168.1.41, PostgreSQL 17), into the empty forgejo
#    DB (provisioned already). --clean --if-exists keeps it re-runnable.
#    Two hard-won rules: (a) transfer the dump to a FILE and restore from a MOUNT --
#    do NOT stream the archive over stdin through ssh/`docker run -i` (a short read
#    truncates it silently -> empty DB, no error); (b) docker_vm has no pg_restore,
#    so borrow one from a throwaway `postgres:17` container (it reaches the LXC like
#    miniflux/paperless do). All ssh hops originate from the Mac, so the NAS never
#    needs to reach the LXC.
ssh nas.dv.zone 'cat /volume2/docker/forgejo-db.dump' | ssh daan@192.168.50.10 'cat > ~/forgejo-db.dump'
ssh daan@192.168.50.10 'ls -l ~/forgejo-db.dump'   # size MUST equal the NAS file
PW=$(op read "op://Homelab/PostgreSQL Forgejo user/password")   # on the Mac
ssh daan@192.168.50.10 "PGPASSWORD='$PW' docker run --rm -e PGPASSWORD \
  -v ~/forgejo-db.dump:/dump:ro postgres:17 \
  pg_restore -h 192.168.1.41 -U forgejo -d forgejo --clean --if-exists --no-owner --verbose /dump"
#    $PW expands on the Mac; the literal single quotes reach the docker_vm shell so a
#    password with shell metacharacters stays intact (assumes no single quote in it).
#    If pg_restore errors "unsupported version ... in file header", the NAS Postgres
#    is newer than 17 -> bump the image tag to match (docker exec postgres postgres --version).

# 5. Copy /data -> the forgejo-data named volume. The dir has UID-2000-owned,
#    0600/0700 files (gitea/jwt/private.pem, indexers, sessions, AND the repos),
#    so a non-root tar SILENTLY skips them -> incomplete copy. Tar as ROOT on the
#    NAS into a tarball, hand it to daanadmin for transfer, extract on docker_vm.
#    (Forgejo must be stopped on both ends -- steps 1 & 3 -- for a consistent copy.)
#    On the NAS (sudo prompts for a password interactively):
sudo tar czf /volume2/docker/forgejo-data.tgz -C /volume2/docker/forgejo .
sudo chown daanadmin:users /volume2/docker/forgejo-data.tgz
#    Transfer via the Mac (NAS rejects `sudo rsync`; docker_vm has no SSH to the NAS):
ssh nas.dv.zone 'cat /volume2/docker/forgejo-data.tgz' | ssh daan@192.168.50.10 'cat > ~/forgejo-data.tgz'
ssh daan@192.168.50.10 'ls -l ~/forgejo-data.tgz'   # size MUST match the NAS tarball
#    On docker_vm, extract into the volume and normalize ownership to the container
#    user (2000). Extracting as root preserves the required 0600 on jwt/private.pem.
MP=$(docker volume inspect forgejo-data -f '{{ .Mountpoint }}')
sudo tar xzf ~/forgejo-data.tgz -C "$MP"
sudo chown -R 2000:2000 "$MP"

# 6. Start Forgejo; it runs its schema migration (no-op on same major) against the
#    restored DB and serves the copied repos.
ssh daan@192.168.50.10 'docker start forgejo'
docker logs -f forgejo   # watch for a clean startup + "Listen: http://0.0.0.0:3000"

# 7. Cut over DNS — point git.dv.zone -> 192.168.50.20 (caddy-internal) in Technitium
dig +short git.dv.zone @192.168.50.30   # expect 192.168.50.20
```

## Verification

- **Container up:** `docker ps` shows `forgejo` on `caddy-internal`; logs show a
  clean startup, schema migration as a no-op, SSH server listening on `:22`.
- **DB restored:** repos/users/issues counts match the NAS (spot-check via the UI
  or `docker exec -u git forgejo forgejo admin user list` — `-u git` because Forgejo
  refuses to run admin commands as root).
- **HTTPS:** `curl -sI https://git.dv.zone/` → 200 with a valid public cert; web UI
  loads; clone over `https://git.dv.zone/...` works.
- **git-over-SSH:** `ssh -T -p 22 git@git.dv.zone` returns Forgejo's greeting;
  `git clone git@git.dv.zone:user/repo.git` succeeds (exercises the caddy-internal
  layer4 route → `forgejo:22`).
- **Authelia SSO:** the "Sign in with Authelia" button completes the OIDC
  round-trip and lands on the matching existing user. **If it fails with an
  invalid-client/secret error**, the new Authelia's `forgejo` client secret differs
  from the one stored in Forgejo's DB — update it:
  `docker exec forgejo forgejo admin auth update-oauth --id <n> --secret <new>`
  (find `<n>` via `... admin auth list`).
- **homepage widget:** if `forgejo_widget_token` was set, the Development-group
  gitea widget renders stats.
- **Idempotency:** re-run `deploy.py`; second run reports no changes.

## Decommission (follow-up, after a few days of confidence)

- Stop the NAS Forgejo container; remove the `forgejo` entry from
  `roles/docker-apps/vars/main.yml` and delete `roles/docker-apps/templates/forgejo.yml.j2`.
- Only then delete `/volume2/docker/forgejo` and the `forgejo-db.dump` on the NAS.
- Update the [docker-apps-migration.md](docker-apps-migration.md) tracker
  (forgejo → ✅ Ported).

## Upgrade to v15 (post-migration, 8.0.3 → 15.0.3)

Done as a follow-up after the migration settled. Target **v15.0.3** — latest stable
and an LTS (supported to 2027-07). Forgejo officially supports skipping majors
(cumulative migrations); 15.0.3 ships the *fixed* versions of every migration, so
the known runtime bugs in intermediate binaries (v13.0.0 Postgres `secret`-table
corruption, v10 TOTP migration failure) never execute on a direct jump.

**Breaking changes that actually touch this stack** (the rest don't, because the
template sets a minimal env config and omits the homepage widget token):
- **v15 cookie rename → forced re-login.** Harmless; all users log in once more.
  Suppress with `FORGEJO__security__COOKIE_REMEMBER_NAME=gitea_incredible` if wanted.
- **v14+ SSH `authorized_keys` startup validation.** From v14 on, Forgejo validates
  `/data/git/.ssh/authorized_keys` at boot and **halts** if it finds keys it didn't
  write. Ours is Forgejo-generated (from the DB) so it should pass; if the container
  fails to boot complaining about authorized_keys, delete that file (Forgejo
  recreates it from the DB) and restart — `docker exec -u git forgejo forgejo admin regenerate keys`.
- **v11 `USE_COMPAT_SSH_URI` default flips to `true`** → clone URLs *display* as
  `ssh://git@git.dv.zone/...` instead of scp-style. Cosmetic (existing remotes keep
  working). Set `FORGEJO__server__SSH_DOMAIN` is unaffected; add
  `FORGEJO__repository__USE_COMPAT_SSH_URI=false` only if you want the old display.

Not affected: Authelia OIDC login source and LFS have **no** breaking changes
v9→v15; PostgreSQL floor stays at 12 (PG17 fine).

**Runbook:**
```bash
# 1. Back up first — DB dump (clean, no -t) + the /data volume snapshot
docker exec postgres ... pg_dump ...        # or rely on PBS / the still-intact NAS copy
# 2. Bump the version in apps.py (8.0.3 -> 15.0.3) -- done -- and redeploy
uv run pyinfra inventory.py --limit docker_vm deploy.py
# 3. Watch the migration run on first boot
ssh daan@192.168.50.10 'docker logs -f forgejo'   # expect cumulative migrations, then Listen :3000
# 4. Re-verify: web UI (re-login via SSO), git-over-SSH clone, repos present.
#    If boot halts on authorized_keys -> delete /data/git/.ssh/authorized_keys, restart.
```

## Out of scope

- Forgejo Actions runners — none configured on the NAS; not part of this port.
