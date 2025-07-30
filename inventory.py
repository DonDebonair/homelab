from op_secrets import SecretString

sudo_password_daan = SecretString("op://Homelab/Proxmox VE daan/password")
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
    ("192.168.1.22", {"ssh_user": "daan", "_sudo_password": str(sudo_password_daan)})
]
