"""Tests for Proxmox operations."""

from unittest.mock import Mock, patch

from operations.proxmox import container
from models.proxmox import (
    ProxmoxContainerArch, ProxmoxContainerOSType, ProxmoxContainerFeatures,
    ProxmoxConsoleMode, ProxmoxContainerSummary, ProxmoxContainerStatus
)


def test_container_create_minimal():
    """Test container creation with minimal parameters."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        # Create a mock generator to capture yielded commands
        result = container.__wrapped__(
            vmid=100,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True
        )

        commands = list(result)

        # Verify the correct command is yielded
        expected_cmd = "pct create 100 ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
        assert len(commands) == 1
        assert commands[0] == expected_cmd


def test_container_create_full_options():
    """Test container creation with full parameter set."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        # Create features object
        features = ProxmoxContainerFeatures(
            nesting=True,
            fuse=True,
            mount=["nfs", "cifs"]
        )

        result = container.__wrapped__(
            vmid=200,
            os_template="debian-12-standard_12.2-1_amd64.tar.zst",
            present=True,
            arch=ProxmoxContainerArch.AMD64,
            cores=4,
            memory=4096,
            swap=2048,
            rootfs="vm-pool:200",
            storage="vm-pool",
            hostname="test-container",
            unprivileged=True,
            os_type=ProxmoxContainerOSType.DEBIAN,
            nameserver="1.1.1.1",
            searchdomain="example.com",
            description="Test container",
            on_boot=True,
            start=True,
            template=False,
            protection=False,
            console=True,
            cmode=ProxmoxConsoleMode.TTY,
            tty=2,
            cpu_limit=2.5,
            cpu_units=2000,
            features=features,
            pool="test-pool",
            tags="test,container",
            timezone="UTC",
            ssh_public_keys="/root/.ssh/authorized_keys"
        )

        commands = list(result)

        # Verify the command contains all expected parameters
        assert len(commands) == 1
        cmd = commands[0]

        # Check basic command structure
        assert cmd.startswith("pct create 200 debian-12-standard_12.2-1_amd64.tar.zst")

        # Check individual parameters
        assert "--arch amd64" in cmd
        assert "--cores 4" in cmd
        assert "--memory 4096" in cmd
        assert "--swap 2048" in cmd
        assert "--rootfs vm-pool:200" in cmd
        assert "--storage vm-pool" in cmd
        assert "--hostname test-container" in cmd
        assert "--unprivileged 1" in cmd
        assert "--ostype debian" in cmd
        assert "--nameserver 1.1.1.1" in cmd
        assert "--searchdomain example.com" in cmd
        assert "--description 'Test container'" in cmd
        assert "--onboot 1" in cmd
        assert "--start 1" in cmd
        assert "--template 0" in cmd
        assert "--protection 0" in cmd
        assert "--console 1" in cmd
        assert "--cmode tty" in cmd
        assert "--tty 2" in cmd
        assert "--cpulimit 2.5" in cmd
        assert "--cpuunits 2000" in cmd
        assert "--pool test-pool" in cmd
        assert "--tags test,container" in cmd
        assert "--timezone UTC" in cmd
        assert "--ssh-public-keys /root/.ssh/authorized_keys" in cmd

        # Check features parameter - be flexible about order
        assert "--features" in cmd
        features_part = cmd[cmd.find("--features"):].split()[1]
        assert "nesting=1" in features_part
        assert "fuse=1" in features_part
        assert "mount=nfs;cifs" in features_part


def test_container_create_with_force():
    """Test container creation with force flag."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        result = container.__wrapped__(
            vmid=300,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            force=True
        )

        commands = list(result)

        # Verify force flag is added
        assert len(commands) == 1
        assert commands[0].endswith(" --force")


def test_container_destroy():
    """Test container destruction."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container exists
        existing_container = ProxmoxContainerSummary(
            vmid=100,
            status=ProxmoxContainerStatus.STOPPED,
            lock=None,
            name="test-container"
        )
        mock_host.get_fact.return_value = {100: existing_container}

        result = container.__wrapped__(
            vmid=100,
            os_template="",  # Not used for destruction
            present=False
        )

        commands = list(result)

        # Verify destroy command
        assert len(commands) == 1
        assert commands[0] == "pct destroy 100"


