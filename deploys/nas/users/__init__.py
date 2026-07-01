from pyinfra.api import deploy

from operations import synology

# NFS identity for the docker_vm. Containers there run as the VM's docker user
# (uid 2000, see group_data/docker_vm.py `docker_uid`), and NFS maps access by
# numeric id -- so the NAS needs an account at that same uid for the docker_vm
# to read/write shared folders (e.g. /volume1/entertainment/torrents). synouser
# auto-assigns a uid on creation, so the operation pins it to 2000 (persisted
# via `synouser --rebuild all`; verified stable on DSM). Primary group stays
# `users` (gid 100); ACLs are granted to this named user per shared folder.
DOCKER_VM_USER = "dockervm"
DOCKER_VM_UID = 2000


@deploy("Ensure NAS service users exist")
def setup_users():
    synology.user(
        name=f"Ensure '{DOCKER_VM_USER}' NFS service user exists (uid {DOCKER_VM_UID})",
        user=DOCKER_VM_USER,
        uid=DOCKER_VM_UID,
        present=True,
        _sudo=True,
    )
