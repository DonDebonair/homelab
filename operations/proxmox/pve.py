from pyinfra import host
from pyinfra.api import HiddenValue, QuoteString, StringCommand, operation

from facts.proxmox.pve import PVEGroups, PVEUsers, PVEAcls, PVEContainers
from models.proxmox import (
    PVEAclType,
    PVEContainerArch, PVEContainerOSType, PVEContainerFeatures, PVEConsoleMode,
    PVEContainerNetworkInterface
)


@operation()
def group(group_id: str, comment: str | None = None, present: bool = True):
    groups = host.get_fact(PVEGroups, _sudo=True)
    group_info = groups.get(group_id) if groups else None
    is_present = group_info is not None
    cmd: list[str | QuoteString] = ["pveum", "group"]

    if not present and is_present:
        cmd.extend(["delete", QuoteString(group_id)])
    elif present and not is_present:
        cmd.extend(["add", QuoteString(group_id)])
        if comment:
            cmd.extend(["--comment", QuoteString(comment)])
    elif present and is_present:
        if comment is not None and comment != group_info.comment:
            cmd.extend(["modify", QuoteString(group_id), "--comment", QuoteString(comment)])
        else:
            host.noop(f"Group '{group_id}' already exists with the same comment.")
            return
    else:
        host.noop(f"Group '{group_id}' does not exist and 'present' is False.")
        return
    yield StringCommand(*cmd)


@operation()
def acl(path: str, role_id: str, subject: str, acl_type: PVEAclType, propagate: bool = True, present: bool = True):
    acls = host.get_fact(PVEAcls, _sudo=True)
    acl_info = acls.get((path, acl_type, subject)) if acls else None
    is_present = acl_info is not None
    cmd: list[str | QuoteString] = ["pveum", "acl"]
    # acl_type is a PVEAclType enum member, so the "--<type>s" flag is from a fixed
    # set of values and safe to interpolate; the subject it refers to is quoted.
    subject_flag = "--" + acl_type + "s"

    if not present and is_present:
        cmd.extend(["delete", QuoteString(path), subject_flag, QuoteString(subject)])
    elif present and not is_present:
        cmd.extend(["modify", QuoteString(path), "--roles", QuoteString(role_id), subject_flag,
                    QuoteString(subject), "--propagate", str(int(propagate))])
    elif present and is_present:
        if role_id != acl_info.role_id or propagate != acl_info.propagate:
            cmd.extend(["modify", QuoteString(path), "--roles", QuoteString(role_id), subject_flag,
                        QuoteString(subject), "--propagate", str(int(propagate))])
        else:
            host.noop(f"ACL for '{subject}' on '{path}' already exists with the '{role_id}' role and propagation.")
            return
    else:
        host.noop(f"ACL for '{subject}' on '{path}' does not exist and 'present' is False.")
        return
    yield StringCommand(*cmd)


@operation()
def user(
        user_id: str,
        password: str | None = None,
        enabled: bool = True,
        expire: int | None = None,
        firstname: str | None = None,
        lastname: str | None = None,
        email: str | None = None,
        comment: str | None = None,
        groups: list[str] | None = None,
        present: bool = True,
        append_groups: bool = False,
):
    users = host.get_fact(PVEUsers, _sudo=True)
    user_info = users.get(user_id) if users else None
    is_present = user_info is not None
    cmd: list[str | QuoteString] = ["pveum", "user"]

    if not present and is_present:
        cmd.extend(["delete", QuoteString(user_id)])
    elif present and not is_present:
        cmd.extend(["add", QuoteString(user_id)])
        if password:
            cmd.extend(["--password", QuoteString(HiddenValue(str(password)))])
        if expire is not None:
            cmd.extend(["--expire", str(expire)])
        if firstname:
            cmd.extend(["--firstname", QuoteString(firstname)])
        if lastname:
            cmd.extend(["--lastname", QuoteString(lastname)])
        if email:
            cmd.extend(["--email", QuoteString(email)])
        if comment:
            cmd.extend(["--comment", QuoteString(comment)])
        if groups:
            cmd.extend(["--groups", QuoteString(",".join(groups))])
        cmd.extend(["--enable", str(int(enabled))])
    elif present and is_present:
        modified = False
        cmd.extend(["modify", QuoteString(user_id)])
        if password:
            cmd.extend(["--password", QuoteString(HiddenValue(str(password)))])
            modified = True
        if enabled != user_info.enabled:
            cmd.extend(["--enable", str(int(enabled))])
            modified = True
        if expire != user_info.expire:
            cmd.extend(["--expire", str(expire) if expire is not None else "0"])
            modified = True
        if firstname != user_info.firstname and firstname is not None:
            cmd.extend(["--firstname", QuoteString(firstname)])
            modified = True
        if lastname != user_info.lastname and lastname is not None:
            cmd.extend(["--lastname", QuoteString(lastname)])
            modified = True
        if email != user_info.email and email is not None:
            cmd.extend(["--email", QuoteString(email)])
            modified = True
        if comment != user_info.comment and comment is not None:
            cmd.extend(["--comment", QuoteString(comment)])
            modified = True
        if groups is not None and set(groups) != set(user_info.groups):
            cmd.extend(["--groups", QuoteString(",".join(groups))])
            if append_groups:
                cmd.extend(["--append", "1"])
            modified = True
        if not modified:
            host.noop(f"User '{user_id}' already exists with the same attributes.")
            return
    yield StringCommand(*cmd)


