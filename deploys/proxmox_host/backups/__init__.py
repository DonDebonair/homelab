from pyinfra import host
from pyinfra.api import deploy

import operations.proxmox.pve as pve
from models.proxmox import PVEBackupMode
from deploys.proxmox_host.backups import secrets


@deploy("Configure PVE backups to PBS")
def configure_backups():
    pve.storage(
        name="Register the PBS datastore as PVE storage",
        storage_id=host.data.pbs_backup_storage_id,
        storage_type="pbs",
        server=host.data.pbs_ip,
        datastore=host.data.pbs_backup_datastore,
        username=host.data.pbs_backup_token_id,
        password=str(secrets.token_secret),
        fingerprint=host.data.pbs_fingerprint,
        _sudo=True,
    )
    pve.backup_job(
        name="Schedule the vzdump backup job to PBS",
        job_id="pve-to-pbs",
        storage=host.data.pbs_backup_storage_id,
        vmid=host.data.backup_vmids,
        schedule=host.data.backup_schedule,
        mode=PVEBackupMode(host.data.backup_mode),
        notes_template="{{guestname}}",
        prune_backups=host.data.backup_prune,
        _sudo=True,
    )