def test_container_recreate_with_force():
    """Test container recreation when force=True and container exists."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container exists
        existing_container = ProxmoxContainerSummary(
            vmid=150,
            status=ProxmoxContainerStatus.RUNNING,
            lock=None,
            name="existing-container"
        )
        mock_host.get_fact.return_value = {150: existing_container}

        result = container.__wrapped__(
            vmid=150,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            hostname="recreated-container",
            force=True
        )

        commands = list(result)

        # Should yield destroy command first, then create command
        assert len(commands) == 2
        assert commands[0] == "pct destroy 150 --force"
        assert commands[1].startswith("pct create 150 ubuntu-22.04-standard_22.04-1_amd64.tar.zst")
        assert "--hostname recreated-container" in commands[1]
        assert "--force" in commands[1]


def test_container_exists_no_force_noop():
    """Test no-op when container exists and force=False."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container exists
        existing_container = ProxmoxContainerSummary(
            vmid=175,
            status=ProxmoxContainerStatus.RUNNING,
            lock=None,
            name="existing-container"
        )
        mock_host.get_fact.return_value = {175: existing_container}

        result = container.__wrapped__(
            vmid=175,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            force=False
        )

        commands = list(result)

        # Should not yield any commands
        assert len(commands) == 0
        # Verify noop was called
        mock_host.noop.assert_called_once_with("Container '175' already exists. Use force=True to recreate.")


def test_container_not_exists_present_false_noop():
    """Test no-op when container doesn't exist and present=False."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        result = container.__wrapped__(
            vmid=250,
            os_template="",
            present=False
        )

        commands = list(result)

        # Should not yield any commands
        assert len(commands) == 0
        # Verify noop was called
        mock_host.noop.assert_called_once_with("Container '250' does not exist and 'present' is False.")


def test_container_features_boolean_conversion():
    """Test that boolean features are correctly converted to 1/0."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        features = ProxmoxContainerFeatures(
            force_rw_sys=True,
            fuse=False,
            keyctl=True,
            mknod=False,
            nesting=True
        )

        result = container.__wrapped__(
            vmid=400,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            features=features
        )

        commands = list(result)

        # Verify boolean conversion in features
        assert len(commands) == 1
        cmd = commands[0]
        assert "--features force_rw_sys=1,fuse=0,keyctl=1,mknod=0,nesting=1" in cmd


def test_container_features_mount_list():
    """Test that mount features are correctly formatted as semicolon-separated list."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        features = ProxmoxContainerFeatures(
            mount=["nfs", "cifs", "fuse"]
        )

        result = container.__wrapped__(
            vmid=500,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            features=features
        )

        commands = list(result)

        # Verify mount list formatting
        assert len(commands) == 1
        cmd = commands[0]
        assert "--features mount=nfs;cifs;fuse" in cmd


def test_container_mixed_features():
    """Test container with mixed feature types (booleans and mount list)."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        features = ProxmoxContainerFeatures(
            nesting=True,
            fuse=False,
            mount=["nfs", "cifs"]
        )

        result = container.__wrapped__(
            vmid=600,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            features=features
        )

        commands = list(result)

        # Verify mixed features formatting - be flexible about order
        assert len(commands) == 1
        cmd = commands[0]
        assert "--features" in cmd
        features_part = cmd[cmd.find("--features"):].split()[1]
        assert "nesting=1" in features_part
        assert "fuse=0" in features_part
        assert "mount=nfs;cifs" in features_part


def test_container_no_features():
    """Test container creation without features parameter."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        result = container.__wrapped__(
            vmid=700,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True
        )

        commands = list(result)

        # Verify no features parameter is added
        assert len(commands) == 1
        cmd = commands[0]
        assert "--features" not in cmd


def test_container_empty_features():
    """Test container creation with empty features object."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        features = ProxmoxContainerFeatures()  # All None values

        result = container.__wrapped__(
            vmid=800,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            features=features
        )

        commands = list(result)

        # Verify no features parameter is added when all features are None
        assert len(commands) == 1
        cmd = commands[0]
        assert "--features" not in cmd


