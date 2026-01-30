"""Configuration management for Slurm MCP server.

Multi-cluster configuration via JSON config file (clusters.json).
Each cluster can have multiple node types (login, data, vscode).

Environment variable SLURM_CLUSTERS_CONFIG can point to a custom JSON config file.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class ClusterNodes(BaseModel):
    """Configuration for different node types within a cluster.
    
    Clusters typically have different nodes for different purposes:
    - login: For job submission, light work (NO heavy data transfers, NO VS Code)
    - data: For large data transfers (data copier nodes)
    - vscode: For IDE sessions (VS Code, Cursor)
    
    The agent can freely choose which node to connect to based on the task.
    """
    
    login: list[str] = Field(
        default_factory=list,
        description="Login node hostnames (for job submission, light work)"
    )
    data: list[str] = Field(
        default_factory=list,
        description="Data copier node hostnames (for large data transfers)"
    )
    vscode: list[str] = Field(
        default_factory=list,
        description="VS Code node hostnames (for IDE sessions)"
    )
    
    def get_node(self, node_type: str, index: int = 0) -> Optional[str]:
        """Get a node hostname by type and index.
        
        Args:
            node_type: Type of node ('login', 'data', 'vscode')
            index: Index of the node (default 0, first node)
            
        Returns:
            Node hostname or None if not found.
        """
        nodes = getattr(self, node_type, [])
        if nodes and 0 <= index < len(nodes):
            return nodes[index]
        return None
    
    def list_all_nodes(self) -> dict[str, list[str]]:
        """List all configured nodes by type."""
        return {
            "login": self.login,
            "data": self.data,
            "vscode": self.vscode,
        }


class ClusterConfig(BaseModel):
    """Configuration for a single Slurm cluster.
    
    This model contains all settings needed to connect to and interact with
    a single Slurm cluster. Supports multiple node types for different purposes.
    """
    
    # Cluster identification
    name: str = Field(description="Unique cluster name/identifier")
    description: Optional[str] = Field(default=None, description="Human-readable description")
    
    # SSH Connection Settings
    ssh_host: Optional[str] = Field(default=None, description="DEPRECATED: Use nodes.login instead. Will be auto-migrated.")
    ssh_port: int = Field(default=22, description="SSH port")
    ssh_user: str = Field(description="SSH username")
    ssh_key_path: Optional[str] = Field(default=None, description="Path to SSH private key file")
    ssh_password: Optional[str] = Field(default=None, description="SSH password (for key passphrase or password auth)")
    ssh_known_hosts: Optional[str] = Field(default=None, description="Path to known_hosts file")
    
    # Multi-node configuration
    nodes: Optional[ClusterNodes] = Field(
        default=None,
        description="Node hostnames by type (login, data, vscode)"
    )
    default_node_type: str = Field(
        default="login",
        description="Default node type to use when not specified"
    )
    
    # Slurm Settings
    default_partition: Optional[str] = Field(default=None, description="Default partition for job submission")
    default_account: Optional[str] = Field(default=None, description="Default account/project for job submission")
    command_timeout: int = Field(default=60, description="Command timeout in seconds")
    
    # GPU/CPU Partition Classification
    gpu_partitions: Optional[str] = Field(default=None, description="Comma-separated list of GPU partition names")
    cpu_partitions: Optional[str] = Field(default=None, description="Comma-separated list of CPU-only partition names")
    
    # Container/Image Settings
    image_dir: Optional[str] = Field(default=None, description="Directory containing .sqsh container images")
    default_image: Optional[str] = Field(default=None, description="Default container image (.sqsh file path)")
    
    # Interactive Session Settings
    interactive_partition: str = Field(default="interactive", description="Partition for interactive jobs")
    interactive_account: Optional[str] = Field(default=None, description="Account/project for interactive jobs")
    interactive_default_time: str = Field(default="4:00:00", description="Default time limit for interactive sessions")
    interactive_default_gpus: int = Field(default=8, description="Default GPUs for interactive sessions")
    interactive_session_timeout: int = Field(default=3600, description="Idle timeout for persistent sessions (seconds)")
    
    # Cluster Directory Structure
    user_root: str = Field(description="User's root directory on cluster (base for other dirs)")
    dir_datasets: Optional[str] = Field(default=None, description="Directory for training datasets")
    dir_results: Optional[str] = Field(default=None, description="Directory for job outputs/results")
    dir_models: Optional[str] = Field(default=None, description="Directory for model checkpoints/weights")
    dir_logs: Optional[str] = Field(default=None, description="Directory for job stdout/stderr logs")
    dir_projects: Optional[str] = Field(default=None, description="Directory for project source code")
    dir_scratch: Optional[str] = Field(default=None, description="Scratch/temp directory for jobs")
    dir_home: Optional[str] = Field(default=None, description="User home directory on cluster")
    dir_container_root: Optional[str] = Field(default=None, description="Custom root overlay for containers")
    gpfs_root: Optional[str] = Field(default=None, description="Root of GPFS/Lustre filesystem")
    
    # Profile storage
    profiles_path: Optional[str] = Field(default=None, description="Path to store interactive session profiles")
    
    @model_validator(mode="after")
    def set_directory_defaults(self) -> "ClusterConfig":
        """Set default directory paths and migrate ssh_host to nodes."""
        # Migrate ssh_host to nodes if nodes not provided
        if self.nodes is None:
            if self.ssh_host:
                logger.warning(
                    f"Cluster '{self.name}': 'ssh_host' is deprecated. "
                    f"Please migrate to 'nodes' format. Auto-migrating '{self.ssh_host}' to nodes.login."
                )
                self.nodes = ClusterNodes(login=[self.ssh_host])
            else:
                # Create empty nodes
                self.nodes = ClusterNodes()
        
        # Validate that at least one node is configured
        if not self.nodes.login and not self.nodes.data and not self.nodes.vscode:
            raise ValueError(
                f"Cluster '{self.name}': At least one node must be configured in 'nodes'. "
                f"Example: \"nodes\": {{\"login\": [\"hostname.example.com\"]}}"
            )
        
        # Set directory defaults based on user_root
        if self.user_root:
            if self.dir_datasets is None:
                self.dir_datasets = f"{self.user_root}/data"
            if self.dir_results is None:
                self.dir_results = f"{self.user_root}/results"
            if self.dir_models is None:
                self.dir_models = f"{self.user_root}/models"
            if self.dir_logs is None:
                self.dir_logs = f"{self.user_root}/logs"
            if self.dir_projects is None:
                self.dir_projects = f"{self.user_root}/Projects"
            if self.dir_container_root is None:
                self.dir_container_root = f"{self.user_root}/root"
            if self.image_dir is None:
                self.image_dir = f"{self.user_root}/images"
            if self.profiles_path is None:
                self.profiles_path = f"{self.user_root}/.slurm_mcp/profiles.json"
        
        # Set interactive account from default account if not specified
        if self.interactive_account is None and self.default_account:
            self.interactive_account = self.default_account
            
        return self
    
    def get_ssh_host(self, node: Optional[str] = None) -> str:
        """Get SSH host for the specified node.
        
        Args:
            node: Can be:
                - None: Use default node type
                - Node type: 'login', 'data', 'vscode' (uses first node of that type)
                - Specific hostname: Used directly
                - 'type:index' format: e.g., 'login:1' for second login node
                
        Returns:
            SSH hostname to connect to.
            
        Raises:
            ValueError: If no valid host can be determined.
        """
        # If no node specified, use default
        if node is None:
            node = self.default_node_type
        
        # Check if it's a node type
        if node in ('login', 'data', 'vscode'):
            nodes_list = getattr(self.nodes, node, [])
            if nodes_list:
                return nodes_list[0]  # Return first node of that type
        
        # Check for 'type:index' format
        if ':' in node:
            parts = node.split(':', 1)
            if len(parts) == 2 and parts[0] in ('login', 'data', 'vscode'):
                node_type, idx_str = parts
                try:
                    idx = int(idx_str)
                    host = self.nodes.get_node(node_type, idx)
                    if host:
                        return host
                except ValueError:
                    pass
        
        # Check if it's a direct hostname that matches any configured node
        all_nodes = self.nodes.list_all_nodes()
        for nodes_list in all_nodes.values():
            if node in nodes_list:
                return node
        
        # If it looks like a hostname (contains a dot), use directly
        if '.' in node:
            return node
        
        raise ValueError(
            f"Cannot determine SSH host for node '{node}'. "
            f"Configure nodes properly in cluster config."
        )
    
    def list_available_nodes(self) -> dict[str, list[str]]:
        """List all available nodes by type.
        
        Returns:
            Dictionary mapping node types to list of hostnames.
        """
        return self.nodes.list_all_nodes()
    
    @property
    def gpu_partition_list(self) -> list[str]:
        """Get list of GPU partitions."""
        if self.gpu_partitions:
            return [p.strip() for p in self.gpu_partitions.split(",")]
        return []
    
    @property
    def cpu_partition_list(self) -> list[str]:
        """Get list of CPU partitions."""
        if self.cpu_partitions:
            return [p.strip() for p in self.cpu_partitions.split(",")]
        return []
    
    @property
    def ssh_key_path_resolved(self) -> Optional[Path]:
        """Get resolved SSH key path."""
        if self.ssh_key_path:
            return Path(self.ssh_key_path).expanduser()
        return None
    
    def get_container_mounts(self) -> str:
        """Generate container mount string from configured directories."""
        mounts = []
        
        if self.dir_datasets:
            mounts.append(f"{self.dir_datasets}:/datasets")
        if self.dir_results:
            mounts.append(f"{self.dir_results}:/results")
        if self.dir_models:
            mounts.append(f"{self.dir_models}:/models")
        if self.dir_logs:
            mounts.append(f"{self.dir_logs}:/logs")
        if self.dir_projects:
            mounts.append(f"{self.dir_projects}:/projects")
        if self.dir_container_root:
            mounts.append(f"{self.dir_container_root}:/root")
        if self.dir_home:
            mounts.append(f"{self.dir_home}:/home")
        if self.gpfs_root:
            mounts.append(f"{self.gpfs_root}:/lustre")
            
        return ",".join(mounts)


class MultiClusterConfig(BaseModel):
    """Configuration for multiple Slurm clusters.
    
    This is the schema for the clusters.json configuration file.
    """
    
    default_cluster: Optional[str] = Field(
        default=None,
        description="Name of the default cluster to use when not specified"
    )
    clusters: list[ClusterConfig] = Field(
        default_factory=list,
        description="List of cluster configurations"
    )
    
    @model_validator(mode="after")
    def validate_clusters(self) -> "MultiClusterConfig":
        """Validate cluster configuration."""
        if not self.clusters:
            return self
        
        # Check for duplicate cluster names
        names = [c.name for c in self.clusters]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate cluster names found in configuration")
        
        # Set default cluster if not specified
        if self.default_cluster is None and self.clusters:
            self.default_cluster = self.clusters[0].name
        
        # Validate default cluster exists
        if self.default_cluster and self.default_cluster not in names:
            raise ValueError(f"Default cluster '{self.default_cluster}' not found in clusters list")
        
        return self
    
    def get_cluster(self, name: Optional[str] = None) -> Optional[ClusterConfig]:
        """Get cluster config by name, or default cluster if name is None."""
        if name is None:
            name = self.default_cluster
        
        for cluster in self.clusters:
            if cluster.name == name:
                return cluster
        
        return None
    
    def list_cluster_names(self) -> list[str]:
        """Get list of all cluster names."""
        return [c.name for c in self.clusters]


def load_clusters_config(config_path: Optional[str] = None) -> MultiClusterConfig:
    """Load multi-cluster configuration from JSON file.
    
    Args:
        config_path: Path to the JSON config file. If None, looks for:
            1. SLURM_CLUSTERS_CONFIG environment variable
            2. ./clusters.json
            3. ~/.slurm_mcp/clusters.json
            
    Returns:
        MultiClusterConfig instance.
        
    Raises:
        FileNotFoundError: If config file not found.
        ValueError: If config file is invalid.
    """
    # Determine config file path
    if config_path is None:
        config_path = os.environ.get("SLURM_CLUSTERS_CONFIG")
    
    if config_path is None:
        # Look for config in standard locations
        candidates = [
            Path("./clusters.json"),
            Path("~/.slurm_mcp/clusters.json").expanduser(),
        ]
        
        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break
    
    if config_path is None:
        raise FileNotFoundError(
            "No clusters.json config file found. Create one at ./clusters.json or "
            "~/.slurm_mcp/clusters.json, or set SLURM_CLUSTERS_CONFIG environment variable."
        )
    
    config_file = Path(config_path).expanduser()
    
    if not config_file.exists():
        raise FileNotFoundError(f"Clusters config file not found: {config_file}")
    
    logger.info(f"Loading cluster configuration from {config_file}")
    
    with open(config_file, "r") as f:
        data = json.load(f)
    
    return MultiClusterConfig(**data)
