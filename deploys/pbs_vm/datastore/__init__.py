from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import apt, files, server

import operations.iscsi as iscsi
import operations.proxmox.pbs as pbs
from deploys.pbs_vm.datastore import secrets

ISCSI_MODULES = ["iscsi_tcp", "scsi_transport_iscsi"]


@deploy("Configure Synology iSCSI datastore")
def configure_datastore():
    apt.packages(
        name="Install iSCSI and partitioning tools",
        packages=["open-iscsi", "parted"],
        _sudo=True,
    )

    for module in ISCSI_MODULES:
        server.modprobe(
            name=f"Load kernel module {module}",
            module=module,
            _sudo=True,
        )
        files.line(
            name=f"Persist kernel module {module} across reboots",
            path="/etc/modules",
            line=module,
            _sudo=True,
        )

    files.replace(
        name="Configure iSCSI nodes for automatic startup",
        path="/etc/iscsi/iscsid.conf",
        text=r"^node.startup = manual",
        replace="node.startup = automatic",
        _sudo=True,
    )

    server.service(
        name="Ensure iscsid is enabled and running",
        service="iscsid",
        running=True,
        enabled=True,
        _sudo=True,
    )

    iscsi.connect(
        name="Connect to the Synology iSCSI target",
        target_iqn=host.data.iscsi_target_iqn,
        portal=host.data.iscsi_portal_ip,
        chap_user=str(secrets.chap_username),
        chap_password=str(secrets.chap_password),
        _sudo=True,
    )

    iscsi.format(
        name="Format the iSCSI LUN (first run only, on a raw device)",
        target_iqn=host.data.iscsi_target_iqn,
        mount_path=host.data.iscsi_mount_path,
        _sudo=True,
    )

    iscsi.mount(
        name="Mount the iSCSI LUN and persist it in fstab",
        target_iqn=host.data.iscsi_target_iqn,
        mount_path=host.data.iscsi_mount_path,
        _sudo=True,
    )

    pbs.datastore(
        name="Create the Synology PBS datastore",
        datastore_name=host.data.iscsi_datastore_name,
        path=host.data.iscsi_mount_path,
        _sudo=True,
    )
