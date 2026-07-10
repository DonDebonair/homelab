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

# Calibre-Web (calibreweb widget): dedicated read-only CWA user, basic auth.
cwa_widget_username = SecretString("op://Homelab/CWA Homepage user/username")
cwa_widget_password = SecretString("op://Homelab/CWA Homepage user/password")

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

SecretString.populate_cache_sync()
