from pyinfra.api import deploy
from pyinfra.operations import files


@deploy("Setup VMs")
def setup_vms():
    # Download Debian 13 ISO if it doesn't exist in /var/lib/vz/template/iso
    # ISO URL: https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.0.0-amd64-netinst.iso
    # SHA256: e363cae0f1f22ed73363d0bde50b4ca582cb2816185cf6eac28e93d9bb9e1504
    files.download(
        name="Download Debian 13 ISO if not present",
        src="https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.0.0-amd64-netinst.iso",
        dest="/var/lib/vz/template/iso/debian-13.0.0-amd64-netinst.iso",
        sha256sum="e363cae0f1f22ed73363d0bde50b4ca582cb2816185cf6eac28e93d9bb9e1504",
        user="root",
        group="root",
        mode="644",
        _sudo=True,
    )

    # I initially wanted to add operations for creating VMs on Proxmox and use those here to setup the Docker VM.
    # However, when using Debian netinst ISO, the installation process requires interactive input, which is quite
    # hard to automate.
    # Alternatively, I could use cloud-init, which requires the Debian cloud image. This is not an ISO, but a qcow2
    # disk image. It can be used to setup a template VM, which can then be cloned to create new VMs.
    # The drawback of this approach is that the template VM has a set disk size, which cannot be changed when
    # cloning. So if I want a VM with a different disk size, I need to change the disk size after cloning, which is
    # another complex operation which is probably very hard to automate.
    # Ultimately, I decided to manually create the Docker VM using the Proxmox web interface. This is a one-time
    # operation, after which I can use pyinfra to manage the VM.
    # Automating VM creation is probably a waste of time, since I don't need many different VMs.
    #
    # References:
    # - Debian netinst ISO: https://www.debian.org/distrib/netinst
    # - Debian cloud images: https://cloud.debian.org/images/cloud/
    # - Example of using cloud-init with Proxmox and Debian 13: https://github.com/UntouchedWagons/Ubuntu-CloudInit-Docs/blob/main/samples/debian/debian-13-cloudinit.sh
    