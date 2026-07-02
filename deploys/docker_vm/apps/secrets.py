from op_secrets import SecretString

miniflux_db_password = SecretString("op://Homelab/PostgreSQL Miniflux user/password")
miniflux_oidc_client_secret = SecretString("op://Homelab/Miniflux OIDC client/password")

forgejo_db_password = SecretString("op://Homelab/PostgreSQL Forgejo user/password")

paperless_db_password = SecretString("op://Homelab/PostgreSQL Paperless user/password")
paperless_secret_key = SecretString("op://Homelab/Paperless secrets/secret key")
paperless_oidc_client_secret = SecretString("op://Homelab/Paperless secrets/OIDC/secret")
paperless_gmail_oauth_client_id = SecretString("op://Homelab/Paperless secrets/Google APIs/client id")
paperless_gmail_oauth_client_secret = SecretString("op://Homelab/Paperless secrets/Google APIs/secret")
paperless_api_token = SecretString("op://Homelab/Paperless secrets/api token")

# homepage portainer widget access token (existing value carried over from the
# NAS deploy; still valid because the /data volume is migrated intact).
portainer_api_token = SecretString("op://Homelab/Portainer/api token")
# Shared secret between the Portainer server (here) and its remote agents (the
# NAS agent). Must match AGENT_SECRET on every agent -- see deploys/nas/docker.
portainer_agent_secret = SecretString("op://Homelab/Portainer/shared agent secret")

SecretString.populate_cache_sync()
