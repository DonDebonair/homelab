# Plan: Renovate via Forgejo Actions (self-hosted runner)

## Context

Docker image versions across the homelab are now **explicitly pinned** — the required
`image`/`version` fields on `ComposeApp` (`deploys/common/docker_compose/models.py`) make an
unpinned app a construction error, and secondary/inline images are pinned in their templates.
Pinning trades a safety problem (silent `:latest` drift) for a staleness problem: versions
must be bumped by hand. This plan closes that loop with **Renovate**, the long-planned
replacement for the dropped `watchtower` (see `open-todos.md`, CLAUDE.md "Docker image
versioning").

This repo is hosted on the homelab's own Forgejo (`ssh://git@git.dv.zone/daan/homelab.git`),
so Renovate runs **natively against Forgejo** — no GitHub App, no external SaaS. Rather than a
permanently-running Renovate daemon, Renovate executes as an **ephemeral Forgejo Actions job**
on a cron schedule. The only long-lived new component is a **Forgejo Actions runner**, which is
general-purpose CI infrastructure we get to reuse beyond Renovate.

The per-repo `renovate.json` (four custom regex managers covering every pinning surface — the
24 `ComposeApp` pairs, the `caddy` base image, the inline sidecars, and the arch-suffixed loki
plugin) is **already written and validated** against Renovate 43 at the repo root. This plan is
about standing up the runner and the workflow that consumes it.

Reference: Nick Cunningham's guides on
[Forgejo + Actions setup](https://nickcunningh.am/blog/how-to-setup-and-configure-forgejo-with-support-for-forgejo-actions-and-more)
and [Renovate + Gitea/Forgejo](https://nickcunningh.am/blog/how-to-automate-version-updates-for-your-self-hosted-docker-containers-with-gitea-renovate-and-komodo).
We follow their runner shape (DinD) but drop **Komodo** — our deploy is `uv run pyinfra`.

## Decisions

- **Runner isolation: Docker-in-Docker, not host socket.** `docker_vm` runs the whole
  production stack, so CI jobs must not share the host Docker daemon (socket = host root;
  container churn next to caddy/authelia). A privileged `docker:dind` sidecar scopes both the
  breakout risk and the container churn to the dind container. The DinD TCP endpoint (`2375`,
  no TLS) stays on the internal compose network only — **never published on a host port**.
  (Future hardening: `docker:dind-rootless` to drop `privileged`.)
- **The runner is a `ComposeApp` in `deploys/docker_vm/apps/apps.py`**, co-located with
  `forgejo`, rendered by a two-service template (`forgejo-runner.yaml.j2`: `runner` + `dind`).
  - The **runner** image (`code.forgejo.org/forgejo/runner`) sits on the `ComposeApp`
    `image`/`version` fields → auto-tracked by Renovate manager **M1**.
  - The **dind** image (`docker:<ver>-dind`) is pinned inline in the template (the redis
    sidecar precedent) → auto-tracked by Renovate manager **M3**. Renovate ends up updating
    its own runner.
- **Actions enabled via env on forgejo**, not app.ini surgery: add
  `FORGEJO__actions__ENABLED: "true"` to `forgejo.yaml.j2`. An env change makes `compose up -d`
  recreate the container, so it applies on the next deploy with no manual restart. Leave
  `DEFAULT_ACTIONS_URL` at its Forgejo default (`https://code.forgejo.org`).
- **Runner ↔ Forgejo over the internal network.** The runner joins `caddy-internal` and
  registers against `http://forgejo:3000` (internal), avoiding a hairpin out through
  Cloudflare. The runner itself is a normal docker_vm container, so its DNS is fine.
- **dind must pin the Technitium resolver (`--dns`).** `git.dv.zone` is **not** public — it is
  behind `caddy-internal` (only `auth`/`whoami`/`rss.dv.zone` are on the Cloudflare tunnel), so
  it is a split-horizon name Technitium resolves to `192.168.50.20`. A normal bridge container
  resolves it via Docker's `127.0.0.11` → host-Technitium forwarding, but a **nested dind job
  container loses that** and falls back to public DNS, which can't resolve it. So dind's
  `dockerd` runs with `--dns [[ host.data.dns_ip ]]` (192.168.50.30). **Verified on docker_vm:**
  a nested container then gets `nameserver 192.168.50.30`, resolves `git.dv.zone → .20`, and
  reaches `https://git.dv.zone/api/v1/version` (valid TLS) through the double-NAT + macvlan
  shim. github.com changelog fetches use public DNS as normal.
- **Registration is declarative via `server.connections` (runner >=12.7, pinned 12.7.3).**
  Forgejo 15's "Create runner" dialog yields a **UUID + Token** pair, not a legacy
  single-use registration token — the old `forgejo-runner register`/`create-runner-file`
  flow doesn't apply (it fails with "registration token not found"). Instead the runner
  gets a `config.yaml` (a `TemplateFile`, `restart_on_change`) whose `server.connections.forgejo`
  block carries `url: http://forgejo:3000`, the UUID, the token, and the `labels`. The daemon
  runs `forgejo-runner daemon --config /config.yaml`; no `.runner` file, no bootstrap step,
  fully idempotent. The **token** is the op secret `forgejo_runner_token`; the **UUID** is a
  non-secret identifier kept in code (`forgejo_runner_uuid` in `secrets.py`).
  `server.connections` requires runner **v12.7.0+** — the earlier 9.0.3 pin silently fell back
  to looking for `.runner` and never connected.
- **Renovate config split:** repo policy stays in `renovate.json` (done); *bot/platform*
  config (`platform`, `endpoint`, token, repo scope, git author) is passed as **workflow env**,
  so no `config.js` file is needed. Bot credentials are **Forgejo Actions secrets**, not
  pyinfra secrets — they live in Forgejo, referenced in the workflow as `${{ secrets.* }}`.
- **Deploy stays manual.** After reviewing/merging a Renovate PR, roll it out with
  `uv run pyinfra inventory.py deploy.py`. We deliberately do **not** wire an on-merge
  auto-deploy Action: that would require `OP_SERVICE_ACCOUNT_TOKEN` + SSH access to every host
  inside the runner, a large blast-radius increase for little gain. (Optional future:
  a `workflow_dispatch` deploy button — out of scope here.)
- **Renovate scope: `daan/homelab` only.** `RENOVATE_AUTODISCOVER=false` +
  `RENOVATE_REPOSITORIES=daan/homelab`.
- **Runner scope: instance-level, but Actions disabled on other repos.** The runner is
  registered at the instance level (Site Admin), so it *could* serve every repo. Rather than
  re-register it repo-scoped, we disabled the Actions unit on the ~155 archived-from-GitHub
  `source-ag/*` repos (`has_actions:false` via the API — see `disable-actions.sh` at the repo
  root, idempotent, re-runnable for future imports). New repos keep Actions on by default, so
  the runner naturally serves `daan/homelab` (and any future repo you leave Actions on).

## Prerequisites (user action)

1Password items (create these; secret resolution happens at import / secret-injection time —
per convention I don't create op items):

- **`Homelab / Forgejo Runner`** → field `registration token` — one-time runner registration
  token from **Forgejo → Site Administration → Actions → Runners → Create new Runner**.
- **`Homelab / Renovate Bot`** → field `forgejo token` — a **Forgejo PAT** for a dedicated
  `renovate-bot` user (scopes: `read:user`, `write:repository`, `write:issue`,
  `read:organization`). Used as the `RENOVATE_TOKEN` Actions secret.
- **`Homelab / Renovate Bot`** → field `github token` — a **github.com** read-only classic PAT
  (no scopes / `public_repo`) so Renovate fetches changelogs without anonymous rate-limits.
  Stored as the **`GH_COM_TOKEN`** Actions secret (Forgejo forbids the `GITHUB_` prefix) and
  passed to Renovate via `RENOVATE_HOST_RULES`, not the usual `GITHUB_COM_TOKEN` env var.

Also (Forgejo UI, one-time): create the **`renovate-bot`** user and add it (or its token) so it
has push access to `daan/homelab`.

## Files created / changed

```
renovate.json                                   # DONE — repo-root policy, 4 custom managers
.forgejo/workflows/renovate.yml                 # NEW — scheduled Renovate job (this repo)
deploys/docker_vm/apps/apps.py                  # +ComposeApp("forgejo-runner", ...)
deploys/docker_vm/apps/templates/
  forgejo-runner.yaml.j2                         # NEW — runner + dind two-service stack
  forgejo-runner-config.yaml.j2                  # NEW — runner config (labels, container opts)
  forgejo.yaml.j2                                # +FORGEJO__actions__ENABLED
deploys/docker_vm/apps/secrets.py               # +forgejo_runner_registration_token SecretString
deploys/docker_vm/apps/vars.py (if present)     # runner instance URL / labels constants
docs/plans/open-todos.md                         # tick Renovate once live
```

Optional automation (mirrors `commands/oidc.py` / `db.py`):
```
commands/renovate.py + cmd.py wiring            # `cmd.py renovate set-secrets` — push the two
                                                 # bot tokens into Forgejo as Actions secrets
                                                 # via the Forgejo API (else set them in the UI)
```

## Implementation steps

1. **Enable Actions on Forgejo.** Add `FORGEJO__actions__ENABLED: "true"` to
   `forgejo.yaml.j2`; deploy `--limit docker_vm`. Verify **Site Admin → Actions** appears.

2. **Add the runner stack.** New `ComposeApp("forgejo-runner", image=
   "code.forgejo.org/forgejo/runner", version="<pin>", ...)` in `apps.py`, external named
   volume for `/data` (holds the `.runner` file — high recovery cost, so `external=True`).
   Two-service template:
   - `dind`: `docker:<ver>-dind`, `privileged: true`,
     `command: ["dockerd","-H","tcp://0.0.0.0:2375","--tls=false"]`, its own data volume,
     **no host-port publish**.
   - `runner`: `code.forgejo.org/forgejo/runner:<ver>`, `environment: DOCKER_HOST=tcp://dind:2375`,
     mounts `/data` + the rendered `config.yaml`, on `caddy-internal`, `depends_on: dind`.
   - `forgejo-runner-config.yaml.j2`: labels (e.g.
     `docker:docker://code.forgejo.org/...` for container jobs, plus
     `ubuntu-latest:docker://ghcr.io/catthehacker/ubuntu:runner-latest` for general CI),
     `container.network`, `runner.capacity`.

3. **Bootstrap-register the runner** (one-time, documented like the SSH-root bootstrap):
   deploy the stack, then
   `docker exec forgejo-runner forgejo-runner create-runner-file --instance http://forgejo:3000
   --token "$REG_TOKEN"` (reg token from the op item). Confirm the runner shows **online** under
   Site Admin → Actions → Runners. The daemon command in the template picks it up on restart.

4. **Add the Renovate workflow** `.forgejo/workflows/renovate.yml`:
   ```yaml
   on:
     schedule: [{ cron: "0 4 * * 1" }]   # weekly, Mondays 04:00
     workflow_dispatch:
   jobs:
     renovate:
       runs-on: docker
       container: renovate/renovate:<pin>
       steps:
         - uses: actions/checkout@v4
         - run: renovate
           env:
             RENOVATE_TOKEN: ${{ secrets.RENOVATE_TOKEN }}
             RENOVATE_HOST_RULES: '[{"hostType":"github","matchHost":"github.com","token":"${{ secrets.GH_COM_TOKEN }}"}]'
             RENOVATE_PLATFORM: forgejo
             RENOVATE_ENDPOINT: https://git.dv.zone/api/v1
             RENOVATE_AUTODISCOVER: "false"
             RENOVATE_REPOSITORIES: daan/homelab
             RENOVATE_GIT_AUTHOR: "Renovate Bot <renovate@dv.zone>"
   ```
   (Pin the `renovate/renovate` tag — it too becomes a Renovate-tracked image.)

5. **Set the two Actions secrets** (`RENOVATE_TOKEN`, `GH_COM_TOKEN`) on `daan/homelab` —
   Forgejo repo **Settings → Actions → Secrets**. (`GH_COM_TOKEN`, not `GITHUB_COM_TOKEN`:
   Forgejo rejects the `GITHUB_` prefix.)

6. **First run.** Trigger via `workflow_dispatch`; expect the onboarding/Dependency Dashboard
   PR, then per-update PRs. Review, merge, and `uv run pyinfra inventory.py deploy.py`.

7. **Docs.** Tick Renovate in `open-todos.md`; note the runner in CLAUDE.md if it becomes
   general CI.

## Verification

- Site Admin → Actions → Runners shows `forgejo-runner` **online** with the expected labels.
- `workflow_dispatch` run reaches "completed"; logs show Renovate discovering `daan/homelab`.
- A Dependency Dashboard issue + at least one version-bump PR appear, with correct
  `depName`/`currentValue` (spot-check a `ComposeApp`, the inline `redis`, and the loki plugin
  to confirm all four managers fire).
- Merge one trivial bump → deploy → the app comes up on the new tag.

## Out of scope / follow-ups

- **Autodiscover across all Forgejo repos** (flip `RENOVATE_AUTODISCOVER=true` once trusted).
- **On-merge auto-deploy** (needs op token + SSH in the runner — declined for blast radius).
- **Rootless DinD** hardening.
- **Digest pinning** for critical/stateful apps (`version="X@sha256:..."`; Renovate maintains
  the digest — the `renovate.json` managers already tolerate it).
- **linuxserver `-lsNNN` / `apache/tika -full`** odd-tag handling is already covered by
  `packageRules` in `renovate.json`; revisit if PRs look noisy.
