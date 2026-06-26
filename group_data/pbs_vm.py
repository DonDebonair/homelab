# Per-group data for the Proxmox Backup Server VM.
# Shared defaults (user, ssh_public_key, names, ...) come from group_data/all.py.
# Add PBS-specific variables (datastores, etc.) here as the deploy grows.
from group_data.all import domain, nas_ip

hostname = "pbs"
hostname_fqdn = f"{hostname}.{domain}"

# Synology iSCSI LUN used as a PBS datastore. The LUN/target (with CHAP) is
# created on the Synology side; CHAP credentials live in 1Password (see
# deploys/pbs_vm/datastore/secrets.py). Set iscsi_target_iqn to the IQN shown in
# Synology SAN Manager after creating the target.
iscsi_target_iqn = "iqn.2000-01.com.synology:NASty.default-target.780e544d140"
iscsi_portal_ip = nas_ip
iscsi_mount_path = "/mnt/synology"
iscsi_datastore_name = "synology"
