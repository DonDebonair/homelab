from op_secrets import SecretString

# DSM admin user for the Homepage `diskstation` widget (basic auth; the widget
# is not 2FA-compatible, so this account must have 2FA disabled -- a manual DSM
# step). Same 1Password item the docker_vm apps deploy reads to render the widget
# config, so the provisioned account and the widget credentials stay in sync.
synology_widget_username = SecretString("op://Homelab/Synology homepage user/username")
synology_widget_password = SecretString("op://Homelab/Synology homepage user/password")

SecretString.populate_cache_sync()
