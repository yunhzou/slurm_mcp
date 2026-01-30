"""Cluster manager for handling multiple Slurm clusters.

This module provides the ClusterManager class which manages connections
and resources for multiple Slurm clusters.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from slurm_mcp.config import ClusterConfig, MultiClusterConfig, get_cluster_configs
from slurm_mcp.directories import DirectoryManager
from slurm_mcp.interactive import InteractiveSessionManager
from slurm_mcp.profiles import ProfileManager
from slurm_mcp.slurm_commands import SlurmCommands
from slurm_mcp.ssh_client import SSHClient

logger = logging.getLogger(__name__)


@dataclass
class ClusterInstances:
    """Container for all instances related to a single cluster."""
    
    config: ClusterConfig
    ssh_client: SSHClient
    slurm_commands: SlurmCommands
    session_manager: InteractiveSessionManager
    profile_manager: ProfileManager
    directory_manager: DirectoryManager
    connected: bool = False


class ClusterManager:
    """Manager for multiple Slurm cluster connections.
    
    This class handles:
    - Loading cluster configurations
    - Managing SSH connections for each cluster
    - Providing cluster-specific instances (SlurmCommands, etc.)
    - Session-level default cluster selection
    
    Example usage:
        manager = ClusterManager()
        await manager.initialize()
        
        # Get instances for default cluster
        instances = await manager.get_cluster_instances()
        
        # Get instances for specific cluster
        instances = await manager.get_cluster_instances("cluster2")
        
        # List all clusters
        clusters = manager.list_clusters()
    """
    
    def __init__(self, config: Optional[MultiClusterConfig] = None):
        """Initialize the cluster manager.
        
        Args:
            config: Optional pre-loaded configuration. If None, will load from
                    standard locations when initialize() is called.
        """
        self._config = config
        self._clusters: dict[str, ClusterInstances] = {}
        self._default_cluster: Optional[str] = None
        self._lock = asyncio.Lock()
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized
    
    @property
    def default_cluster(self) -> Optional[str]:
        """Get the name of the default cluster."""
        return self._default_cluster
    
    @default_cluster.setter
    def default_cluster(self, cluster_name: str) -> None:
        """Set the default cluster.
        
        Args:
            cluster_name: Name of the cluster to set as default.
            
        Raises:
            ValueError: If cluster name is not found in configuration.
        """
        if self._config and cluster_name not in self._config.list_cluster_names():
            raise ValueError(f"Cluster '{cluster_name}' not found in configuration")
        self._default_cluster = cluster_name
    
    async def initialize(self) -> None:
        """Initialize the cluster manager.
        
        Loads configuration and prepares cluster instances (but does not connect).
        
        Raises:
            ValueError: If no valid configuration is found.
        """
        async with self._lock:
            if self._initialized:
                return
            
            # Load configuration if not provided
            if self._config is None:
                self._config = get_cluster_configs()
            
            # Set default cluster
            self._default_cluster = self._config.default_cluster
            
            # Initialize cluster instances (lazy - connections made on first use)
            for cluster_config in self._config.clusters:
                self._clusters[cluster_config.name] = self._create_cluster_instances(cluster_config)
            
            self._initialized = True
            logger.info(f"ClusterManager initialized with {len(self._clusters)} cluster(s)")
    
    def _create_cluster_instances(self, config: ClusterConfig) -> ClusterInstances:
        """Create instances for a cluster (without connecting).
        
        Args:
            config: Cluster configuration.
            
        Returns:
            ClusterInstances with all managers initialized.
        """
        # Create SSH client
        ssh_client = SSHClient(config)
        
        # Create Slurm commands wrapper
        slurm_commands = SlurmCommands(ssh_client, config)
        
        # Create session manager
        session_manager = InteractiveSessionManager(ssh_client, slurm_commands, config)
        
        # Create profile manager
        profile_manager = ProfileManager(ssh_client, config)
        
        # Create directory manager
        directory_manager = DirectoryManager(ssh_client, config)
        
        return ClusterInstances(
            config=config,
            ssh_client=ssh_client,
            slurm_commands=slurm_commands,
            session_manager=session_manager,
            profile_manager=profile_manager,
            directory_manager=directory_manager,
            connected=False,
        )
    
    async def get_cluster_instances(self, cluster_name: Optional[str] = None) -> ClusterInstances:
        """Get instances for a cluster, connecting if necessary.
        
        Args:
            cluster_name: Name of the cluster. If None, uses default cluster.
            
        Returns:
            ClusterInstances for the requested cluster.
            
        Raises:
            ValueError: If cluster is not found or manager not initialized.
        """
        if not self._initialized:
            await self.initialize()
        
        # Use default cluster if not specified
        if cluster_name is None:
            cluster_name = self._default_cluster
        
        if cluster_name is None:
            raise ValueError("No cluster specified and no default cluster configured")
        
        if cluster_name not in self._clusters:
            raise ValueError(f"Cluster '{cluster_name}' not found. Available: {list(self._clusters.keys())}")
        
        instances = self._clusters[cluster_name]
        
        # Connect if not already connected
        if not instances.connected:
            async with self._lock:
                # Double-check after acquiring lock
                if not instances.connected:
                    logger.info(f"Connecting to cluster '{cluster_name}'...")
                    await instances.ssh_client.connect()
                    instances.connected = True
                    logger.info(f"Connected to cluster '{cluster_name}'")
        
        return instances
    
    def list_clusters(self) -> list[dict]:
        """List all configured clusters.
        
        Returns:
            List of cluster info dictionaries with name, description, host, and connection status.
        """
        clusters = []
        
        for name, instances in self._clusters.items():
            clusters.append({
                "name": name,
                "description": instances.config.description,
                "ssh_host": instances.config.ssh_host,
                "ssh_user": instances.config.ssh_user,
                "connected": instances.connected,
                "is_default": name == self._default_cluster,
            })
        
        return clusters
    
    def get_cluster_config(self, cluster_name: Optional[str] = None) -> Optional[ClusterConfig]:
        """Get configuration for a specific cluster.
        
        Args:
            cluster_name: Name of the cluster. If None, uses default cluster.
            
        Returns:
            ClusterConfig or None if not found.
        """
        if cluster_name is None:
            cluster_name = self._default_cluster
        
        if cluster_name and cluster_name in self._clusters:
            return self._clusters[cluster_name].config
        
        return None
    
    async def connect_cluster(self, cluster_name: str) -> bool:
        """Explicitly connect to a cluster.
        
        Args:
            cluster_name: Name of the cluster to connect.
            
        Returns:
            True if connection successful.
            
        Raises:
            ValueError: If cluster not found.
        """
        if cluster_name not in self._clusters:
            raise ValueError(f"Cluster '{cluster_name}' not found")
        
        instances = self._clusters[cluster_name]
        
        if not instances.connected:
            async with self._lock:
                if not instances.connected:
                    await instances.ssh_client.connect()
                    instances.connected = True
        
        return True
    
    async def disconnect_cluster(self, cluster_name: str) -> bool:
        """Disconnect from a cluster.
        
        Args:
            cluster_name: Name of the cluster to disconnect.
            
        Returns:
            True if disconnection successful.
        """
        if cluster_name not in self._clusters:
            return False
        
        instances = self._clusters[cluster_name]
        
        if instances.connected:
            async with self._lock:
                if instances.connected:
                    await instances.ssh_client.disconnect()
                    instances.connected = False
        
        return True
    
    async def disconnect_all(self) -> None:
        """Disconnect from all clusters."""
        for cluster_name in self._clusters:
            await self.disconnect_cluster(cluster_name)
    
    def set_default_cluster(self, cluster_name: str) -> None:
        """Set the session-level default cluster.
        
        Args:
            cluster_name: Name of the cluster to set as default.
            
        Raises:
            ValueError: If cluster not found.
        """
        if cluster_name not in self._clusters:
            raise ValueError(f"Cluster '{cluster_name}' not found. Available: {list(self._clusters.keys())}")
        
        self._default_cluster = cluster_name
        logger.info(f"Default cluster set to '{cluster_name}'")
    
    async def __aenter__(self) -> "ClusterManager":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - disconnect all clusters."""
        await self.disconnect_all()


# Global cluster manager instance (lazy initialized)
_cluster_manager: Optional[ClusterManager] = None


async def get_cluster_manager() -> ClusterManager:
    """Get or create the global ClusterManager instance.
    
    Returns:
        Initialized ClusterManager instance.
    """
    global _cluster_manager
    
    if _cluster_manager is None:
        _cluster_manager = ClusterManager()
    
    if not _cluster_manager.is_initialized:
        await _cluster_manager.initialize()
    
    return _cluster_manager


async def reset_cluster_manager() -> None:
    """Reset the global cluster manager (disconnect and clear)."""
    global _cluster_manager
    
    if _cluster_manager is not None:
        await _cluster_manager.disconnect_all()
        _cluster_manager = None
