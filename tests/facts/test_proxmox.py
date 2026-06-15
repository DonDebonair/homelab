from facts.proxmox.pve import PVEContainers, PVEContainer
from models.proxmox import (
    PVEContainerStatus, PVEContainerLock, PVEContainerConfig,
    PVEContainerArch, PVEContainerOSType, PVEContainerFeatures
)


def test_proxmox_containers_process():
    """Test ProxmoxContainers.process() correctly parses pct list output."""
    fact = PVEContainers()

    # Sample output from pct list command
    output = [
        "VMID       Status     Lock         Name",
        "100        running                 postgres",
        "101        stopped                 test1",
        "102        running    backup       web-server",
        "",  # Empty line should be ignored
        "103        stopped                 ",  # Container with empty name
        "104        running    migrate      db-server",
    ]

    result = fact.process(output)

    # Verify the result structure
    assert isinstance(result, dict)
    assert len(result) == 5

    # Test container 100
    assert 100 in result
    container_100 = result[100]
    assert container_100.vmid == 100
    assert container_100.status == PVEContainerStatus.RUNNING
    assert container_100.lock is None
    assert container_100.name == "postgres"

    # Test container 101
    assert 101 in result
    container_101 = result[101]
    assert container_101.vmid == 101
    assert container_101.status == PVEContainerStatus.STOPPED
    assert container_101.lock is None
    assert container_101.name == "test1"

    # Test container 102 with lock
    assert 102 in result
    container_102 = result[102]
    assert container_102.vmid == 102
    assert container_102.status == PVEContainerStatus.RUNNING
    assert container_102.lock == PVEContainerLock.BACKUP
    assert container_102.name == "web-server"

    # Test container 103 with empty name
    assert 103 in result
    container_103 = result[103]
    assert container_103.vmid == 103
    assert container_103.status == PVEContainerStatus.STOPPED
    assert container_103.lock is None
    assert container_103.name == ""

    # Test container 104 with migrate lock
    assert 104 in result
    container_104 = result[104]
    assert container_104.vmid == 104
    assert container_104.status == PVEContainerStatus.RUNNING
    assert container_104.lock == PVEContainerLock.MIGRATE
    assert container_104.name == "db-server"


def test_proxmox_container_process():
    """Test ProxmoxContainer.process() correctly parses pct config output."""
    fact = PVEContainer()

    # Sample output from pct config command
    output = [
        "arch: amd64",
        "cores: 2",
        "features: nesting=1",
        "hostname: postgres",
        "memory: 4096",
        "net0: name=eth0,bridge=vmbr0,firewall=1,hwaddr=BC:24:11:80:25:32,ip=dhcp,ip6=dhcp,type=veth",
        "ostype: ubuntu",
        "rootfs: vm-pool:subvol-100-disk-0,size=8G",
        "swap: 2048",
        "unprivileged: 1"
    ]

    result = fact.process(output)

    # Verify the result structure
    assert isinstance(result, PVEContainerConfig)

    # Test basic configuration fields
    assert result.arch == PVEContainerArch.AMD64
    assert result.cores == 2
    assert result.hostname == "postgres"
    assert result.memory == 4096
    assert result.ostype == PVEContainerOSType.UBUNTU
    assert result.swap == 2048
    assert result.unprivileged is True

    # Test features parsing - now it's a ProxmoxContainerFeatures object
    assert result.features is not None
    assert isinstance(result.features, PVEContainerFeatures)
    assert result.features.nesting is True  # Should be converted from "1" to boolean

    # Test network interface parsing
    assert result.network_interfaces is not None
    assert 0 in result.network_interfaces
    net0 = result.network_interfaces[0]
    assert net0.name == "eth0"
    assert net0.bridge == "vmbr0"
    assert net0.firewall is True  # Should be converted from "1" to boolean
    assert net0.hwaddr == "BC:24:11:80:25:32"
    assert net0.ip == "dhcp"
    assert net0.ip6 == "dhcp"
    assert net0.type == "veth"

    # Test rootfs parsing
    assert result.rootfs.volume == "vm-pool:subvol-100-disk-0"
    assert result.rootfs.size == "8G"


