from op_secrets import SecretString

user_password = SecretString("op://Homelab/Docker VM daan/password")
user_password_salt = SecretString("op://Homelab/Docker VM daan/salt")

SecretString.populate_cache_sync()
