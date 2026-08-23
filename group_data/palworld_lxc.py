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
