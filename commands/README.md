# `commands/` — pyinfra credential helpers

CLI helpers for provisioning new credentials in the **pyinfra** setup. They are the
pyinfra-era counterpart to the Ansible `scripting/` helpers (`db.py`, `oidc.py`), kept in
a separate package with its own entrypoint (`cmd.py`) so the two setups don't clash.

Each command does three things:

1. Generates a credential (a random DB password, or an OIDC client secret + its
   pbkdf2-sha512 hash).
2. Appends the config entry to the relevant pyinfra module (preserving formatting via
   targeted text insertion — no manual editing).
3. Creates the matching **1Password** item in the `Homelab` vault via `onepassword-sdk`.

The entrypoint is `cmd.py` at the repo root:

```bash
uv run python cmd.py db --help
uv run python cmd.py oidc --help
```

## Requirements

- `OP_SERVICE_ACCOUNT_TOKEN` must be set for the 1Password item to be created, and the
  token must have **write** access to the `Homelab` vault. If creation fails (read-only
  token, duplicate item, ...), the command still edits the config files and prints the
  secret plus the exact `op://` reference so you can create the item manually.
- Run everything through `uv` so the project dependencies (`cyclopts`, `onepassword-sdk`,
  `libpass`) are available.

## `db add-db` — PostgreSQL database + user

Adds a `PostgresDBConfig` entry to `deploys/postgres_lxc/databases/vars.py` and a matching
`SecretString` reference to `deploys/postgres_lxc/databases/secrets.py`, then creates the
1Password item `PostgreSQL <display> user` (fields `username`, `password`).

```bash
uv run python cmd.py db add-db <name> [--user <user>] [--display-name <Display>] [--dry-run]
```

- `name` — lowercase database/user name (e.g. `nocodb`). Used verbatim for the DB name,
  the role, and the `<name>_password` secrets variable.
- `--user` — owning role; defaults to `name`.
- `--display-name` — display-cased app name used in the 1Password item title (e.g.
  `NocoDB`, `n8n`, `pgAdmin`). Defaults to `name.capitalize()`.
- `--dry-run` — print the edited files instead of writing them, and skip 1Password.

The generated password lands in `op://Homelab/PostgreSQL <display> user/password`, which
is exactly the reference the new `secrets.py` line resolves at deploy time. Apply it with:

```bash
uv run pyinfra inventory.py deploys.postgres_lxc.databases -y --limit postgres_lxc
```

> Note: the pyinfra `PostgresDBConfig` model has no `extensions` field, so (unlike the
> Ansible helper) there is no `--extensions` option.

Example:

```bash
uv run python cmd.py db add-db nocodb --display-name NocoDB
```

## `oidc add-client` — Authelia OIDC client

Appends a client dict to `oidc_clients` in `deploys/docker_vm/proxies/vars.py` and creates
the 1Password item `<name> OIDC client` (field `password` = the raw secret). The **hash**
(`$pbkdf2-sha512$310000$...`) is embedded in the config; the **raw** secret lives only in
1Password / the client app — so nothing is added to `proxies/secrets.py`.

```bash
uv run python cmd.py oidc add-client <name> <redirect_url> \
    [--policy two_factor|one_factor] \
    [--auth-method client_secret_basic|client_secret_post] \
    [--scopes openid --scopes groups ...] \
    [--claims-policy default] [--pkce] [--dry-run]
```

- `name` — display name (e.g. `Technitium DNS`). The `client_id` is a slug of it
  (`technitium-dns`).
- `redirect_url` — the client's redirect URI.
- `--policy` — Authelia `authorization_policy` (default `two_factor`).
- `--auth-method` — `token_endpoint_auth_method` (default `client_secret_basic`).
- `--scopes` — repeatable; defaults to `openid groups email profile`.
- `--claims-policy` — optional claims policy name (e.g. `default`, as Grafana uses) to
  restore claims into the ID token.
- `--pkce` — require PKCE with the `S256` challenge method.
- `--dry-run` — print the edited file instead of writing it, and skip 1Password.

Apply it by re-rendering the Authelia config on the Docker VM:

```bash
uv run pyinfra inventory.py deploys.docker_vm.proxies -y --limit docker_vm
```

Example (matching the existing Technitium client):

```bash
uv run python cmd.py oidc add-client "Technitium DNS" https://dns.dv.zone/sso/callback \
    --auth-method client_secret_post --pkce
```

## Module layout

| File | Responsibility |
|------|----------------|
| `db.py` | `db add-db` command |
| `oidc.py` | `oidc add-client` command |
| `secrets.py` | password / client-secret generation and the Authelia pbkdf2-sha512 hash |
| `onepassword.py` | create a 1Password item in the `Homelab` vault (with print-fallback) |
| `source_edit.py` | insert entries into the target Python config modules |
