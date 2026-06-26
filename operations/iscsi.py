import re

from pyinfra import host
from pyinfra.api import HiddenValue, QuoteString, StringCommand, operation
from pyinfra.facts.files import FindInFile

from facts.iscsi import ISCSISessions


@operation()
def connect(
        target_iqn: str,
        portal: str,
        chap_user: str,
        chap_password: str,
        present: bool = True,
):
    """
    Connect to (or disconnect from) an iSCSI target with CHAP authentication,
    configuring the node for automatic startup so it reconnects on boot.

    Idempotency is keyed on whether a session for ``target_iqn`` is already
    active (``ISCSISessions``); CHAP/node configuration is (re)applied only when
    establishing a new session.

    Args:
        target_iqn: The target IQN, e.g. ``iqn.2000-01.com.synology:DS.Target-1``
        portal: The iSCSI portal address (Synology IP, optionally ``ip:port``)
        chap_user: CHAP username configured on the target
        chap_password: CHAP password configured on the target
        present: Whether the session should exist (True) or be torn down (False)
    """
    sessions = host.get_fact(ISCSISessions, _sudo=True)
    is_present = bool(sessions and target_iqn in sessions)
    node = ["iscsiadm", "-m", "node", "-T", QuoteString(target_iqn), "-p", QuoteString(portal)]

    if present and not is_present:
        yield StringCommand("iscsiadm", "-m", "discovery", "-t", "sendtargets", "-p", QuoteString(portal))
        yield StringCommand(*node, "-o", "update", "-n", "node.session.auth.authmethod", "-v", "CHAP")
        yield StringCommand(*node, "-o", "update", "-n", "node.session.auth.username", "-v", QuoteString(chap_user))
        yield StringCommand(*node, "-o", "update", "-n", "node.session.auth.password",
                            "-v", QuoteString(HiddenValue(str(chap_password))))
        yield StringCommand(*node, "-o", "update", "-n", "node.startup", "-v", "automatic")
        yield StringCommand(*node, "--login")
    elif not present and is_present:
        yield StringCommand(*node, "--logout")
        yield StringCommand(*node, "-o", "delete")
    elif present and is_present:
        host.noop(f"iSCSI session for '{target_iqn}' is already active.")
        return
    else:
        host.noop(f"iSCSI session for '{target_iqn}' does not exist and 'present' is False.")
        return


def _detect_device(target_iqn: str) -> str:
    """
    Shell snippet that resolves the block device backing ``target_iqn`` at
    execution time (the device name for a freshly logged-in target is only
    knowable then, not when facts are gathered) and exposes ``$device`` /
    ``$partition``. Shared by the format and mount scripts.
    """
    return f"""target_iqn='{target_iqn}'
device=$(iscsiadm -m session -P 3 | awk -v t="$target_iqn" '$1=="Target:"{{cur=$2}} cur==t && /Attached scsi disk/{{for(i=1;i<=NF;i++) if($i=="disk") print "/dev/"$(i+1)}}' | head -n1)
if [ -z "$device" ]; then echo "No iSCSI device found for $target_iqn" >&2; exit 1; fi
partition="${{device}}1\""""


def _format_script(target_iqn: str, fs_type: str) -> str:
    """GPT-partition and format the device, but only if it has no filesystem."""
    return f"""set -e
fs_type='{fs_type}'
{_detect_device(target_iqn)}
if blkid -s UUID -o value "$partition" >/dev/null 2>&1; then
    echo "$partition already has a filesystem; refusing to reformat" >&2
    exit 0
fi
parted "$device" --script mklabel gpt
parted "$device" --script mkpart primary "$fs_type" 0% 100%
udevadm settle || sleep 3
mkfs."$fs_type" "$partition\""""


def _mount_script(target_iqn: str, mount_path: str, fs_type: str) -> str:
    """Add a UUID-based fstab entry for the device's partition and mount it."""
    return f"""set -e
mount_path='{mount_path}'
fs_type='{fs_type}'
{_detect_device(target_iqn)}
uuid=$(blkid -s UUID -o value "$partition")
if [ -z "$uuid" ]; then echo "Could not determine UUID for $partition" >&2; exit 1; fi
cp /etc/fstab "/etc/fstab.backup.$(date +%Y%m%d-%H%M%S)"
sed -i "\\|[[:space:]]${{mount_path}}[[:space:]]|d" /etc/fstab
echo "UUID=${{uuid}} ${{mount_path}} ${{fs_type}} _netdev,nofail,x-systemd.device-timeout=30 0 2" >> /etc/fstab
mkdir -p "$mount_path"
mountpoint -q "$mount_path" || mount "$mount_path\""""


@operation()
def format(
        target_iqn: str,
        mount_path: str,
        fs_type: str = "ext4",
):
    """
    Partition and format the block device backing an iSCSI target. **This is the
    only destructive operation** and is doubly guarded: it is skipped entirely
    once the datastore is provisioned (``mount_path`` present in ``/etc/fstab``),
    and the emitted script additionally refuses to touch a device that already
    carries a filesystem. Run once, on a raw LUN.

    Args:
        target_iqn: The target IQN whose attached disk should be formatted
        mount_path: Datastore mount path, used as the "already provisioned" guard
        fs_type: Filesystem to create (ext4 by default)
    """
    fstab_matches = host.get_fact(
        FindInFile, path="/etc/fstab", pattern=re.escape(mount_path), _sudo=True
    )
    if fstab_matches:
        host.noop(f"LUN for '{mount_path}' is already provisioned (present in /etc/fstab).")
        return

    yield StringCommand(_format_script(target_iqn, fs_type))


@operation()
def mount(
        target_iqn: str,
        mount_path: str,
        fs_type: str = "ext4",
):
    """
    Add a UUID-based ``/etc/fstab`` entry for the iSCSI device's partition and
    mount it. Non-destructive and safe to re-run; keyed on whether ``mount_path``
    already has an fstab entry.

    Args:
        target_iqn: The target IQN whose attached disk should be mounted
        mount_path: Where to mount the filesystem, e.g. ``/mnt/synology``
        fs_type: Filesystem type for the fstab entry (ext4 by default)
    """
    fstab_matches = host.get_fact(
        FindInFile, path="/etc/fstab", pattern=re.escape(mount_path), _sudo=True
    )
    if fstab_matches:
        host.noop(f"Mount '{mount_path}' is already configured in /etc/fstab.")
        return

    yield StringCommand(_mount_script(target_iqn, mount_path, fs_type))
