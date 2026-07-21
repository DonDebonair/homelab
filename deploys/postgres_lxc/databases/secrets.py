from op_secrets import SecretString

authelia_password = SecretString("op://Homelab/PostgreSQL Authelia user/password")
miniflux_password = SecretString("op://Homelab/PostgreSQL Miniflux user/password")
grafana_password = SecretString("op://Homelab/PostgreSQL Grafana user/password")
forejo_password = SecretString("op://Homelab/PostgreSQL Forgejo user/password")
nocodb_password = SecretString("op://Homelab/PostgreSQL NocoDB user/password")
n8n_password = SecretString("op://Homelab/PostgreSQL n8n user/password")
paperless_password = SecretString("op://Homelab/PostgreSQL Paperless user/password")
outline_password = SecretString("op://Homelab/PostgreSQL Outline user/password")
affine_password = SecretString("op://Homelab/PostgreSQL AFFiNE user/password")
bookorbit_password = SecretString("op://Homelab/PostgreSQL BookOrbit user/password")

SecretString.populate_cache_sync()
