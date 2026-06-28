from op_secrets import SecretString

# Password the Brother scanner authenticates with over SMB. Create this item in
# 1Password before the first deploy.
scanner_smb_password = SecretString("op://Homelab/Paperless secrets/Brother Scanner/password")

SecretString.populate_cache_sync()
