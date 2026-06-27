# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Configuration for a personal homelab running on a Minisforum MS-A2 (Proxmox host) and a Synology DS1621+ NAS. The repo holds **two parallel configuration management systems** that target different hosts:

- **Ansible** (legacy) — entrypoint `nas.yml`, drives the Synology NAS via roles in `roles/`. Uses `ansible-vault` (password in `.vault_pass`).
- **pyinfra** (current) — entrypoint `deploy.py`, drives the Proxmox host, the PostgreSQL LXC, and the Docker VM. Inventory is `inventory.py`. The intended direction is to migrate everything off Ansible onto pyinfra; new work happens here.

Both systems coexist; do not assume one replaces the other unless the task says so.

## Toolchain

- Python `>=3.14`. Dependencies managed with `uv` (see `uv.lock`, `pyproject.toml`).
- `pyinfra` is installed as an **editable path dependency from `../pyinfra`** (sibling checkout). Changes there affect this repo at runtime; if a pyinfra import or behavior looks wrong, check the sibling source.
   More information on how pyinfra works can be found at https://docs.pyinfra.com/en/latest/llms.txt
- `pyinfra-testing` (the data-driven test harness for facts/operations) is likewise an **editable path dependency from `../pyinfra-testing`**. All fact/operation tests are generated from JSON case files via this harness — see [Testing](#testing-pyinfra-facts--operations). Its `README.md` documents the full case-file format.
- `OP_SERVICE_ACCOUNT_TOKEN` must be set in the environment for any pyinfra run that imports `op_secrets` — secret resolution happens at import time via `SecretString.populate_cache_sync()`.

## Common commands

```bash
# pyinfra: run all deploys against all hosts in inventory
uv run pyinfra inventory.py deploy.py

# pyinfra: limit to one host group (groups defined by list names in inventory.py)
uv run pyinfra inventory.py --limit docker_vm deploy.py

# Ansible: run NAS playbook (tags scope it to a subset of roles)
ansible-playbook nas.yml
ansible-playbook -t docker-apps nas.yml

# Ansible: encrypt a value for inline use
ansible-vault encrypt_string -n <name> '<value>'

# Tests — data-driven harness over custom pyinfra facts/operations under tests/
uv run pytest
uv run pytest tests/test_facts.py        # just the fact suites
uv run pytest tests/test_operations.py   # just the operation suites

# Helper CLI (cyclopts) for Ansible-side config edits
uv run python script.py db add-db <name> [--user <u>] [--extensions ext1 ext2] [--dry-run]
uv run python script.py oidc add-client <name> <redirect_url> [--dry-run]
```

## Architecture

### pyinfra side

`deploy.py` is dispatched by host group (`"nas" in host.groups`, `"proxmox_host" in host.groups`, etc.) — each conditional block calls deploy functions imported from `deploys/<group>/`. Adding a new host group means: (1) add a list in `inventory.py`, (2) add a `group_data/<group>.py`, (3) add a `deploys/<group>/` package, (4) wire it into `deploy.py`.

Layered, reusable extensions to pyinfra live at the repo root:

- `models/` — `@dataclass` types and `StrEnum`s shared between facts and operations (e.g. `ProxmoxContainerConfig`, `DockerNetwork`). Treat these as the source of truth for the shape of Proxmox/Synology data.
- `facts/` — custom `FactBase` subclasses that shell out (`pveum`, `pct list`, Synology equivalents) and parse the result into model instances. Each declares `requires_command()`.
- `operations/` — custom `@operation`-decorated functions that read facts via `host.get_fact(...)`, diff against desired state, and `yield` the shell command(s) to converge. Always check the existing fact before issuing a command (idempotency pattern: read fact → compare → yield only if change needed → otherwise `host.noop(...)`).
- `deploys/<group>/<feature>/__init__.py` — `@deploy`-decorated entry functions that compose pyinfra operations (built-in + custom) into a feature. Re-exported through `deploys/<group>/__init__.py` so `deploy.py` can import them by name.
- `group_data/` — per-group host variables; pyinfra auto-loads these by group name. `group_data/all.py` is the global default.

### Docker image versioning

**Every container image must be pinned to an explicit version — never `:latest` or untagged.**

- For compose services, pinning is enforced through the **required `image` and `version` fields on `ComposeApp`** (`deploys/common/docker_compose/models.py`). They have no defaults, so a new app can't be constructed without them. The compose template renders the image as `image: [[ app.image ]]:[[ app.version ]]` — do not hardcode an image/tag in a template.
- The version literal lives on the `ComposeApp` in the group's `apps.py`, co-located with the app. **Exception:** `caddy_version` stays in `deploys/docker_vm/proxies/vars.py` because the custom-image *build* (`docker.build`) needs the same value; `apps.py` imports it so there's still one source of truth.
- **Secondary images** (a sidecar like authelia's `redis`, which the single-image `ComposeApp` can't express) and **non-compose images** (`docker.plugin`, `docker.build` base images) are pinned inline where they're declared. Note the loki log-driver plugin uses an **arch-suffixed** tag (`grafana/loki-docker-driver:<ver>-amd64`) because it publishes no multi-arch tag.
- To bump a version: change the `version` field (or the inline tag), then redeploy. Look up the current tag on the registry rather than guessing. Automating bumps with Renovate is planned once all apps are migrated off Ansible onto the docker_vm.

### Testing (pyinfra facts & operations)

Custom facts and operations are tested **exclusively** through the `pyinfra-testing` harness as data-driven JSON cases — **not** hand-written `unittest`/pytest functions. **Any new fact or operation (or change to one) must ship with harness cases.**

- **Discovery.** `tests/test_facts.py` and `tests/test_operations.py` auto-generate one `unittest` test per JSON file. Each subdirectory is named after the target's dotted path: `tests/facts/<module>.<FactClass>/` (e.g. `tests/facts/proxmox.pve.PVEContainers/`) and `tests/operations/<module>.<operation>/` (e.g. `tests/operations/proxmox.pve.container/`). To add a test, drop another `.json` file in the matching directory; to cover a new fact/operation, create its directory.
- **Fact case** = `output` (the raw command lines `process()` receives) + the expected `fact`, plus `command` and `requires_command`. The expected `fact` is the result of `process()` JSON-normalised: dataclasses are compared via `dataclasses.asdict` (list **every** field, including `None` ones), `StrEnum`s by value, and non-string dict keys (int VMIDs, tuple ACL keys) by their canonical string form.
- **Operation case** = `args`/`kwargs` + injected `facts` (keyed by `<module>.<FactClass>`) → expected `commands` (or `noop_description` for a no-op). Mock the facts the operation reads via `host.get_fact(...)`.
- **Write plain JSON — the harness reconstructs typed values.** Enum/dataclass operation arguments are built from the operation's own annotations (`"arch": "amd64"` → `PVEContainerArch.AMD64`; `"features": {"nesting": true}` → the dataclass), and int/tuple/enum fact keys are matched via a canonical string key. Do not try to construct Python objects in JSON.
- Generate expected values by running `process()` / the operation rather than hand-transcribing long command strings; see `../pyinfra-testing/README.md` for the complete case-file format and supported types.

### Secrets (1Password)

`op_secrets.SecretString` is a `str` subclass that holds an `op://...` reference and resolves the real value lazily via the 1Password SDK. `SecretString.populate_cache_sync()` must be called once after constructing all references (already done in `inventory.py` and `deploys/*/secrets.py` modules) — this batches the lookups. `str(secret)` and string concatenation transparently expand to the real value; the bare object still prints as the reference, so it's safe to log.

Use `SecretString` for any new secret rather than passing plaintext through code.

### Ansible side

Standard role layout under `roles/<role>/{tasks,templates,vars,files}`. `nas.yml` defines all variables inline (including some `!vault`-encrypted secrets). `script.py` (commands `db` and `oidc`) edits these YAML files programmatically using `ruamel.yaml` round-trip mode while preserving `!vault` tagged scalars — when modifying that script, keep round-trip semantics intact or comments/encryption blocks will be lost.

### Bootstrap note

For `proxmox_host`, `postgres_lxc`, and `docker_vm`: first run requires SSH key setup and root login. After that, switch the inventory `ssh_user` to a non-root user (already the case in `inventory.py`).
