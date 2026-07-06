from pyinfra.api import deploy

from operations import synology
from deploys.nas.users import secrets

# NFS identity for the docker_vm. Containers there run as the VM's docker user
# (uid 2000, see group_data/docker_vm.py `docker_uid`), and NFS maps access by
# numeric id -- so the NAS needs an account at that same uid for the docker_vm
# to read/write shared folders (e.g. /volume1/entertainment/torrents). synouser
# auto-assigns a uid on creation, so the operation pins it to 2000 (persisted
# via `synouser --rebuild all`; verified stable on DSM). Primary group stays
# `users` (gid 100); ACLs are granted to this named user per shared folder.
DOCKER_VM_USER = "dockervm"
DOCKER_VM_UID = 2000

# Homepage `diskstation` widget account. Resolve the username to a plain str: the
# `synogroup --member` op joins the member list, and str.join reads a
# SecretString's underlying value (the op:// reference), not its resolved __str__
# -- so a SecretString member would emit the reference. The password stays a
# SecretString (the user op interpolates it via an f-string, which resolves).
WIDGET_USER = str(secrets.synology_widget_username)


@deploy("Ensure NAS service users exist")
def setup_users():
    synology.user(
        name=f"Ensure '{DOCKER_VM_USER}' NFS service user exists (uid {DOCKER_VM_UID})",
        user=DOCKER_VM_USER,
        uid=DOCKER_VM_UID,
        present=True,
        _sudo=True,
    )

    # DSM admin account the Homepage diskstation widget logs in as. The widget
    # reads system/storage APIs that require admin rights, so the user is added
    # to the built-in `administrators` group. 2FA must be disabled for this
    # account by hand in DSM -- the widget can't complete a 2FA challenge.
    synology.user(
        name="Ensure Synology homepage widget user exists",
        user=WIDGET_USER,
        password=secrets.synology_widget_password,
        present=True,
        _sudo=True,
    )
    synology.group_members(
        name="Add homepage widget user to 'administrators'",
        group="administrators",
        members=[WIDGET_USER],
        add=True,
        _sudo=True,
    )
