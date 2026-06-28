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

SecretString.populate_cache_sync()
