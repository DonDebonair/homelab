from op_secrets import SecretString

user_password = SecretString("op://Homelab/PostgreSQL LXC daan/password")
user_password_salt = SecretString("op://Homelab/PostgreSQL LXC daan/salt")

SecretString.populate_cache_sync()
