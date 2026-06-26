from op_secrets import SecretString

user_password = SecretString("op://Homelab/PBS daan/password")
user_password_salt = SecretString("op://Homelab/PBS daan/salt")

SecretString.populate_cache_sync()
