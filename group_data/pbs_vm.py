# Per-group data for the Proxmox Backup Server VM.
# Shared defaults (user, ssh_public_key, names, ...) come from group_data/all.py.
# Add PBS-specific variables (datastores, etc.) here as the deploy grows.
from group_data.all import domain, nas_ip
from group_data.proxmox_host import backup_vmids as proxmox_backup_vmids

hostname = "pbs"
hostname_fqdn = f"{hostname}.{domain}"

# The guests whose backups should exist in PBS. Assigned rather than just imported, because
# pyinfra leaves imported names out of group data.
backup_vmids = proxmox_backup_vmids

# Synology iSCSI LUN used as a PBS datastore. The LUN/target (with CHAP) is
# created on the Synology side; CHAP credentials live in 1Password (see
# deploys/pbs_vm/datastore/secrets.py). Set iscsi_target_iqn to the IQN shown in
# Synology SAN Manager after creating the target.
iscsi_target_iqn = "iqn.2000-01.com.synology:NASty.default-target.780e544d140"
iscsi_portal_ip = nas_ip
iscsi_mount_path = "/mnt/synology"
iscsi_datastore_name = "synology"
# Pruning only drops snapshot indexes; GC is what frees the chunks. It has to be scheduled
# explicitly, and without it the datastore fills up and every backup fails. Runs after the
# 02:00 backup job (group_data/proxmox_host.py) and its prune have finished.
iscsi_datastore_gc_schedule = "05:00"
