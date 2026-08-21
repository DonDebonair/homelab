ssh_public_key = "/Users/daan/.ssh/id_ed25519.pub"
firstname = "Daan"
lastname = "Debie"
email = "daan@dv.email"
user = "daan"
home = f"/home/{user}"
nas_ip = "192.168.1.21"
proxmox_ip = "192.168.1.22"
postgres_lxc_ip = "192.168.1.41"
pbs_ip = "192.168.1.51"
domain = "dv.zone"

# PBS is addressed by name (not IP) wherever TLS is verified: its Let's Encrypt
# certificate only carries DNS:pbs.dv.zone as a SAN.
pbs_fqdn = f"pbs.{domain}"

# Loki's address on the macvlan (physical LAN) network, so *other* hosts -- e.g.
# Docker containers still running on the NAS -- can push logs to it directly.
# Must be a free LAN IP outside the router's DHCP pool (cf. .20/.21/.30/.11).
loki_macvlan_ip = "192.168.50.31"
