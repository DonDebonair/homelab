import json
from typing import override, Union

from pyinfra.api import FactBase, QuoteString, StringCommand

from models.proxmox import (
    PVEGroupInfo,
    PVEUserInfo,
    PVEAclType,
    PVEAclInfo,
    PVEContainerArch,
    PVEContainerOSType,
    PVEContainerNetworkInterface,
    PVEContainerRootFS,
    PVEContainerFeatures,
    PVEContainerConfig,
    PVEContainerStatus,
    PVEContainerLock,
    PVEContainerSummary,
    PVEStorageInfo,
    PVEBackupMode,
    PVEBackupJobInfo,
)


class PVEGroups(FactBase[dict[str, PVEGroupInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pveum"

    @override
    def command(self) -> str:
        return "pveum group list --output-format json"

    @override
    def process(self, output: str) -> dict[str, PVEGroupInfo]:
        groups_data = json.loads("\n".join(output))

        groups = {}
        for group in groups_data:
            groups[group["groupid"]] = PVEGroupInfo(
                group_id=group["groupid"],
                comment=group.get("comment"),
                users=group["users"].split(",") if group["users"] else [],
            )
        return groups


class PVEUsers(FactBase[dict[str, PVEUserInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pveum"

    @override
    def command(self) -> str:
        return "pveum user list --full --output-format json"

    @override
    def process(self, output: str) -> dict[str, PVEUserInfo]:
        users_data = json.loads("\n".join(output))

        users = {}
        for user in users_data:
            users[user["userid"]] = PVEUserInfo(
                user_id=user["userid"],
                enabled=bool(user["enable"]),
                expire=user["expire"] if user["expire"] != 0 else None,
                firstname=user.get("firstname"),
                lastname=user.get("lastname"),
                email=user.get("email"),
                comment=user.get("comment"),
                groups=user["groups"].split(",") if user["groups"] else [],
                realm_type=user["realm-type"],
            )
        return users


class PVEAcls(FactBase[dict[tuple[str, str, str], PVEAclInfo]]):
    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pveum"

    @override
    def command(self) -> str:
        return "pveum acl list --output-format json"

    @override
    def process(self, output: list[str]) -> dict[tuple[str, str, str], PVEAclInfo]:
        acls_data = json.loads("\n".join(output))

        acls = {}
        for acl in acls_data:
            key = (acl["path"], acl["type"], acl["ugid"])
            acls[key] = PVEAclInfo(
                path=acl["path"],
                propagate=bool(acl["propagate"]),
                role_id=acl["roleid"],
                subject=acl["ugid"],
                type=PVEAclType(acl["type"]),
            )
        return acls


class PVEContainers(FactBase[dict[int, PVEContainerSummary]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pct"

    @override
    def command(self) -> str:
        return "pct list"

    @override
    def process(self, output: list[str]) -> dict[int, PVEContainerSummary]:
        containers = {}
        if not output or len(output) < 2:
            return containers

        # Use header to determine column positions
        header = output[0]
        vmid_start = header.find("VMID")
        status_start = header.find("Status")
        lock_start = header.find("Lock")
        name_start = header.find("Name")

        for line in output[1:]:
            if not line.strip():
                continue
            # Extract fields by slicing using header positions
            vmid_str = line[vmid_start:status_start].strip()
            status_str = line[status_start:lock_start].strip()
            lock_str = line[lock_start:name_start].strip()
            name_str = line[name_start:].strip()

            if not vmid_str or not status_str:
                continue
            try:
                vmid = int(vmid_str)
            except ValueError:
                continue
            try:
                status = PVEContainerStatus(status_str)
            except ValueError:
                status = PVEContainerStatus.UNKNOWN

            if lock_str:
                try:
                    lock = PVEContainerLock(lock_str)
                except ValueError:
                    lock = PVEContainerLock.UNKNOWN
            else:
                lock = None

            containers[vmid] = PVEContainerSummary(
                vmid=vmid,
                status=status,
                lock=lock,
                name=name_str
            )
        return containers


class PVEContainer(FactBase[Union[PVEContainerConfig, None]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pct"

    @override
    def command(self, ctid: int) -> StringCommand:
        return StringCommand("pct", "config", QuoteString(str(ctid)))

    @override
    def process(self, output: list[str]) -> PVEContainerConfig | None:
        if not output:
            return None

        config_dict = {}

        # Parse the output into key-value pairs
        for line in output:
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            config_dict[key.strip()] = value.strip()

        # Extract required fields
        try:
            arch = PVEContainerArch(config_dict['arch'])
            cores = int(config_dict['cores'])
            hostname = config_dict['hostname']
            memory = int(config_dict['memory'])
            ostype = PVEContainerOSType(config_dict['ostype'])
            swap = int(config_dict['swap'])
            unprivileged = bool(int(config_dict['unprivileged']))
        except (KeyError, ValueError):
            # If any required field is missing or invalid, return None
            return None

        # Parse rootfs
        rootfs_raw = config_dict.get('rootfs', '')
        rootfs = self._parse_rootfs(rootfs_raw)
        if not rootfs:
            return None

        # Parse optional features
        features = None
        if 'features' in config_dict:
            features = self._parse_features(config_dict['features'])

        # Parse network interfaces
        network_interfaces = {}
        for key, value in config_dict.items():
            if key.startswith('net') and key[3:].isdigit():
                net_num = int(key[3:])
                net_interface = self._parse_network_interface(value)
                if net_interface:
                    network_interfaces[net_num] = net_interface

        return PVEContainerConfig(
            arch=arch,
            cores=cores,
            hostname=hostname,
            memory=memory,
            ostype=ostype,
            rootfs=rootfs,
            swap=swap,
            unprivileged=unprivileged,
            features=features,
            network_interfaces=network_interfaces if network_interfaces else None
        )

    def _parse_rootfs(self, rootfs_str: str) -> PVEContainerRootFS | None:
        if not rootfs_str:
            return None

        parts = rootfs_str.split(',')
        if not parts:
            return None

        volume = parts[0]
        rootfs_config = {'volume': volume}

        # Parse additional options
        for part in parts[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()

                if key in ['acl', 'quota', 'replicate', 'ro', 'shared']:
                    rootfs_config[key] = bool(int(value))
                elif key == 'mountoptions':
                    rootfs_config[key] = value.split(';')
                else:
                    rootfs_config[key] = value

        return PVEContainerRootFS(**rootfs_config)

    def _parse_features(self, features_str: str) -> PVEContainerFeatures:
        features = PVEContainerFeatures()
        parts = features_str.split(',')

        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Convert 1|0 to boolean for known boolean features
                if key in ['force_rw_sys', 'fuse', 'keyctl', 'mknod', 'nesting'] and value in ['0', '1']:
                    setattr(features, key, bool(int(value)))
                elif key == 'mount':
                    # Parse mount as list of filesystem types
                    setattr(features, key, value.split(';'))
                else:
                    # For other features, set as string (though there shouldn't be any others)
                    setattr(features, key, value)

        return features

    def _parse_network_interface(self, net_str: str) -> PVEContainerNetworkInterface | None:
        parts = net_str.split(',')
        net_config = {}

        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()

                if key == 'name':
                    net_config['name'] = value
                elif key in ['firewall', 'link_down'] and value in ['0', '1']:
                    net_config[key] = bool(int(value))
                elif key in ['mtu', 'rate', 'tag'] and value.isdigit():
                    net_config[key] = int(value)
                elif key == 'trunks':
                    net_config[key] = [int(x) for x in value.split(';') if x.isdigit()]
                else:
                    net_config[key] = value

        if 'name' not in net_config:
            return None

        return PVEContainerNetworkInterface(**net_config)


class PVEStorages(FactBase[dict[str, PVEStorageInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pvesh"

    @override
    def command(self) -> str:
        return "pvesh get /storage --output-format json"

    @override
    def process(self, output: list[str]) -> dict[str, PVEStorageInfo]:
        storages_data = json.loads("\n".join(output))

        storages = {}
        for storage in storages_data:
            storage_id = storage["storage"]
            storages[storage_id] = PVEStorageInfo(
                storage=storage_id,
                type=storage["type"],
                content=storage.get("content"),
                server=storage.get("server"),
                datastore=storage.get("datastore"),
                username=storage.get("username"),
                fingerprint=storage.get("fingerprint"),
                disabled=bool(storage.get("disable", 0)),
            )
        return storages


class PVEBackupJobs(FactBase[dict[str, PVEBackupJobInfo]]):

    @override
    def requires_command(self, *args, **kwargs) -> str | None:
        return "pvesh"

    @override
    def command(self) -> str:
        return "pvesh get /cluster/backup --output-format json"

    @override
    def process(self, output: list[str]) -> dict[str, PVEBackupJobInfo]:
        jobs_data = json.loads("\n".join(output))

        jobs = {}
        for job in jobs_data:
            job_id = job["id"]
            jobs[job_id] = PVEBackupJobInfo(
                id=job_id,
                # `enabled` defaults to on when the property is absent.
                enabled=bool(job.get("enabled", 1)),
                schedule=job["schedule"],
                storage=job["storage"],
                vmid=job.get("vmid", ""),
                mode=PVEBackupMode(job["mode"]),
                notes_template=job.get("notes-template"),
                prune_backups=job.get("prune-backups"),
                comment=job.get("comment"),
            )
        return jobs
