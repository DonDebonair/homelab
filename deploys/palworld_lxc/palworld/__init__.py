from pathlib import Path

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, server, systemd

from deploys.palworld_lxc.palworld import secrets
from deploys.palworld_lxc.palworld.vars import (
    BIN_DIR, CONFIG_DIR, HOME_DIR, PALSERVER_SH, PALWORLD_APP_ID, RCON_SCRIPT, SAVED_DIR,
    SERVER_DIR, SERVICE_GROUP, SERVICE_USER, SETTINGS_FILE, STEAMCMD_DIR, STEAMCMD_SH,
    STEAMCMD_TARBALL,
)

templates_dir = Path(__file__).resolve().parent / "templates"


def _ini_safe(label: str, value: str) -> str:
    """
    Guard the two secrets that get interpolated into PalWorldSettings.ini.

    The engine's OptionSettings is one flat, comma-separated list of double-quoted values with no
    escaping whatsoever, so a password containing `"` or `,` does not fail loudly -- it truncates
    the setting and every setting after it silently reverts to a default. A server that quietly
    drops its own password is worth one assertion.
    """
    if '"' in value or "," in value:
        raise ValueError(f"{label} must not contain a double quote or a comma (PalWorldSettings.ini "
                         f"has no escaping); regenerate it in 1Password without those characters")
    return value


