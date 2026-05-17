from op_secrets import SecretString

# stage 1 — caddy
cloudflare_api_token        = SecretString("op://Homelab/Cloudflare/apikey")

# stage 2 — authelia
authelia_redis_password     = SecretString("op://Homelab/Authelia Secrets/redis-password")
authelia_smtp_password      = SecretString("op://Homelab/Authelia Secrets/smtp-password")
authelia_smtp_username      = SecretString("op://Homelab/Authelia Secrets/smtp-username")
authelia_jwt_secret         = SecretString("op://Homelab/Authelia Secrets/jwt-secret")
authelia_session_secret     = SecretString("op://Homelab/Authelia Secrets/session-secret")
authelia_storage_encryption = SecretString("op://Homelab/Authelia Secrets/storage-encryption-key")
authelia_hmac_secret        = SecretString("op://Homelab/Authelia Secrets/hmac-secret")
authelia_jwks_private_pem   = SecretString("op://Homelab/Authelia Secrets/oidc-jwks-private.pem")
authelia_jwks_public_pem    = SecretString("op://Homelab/Authelia Secrets/oidc-jwks-public.pem")
authelia_ldap_username      = SecretString("op://Homelab/Authelia LDAP client/name")
authelia_ldap_password      = SecretString("op://Homelab/Authelia LDAP client/password")
authelia_db_password        = SecretString("op://Homelab/PostgreSQL Authelia user/password")

SecretString.populate_cache_sync()
