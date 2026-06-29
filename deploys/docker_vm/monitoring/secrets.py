from op_secrets import SecretString

# Grafana connects to the `grafana` DB/user on the postgres_lxc (already
# provisioned in deploys/postgres_lxc/databases/).
grafana_db_password = SecretString("op://Homelab/PostgreSQL Grafana user/password")
# Authelia OIDC client secret (plaintext). Must match the secret_hash registered
# for the "grafana" client in deploys/docker_vm/proxies/vars.py.
grafana_oidc_client_secret = SecretString("op://Homelab/Grafana OIDC client/password")

# SNMPv3 credentials the snmp-exporter uses to poll the Synology NAS.
# NB: the username field's *id* is `username` (its display label is "rouser"); the
# 1Password SDK resolves by id, not label, so the reference must use `username`.
snmp_username = SecretString("op://Homelab/Synology SNMP/username")
snmp_password = SecretString("op://Homelab/Synology SNMP/password")
snmp_priv_password = SecretString("op://Homelab/Synology SNMP/SNMP privacy password")

SecretString.populate_cache_sync()