@operation()
def container(
        vmid: int,
        os_template: str,
        present: bool = True,
        arch: PVEContainerArch | None = None,
        cores: int | None = None,
        memory: int | None = None,
        swap: int | None = None,
        rootfs: str | None = None,
        storage: str | None = None,
        hostname: str | None = None,
        unprivileged: bool | None = None,
        os_type: PVEContainerOSType | None = None,
        nameserver: str | None = None,
        searchdomain: str | None = None,
        description: str | None = None,
        on_boot: bool | None = None,
        start: bool | None = None,
        template: bool | None = None,
        protection: bool | None = None,
        console: bool | None = None,
        cmode: PVEConsoleMode | None = None,
        tty: int | None = None,
        cpu_limit: float | None = None,
        cpu_units: int | None = None,
        features: PVEContainerFeatures | None = None,
        networks: dict[int, PVEContainerNetworkInterface] | list[PVEContainerNetworkInterface] | None = None,
        pool: str | None = None,
        tags: str | None = None,
        timezone: str | None = None,
        ssh_public_keys: str | None = None,
        force: bool = False,
):
    """
    Create or remove a Proxmox container.

    Args:
        vmid: The (unique) ID of the VM (100-999999999)
        os_template: The OS template or backup file
        present: Whether the container should exist (True) or not (False)
        features: ProxmoxContainerFeatures object for container features
        networks: Dict mapping network interface numbers to ProxmoxContainerNetworkInterface objects,
                 or list of ProxmoxContainerNetworkInterface objects (auto-assigned to net0, net1, etc.)
        force: Allow overwriting existing container
        ... (other parameters as documented in pct create help)
    """
    containers = host.get_fact(PVEContainers, _sudo=True)
    container_info = containers.get(vmid) if containers else None
    is_present = container_info is not None

    def _build_create_command():
        """Helper function to build the pct create command bits"""
        cmd = ["pct", "create", QuoteString(str(vmid)), QuoteString(os_template)]

        # Add optional parameters. Enum values come from a fixed, known set so they
        # are safe; everything else originating from the caller is quoted.
        if arch is not None:
            cmd.extend(["--arch", arch.value])
        if cores is not None:
            cmd.extend(["--cores", str(cores)])
        if memory is not None:
            cmd.extend(["--memory", str(memory)])
        if swap is not None:
            cmd.extend(["--swap", str(swap)])
        if rootfs is not None:
            cmd.extend(["--rootfs", QuoteString(rootfs)])
        if storage is not None:
            cmd.extend(["--storage", QuoteString(storage)])
        if hostname is not None:
            cmd.extend(["--hostname", QuoteString(hostname)])
        if unprivileged is not None:
            cmd.extend(["--unprivileged", str(int(unprivileged))])
        if os_type is not None:
            cmd.extend(["--ostype", os_type.value])
        if nameserver is not None:
            cmd.extend(["--nameserver", QuoteString(nameserver)])
        if searchdomain is not None:
            cmd.extend(["--searchdomain", QuoteString(searchdomain)])
        if description is not None:
            cmd.extend(["--description", QuoteString(description)])
        if on_boot is not None:
            cmd.extend(["--onboot", str(int(on_boot))])
        if start is not None:
            cmd.extend(["--start", str(int(start))])
        if template is not None:
            cmd.extend(["--template", str(int(template))])
        if protection is not None:
            cmd.extend(["--protection", str(int(protection))])
        if console is not None:
            cmd.extend(["--console", str(int(console))])
        if cmode is not None:
            cmd.extend(["--cmode", cmode.value])
        if tty is not None:
            cmd.extend(["--tty", str(tty)])
        if cpu_limit is not None:
            cmd.extend(["--cpulimit", str(cpu_limit)])
        if cpu_units is not None:
            cmd.extend(["--cpuunits", str(cpu_units)])
        if pool is not None:
            cmd.extend(["--pool", QuoteString(pool)])
        if tags is not None:
            cmd.extend(["--tags", QuoteString(tags)])
        if timezone is not None:
            cmd.extend(["--timezone", QuoteString(timezone)])
        if ssh_public_keys is not None:
            cmd.extend(["--ssh-public-keys", QuoteString(ssh_public_keys)])

        # Handle features using ProxmoxContainerFeatures class. The whole
        # comma-separated value is quoted as a single argument.
        if features is not None:
            features_parts = []
            if features.force_rw_sys is not None:
                features_parts.append(f"force_rw_sys={int(features.force_rw_sys)}")
            if features.fuse is not None:
                features_parts.append(f"fuse={int(features.fuse)}")
            if features.keyctl is not None:
                features_parts.append(f"keyctl={int(features.keyctl)}")
            if features.mknod is not None:
                features_parts.append(f"mknod={int(features.mknod)}")
            if features.nesting is not None:
                features_parts.append(f"nesting={int(features.nesting)}")
            if features.mount is not None:
                features_parts.append(f"mount={';'.join(features.mount)}")

            if features_parts:
                cmd.extend(["--features", QuoteString(",".join(features_parts))])

        # Handle network interfaces. Each --net<id> value is a single quoted argument.
        if networks is not None:
            # Convert list to dict with auto-incrementing IDs if needed
            if isinstance(networks, list):
                networks_dict = {i: net_interface for i, net_interface in enumerate(networks)}
            else:
                networks_dict = networks

            for net_id, net_interface in networks_dict.items():
                net_parts = [f"name={net_interface.name}"]

                if net_interface.bridge is not None:
                    net_parts.append(f"bridge={net_interface.bridge}")
                if net_interface.firewall is not None:
                    net_parts.append(f"firewall={int(net_interface.firewall)}")
                if net_interface.gw is not None:
                    net_parts.append(f"gw={net_interface.gw}")
                if net_interface.gw6 is not None:
                    net_parts.append(f"gw6={net_interface.gw6}")
                if net_interface.hwaddr is not None:
                    net_parts.append(f"hwaddr={net_interface.hwaddr}")
                if net_interface.ip is not None:
                    net_parts.append(f"ip={net_interface.ip}")
                if net_interface.ip6 is not None:
                    net_parts.append(f"ip6={net_interface.ip6}")
                if net_interface.link_down is not None:
                    net_parts.append(f"link_down={int(net_interface.link_down)}")
                if net_interface.mtu is not None:
                    net_parts.append(f"mtu={net_interface.mtu}")
                if net_interface.rate is not None:
                    net_parts.append(f"rate={net_interface.rate}")
                if net_interface.tag is not None:
                    net_parts.append(f"tag={net_interface.tag}")
                if net_interface.trunks is not None:
                    net_parts.append(f"trunks={';'.join(map(str, net_interface.trunks))}")
                if net_interface.type is not None:
                    net_parts.append(f"type={net_interface.type}")

                cmd.extend([f"--net{int(net_id)}", QuoteString(",".join(net_parts))])

        return cmd

    if not present and is_present:
        # Remove container
        cmd = ["pct", "destroy", QuoteString(str(vmid))]
        if force:
            cmd.append("--force")
        yield StringCommand(*cmd)
    elif present and not is_present:
        # Create container
        cmd = _build_create_command()
        if force:
            cmd.append("--force")
        yield StringCommand(*cmd)
    elif present and is_present:
        # Container exists and should exist
        if force:
            # Recreate container if force is True
            cmd = ["pct", "destroy", QuoteString(str(vmid)), "--force"]  # Force destroy even if running
            yield StringCommand(*cmd)

            # Then create it again
            cmd = _build_create_command()
            cmd.append("--force")
            yield StringCommand(*cmd)
        else:
            host.noop(f"Container '{vmid}' already exists. Use force=True to recreate.")
            return
    else:
        # Container doesn't exist and shouldn't exist
        host.noop(f"Container '{vmid}' does not exist and 'present' is False.")
        return
