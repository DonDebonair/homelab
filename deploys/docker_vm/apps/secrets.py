from op_secrets import SecretString

miniflux_db_password = SecretString("op://Homelab/PostgreSQL Miniflux user/password")
miniflux_oidc_client_secret = SecretString("op://Homelab/Miniflux OIDC client/password")

paperless_db_password = SecretString("op://Homelab/PostgreSQL Paperless user/password")
paperless_secret_key = SecretString("op://Homelab/Paperless secrets/secret key")
paperless_oidc_client_secret = SecretString("op://Homelab/Paperless secrets/oidc secret")
paperless_gmail_oauth_client_id = SecretString("op://Homelab/Paperless secrets/googleapis client id")
paperless_gmail_oauth_client_secret = SecretString("op://Homelab/Paperless secrets/googleapis secret")
paperless_api_token = SecretString("op://Homelab/Paperless secrets/api token")

SecretString.populate_cache_sync()