def test_proxmox_container_process_minimal():
    """Test ProxmoxContainer.process() with minimal required fields."""
    fact = PVEContainer()

    # Minimal output with only required fields
    output = [
        "arch: arm64",
        "cores: 1",
        "hostname: minimal-test",
        "memory: 512",
        "ostype: alpine",
        "rootfs: local:vm-200-disk-0",
        "swap: 0",
        "unprivileged: 0"
    ]

    result = fact.process(output)

    # Verify the result
    assert isinstance(result, PVEContainerConfig)
    assert result.arch == PVEContainerArch.ARM64
    assert result.cores == 1
    assert result.hostname == "minimal-test"
    assert result.memory == 512
    assert result.ostype == PVEContainerOSType.ALPINE
    assert result.swap == 0
    assert result.unprivileged is False
    assert result.features is None
    assert result.network_interfaces is None
    assert result.rootfs.volume == "local:vm-200-disk-0"
    assert result.rootfs.size is None


def test_proxmox_container_process_complex_features():
    """Test ProxmoxContainer.process() with complex features."""
    fact = PVEContainer()

    output = [
        "arch: amd64",
        "cores: 4",
        "features: fuse=1,keyctl=0,mount=nfs;cifs,nesting=1",
        "hostname: complex-test",
        "memory: 8192",
        "ostype: debian",
        "rootfs: storage:subvol-300-disk-0,acl=1,quota=1,size=20G",
        "swap: 4096",
        "unprivileged: 1"
    ]

    result = fact.process(output)

    assert isinstance(result, PVEContainerConfig)

    # Test complex features parsing - now it's a ProxmoxContainerFeatures object
    assert result.features is not None
    assert isinstance(result.features, PVEContainerFeatures)
    assert result.features.fuse is True
    assert result.features.keyctl is False
    assert result.features.mount == ["nfs", "cifs"]  # Should be parsed as list
    assert result.features.nesting is True

    # Test complex rootfs parsing
    assert result.rootfs.volume == "storage:subvol-300-disk-0"
    assert result.rootfs.acl is True
    assert result.rootfs.quota is True
    assert result.rootfs.size == "20G"


def test_proxmox_container_process_invalid_input():
    """Test ProxmoxContainer.process() with invalid/missing required fields."""
    fact = PVEContainer()

    # Missing required field (hostname)
    output_missing_hostname = [
        "arch: amd64",
        "cores: 2",
        "memory: 4096",
        "ostype: ubuntu",
        "rootfs: vm-pool:subvol-100-disk-0",
        "swap: 2048",
        "unprivileged: 1"
    ]

    result = fact.process(output_missing_hostname)
    assert result is None

    # Invalid architecture
    output_invalid_arch = [
        "arch: invalid_arch",
        "cores: 2",
        "hostname: test",
        "memory: 4096",
        "ostype: ubuntu",
        "rootfs: vm-pool:subvol-100-disk-0",
        "swap: 2048",
        "unprivileged: 1"
    ]

    result = fact.process(output_invalid_arch)
    assert result is None

    # Empty output
    result = fact.process([])
    assert result is None

    # Missing rootfs
    output_missing_rootfs = [
        "arch: amd64",
        "cores: 2",
        "hostname: test",
        "memory: 4096",
        "ostype: ubuntu",
        "swap: 2048",
        "unprivileged: 1"
    ]

    result = fact.process(output_missing_rootfs)
    assert result is None


def test_proxmox_container_process_multiple_networks():
    """Test ProxmoxContainer.process() with multiple network interfaces."""
    fact = PVEContainer()

    output = [
        "arch: amd64",
        "cores: 2",
        "hostname: multi-net",
        "memory: 2048",
        "net0: name=eth0,bridge=vmbr0,firewall=1,ip=192.168.1.100/24",
        "net1: name=eth1,bridge=vmbr1,firewall=0,ip=10.0.0.50/24,tag=100",
        "ostype: ubuntu",
        "rootfs: vm-pool:subvol-400-disk-0",
        "swap: 1024",
        "unprivileged: 1"
    ]

    result = fact.process(output)

    assert isinstance(result, PVEContainerConfig)
    assert result.network_interfaces is not None
    assert len(result.network_interfaces) == 2

    # Test net0
    net0 = result.network_interfaces[0]
    assert net0.name == "eth0"
    assert net0.bridge == "vmbr0"
    assert net0.firewall is True
    assert net0.ip == "192.168.1.100/24"

    # Test net1
    net1 = result.network_interfaces[1]
    assert net1.name == "eth1"
    assert net1.bridge == "vmbr1"
    assert net1.firewall is False
    assert net1.ip == "10.0.0.50/24"
    assert net1.tag == 100
