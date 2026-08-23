from op_secrets import SecretString

sudo_password_proxmox_ve_daan = SecretString("op://Homelab/Proxmox VE daan/password")
sudo_password_postgres_lxc_daan = SecretString("op://Homelab/PostgreSQL LXC daan/password")
sudo_password_docker_vm_daan = SecretString("op://Homelab/Docker VM daan/password")
sudo_password_pbs_vm_daan = SecretString("op://Homelab/PBS daan/password")
sudo_password_palworld_lxc_daan = SecretString("op://Homelab/Palworld LXC daan/password")
SecretString.populate_cache_sync()

nas = [
    ("192.168.1.21", {
        "ssh_file_transfer_protocol": "scp",
        "ssh_port": 22910,
        "ssh_user": "daanadmin",
        "_env": {
            "PATH": "/sbin:/bin:/usr/sbin:/usr/bin:/usr/syno/sbin:/usr/syno/bin:/usr/local/sbin:/usr/local/bin"
        }
    })
]
proxmox_host = [
    # First time running this, you need to set up SSH keys and allow root login. After that, you can change the user.
    ("192.168.1.22", {"ssh_user": "daan", "_sudo_password": str(sudo_password_proxmox_ve_daan)})
]
postgres_lxc = [
    # First time running this, you need to set up SSH keys and allow root login. After that, you can change the user.
    ("192.168.1.41", {"ssh_user": "daan", "_sudo_password": str(sudo_password_postgres_lxc_daan)})
]
palworld_lxc = [
    # Unlike the hosts above, this LXC needs no manual SSH/root prep: `pct create --ssh-public-keys`
    # (deploys/proxmox_host/lxcs) seeds root's authorized_keys, and root has no password at all.
    #
    # The bootstrap is two passes, because the Debian LXC template ships without a sudo binary and
    # pyinfra gathers *all* facts up front -- so common_debian_setup's sudo-requiring facts fail on a
    # bare container no matter that an apt.packages(["sudo"]) is queued ahead of them. Pass 1 runs
    # only the users deploy, as root, which installs sudo and creates the user:
    #
    #   uv run pyinfra inventory.py --limit palworld_lxc --data ssh_user=root deploys.palworld_lxc.users.users -y
    #   uv run pyinfra inventory.py --limit palworld_lxc deploy.py -y
    #
    # Pass 2 (and every run after) goes through daan below. The second one also sets PermitRootLogin
    # no, closing the door pass 1 came in through; `pct enter 101` on the PVE host stays as the
    # out-of-band way back in.
    ("192.168.1.42", {"ssh_user": "daan", "_sudo_password": str(sudo_password_palworld_lxc_daan)})
]
docker_vm = [
    # First time running this, you need to set up SSH keys and allow root login. After that, you can change the user.
    ("192.168.50.10", {"ssh_user": "daan", "_sudo_password": str(sudo_password_docker_vm_daan)})
]
pbs_vm = [
    # First time running this, you need to set up SSH keys and allow root login. After that, you can change the user.
    ("192.168.1.51", {"ssh_user": "daan", "_sudo_password": str(sudo_password_pbs_vm_daan)})
]
