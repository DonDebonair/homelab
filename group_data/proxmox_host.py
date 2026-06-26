from group_data.all import domain

hostname = "pve"
hostname_fqdn = f"{hostname}.{domain}"

# --- Backups to PBS ----------------------------------------------------------
# PBS API token secret lives in 1Password (see
# deploys/proxmox_host/backups/secrets.py). Fill in the fingerprint (from
# `proxmox-backup-manager cert info` on PBS) and the docker_vm VMID.
pbs_backup_storage_id = "pbs"
pbs_backup_datastore = "synology"
pbs_backup_token_id = "pve@pbs!backup"
pbs_fingerprint = "38:d4:52:64:13:01:5a:d1:5a:1d:bb:3e:ab:11:af:d9:ae:4b:79:94:25:d5:fb:1f:c5:40:44:97:5e:95:2b:1f"

postgres_lxc_vmid = 100  # created by deploys/proxmox_host/lxcs
docker_vm_vmid = 200  # the docker_vm is created manually in PVE
backup_vmids = [postgres_lxc_vmid, docker_vm_vmid]
backup_schedule = "02:00"
backup_mode = "snapshot"
backup_prune = "keep-last=3,keep-daily=7,keep-weekly=4,keep-monthly=2"
