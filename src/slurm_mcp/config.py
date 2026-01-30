"""Configuration management for Slurm MCP server.

Supports both single-cluster (backward compatible) and multi-cluster configurations.

Multi-cluster configuration can be done via:
1. JSON config file (clusters.json)
2. Environment variable SLURM_CLUSTERS_CONFIG pointing to a JSON file
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ClusterConfig(BaseModel):
    """Configuration for a single Slurm cluster.
    
    This model contains all settings needed to connect to and interact with
    a single Slurm cluster.
    """
    
    # Cluster identification
    name: str = Field(description="Unique cluster name/identifier")
    description: Optional[str] = Field(default=None, description="Human-readable description")
    
    # SSH Connection Settings
    ssh_host: str = Field(description="Remote Slurm login node hostname")
    ssh_port: int = Field(default=22, description="SSH port")
    ssh_user: str = Field(description="SSH username")
    ssh_key_path: Optional[str] = Field(default=None, description="Path to SSH private key file")
    ssh_password: Optional[str] = Field(default=None, description="SSH password (for key passphrase or password auth)")
    ssh_known_hosts: Optional[str] = Field(default=None, description="Path to known_hosts file")
    
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
        """Set default directory paths based on user_root if not explicitly provided."""
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


class Settings(BaseSettings):
    """Configuration settings for Slurm MCP server (single-cluster mode).
    
    All settings can be configured via environment variables with the SLURM_ prefix.
    This class is kept for backward compatibility.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="SLURM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # SSH Connection Settings
    ssh_host: str = Field(
        default="",
        description="Remote Slurm login node hostname"
    )
    ssh_port: int = Field(
        default=22,
        description="SSH port"
    )
    ssh_user: str = Field(
        default="",
        description="SSH username"
    )
    ssh_key_path: Optional[str] = Field(
        default=None,
        description="Path to SSH private key file"
    )
    ssh_password: Optional[str] = Field(
        default=None,
        description="SSH password (for key passphrase or password auth)"
    )
    ssh_known_hosts: Optional[str] = Field(
        default=None,
        description="Path to known_hosts file"
    )
    
    # Slurm Settings
    default_partition: Optional[str] = Field(
        default=None,
        description="Default partition for job submission"
    )
    default_account: Optional[str] = Field(
        default=None,
        description="Default account/project for job submission"
    )
    command_timeout: int = Field(
        default=60,
        description="Command timeout in seconds"
    )
    
    # GPU/CPU Partition Classification
    gpu_partitions: Optional[str] = Field(
        default=None,
        description="Comma-separated list of GPU partition names"
    )
    cpu_partitions: Optional[str] = Field(
        default=None,
        description="Comma-separated list of CPU-only partition names"
    )
    
    # Container/Image Settings
    image_dir: Optional[str] = Field(
        default=None,
        description="Directory containing .sqsh container images"
    )
    default_image: Optional[str] = Field(
        default=None,
        description="Default container image (.sqsh file path)"
    )
    
    # Interactive Session Settings
    interactive_partition: str = Field(
        default="interactive",
        description="Partition for interactive jobs"
    )
    interactive_account: Optional[str] = Field(
        default=None,
        description="Account/project for interactive jobs"
    )
    interactive_default_time: str = Field(
        default="4:00:00",
        description="Default time limit for interactive sessions"
    )
    interactive_default_gpus: int = Field(
        default=8,
        description="Default GPUs for interactive sessions"
    )
    interactive_session_timeout: int = Field(
        default=3600,
        description="Idle timeout for persistent sessions (seconds)"
    )
    
    # Cluster Directory Structure
    user_root: str = Field(
        default="",
        description="User's root directory on cluster (base for other dirs)"
    )
    dir_datasets: Optional[str] = Field(
        default=None,
        description="Directory for training datasets"
    )
    dir_results: Optional[str] = Field(
        default=None,
        description="Directory for job outputs/results"
    )
    dir_models: Optional[str] = Field(
        default=None,
        description="Directory for model checkpoints/weights"
    )
    dir_logs: Optional[str] = Field(
        default=None,
        description="Directory for job stdout/stderr logs"
    )
    dir_projects: Optional[str] = Field(
        default=None,
        description="Directory for project source code"
    )
    dir_scratch: Optional[str] = Field(
        default=None,
        description="Scratch/temp directory for jobs"
    )
    dir_home: Optional[str] = Field(
        default=None,
        description="User home directory on cluster"
    )
    dir_container_root: Optional[str] = Field(
        default=None,
        description="Custom root overlay for containers"
    )
    gpfs_root: Optional[str] = Field(
        default=None,
        description="Root of GPFS/Lustre filesystem"
    )
    
    # Profile storage
    profiles_path: Optional[str] = Field(
        default=None,
        description="Path to store interactive session profiles"
    )
    
    # Multi-cluster settings
    clusters_config: Optional[str] = Field(
        default=None,
        description="Path to JSON config file for multi-cluster setup"
    )
    
    @model_validator(mode="after")
    def set_directory_defaults(self) -> "Settings":
        """Set default directory paths based on user_root if not explicitly provided."""
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
    
    def to_cluster_config(self, name: str = "default") -> ClusterConfig:
        """Convert Settings to ClusterConfig for backward compatibility."""
        return ClusterConfig(
            name=name,
            ssh_host=self.ssh_host,
            ssh_port=self.ssh_port,
            ssh_user=self.ssh_user,
            ssh_key_path=self.ssh_key_path,
            ssh_password=self.ssh_password,
            ssh_known_hosts=self.ssh_known_hosts,
            default_partition=self.default_partition,
            default_account=self.default_account,
            command_timeout=self.command_timeout,
            gpu_partitions=self.gpu_partitions,
            cpu_partitions=self.cpu_partitions,
            image_dir=self.image_dir,
            default_image=self.default_image,
            interactive_partition=self.interactive_partition,
            interactive_account=self.interactive_account,
            interactive_default_time=self.interactive_default_time,
            interactive_default_gpus=self.interactive_default_gpus,
            interactive_session_timeout=self.interactive_session_timeout,
            user_root=self.user_root,
            dir_datasets=self.dir_datasets,
            dir_results=self.dir_results,
            dir_models=self.dir_models,
            dir_logs=self.dir_logs,
            dir_projects=self.dir_projects,
            dir_scratch=self.dir_scratch,
            dir_home=self.dir_home,
            dir_container_root=self.dir_container_root,
            gpfs_root=self.gpfs_root,
            profiles_path=self.profiles_path,
        )


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


def get_settings() -> Settings:
    """Get settings instance. Can be overridden for testing."""
    return Settings()


def get_cluster_configs() -> MultiClusterConfig:
    """Load cluster configurations.
    
    This function tries to load configurations in the following order:
    1. JSON config file (if SLURM_CLUSTERS_CONFIG is set or clusters.json exists)
    2. Fall back to environment variables (single cluster mode)
    
    Returns:
        MultiClusterConfig instance.
    """
    # First, try to load from JSON config file
    try:
        return load_clusters_config()
    except FileNotFoundError:
        logger.debug("No clusters.json found, falling back to environment variables")
    
    # Fall back to environment variables (single cluster mode)
    settings = get_settings()
    
    # Check if we have valid single-cluster config
    if not settings.ssh_host or not settings.ssh_user:
        raise ValueError(
            "No cluster configuration found. Either create a clusters.json file "
            "or set SLURM_SSH_HOST and SLURM_SSH_USER environment variables."
        )
    
    # Convert to multi-cluster format with single cluster
    cluster_config = settings.to_cluster_config(name="default")
    
    return MultiClusterConfig(
        default_cluster="default",
        clusters=[cluster_config]
    )
