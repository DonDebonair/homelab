from group_data.all import domain, pbs_fqdn

hostname = "pve"
hostname_fqdn = f"{hostname}.{domain}"

# --- Backups to PBS ----------------------------------------------------------
# PBS API token secret lives in 1Password (see
# deploys/proxmox_host/backups/secrets.py).
#
# The storage deliberately pins no certificate fingerprint: PBS serves a
# publicly-trusted Let's Encrypt certificate, so PVE verifies it against the
# system CA store. A pinned fingerprint would have to be re-set by hand after
# every ACME renewal, and a stale pin fails the storage closed ("fingerprint
# ... not verified"), taking every backup job down with it. Verification is by
# name for the same reason -- the certificate's only SAN is DNS:pbs.dv.zone,
# so connecting to the bare IP would fail the hostname check.
pbs_backup_storage_id = "pbs"
pbs_backup_server = pbs_fqdn
pbs_backup_datastore = "synology"
pbs_backup_token_id = "pve@pbs!backup"

postgres_lxc_vmid = 100  # created by deploys/proxmox_host/lxcs
palworld_lxc_vmid = 101  # created by deploys/proxmox_host/lxcs
docker_vm_vmid = 200  # the docker_vm is created manually in PVE
# The Palworld container is in here for its save data: the world is the only thing
# on it that can't be re-downloaded from Steam.
backup_vmids = [postgres_lxc_vmid, palworld_lxc_vmid, docker_vm_vmid]
backup_schedule = "02:00"
backup_mode = "snapshot"
backup_prune = "keep-last=3,keep-daily=7,keep-weekly=4,keep-monthly=2"
