from op_secrets import SecretString

# Bootstrapped manually: `proxmox-backup-manager user generate-token pve@pbs backup`
# reveals the token value once; paste it into this 1Password item.
token_secret = SecretString("op://Homelab/PBS PVE backup token/password")

SecretString.populate_cache_sync()
