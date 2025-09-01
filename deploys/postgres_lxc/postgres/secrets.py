from op_secrets import SecretString

postgres_password = SecretString("op://Homelab/Homelab PostgreSQL DB/password")

SecretString.populate_cache_sync()
