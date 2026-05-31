from op_secrets import SecretString

technitium_admin_password = SecretString("op://Homelab/Technitium DNS/password")
technitium_oidc_client_secret = SecretString("op://Homelab/Technitium DNS/OIDC client secret")

SecretString.populate_cache_sync()
