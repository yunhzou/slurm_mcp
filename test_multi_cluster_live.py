#!/usr/bin/env python3
"""Test script for multi-cluster functionality.

This script tests connecting to multiple clusters and creating files.
"""

import asyncio
import sys
from datetime import datetime

# Add the source directory to path
sys.path.insert(0, "/Users/yunhengz/slurm_mcp/src")

from slurm_mcp.config import load_clusters_config
from slurm_mcp.cluster_manager import ClusterManager


async def test_multi_cluster():
    """Test multi-cluster connectivity and file operations."""
    
    print("=" * 60)
    print("Multi-Cluster Test")
    print("=" * 60)
    
    # Load configuration
    config = load_clusters_config("/Users/yunhengz/slurm_mcp/clusters.json")
    print(f"\n✓ Loaded config with {len(config.clusters)} clusters:")
    for c in config.clusters:
        print(f"  - {c.name}: {c.ssh_host}")
    
    # Create cluster manager
    manager = ClusterManager(config)
    await manager.initialize()
    print(f"\n✓ ClusterManager initialized")
    print(f"  Default cluster: {manager.default_cluster}")
    
    # Test each cluster
    for cluster_name in config.list_cluster_names():
        print(f"\n{'='*60}")
        print(f"Testing cluster: {cluster_name}")
        print("=" * 60)
        
        try:
            # Get cluster instances (this will connect)
            print(f"\n→ Connecting to {cluster_name}...")
            instances = await manager.get_cluster_instances(cluster_name)
            print(f"✓ Connected to {cluster_name}")
            
            # Test SSH command
            print(f"\n→ Running 'hostname' command...")
            result = await instances.ssh_client.execute("hostname")
            if result.success:
                print(f"✓ Hostname: {result.stdout.strip()}")
            else:
                print(f"✗ Failed: {result.stderr}")
                continue
            
            # Create hello world file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"Hello World from multi-cluster test!\n\nCluster: {cluster_name}\nTimestamp: {timestamp}\nHost: {result.stdout.strip()}\n"
            
            file_path = f"{instances.config.user_root}/hello_world_test.txt"
            print(f"\n→ Creating file: {file_path}")
            
            await instances.ssh_client.write_remote_file(content, file_path, make_dirs=True)
            print(f"✓ File created successfully")
            
            # Verify by reading it back
            print(f"\n→ Reading file back...")
            read_content = await instances.ssh_client.read_remote_file(file_path)
            print(f"✓ File contents:\n{'-'*40}")
            print(read_content)
            print(f"{'-'*40}")
            
        except Exception as e:
            print(f"✗ Error with {cluster_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Cleanup
    print(f"\n{'='*60}")
    print("Disconnecting from all clusters...")
    await manager.disconnect_all()
    print("✓ All connections closed")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_multi_cluster())
