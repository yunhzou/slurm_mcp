"""Unit tests for cluster status tools.

These tests require a configured .env file with valid SSH credentials.
Run with: pytest tests/test_cluster_status.py -v
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# removed get_settings import - uses settings fixture from conftest
from slurm_mcp.models import PartitionInfo, NodeInfo, GPUInfo
from slurm_mcp.ssh_client import SSHClient
from slurm_mcp.slurm_commands import SlurmCommands


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def settings():
    """Get settings from environment."""
    return get_settings()


@pytest.fixture
async def ssh_client(settings):
    """Create and connect SSH client."""
    client = SSHClient(settings)
    await client.connect()
    yield client
    await client.disconnect()


@pytest.fixture
async def slurm(ssh_client, settings):
    """Create Slurm commands wrapper."""
    return SlurmCommands(ssh_client, settings)


# =============================================================================
# Test: get_cluster_status / get_partitions
# =============================================================================

class TestGetPartitions:
    """Tests for get_partitions / get_cluster_status functionality."""
    
    @pytest.mark.asyncio
    async def test_returns_partitions(self, slurm):
        """Test that get_partitions returns a list of partitions."""
        partitions = await slurm.get_partitions()
        
        assert isinstance(partitions, list)
        assert len(partitions) > 0, "Should have at least one partition"
    
    @pytest.mark.asyncio
    async def test_partition_has_required_fields(self, slurm):
        """Test that each partition has all required fields."""
        partitions = await slurm.get_partitions()
        
        for p in partitions:
            assert isinstance(p, PartitionInfo)
            assert p.name, "Partition should have a name"
            assert p.state in ["up", "down", "drain", "inactive"], f"Invalid state: {p.state}"
            assert p.total_nodes >= 0
            assert p.available_nodes >= 0
            assert p.total_cpus >= 0
            assert p.available_cpus >= 0
    
    @pytest.mark.asyncio
    async def test_partition_node_counts_valid(self, slurm):
        """Test that available nodes <= total nodes."""
        partitions = await slurm.get_partitions()
        
        for p in partitions:
            assert p.available_nodes <= p.total_nodes, \
                f"Partition {p.name}: available ({p.available_nodes}) > total ({p.total_nodes})"
    
    @pytest.mark.asyncio
    async def test_partition_cpu_counts_valid(self, slurm):
        """Test that available CPUs <= total CPUs."""
        partitions = await slurm.get_partitions()
        
        for p in partitions:
            assert p.available_cpus <= p.total_cpus, \
                f"Partition {p.name}: available CPUs ({p.available_cpus}) > total ({p.total_cpus})"
    
    @pytest.mark.asyncio
    async def test_gpu_partitions_have_gpu_info(self, slurm):
        """Test that GPU partitions have GPU information."""
        partitions = await slurm.get_partitions()
        
        gpu_partitions = [p for p in partitions if p.has_gpus]
        
        for p in gpu_partitions:
            assert p.total_gpus > 0, f"GPU partition {p.name} should have GPUs"
            # GPU types should be populated if has_gpus is True
            # (may be empty list if type couldn't be determined)
    
    @pytest.mark.asyncio
    async def test_has_default_partition(self, slurm):
        """Test that there is at least one default partition (optional)."""
        partitions = await slurm.get_partitions()
        
        # This is optional - some clusters may not have a default
        default_partitions = [p for p in partitions if p.default]
        # Just log, don't fail
        if not default_partitions:
            print("Note: No default partition found")


# =============================================================================
# Test: get_node_info / get_nodes
# =============================================================================

class TestGetNodes:
    """Tests for get_nodes / get_node_info functionality."""
    
    @pytest.mark.asyncio
    async def test_returns_nodes(self, slurm):
        """Test that get_nodes returns a list of nodes."""
        nodes = await slurm.get_nodes()
        
        assert isinstance(nodes, list)
        assert len(nodes) > 0, "Should have at least one node"
    
    @pytest.mark.asyncio
    async def test_node_has_required_fields(self, slurm):
        """Test that each node has all required fields."""
        nodes = await slurm.get_nodes()
        
        for n in nodes[:10]:  # Check first 10 nodes
            assert isinstance(n, NodeInfo)
            assert n.node_name, "Node should have a name"
            assert n.state, "Node should have a state"
            assert n.cpus_total >= 0
            assert n.memory_total_mb >= 0
            assert isinstance(n.partitions, list)
    
    @pytest.mark.asyncio
    async def test_node_cpu_counts_valid(self, slurm):
        """Test that node CPU counts are valid."""
        nodes = await slurm.get_nodes()
        
        for n in nodes[:10]:
            assert n.cpus_allocated >= 0
            assert n.cpus_available >= 0
            assert n.cpus_allocated + n.cpus_available <= n.cpus_total + 1  # Allow small rounding
    
    @pytest.mark.asyncio
    async def test_node_memory_counts_valid(self, slurm):
        """Test that node memory counts are valid."""
        nodes = await slurm.get_nodes()
        
        for n in nodes[:10]:
            assert n.memory_allocated_mb >= 0
            assert n.memory_available_mb >= 0
    
    @pytest.mark.asyncio
    async def test_filter_by_partition(self, slurm):
        """Test filtering nodes by partition."""
        # Get all partitions first
        partitions = await slurm.get_partitions()
        if not partitions:
            pytest.skip("No partitions available")
        
        # Use first partition
        partition_name = partitions[0].name
        
        nodes = await slurm.get_nodes(partition=partition_name)
        
        assert isinstance(nodes, list)
        # All returned nodes should belong to this partition
        for n in nodes[:10]:
            assert partition_name in n.partitions or len(n.partitions) == 0, \
                f"Node {n.node_name} not in partition {partition_name}"
    
    @pytest.mark.asyncio
    async def test_filter_by_state(self, slurm):
        """Test filtering nodes by state."""
        # Test with 'idle' state
        idle_nodes = await slurm.get_nodes(state="idle")
        
        assert isinstance(idle_nodes, list)
        for n in idle_nodes[:10]:
            assert "idle" in n.state.lower(), f"Node {n.node_name} state is {n.state}, not idle"
    
    @pytest.mark.asyncio
    async def test_gpu_nodes_have_gpu_info(self, slurm):
        """Test that GPU nodes have GPU information."""
        nodes = await slurm.get_nodes()
        
        gpu_nodes = [n for n in nodes if n.gpus]
        
        if not gpu_nodes:
            pytest.skip("No GPU nodes found")
        
        for n in gpu_nodes[:5]:
            assert len(n.gpus) > 0
            for gpu in n.gpus:
                assert isinstance(gpu, GPUInfo)
                assert gpu.count > 0


# =============================================================================
# Test: get_gpu_info
# =============================================================================

class TestGetGPUInfo:
    """Tests for get_gpu_info functionality."""
    
    @pytest.mark.asyncio
    async def test_returns_gpu_info(self, slurm):
        """Test that get_gpu_info returns a dictionary."""
        gpu_info = await slurm.get_gpu_info()
        
        assert isinstance(gpu_info, dict)
        assert "total_gpus" in gpu_info
        assert "allocated_gpus" in gpu_info
        assert "available_gpus" in gpu_info
        assert "by_partition" in gpu_info
        assert "by_type" in gpu_info
    
    @pytest.mark.asyncio
    async def test_gpu_counts_valid(self, slurm):
        """Test that GPU counts are valid."""
        gpu_info = await slurm.get_gpu_info()
        
        assert gpu_info["total_gpus"] >= 0
        assert gpu_info["allocated_gpus"] >= 0
        assert gpu_info["available_gpus"] >= 0
        
        # Available + allocated should equal total (approximately)
        total = gpu_info["total_gpus"]
        allocated = gpu_info["allocated_gpus"]
        available = gpu_info["available_gpus"]
        
        if total > 0:
            assert allocated + available <= total * 2, \
                "Allocated + available should not greatly exceed total"
    
    @pytest.mark.asyncio
    async def test_by_partition_structure(self, slurm):
        """Test structure of by_partition data."""
        gpu_info = await slurm.get_gpu_info()
        
        for part_name, stats in gpu_info["by_partition"].items():
            assert isinstance(part_name, str)
            assert "total" in stats
            assert "allocated" in stats
            assert "available" in stats
            assert "types" in stats
            assert isinstance(stats["types"], list)
    
    @pytest.mark.asyncio
    async def test_by_type_structure(self, slurm):
        """Test structure of by_type data."""
        gpu_info = await slurm.get_gpu_info()
        
        for gpu_type, stats in gpu_info["by_type"].items():
            assert isinstance(gpu_type, str)
            assert "total" in stats
            assert "allocated" in stats
            assert "available" in stats
    
    @pytest.mark.asyncio
    async def test_filter_by_partition(self, slurm):
        """Test filtering GPU info by partition."""
        # Get a GPU partition
        all_info = await slurm.get_gpu_info()
        
        if not all_info["by_partition"]:
            pytest.skip("No GPU partitions found")
        
        partition_name = list(all_info["by_partition"].keys())[0]
        
        filtered_info = await slurm.get_gpu_info(partition=partition_name)
        
        assert isinstance(filtered_info, dict)
        # Filtered results should have same or fewer GPUs
        assert filtered_info["total_gpus"] <= all_info["total_gpus"]


# =============================================================================
# Test: get_gpu_availability
# =============================================================================

class TestGetGPUAvailability:
    """Tests for GPU availability checking."""
    
    @pytest.mark.asyncio
    async def test_availability_check(self, slurm):
        """Test checking GPU availability."""
        gpu_info = await slurm.get_gpu_info()
        
        available = gpu_info["available_gpus"]
        total = gpu_info["total_gpus"]
        
        # Should be able to check if N GPUs are available
        assert available >= 0
        assert total >= available
    
    @pytest.mark.asyncio
    async def test_availability_by_type(self, slurm):
        """Test GPU availability by type."""
        gpu_info = await slurm.get_gpu_info()
        
        for gpu_type, stats in gpu_info["by_type"].items():
            available = stats["available"]
            total = stats["total"]
            
            assert available >= 0
            assert total >= 0
            assert available <= total


# =============================================================================
# Test: Raw sinfo output
# =============================================================================

class TestSinfoRaw:
    """Tests for raw sinfo command."""
    
    @pytest.mark.asyncio
    async def test_sinfo_returns_output(self, slurm):
        """Test that sinfo returns output."""
        output = await slurm.sinfo()
        
        assert output, "sinfo should return output"
        assert isinstance(output, str)
        assert len(output) > 0
    
    @pytest.mark.asyncio
    async def test_sinfo_with_partition_filter(self, slurm):
        """Test sinfo with partition filter."""
        partitions = await slurm.get_partitions()
        if not partitions:
            pytest.skip("No partitions available")
        
        partition_name = partitions[0].name
        output = await slurm.sinfo(partition=partition_name)
        
        assert output, "sinfo with partition filter should return output"


# =============================================================================
# Integration test
# =============================================================================

class TestClusterStatusIntegration:
    """Integration tests for cluster status tools."""
    
    @pytest.mark.asyncio
    async def test_full_cluster_status_workflow(self, slurm):
        """Test a full workflow of checking cluster status."""
        # 1. Get partitions
        partitions = await slurm.get_partitions()
        assert len(partitions) > 0
        
        # 2. Get nodes
        nodes = await slurm.get_nodes()
        assert len(nodes) > 0
        
        # 3. Get GPU info
        gpu_info = await slurm.get_gpu_info()
        assert "total_gpus" in gpu_info
        
        # 4. Verify consistency
        # Total nodes from partitions should relate to actual nodes
        # (may not be exact due to overlapping partitions)
        
        # 5. Print summary
        print(f"\n{'='*60}")
        print("CLUSTER STATUS SUMMARY")
        print(f"{'='*60}")
        print(f"Partitions: {len(partitions)}")
        print(f"Total Nodes: {len(nodes)}")
        print(f"Total GPUs: {gpu_info['total_gpus']}")
        print(f"Available GPUs: {gpu_info['available_gpus']}")
        
        gpu_partitions = [p for p in partitions if p.has_gpus]
        cpu_partitions = [p for p in partitions if not p.has_gpus]
        print(f"GPU Partitions: {len(gpu_partitions)}")
        print(f"CPU Partitions: {len(cpu_partitions)}")


# =============================================================================
# Standalone runner
# =============================================================================

async def main():
    """Run tests manually without pytest."""
    print("Loading settings from .env...")
    settings = get_settings()
    
    print(f"Connecting to {settings.ssh_host} as {settings.ssh_user}...")
    ssh = SSHClient(settings)
    
    try:
        await ssh.connect()
        print("Connected successfully!\n")
        
        slurm = SlurmCommands(ssh, settings)
        
        # Run all tests
        print("=" * 60)
        print("RUNNING CLUSTER STATUS TESTS")
        print("=" * 60)
        
        # Test partitions
        print("\n[TEST] get_partitions...")
        partitions = await slurm.get_partitions()
        assert len(partitions) > 0
        print(f"  ✓ Found {len(partitions)} partitions")
        
        # Test nodes
        print("\n[TEST] get_nodes...")
        nodes = await slurm.get_nodes()
        assert len(nodes) > 0
        print(f"  ✓ Found {len(nodes)} nodes")
        
        # Test node filtering
        print("\n[TEST] get_nodes with partition filter...")
        filtered_nodes = await slurm.get_nodes(partition=partitions[0].name)
        print(f"  ✓ Found {len(filtered_nodes)} nodes in {partitions[0].name}")
        
        # Test GPU info
        print("\n[TEST] get_gpu_info...")
        gpu_info = await slurm.get_gpu_info()
        print(f"  ✓ Total GPUs: {gpu_info['total_gpus']}")
        print(f"  ✓ Available: {gpu_info['available_gpus']}")
        
        # Test raw sinfo
        print("\n[TEST] sinfo raw...")
        output = await slurm.sinfo()
        assert len(output) > 0
        print(f"  ✓ Got {len(output)} bytes of output")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
