from op_secrets import SecretString

cloudflare_api_token = SecretString("op://Homelab/Cloudflare/apikey")

SecretString.populate_cache_sync()
