import asyncio
from op_secrets import SecretString

user_password = SecretString("op://Homelab/Proxmox VE daan/password")
user_password_salt = SecretString("op://Homelab/Proxmox VE daan/salt")

SecretString.populate_cache_sync()