@deploy("Install Palworld dedicated server")
def setup_palworld_server():
    """
    Install SteamCMD and the Palworld dedicated server (Steam app 2394010), configure it, and run
    it under systemd with a nightly restart.

    Debian carries `steamcmd` only in non-free, and this container's sources are main + contrib,
    so rather than widen the archive for one package we use Valve's own tarball -- which is what
    the Palworld docs point at anyway. The launcher inside it is a 32-bit ELF, hence lib32gcc-s1
    and lib32stdc++6; those are ordinary amd64 packages carrying 32-bit runtimes, so no
    `dpkg --add-architecture i386` is needed.
    """
    apt.packages(
        name="Install SteamCMD runtime dependencies",
        # xdg-user-dirs: steamcmd shells out to xdg-user-dir and logs noisy errors without it.
        packages=["lib32gcc-s1", "lib32stdc++6", "ca-certificates", "xdg-user-dirs"],
        update=True,
        cache_time=3600,
        _sudo=True,
    )
    server.group(
        name=f"Ensure '{SERVICE_GROUP}' group exists",
        group=SERVICE_GROUP,
        system=True,
        _sudo=True,
    )
    server.user(
        name=f"Ensure '{SERVICE_USER}' service user exists",
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        home=HOME_DIR,
        # Steam writes ~/.steam and ~/.local regardless of --force_install_dir, so it needs a
        # real home. No login shell: nothing should ever be sitting on this account.
        shell="/usr/sbin/nologin",
        system=True,
        create_home=True,
        _sudo=True,
    )
    # Every level of the Pal/Saved chain is listed explicitly rather than relying on the leaf to
    # pull its parents into being. files.directory shells out to `mkdir -p`, which creates missing
    # *parents* as root and applies user/group only to the final component -- so creating just
    # CONFIG_DIR leaves Pal/Saved owned by root. The server can still write its config (the leaf is
    # its own), but the engine creates SaveGames/ and Logs/ inside Saved/ at runtime, and it cannot
    # mkdir in a root-owned directory. The failure is silent and vicious: the server starts, binds
    # the port, answers RCON and completes the UDP handshake, but never creates a world, so clients
    # sit on an endless black screen and nothing whatsoever appears in the server log.
    for directory in (
        HOME_DIR, STEAMCMD_DIR, SERVER_DIR, BIN_DIR,
        f"{SERVER_DIR}/Pal", SAVED_DIR, f"{SAVED_DIR}/Config", CONFIG_DIR,
    ):
        files.directory(
            name=f"Ensure {directory} exists",
            path=directory,
            user=SERVICE_USER,
            group=SERVICE_GROUP,
            mode="750",
            _sudo=True,
        )
    # Deliberately unpinned, unlike the other files.download calls in this repo: Valve rolls this
    # tarball forward in place and publishes no checksum, so a sha256sum here would break the
    # deploy the next time they rebuild it. Without one, files.download is idempotent on the
    # destination existing -- and steamcmd self-updates on every run anyway, so a stale tarball
    # only ever matters for the very first bootstrap.
    files.download(
        name="Download SteamCMD",
        src="https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz",
        dest=STEAMCMD_TARBALL,
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        mode="640",
        _sudo=True,
    )
    server.shell(
        name="Extract SteamCMD",
        commands=[f"tar -xzf {STEAMCMD_TARBALL} -C {STEAMCMD_DIR}"],
        # _sudo on the fact, not just the command: /opt/palworld is 0750 palworld:palworld, so
        # the unprivileged deploy user cannot stat inside it. Without this the fact comes back
        # empty, the guard is always true, and the extract re-runs on every deploy.
        _if=lambda: not host.get_fact(File, path=STEAMCMD_SH, _sudo=True),
        _sudo=True,
        _sudo_user=SERVICE_USER,
    )
    # Only on first install. app_update is idempotent, but it is also a ~5 GB integrity pass
    # against Valve's CDN; running it on every deploy would make a routine converge run take
    # minutes and pointlessly rewrite game files under a live server. Updates are handled at
    # service start instead -- see ExecStartPre in the unit.
    server.shell(
        name="Install the Palworld dedicated server via SteamCMD",
        commands=[
            f"{STEAMCMD_SH} +force_install_dir {SERVER_DIR} "
            f"+login anonymous +app_update {PALWORLD_APP_ID} validate +quit"
        ],
        # Same reason as the extract above -- and here the cost of getting it wrong is a full
        # ~5 GB integrity pass against Valve's CDN on every single deploy.
        _if=lambda: not host.get_fact(File, path=PALSERVER_SH, _sudo=True),
        _sudo=True,
        _sudo_user=SERVICE_USER,
        _timeout=3600,
    )
    rcon = files.template(
        name="Install the palworld-rcon helper",
        src=str(templates_dir / "palworld-rcon.j2"),
        dest=RCON_SCRIPT,
        settings_file=SETTINGS_FILE,
        rcon_port=host.data.palworld_rcon_port,
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        mode="750",
        _sudo=True,
    )
    settings = files.template(
        name="Configure the Palworld server",
        src=str(templates_dir / "PalWorldSettings.ini.j2"),
        dest=SETTINGS_FILE,
        server_name=host.data.palworld_server_name,
        server_description=host.data.palworld_server_description,
        max_players=host.data.palworld_max_players,
        game_port=host.data.palworld_game_port,
        rcon_port=host.data.palworld_rcon_port,
        # str() before the template, not inside it: a SecretString only resolves through
        # __str__, and Jinja's filters would happily emit the bare op:// reference instead.
        admin_password=_ini_safe("AdminPassword", str(secrets.admin_password)),
        server_password=_ini_safe("ServerPassword", str(secrets.server_password)),
        user=SERVICE_USER,
        group=SERVICE_GROUP,
        mode="640",
        _sudo=True,
    )
    service = files.template(
        name="Install the palworld systemd unit",
        src=str(templates_dir / "palworld.service.j2"),
        dest="/etc/systemd/system/palworld.service",
        service_user=SERVICE_USER,
        service_group=SERVICE_GROUP,
        home_dir=HOME_DIR,
        server_dir=SERVER_DIR,
        steamcmd_sh=STEAMCMD_SH,
        rcon_script=RCON_SCRIPT,
        app_id=PALWORLD_APP_ID,
        game_port=host.data.palworld_game_port,
        max_players=host.data.palworld_max_players,
        _sudo=True,
    )
    restart_service = files.template(
        name="Install the palworld-restart systemd unit",
        src=str(templates_dir / "palworld-restart.service.j2"),
        dest="/etc/systemd/system/palworld-restart.service",
        _sudo=True,
    )
    restart_timer = files.template(
        name="Install the palworld-restart systemd timer",
        src=str(templates_dir / "palworld-restart.timer.j2"),
        dest="/etc/systemd/system/palworld-restart.timer",
        on_calendar=host.data.palworld_restart_on_calendar,
        _sudo=True,
    )
    units_changed = (
        lambda: service.did_change() or restart_service.did_change() or restart_timer.did_change()
    )
    server.shell(
        name="Reload systemd after writing palworld units",
        commands=["systemctl daemon-reload"],
        _sudo=True,
        _if=units_changed,
    )
    systemd.service(
        name="Enable and start the Palworld server",
        service="palworld.service",
        running=True,
        enabled=True,
        _sudo=True,
    )
    # The server reads PalWorldSettings.ini once, at startup, so a settings change that is not
    # followed by a restart is a change that silently has not happened yet. Going through
    # systemctl restart means the RCON ExecStop saves the world on the way down.
    server.shell(
        name="Restart the Palworld server to apply configuration changes",
        commands=["systemctl restart palworld.service"],
        _sudo=True,
        _if=lambda: settings.did_change() or rcon.did_change() or units_changed(),
    )
    systemd.service(
        name="Enable the nightly Palworld restart timer",
        service="palworld-restart.timer",
        running=True,
        enabled=True,
        _sudo=True,
    )
