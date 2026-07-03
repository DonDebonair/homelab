from op_secrets import SecretString

miniflux_db_password = SecretString("op://Homelab/PostgreSQL Miniflux user/password")
miniflux_oidc_client_secret = SecretString("op://Homelab/Miniflux OIDC client/password")

forgejo_db_password = SecretString("op://Homelab/PostgreSQL Forgejo user/password")

# n8n DB user on the postgres_lxc. Same ref the lxc side provisions the user with
# (deploys/postgres_lxc/databases/secrets.py) so app and DB agree on the password.
n8n_db_password = SecretString("op://Homelab/PostgreSQL n8n user/password")

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

# homepage Overseerr widget access token (Overseerr API key). Fresh install --
# generated at first-run setup, then stored in 1Password (not carried over).
overseerr_api_token = SecretString("op://Homelab/Overseerr/password")

# homepage portainer widget access token (existing value carried over from the
# NAS deploy; still valid because the /data volume is migrated intact).
portainer_api_token = SecretString("op://Homelab/Portainer/api token")
# Shared secret between the Portainer server (here) and its remote agents (the
# NAS agent). Must match AGENT_SECRET on every agent -- see deploys/nas/docker.
portainer_agent_secret = SecretString("op://Homelab/Portainer/shared agent secret")

SecretString.populate_cache_sync()
