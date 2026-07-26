# Plan: Vikunja (to-do / task manager) on docker_vm

## Context

[Vikunja](https://vikunja.io) is a self-hosted to-do & task manager (list / gantt / table /
kanban views), next off the [apps-to-try](apps-to-try.md) wishlist. It ships as a **single
unified image** (`vikunja/vikunja`; the old split `vikunja/api` + `vikunja/frontend` images
are deprecated) that serves the API and the SPA on **one port, 3456**.

Standard `ComposeApp` + per-app template deploy on `docker_vm`, LAN-only behind
`caddy-internal` at **`vikunja.dv.zone`**, backed by the shared **postgres_lxc** and gated by
**native OIDC against Authelia** (no forward-auth) — same shape as Outline / AFFiNE /
BookOrbit.

**Decisions locked:**

- **Image/version:** `vikunja/vikunja:2.4.0` — latest stable (released 2026-07-19; verified on
  Docker Hub). Picked up automatically by Renovate manager M1 (adjacent `image=`/`version=`).
- **Auth: OIDC-only.** `auth.local.enabled=false` + `service.enableregistration=false`, so the
  login page offers only the Authelia button. Break-glass = flip `VIKUNJA_AUTH_LOCAL_ENABLED`
  back to `true` and redeploy.
- **Mailer:** off for this deploy (no reminder/notification e-mail). Adding it later is one
  `VIKUNJA_MAILER_*` block + a dedicated Mailgun 1Password item, like Outline/AFFiNE.
- **Homepage:** plain discovery labels now; the live Vikunja widget is a follow-up (it needs an
  API token that can only be generated after the first login).
- **No redis / keyvalue backend:** single instance → `keyvalue.type=memory` (the default). Redis
  is only needed for multi-instance or redis-backed rate limiting.

## Already done (uncommitted, present in the working tree)

Both helper commands have already been run, so the DB and the OIDC client entries exist in
code and the credentials exist in 1Password:

