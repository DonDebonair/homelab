# Tunables for the Palworld dedicated server (deploys/palworld_lxc/palworld). The filesystem
# layout and Steam app id live in that package's vars.py; what you would actually want to change
# lives here.

palworld_server_name = "Catgirl & Dandy's Palworld Server"
palworld_server_description = "Private server - ask Daan for the password"
palworld_max_players = 32

# UDP 8211 is the only port the router forwards; RCON is LAN-only (the server has no setting to
# bind it to loopback, so it listens on all interfaces -- do not forward it).
palworld_game_port = 8211
palworld_rcon_port = 25575

# The server leaks memory for as long as a world stays loaded, so it gets restarted nightly.
# Zone is explicit because the container's clock is UTC; systemd >= 252 accepts it inline.
palworld_restart_on_calendar = "*-*-* 05:00:00 Europe/Amsterdam"

# The engine writes a full world snapshot every ~30s while a player is online and never removes
# one, so the save directory grows without bound. Level.sav is tens of KB for a fresh world but
# routinely 20-60 MB once bases are built, which at ~120 snapshots per hour of play is GB/day.
#
# Keeping 48 bounds the worst case at roughly 48 x 60 MB ~= 3 GB on a 32 GB rootfs, and still
# leaves ~25 minutes of play to roll back through. Anything longer-horizon is what the nightly
# vzdump to PBS is for -- these snapshots are for "undo the last few minutes", not for archival.
palworld_save_backup_keep = 48
# Every 15 minutes rather than hourly: the prune is a directory listing, and a longer interval
# just means more snapshots piled up between runs.
palworld_save_prune_on_calendar = "*:0/15"
