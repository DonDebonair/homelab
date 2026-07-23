from urllib.parse import quote

from op_secrets import SecretString

miniflux_db_password = SecretString("op://Homelab/PostgreSQL Miniflux user/password")
miniflux_oidc_client_secret = SecretString("op://Homelab/Miniflux OIDC client/password")

forgejo_db_password = SecretString("op://Homelab/PostgreSQL Forgejo user/password")

# n8n DB user on the postgres_lxc. Same ref the lxc side provisions the user with
# (deploys/postgres_lxc/databases/secrets.py) so app and DB agree on the password.
n8n_db_password = SecretString("op://Homelab/PostgreSQL n8n user/password")

# nocodb DB user on the postgres_lxc (same ref the lxc side provisions it with).
nocodb_db_password = SecretString("op://Homelab/PostgreSQL NocoDB user/password")

# pgAdmin. The OIDC client secret MUST be the same plaintext whose pbkdf2 hash is
# registered for the `pgadmin` client in deploys/docker_vm/proxies/vars.py (i.e.
# the value carried over from the Ansible `pgadmin.oidc.secret` vault entry) --
# otherwise Authelia rejects the token exchange. The default password only
# satisfies the image's first-init env check (internal login is disabled by OIDC).
pgadmin_oidc_client_secret = SecretString("op://Homelab/pgAdmin OIDC client/password")
pgadmin_default_password = SecretString("op://Homelab/pgAdmin/password")

paperless_db_password = SecretString("op://Homelab/PostgreSQL Paperless user/password")
paperless_secret_key = SecretString("op://Homelab/Paperless secrets/secret key")
paperless_oidc_client_secret = SecretString("op://Homelab/Paperless secrets/OIDC/secret")
paperless_gmail_oauth_client_id = SecretString("op://Homelab/Paperless secrets/Google APIs/client id")
paperless_gmail_oauth_client_secret = SecretString("op://Homelab/Paperless secrets/Google APIs/secret")
paperless_api_token = SecretString("op://Homelab/Paperless secrets/api token")

# Outline. The DB password ref MUST match deploys/postgres_lxc/databases/secrets.py
# so app and DB agree. The OIDC client secret is the raw plaintext whose pbkdf2 hash
# is registered for the `outline` client in deploys/docker_vm/proxies/vars.py --
# otherwise Authelia rejects the token exchange. SECRET_KEY/UTILS_SECRET are Outline's
# own 32-byte-hex data-at-rest keys. SMTP is a dedicated Mailgun user for Outline.
outline_db_password = SecretString("op://Homelab/PostgreSQL Outline user/password")
outline_oidc_client_secret = SecretString("op://Homelab/Outline OIDC client/password")
outline_secret_key = SecretString("op://Homelab/Outline secrets/secret key")
outline_utils_secret = SecretString("op://Homelab/Outline secrets/utils secret")
outline_smtp_username = SecretString("op://Homelab/Outline secrets/SMTP/username")
outline_smtp_password = SecretString("op://Homelab/Outline secrets/SMTP/password")
# Public Notion OAuth integration for the Settings -> Import -> Notion importer.
# Redirect URI registered in Notion: https://outline.dv.zone/api/notion.callback
outline_notion_client_id = SecretString("op://Homelab/Outline secrets/Notion connection/client id")
outline_notion_client_secret = SecretString("op://Homelab/Outline secrets/Notion connection/client secret")

# AFFiNE. Same rules as Outline above: the DB ref must match
# deploys/postgres_lxc/databases/secrets.py, and the OIDC secret is the plaintext behind the
# `affine` client's pbkdf2 hash in deploys/docker_vm/proxies/vars.py. Unlike Outline's, this
# secret is rendered into config.json rather than an env var -- AFFiNE has no OIDC env vars.
# SMTP is a dedicated Mailgun user for AFFiNE.
affine_db_password = SecretString("op://Homelab/PostgreSQL AFFiNE user/password")
affine_oidc_client_secret = SecretString("op://Homelab/AFFiNE OIDC client/password")
affine_smtp_username = SecretString("op://Homelab/AFFiNE secrets/SMTP/username")
affine_smtp_password = SecretString("op://Homelab/AFFiNE secrets/SMTP/password")

# homepage Tautulli widget access token (Tautulli API key). Carried over from
# the NAS deploy; still valid because the /config volume is migrated intact.
tautulli_api_token = SecretString("op://Homelab/Tautulli/api token")

# homepage Seerr widget access token (Seerr API key). Fresh install -- generated
# at first-run setup, then stored in 1Password (not carried over from overseerr).
seerr_api_token = SecretString("op://Homelab/Seerr/password")

# homepage portainer widget access token (existing value carried over from the
# NAS deploy; still valid because the /data volume is migrated intact).
portainer_api_token = SecretString("op://Homelab/Portainer/api token")
# Shared secret between the Portainer server (here) and its remote agents (the
# NAS agent). Must match AGENT_SECRET on every agent -- see deploys/nas/docker.
portainer_agent_secret = SecretString("op://Homelab/Portainer/shared agent secret")

# homepage widget API tokens for services homepage only links to -- Plex and the
# *arr stack live elsewhere; these keys just let the homepage widgets query them.
plex_api_token = SecretString("op://Homelab/Plex/api token")
sonarr_api_token = SecretString("op://Homelab/Sonarr/api token")
radarr_api_token = SecretString("op://Homelab/Radarr/api token")
prowlarr_api_token = SecretString("op://Homelab/Prowlarr/api token")

