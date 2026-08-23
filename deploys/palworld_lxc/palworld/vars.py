"""Filesystem layout and identifiers for the Palworld dedicated server.

Tunables (server name, ports, player cap, restart schedule) live in group_data/palworld_lxc.py.
"""

# Steam's application id for the Palworld *dedicated server* (the game itself is 1623730).
PALWORLD_APP_ID = 2394010

# Unprivileged account the server and every steamcmd invocation run as. Steam refuses to run
# as root, and there is no reason for a public-facing game server to have more than this.
SERVICE_USER = "palworld"
SERVICE_GROUP = "palworld"

HOME_DIR = "/opt/palworld"
STEAMCMD_DIR = f"{HOME_DIR}/steamcmd"
SERVER_DIR = f"{HOME_DIR}/server"
BIN_DIR = f"{HOME_DIR}/bin"

STEAMCMD_TARBALL = f"{STEAMCMD_DIR}/steamcmd_linux.tar.gz"
STEAMCMD_SH = f"{STEAMCMD_DIR}/steamcmd.sh"
PALSERVER_SH = f"{SERVER_DIR}/PalServer.sh"

# Where the server reads its runtime configuration. The engine generates this on first boot by
# copying DefaultPalWorldSettings.ini; we write it ourselves instead, so the settings are
# declarative rather than whatever the last person edited by hand.
SAVED_DIR = f"{SERVER_DIR}/Pal/Saved"
CONFIG_DIR = f"{SAVED_DIR}/Config/LinuxServer"
SETTINGS_FILE = f"{CONFIG_DIR}/PalWorldSettings.ini"

RCON_SCRIPT = f"{BIN_DIR}/palworld-rcon"
