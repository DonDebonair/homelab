from op_secrets import SecretString

# Shared secret between the docker_vm Portainer server and this NAS agent; must
# match portainer_agent_secret on the server (deploys/docker_vm/apps/secrets.py).
portainer_agent_secret = SecretString("op://Homelab/Portainer/shared agent secret")

SecretString.populate_cache_sync()
