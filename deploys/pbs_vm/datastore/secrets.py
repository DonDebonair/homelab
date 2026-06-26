from op_secrets import SecretString

chap_username = SecretString("op://Homelab/Synology iSCSI PBS/username")
chap_password = SecretString("op://Homelab/Synology iSCSI PBS/password")

SecretString.populate_cache_sync()