def test_container_with_single_network():
    """Test container creation with a single network interface."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        # Create a network interface
        from models.proxmox import ProxmoxContainerNetworkInterface
        network = ProxmoxContainerNetworkInterface(
            name="eth0",
            bridge="vmbr0",
            firewall=True,
            ip="192.168.1.100/24",
            hwaddr="AA:BB:CC:DD:EE:FF"
        )

        result = container.__wrapped__(
            vmid=900,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            networks={0: network}
        )

        commands = list(result)

        # Verify network parameter is added correctly
        assert len(commands) == 1
        cmd = commands[0]
        assert "--net0" in cmd
        assert "name=eth0" in cmd
        assert "bridge=vmbr0" in cmd
        assert "firewall=1" in cmd
        assert "ip=192.168.1.100/24" in cmd
        assert "hwaddr=AA:BB:CC:DD:EE:FF" in cmd


def test_container_with_multiple_networks():
    """Test container creation with multiple network interfaces."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        from models.proxmox import ProxmoxContainerNetworkInterface

        # Create multiple network interfaces
        network0 = ProxmoxContainerNetworkInterface(
            name="eth0",
            bridge="vmbr0",
            firewall=True,
            ip="dhcp"
        )

        network1 = ProxmoxContainerNetworkInterface(
            name="eth1",
            bridge="vmbr1",
            firewall=False,
            ip="192.168.100.50/24",
            tag=100,
            mtu=1500
        )

        result = container.__wrapped__(
            vmid=950,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            networks={0: network0, 1: network1}
        )

        commands = list(result)

        # Verify both network parameters are added correctly
        assert len(commands) == 1
        cmd = commands[0]

        # Check net0
        assert "--net0" in cmd
        assert "name=eth0" in cmd and "bridge=vmbr0" in cmd
        assert "firewall=1" in cmd and "ip=dhcp" in cmd

        # Check net1
        assert "--net1" in cmd
        assert "name=eth1" in cmd and "bridge=vmbr1" in cmd
        assert "firewall=0" in cmd and "ip=192.168.100.50/24" in cmd
        assert "tag=100" in cmd and "mtu=1500" in cmd


def test_container_with_complex_network():
    """Test container creation with a network interface using all options."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        from models.proxmox import ProxmoxContainerNetworkInterface

        # Create a complex network interface with all possible options
        network = ProxmoxContainerNetworkInterface(
            name="eth0",
            bridge="vmbr0",
            firewall=True,
            gw="192.168.1.1",
            gw6="fe80::1",
            hwaddr="AA:BB:CC:DD:EE:FF",
            ip="192.168.1.100/24",
            ip6="2001:db8::100/64",
            link_down=False,
            mtu=9000,
            rate=1000,
            tag=200,
            trunks=[100, 200, 300],
            type="veth"
        )

        result = container.__wrapped__(
            vmid=975,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True,
            networks={0: network}
        )

        commands = list(result)

        # Verify all network options are included
        assert len(commands) == 1
        cmd = commands[0]
        assert "--net0" in cmd

        # Extract the network configuration part
        net_part = None
        cmd_parts = cmd.split()
        for i, part in enumerate(cmd_parts):
            if part == "--net0" and i + 1 < len(cmd_parts):
                net_part = cmd_parts[i + 1]
                break

        assert net_part is not None
        assert "name=eth0" in net_part
        assert "bridge=vmbr0" in net_part
        assert "firewall=1" in net_part
        assert "gw=192.168.1.1" in net_part
        assert "gw6=fe80::1" in net_part
        assert "hwaddr=AA:BB:CC:DD:EE:FF" in net_part
        assert "ip=192.168.1.100/24" in net_part
        assert "ip6=2001:db8::100/64" in net_part
        assert "link_down=0" in net_part
        assert "mtu=9000" in net_part
        assert "rate=1000" in net_part
        assert "tag=200" in net_part
        assert "trunks=100;200;300" in net_part
        assert "type=veth" in net_part


def test_container_no_networks():
    """Test container creation without networks parameter."""
    with patch('operations.proxmox.host') as mock_host:
        # Mock that container doesn't exist
        mock_host.get_fact.return_value = {}

        result = container.__wrapped__(
            vmid=1000,
            os_template="ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            present=True
        )

        commands = list(result)

        # Verify no network parameters are added
        assert len(commands) == 1
        cmd = commands[0]
        assert "--net0" not in cmd
        assert "--net1" not in cmd
