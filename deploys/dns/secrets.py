from op_secrets import SecretString

technitium_admin_password = SecretString("op://Homelab/Technitium DNS/password")
technitium_oidc_client_secret = SecretString("op://Homelab/Technitium DNS/OIDC client secret")

# Homepage `technitium` widget key: a non-expiring token for a dedicated non-admin
# Technitium user whose group grants only Dashboard->View (the widget calls just
# dashboard/stats/get).
technitium_api_token = SecretString("op://Homelab/Technitium Homepage user/api token")

SecretString.populate_cache_sync()
