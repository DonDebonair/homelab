from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server, systemd

templates_dir = Path(__file__).resolve().parent / "templates"


@deploy("Publish PBS backup age metrics")
def setup_backup_metrics():
    """
    Publish each guest's last completed backup time through node-exporter's textfile
    collector, so an alert can catch backups that have stopped. It reads the datastore
    rather than task history because a finished snapshot is what actually matters.
    """
    script = files.template(
        name="Install the backup metrics script",
        src=str(templates_dir / "pbs-backup-metrics.py.j2"),
        dest="/usr/local/bin/pbs-backup-metrics",
        mode="0755",
        user="root",
        group="root",
        datastore_name=host.data.iscsi_datastore_name,
        datastore_path=host.data.iscsi_mount_path,
        vmids=host.data.backup_vmids,
        _sudo=True,
    )
    service = files.template(
        name="Install the backup metrics service",
        src=str(templates_dir / "pbs-backup-metrics.service.j2"),
        dest="/etc/systemd/system/pbs-backup-metrics.service",
        _sudo=True,
    )
    timer = files.template(
        name="Install the backup metrics timer",
        src=str(templates_dir / "pbs-backup-metrics.timer.j2"),
        dest="/etc/systemd/system/pbs-backup-metrics.timer",
        _sudo=True,
    )
    server.shell(
        name="Reload systemd after writing the backup metrics units",
        commands=["systemctl daemon-reload"],
        _sudo=True,
        _if=lambda: service.did_change() or timer.did_change(),
    )
    systemd.service(
        name="Enable and start the backup metrics timer",
        service="pbs-backup-metrics.timer",
        running=True,
        enabled=True,
        _sudo=True,
    )
    server.shell(
        name="Publish the backup metrics now",
        commands=["systemctl start pbs-backup-metrics.service"],
        _sudo=True,
        _if=script.did_change,
    )
