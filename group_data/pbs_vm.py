# Per-group data for the Proxmox Backup Server VM.
# Shared defaults (user, ssh_public_key, names, ...) come from group_data/all.py.
# Add PBS-specific variables (datastores, etc.) here as the deploy grows.
from group_data.all import domain

hostname = "pbs"
hostname_fqdn = f"{hostname}.{domain}"
