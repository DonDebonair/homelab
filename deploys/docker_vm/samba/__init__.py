from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.server import Command
from pyinfra.operations import apt, files, server, systemd

from deploys.docker_vm.samba import secrets

templates_dir = Path(__file__).resolve().parent / "templates"

# SMB share the Brother scanner writes into and the dedicated account it
# authenticates as. The share itself is exposed as the docker apps user so the
# Paperless consumer can read and delete what the scanner drops.
SHARE_NAME = "paperless-consume"
SCANNER_USER = "scanner"


def _scanner_smb_password_unset() -> bool:
    """True when the `scanner` Samba account has no passdb entry yet."""
    out = host.get_fact(
        Command,
        command=f"pdbedit -L -u {SCANNER_USER} >/dev/null 2>&1 && echo EXISTS || true",
    )
    text = out if isinstance(out, str) else "".join(out or [])
    return "EXISTS" not in text


@deploy("Setup Samba scan-to-consume share")
def setup_samba():
    """
    Expose the Paperless consume inbox over SMB so the Brother MFC-L8690CDW can
    scan documents straight into it (mirrors how the scanner fed Paperless when
    it ran on the Synology NAS).

    The consume directory itself is created and owned (uid/gid = docker_uid) by
    the Paperless ComposeApp bind mount in `deploys/docker_vm/apps`. Here we only
    layer SMB access on top:

    - a no-login `scanner` system account the printer authenticates as, and
    - a share with `force user`/`force group` set to the docker apps user, so
      every file the scanner writes is owned by the Paperless consumer
      (USERMAP_UID/GID) and gets read + deleted as expected.

    The printer connects by IP to 192.168.50.10, share `paperless-consume`.
    """
    consume_path = f"{host.data.docker_volumes_base}/paperless/consume"

    apt.packages(
        name="Install Samba",
        packages=["samba"],
        _sudo=True,
    )

    # No-login account purely for SMB authentication; file access is remapped to
    # the docker apps user via `force user` in the share config.
    server.user(
        name=f"Ensure '{SCANNER_USER}' system user exists",
        user=SCANNER_USER,
        system=True,
        create_home=False,
        shell="/usr/sbin/nologin",
        _sudo=True,
    )

    config = files.template(
        name="Install smb.conf",
        src=str(templates_dir / "smb.conf.j2"),
        dest="/etc/samba/smb.conf",
        share_name=SHARE_NAME,
        consume_path=consume_path,
        scanner_user=SCANNER_USER,
        force_user=host.data.docker_user,
        force_group=host.data.default_group,
        _sudo=True,
    )

    # Set the Samba password only when the account isn't in the passdb yet, so
    # the deploy stays idempotent. To rotate, run `smbpasswd scanner` on the host
    # (or `pdbedit -x scanner` then redeploy).
    server.shell(
        name=f"Set Samba password for '{SCANNER_USER}'",
        commands=[
            "printf '%s\\n%s\\n' "
            f"'{secrets.scanner_smb_password}' '{secrets.scanner_smb_password}' "
            f"| smbpasswd -s -a {SCANNER_USER}"
        ],
        _sudo=True,
        _if=_scanner_smb_password_unset,
    )

    systemd.service(
        name="Enable and start smbd",
        service="smbd",
        running=True,
        enabled=True,
        _sudo=True,
    )

    server.shell(
        name="Reload smbd after config change",
        commands=["systemctl reload smbd"],
        _sudo=True,
        _if=config.did_change,
    )