- `deploys/postgres_lxc/databases/vars.py` — `PostgresDBConfig(name="vikunja", user="vikunja", …)`
  (**no extensions needed**: Vikunja's xorm migrations only create ordinary tables).
- `deploys/postgres_lxc/databases/secrets.py` — `vikunja_password` →
  `op://Homelab/PostgreSQL Vikunja user/password`.
- `deploys/docker_vm/proxies/vars.py` — Authelia client `vikunja`, `two_factor`,
  `client_secret_basic`, `claims_policy: default`, redirect URI
  `https://vikunja.dv.zone/auth/openid/authelia`.

Neither has been applied to a host yet — that's step 1 and 2 of the order of operations.

## OIDC wiring (the part with a hard constraint)

Vikunja's callback path is **`<publicurl>/auth/openid/<provider key>`**, where *provider key*
is the lowercased key of the provider map. The registered Authelia redirect URI ends in
`/authelia`, so the provider key **must** be `authelia` and the env vars therefore read
`VIKUNJA_AUTH_OPENID_PROVIDERS_AUTHELIA_*`. Changing the key means re-registering the URI.

- `AUTHURL` is the **issuer** (`https://auth.dv.zone`); Vikunja does OIDC **discovery** against
  `<authurl>/.well-known/openid-configuration` at runtime, from the server. That's why the
  container gets an explicit `dns:` pin to `host.data.dns_ip` — the same fix
  affine/bookorbit/portainer needed so a stale `/etc/resolv.conf` snapshot can't leave the
  issuer unresolvable ([[project_portainer_oidc_dns_pin]]).
- The **`email` claim is mandatory** — user creation fails without it. Our Authelia client
  already carries `claims_policy: default`, which puts `email`, `preferred_username`, `name`
  and `groups` into the **ID token**, which is exactly where Vikunja reads them (it only calls
  the userinfo endpoint when `forceuserinfo: true`). So no `forceuserinfo` needed.
- Requested `SCOPE`: `"openid profile email"` (a subset of what the client is registered for;
  `groups` is only useful with the `vikunja_scope` team-provisioning feature, which we don't use).
- `LOGOUTURL: https://auth.dv.zone/logout` so signing out of Vikunja ends the Authelia session too.
- No `import secure` on the Caddy labels: a blanket forward-auth would double-gate and break the
  OAuth callback (same note as Outline/BookOrbit).

## Storage: external named volume + a one-shot chown init

`files.basepath` (`/app/vikunja/files`) holds every task attachment and user avatar → high
recovery cost → `NamedVolume(name="vikunja-files", …, external=True)` per
[[feedback_named_volumes_external]].

That needs one extra step, because the image is `FROM scratch` with `USER 1000` and **no
`/app/vikunja/files` directory baked in** — so Docker has no ownership to copy into a fresh
volume. **Verified on docker_vm (Docker 29.4.3)**: an empty named volume mounted at a path the
image does not contain comes up `root:root 0755`, uid 1000 gets `Permission denied`, and only
`0:0` can write. Upstream's ["File permissions"](https://vikunja.io/docs/full-docker-example/#file-permissions)
note is about matching *host bind* ownership with `--user`; **changing the container user does
not help here** — any other non-root uid (e.g. our `dockerlimited` 2000) fails identically.

So the template adds a **one-shot `vikunja-init` service** (`busybox:1.38.0`, `user: "0:0"`,
`chown -R 1000:1000 /app/vikunja/files`, `restart: "no"`) and the main service gates on it with
`depends_on: {vikunja-init: {condition: service_completed_successfully}}` — exactly the idiom
`affine-migration` already uses in `affine.yaml.j2`. It is idempotent, re-runs in milliseconds on
every `compose up -d`, and keeps the server itself non-root at uid 1000. busybox is a secondary
image pinned inline, so Renovate manager M3 tracks it.

Alternatives considered and rejected: `user: "0:0"` on the server (one line, but runs Vikunja as
root and leaves every attachment root-owned — upstream suggests it only for rootless Docker); a
`BindMount(uid=1000, gid=1000)`, which the helper would create with correct ownership and needs no
init container, but keeps the state out of the named-volume convention.

## Database

Discrete settings (`VIKUNJA_DATABASE_HOST/USER/PASSWORD/DATABASE`), not a DSN — so **pass the
password raw**: Vikunja builds the connection string itself and `url.PathEscape`s the password
(`pkg/db/db.go`), so pre-encoding it here would double-escape and fail auth. This is the
paperless case, not the AFFiNE/BookOrbit `DATABASE_URL` case.

Secret env values are rendered **double-quoted** in the compose template. Generated passwords
draw from `!$()?=^_;:,.-` and a plain YAML scalar starting with `!` or `?` would be a parse
error; quoting removes that class of failure (the charset has no `"` or `\`).

`VIKUNJA_DATABASE_SSLMODE: disable` — the LXC hop is on the trusted LAN, matching every other
app on this Postgres.

## Secrets

| Variable | 1Password ref | Status |
|---|---|---|
| `vikunja_db_password` | `op://Homelab/PostgreSQL Vikunja user/password` | exists (`db add-db`) |
| `vikunja_oidc_client_secret` | `op://Homelab/Vikunja OIDC client/password` | exists (`oidc add-client`) |
| `vikunja_service_secret` | `op://Homelab/Vikunja secrets/service secret` | **must be created** |

`service.secret` signs JWTs and backs other crypto. **If unset, Vikunja generates a random one
at every startup and invalidates all sessions on each restart** — so it has to be pinned. Per
[[feedback_user_creates_1password_items]] this item is created by hand: a `Vikunja secrets` item
in the `Homelab` vault with a field whose **id** resolves as `service secret`
([[feedback_op_sdk_resolves_by_field_id]]), value = 32 random bytes hex
(`openssl rand -hex 32`). Deploy is blocked on this one item.

## Files to create / change

1. **`deploys/docker_vm/apps/secrets.py`** — add the three `SecretString`s above (before
   `populate_cache_sync()`), with a comment noting the DB password is passed raw and the OIDC
   secret is the plaintext behind the `vikunja` client's pbkdf2 hash in `proxies/vars.py`.

2. **`deploys/docker_vm/apps/apps.py`** — append:

   ```python
   ComposeApp(
       name="vikunja",
       image="vikunja/vikunja",
       version="2.4.0",
       domain="vikunja.dv.zone",
       volumes=[
           # Task attachments + avatars -> external so `down -v` can't wipe them. The
           # scratch image runs as uid 1000 and has no files dir to copy ownership from,
           # so the vikunja-init one-shot in the template chowns this volume first.
           NamedVolume(name="vikunja-files", mount_path="/app/vikunja/files", external=True),
       ],
   )
   ```

3. **`deploys/docker_vm/apps/templates/vikunja.yaml.j2`** — new compose template, two services:

   - `vikunja-init`: `busybox:1.38.0`, `user: "0:0"`,
     `command: ["chown", "-R", "1000:1000", "/app/vikunja/files"]`, mounts `vikunja-files`,
     `restart: "no"` (see the storage section).
   - `vikunja`: `depends_on: {vikunja-init: {condition: service_completed_successfully}}`,
     `dns: [host.data.dns_ip]`, network `caddy-internal`, volumes via `vol.service_volumes(app)`,
     `expose: 3456`, `restart: unless-stopped`.
   - env: `VIKUNJA_SERVICE_PUBLICURL: https://vikunja.dv.zone/`, `VIKUNJA_SERVICE_SECRET`,
     `VIKUNJA_SERVICE_TIMEZONE: Europe/Amsterdam`, `VIKUNJA_SERVICE_ENABLEREGISTRATION: "false"`,
     `VIKUNJA_SERVICE_IPEXTRACTIONMETHOD: xff` + `VIKUNJA_SERVICE_TRUSTEDPROXIES: 172.101.0.0/16`
     (the `caddy-internal` subnet — otherwise every request is logged/throttled as Caddy's IP),
     the four `VIKUNJA_DATABASE_*` settings + `SSLMODE: disable`,
     `VIKUNJA_FILES_BASEPATH: /app/vikunja/files`, `VIKUNJA_AUTH_LOCAL_ENABLED: "false"`,
     `VIKUNJA_AUTH_OPENID_ENABLED: "true"`, and the five
     `VIKUNJA_AUTH_OPENID_PROVIDERS_AUTHELIA_{NAME,AUTHURL,LOGOUTURL,CLIENTID,CLIENTSECRET,SCOPE}`.
   - labels: `caddy_internal: [[ app.domain ]]`, `caddy_internal.reverse_proxy: "{{upstreams 3456}}"`,
     `homepage.group: Office`, `homepage.name: Vikunja`, `homepage.icon: vikunja`,
     `homepage.href`, `homepage.weight: 1030` (after outline 1010 / affine 1020).

4. **`docs/plans/apps-to-try.md`** — flip Vikunja ⬜ → ✅.

No new facts/operations, so **no `pyinfra-testing` cases** are needed. No DNS work either:
`*.dv.zone` already resolves to the internal Caddy ([[project_wildcard_dns_dv_zone]]).

## Order of operations

1. Create the `Vikunja secrets / service secret` 1Password item (blocking).
2. Apply the DB: `uv run pyinfra inventory.py deploys.postgres_lxc.databases -y --limit postgres_lxc`.
3. Apply Authelia: `uv run pyinfra inventory.py deploys.docker_vm.proxies -y --limit docker_vm`
   (the rendered `configuration.yml` is `restart_on_change`, so Authelia restarts itself).
4. Write the three code changes above.
5. Deploy the app: `uv run pyinfra inventory.py deploys.docker_vm.apps -y --limit docker_vm`.
6. Verify (below), then commit to `main` ([[feedback_trunk_based]]) — push only if asked.

## Verification

- `ssh dockervm.dv.zone 'docker compose -p vikunja ps -a'` → `vikunja` up, `vikunja-init` exited
  0; `docker logs vikunja` shows the xorm migrations running once against Postgres and no
  `permission denied` on `/app/vikunja/files`.
- Volume ownership actually flipped:
  `docker run --rm -v vikunja-files:/f busybox:1.38.0 ls -ldn /f` → owner `1000 1000`.
- `psql` on postgres_lxc: `\dt` in the `vikunja` DB lists the created tables.
- `curl -s https://vikunja.dv.zone/api/v1/info` → `"local":{"enabled":false}` and an
  `openid_connect` provider entry named `Authelia` with the expected `auth_url`.
- Browser: `https://vikunja.dv.zone` shows only the Authelia button → login round-trips through
  `auth.dv.zone` → lands on the Vikunja home with the user created from the `email` claim.
- Create a task with an attachment (exercises the bind mount), then `docker restart vikunja` and
  confirm the session survives (proves `service.secret` is pinned, not regenerated).

## Follow-ups / out of scope

- **Homepage widget** (`type: vikunja`, `version: 2`, `enableTaskList`): needs an API token
  generated in Vikunja's UI after first login + a 1Password item; small separate change.
- **Mailer** (Mailgun SMTP user) — enables reminders, mention e-mails, task-due notifications.
- **CalDAV** (`service.enablecaldav`, on by default) authenticates with a *local* username +
  password, which OIDC-only users don't have — so it is effectively unusable in this setup.
  Revisit only if calendar sync is wanted.
- **Metrics**: Vikunja exposes Prometheus metrics behind `VIKUNJA_METRICS_ENABLED`; could be
  scraped by the docker_vm Prometheus later.
