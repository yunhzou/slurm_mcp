"""Cluster manager for handling multiple Slurm clusters.

This module provides the ClusterManager class which manages connections
and resources for multiple Slurm clusters, with support for different
node types (login, data, vscode) within each cluster.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from slurm_mcp.config import ClusterConfig, MultiClusterConfig, get_cluster_configs
from slurm_mcp.directories import DirectoryManager
from slurm_mcp.interactive import InteractiveSessionManager
from slurm_mcp.profiles import ProfileManager
from slurm_mcp.slurm_commands import SlurmCommands
from slurm_mcp.ssh_client import SSHClient

logger = logging.getLogger(__name__)


@dataclass
class NodeConnection:
    """Represents a connection to a specific node."""
    
    hostname: str
    ssh_client: SSHClient
    connected: bool = False


@dataclass
class ClusterInstances:
    """Container for all instances related to a single cluster.
    
    Supports multiple node connections within the same cluster.
    """
    
    config: ClusterConfig
    # Node connections keyed by hostname
    node_connections: dict[str, NodeConnection] = field(default_factory=dict)
    # Current active node hostname
    current_node: Optional[str] = None
    
    @property
    def ssh_client(self) -> Optional[SSHClient]:
        """Get SSH client for current node."""
        if self.current_node and self.current_node in self.node_connections:
            return self.node_connections[self.current_node].ssh_client
        return None
    
    @property
    def connected(self) -> bool:
        """Check if any node is connected."""
        return any(nc.connected for nc in self.node_connections.values())
    
    @property
    def slurm_commands(self) -> Optional[SlurmCommands]:
        """Get Slurm commands for current node."""
        if self.ssh_client:
            return SlurmCommands(self.ssh_client, self.config)
        return None
    
    @property
    def session_manager(self) -> Optional[InteractiveSessionManager]:
        """Get session manager for current node."""
        if self.ssh_client and self.slurm_commands:
            return InteractiveSessionManager(self.ssh_client, self.slurm_commands, self.config)
        return None
    
    @property
    def profile_manager(self) -> Optional[ProfileManager]:
        """Get profile manager for current node."""
        if self.ssh_client:
            return ProfileManager(self.ssh_client, self.config)
        return None
    
    @property
    def directory_manager(self) -> Optional[DirectoryManager]:
        """Get directory manager for current node."""
        if self.ssh_client:
            return DirectoryManager(self.ssh_client, self.config)
        return None


class ClusterManager:
    """Manager for multiple Slurm cluster connections.
    
    This class handles:
    - Loading cluster configurations
    - Managing SSH connections to different nodes within each cluster
    - Supporting different node types (login, data, vscode)
    - Providing cluster-specific instances (SlurmCommands, etc.)
    - Session-level default cluster selection
    
    Example usage:
        manager = ClusterManager()
        await manager.initialize()
        
        # Connect to default cluster, default node
        instances = await manager.get_cluster_instances()
        
        # Connect to specific cluster and node type
        instances = await manager.get_cluster_instances("cluster1", node="data")
        
        # Connect to specific hostname
        instances = await manager.get_cluster_instances("cluster1", node="cluster1-dc-02.example.com")
        
        # List all available nodes
        nodes = manager.list_cluster_nodes("cluster1")
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
                self._clusters[cluster_config.name] = ClusterInstances(
                    config=cluster_config,
                    node_connections={},
                    current_node=None,
                )
            
            self._initialized = True
            logger.info(f"ClusterManager initialized with {len(self._clusters)} cluster(s)")
    
    def _create_ssh_client(self, config: ClusterConfig, hostname: str) -> SSHClient:
        """Create an SSH client for a specific hostname.
        
        Args:
            config: Cluster configuration.
            hostname: The hostname to connect to.
            
        Returns:
            SSHClient configured for the hostname.
        """
        # Create a modified config with the specific hostname
        # We use the same config but override ssh_host when connecting
        return SSHClient(config, hostname_override=hostname)
    
    async def get_cluster_instances(
        self,
        cluster_name: Optional[str] = None,
        node: Optional[str] = None,
    ) -> ClusterInstances:
        """Get instances for a cluster and node, connecting if necessary.
        
        Args:
            cluster_name: Name of the cluster. If None, uses default cluster.
            node: Node specification. Can be:
                - None: Use default node type (usually 'login')
                - Node type: 'login', 'data', 'vscode'
                - Specific hostname
                - 'type:index' format: e.g., 'login:1'
            
        Returns:
            ClusterInstances for the requested cluster/node.
            
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
        config = instances.config
        
        # Resolve the hostname
        hostname = config.get_ssh_host(node)
        
        # Check if we already have a connection to this node
        if hostname not in instances.node_connections:
            # Create new connection
            ssh_client = self._create_ssh_client(config, hostname)
            instances.node_connections[hostname] = NodeConnection(
                hostname=hostname,
                ssh_client=ssh_client,
                connected=False,
            )
        
        node_conn = instances.node_connections[hostname]
        
        # Connect if not already connected
        if not node_conn.connected:
            async with self._lock:
                if not node_conn.connected:
                    logger.info(f"Connecting to {cluster_name}:{hostname}...")
                    await node_conn.ssh_client.connect()
                    node_conn.connected = True
                    logger.info(f"Connected to {cluster_name}:{hostname}")
        
        # Set current node
        instances.current_node = hostname
        
        return instances
    
    def list_clusters(self) -> list[dict]:
        """List all configured clusters.
        
        Returns:
            List of cluster info dictionaries.
        """
        clusters = []
        
        for name, instances in self._clusters.items():
            config = instances.config
            
            # Get available nodes info
            available_nodes = config.list_available_nodes()
            
            # Get connected nodes
            connected_nodes = [
                hostname for hostname, nc in instances.node_connections.items()
                if nc.connected
            ]
            
            clusters.append({
                "name": name,
                "description": config.description,
                "ssh_user": config.ssh_user,
                "available_nodes": available_nodes,
                "connected_nodes": connected_nodes,
                "current_node": instances.current_node,
                "is_default": name == self._default_cluster,
            })
        
        return clusters
    
    def list_cluster_nodes(self, cluster_name: Optional[str] = None) -> dict[str, list[str]]:
        """List all available nodes for a cluster.
        
        Args:
            cluster_name: Name of the cluster. If None, uses default cluster.
            
        Returns:
            Dictionary mapping node types to list of hostnames.
        """
        if cluster_name is None:
            cluster_name = self._default_cluster
        
        if cluster_name and cluster_name in self._clusters:
            return self._clusters[cluster_name].config.list_available_nodes()
        
        return {}
    
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
    
    async def connect_node(self, cluster_name: str, node: Optional[str] = None) -> str:
        """Explicitly connect to a specific node.
        
        Args:
            cluster_name: Name of the cluster.
            node: Node specification (type, hostname, or type:index).
            
        Returns:
            The hostname that was connected to.
            
        Raises:
            ValueError: If cluster not found.
        """
        instances = await self.get_cluster_instances(cluster_name, node)
        return instances.current_node or ""
    
    async def disconnect_node(self, cluster_name: str, hostname: str) -> bool:
        """Disconnect from a specific node.
        
        Args:
            cluster_name: Name of the cluster.
            hostname: The hostname to disconnect.
            
        Returns:
            True if disconnection successful.
        """
        if cluster_name not in self._clusters:
            return False
        
        instances = self._clusters[cluster_name]
        
        if hostname in instances.node_connections:
            node_conn = instances.node_connections[hostname]
            if node_conn.connected:
                async with self._lock:
                    if node_conn.connected:
                        await node_conn.ssh_client.disconnect()
                        node_conn.connected = False
                        
                        # Clear current node if it was this one
                        if instances.current_node == hostname:
                            instances.current_node = None
            return True
        
        return False
    
    async def disconnect_cluster(self, cluster_name: str) -> bool:
        """Disconnect all nodes from a cluster.
        
        Args:
            cluster_name: Name of the cluster to disconnect.
            
        Returns:
            True if disconnection successful.
        """
        if cluster_name not in self._clusters:
            return False
        
        instances = self._clusters[cluster_name]
        
        for hostname in list(instances.node_connections.keys()):
            await self.disconnect_node(cluster_name, hostname)
        
        return True
    
    async def disconnect_all(self) -> None:
        """Disconnect from all clusters and nodes."""
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