# homepage widget API tokens for apps deployed here (carried over unchanged with
# the migrated configs).
miniflux_api_token = SecretString("op://Homelab/Miniflux/api token")
sabnzbd_api_token = SecretString("op://Homelab/SABnzbd/api token")

# Forgejo (gitea widget): a read-only token (repository/issue/notification) for homepage.
forgejo_api_token_homepage = SecretString("op://Homelab/Forgejo/api token homepage")

# Synology DiskStation (diskstation widget, static entry in services.yaml): a
# dedicated DSM admin user, provisioned in code by the NAS users deploy
# (deploys/nas/users) and added to `administrators`. 2FA is disabled for it by
# hand in DSM -- the diskstation widget can't complete a 2FA challenge.
synology_widget_username = SecretString("op://Homelab/Synology homepage user/username")
synology_widget_password = SecretString("op://Homelab/Synology homepage user/password")

# Proxmox VE / PBS widgets (static entries in services.yaml). API tokens on the
# read-only homepage@pve (PVEAuditor) / homepage@pbs (Audit) users provisioned by
# deploys/proxmox_host/users and deploys/pbs_vm/users. The widget takes the token
# id as `username` and the token secret as `password`.
proxmox_widget_token_id = SecretString("op://Homelab/PVE Homepage widget/token id")
proxmox_widget_secret = SecretString("op://Homelab/PVE Homepage widget/secret")
pbs_widget_token_id = SecretString("op://Homelab/PBS Homepage widget/token id")
pbs_widget_secret = SecretString("op://Homelab/PBS Homepage widget/secret")

# Forgejo Actions runner connection token (the secret half of the UUID+Token pair
# from Forgejo's "Create runner" dialog). Rendered into the runner's config.yaml
# under server.connections. Forgejo runner >=12.7 consumes this declaratively --
# no `register` step. See deploys/docker_vm/apps/templates/forgejo-runner-config.yaml.j2
# and docs/plans/renovate-forgejo-actions.md.
forgejo_runner_token = SecretString("op://Homelab/Forgejo/runner token")
# The non-secret half of that pair -- the runner's UUID (shown in Site Admin ->
# Actions -> Runners). Identifies this registration; not sensitive, so kept in code.
forgejo_runner_uuid = "c3a69254-f967-4158-8779-fed50a8239e0"

unifi_controller_homepage_username = SecretString("op://Homelab/UniFi Controller/Homepage/username")
unifi_controller_homepage_password = SecretString("op://Homelab/UniFi Controller/Homepage/password")

# Garage (single-node S3 object store). `rpc secret` is the 32-byte-hex cluster RPC
# key (openssl rand -hex 32); on a single node it still must be set. `admin token` is
# the bearer token for Garage's admin API -- the garage-webui sidecar authenticates to
# it with the same value via API_ADMIN_KEY. Both are rendered into garage.toml.
garage_rpc_secret = SecretString("op://Homelab/Garage/rpc secret")
garage_admin_token = SecretString("op://Homelab/Garage/admin token")

# any-sync-bundle's S3 credentials -- a dedicated Garage key (`any-sync`) with RW on the
# `anytype-data` bucket. Passed to the bundle as the standard AWS_ACCESS_KEY_ID /
# AWS_SECRET_ACCESS_KEY env vars. The key ID is a Garage identifier (GK...), the secret is
# the sensitive half; both live in the one 1Password item.
any_sync_s3_access_key = SecretString("op://Homelab/Anytype secrets/Garage S3/access key id")
any_sync_s3_secret_key = SecretString("op://Homelab/Anytype secrets/Garage S3/secret access key")

# BookOrbit. DB ref matches the postgres_lxc side (cmd.py db add-db bookorbit --display-name
# BookOrbit provisions the role with the same item). JWT_SECRET signs login tokens;
# SETUP_BOOTSTRAP_TOKEN gates first-run admin creation. OIDC is configured in BookOrbit's UI
# (client `bookorbit` in proxies/vars.py), so -- like Shelfmark -- its secret is not an
# env var here.
bookorbit_db_password = SecretString("op://Homelab/PostgreSQL BookOrbit user/password")
bookorbit_jwt_secret = SecretString("op://Homelab/BookOrbit secrets/JWT secret")
bookorbit_bootstrap_token = SecretString("op://Homelab/BookOrbit secrets/bootstrap token")

SecretString.populate_cache_sync()

# AFFiNE reaches Postgres through prisma, which parses DATABASE_URL strictly as a URL. Our
# generated passwords (commands/secrets.py) may contain ':' '?' '=' '$' ';' ',' -- all legal in
# a Postgres password but not in a URL's userinfo, where an unescaped ':' makes prisma read the
# rest as a port and die with P1013 "invalid port number". So percent-encode it, safe="" so
# nothing is left unescaped. Apps that take discrete host/user/password settings (paperless) or
# whose driver is lenient (outline) interpolate the password raw and don't need this.
#
# str() is load-bearing here, and this has to sit after populate_cache_sync() to work:
# SecretString only expands via __str__, so passing the object straight to quote() -- or to
# jinja's |urlencode in the template -- would encode the literal op:// reference instead of the
# password, with no error. Same class of bug as the str.join gotcha.
affine_db_password_url = quote(str(affine_db_password), safe="")

# BookOrbit is a Node app that parses DATABASE_URL strictly as a URL -- same P1013-class risk
# as AFFiNE, so percent-encode the password (safe="" leaves nothing unescaped). str() is
# load-bearing and must run after populate_cache_sync(); see affine_db_password_url above.
bookorbit_db_password_url = quote(str(bookorbit_db_password), safe="")
