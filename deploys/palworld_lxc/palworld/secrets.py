from op_secrets import SecretString

# The field part of an op:// reference matches the field's *label*, spaces and all -- not the
# underscore-cased id you might expect (1Password gives custom fields a generated uuid for an id).
#
# Palworld uses AdminPassword as the RCON password too, so there is no third secret here.
admin_password = SecretString("op://Homelab/Palworld Server/admin password")
server_password = SecretString("op://Homelab/Palworld Server/server password")

SecretString.populate_cache_sync()
