"""Configuration management for Slurm MCP server."""

from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Slurm MCP server.
    
    All settings can be configured via environment variables with the SLURM_ prefix.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="SLURM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # SSH Connection Settings
    ssh_host: str = Field(
        description="Remote Slurm login node hostname"
    )
    ssh_port: int = Field(
        default=22,
        description="SSH port"
    )
    ssh_user: str = Field(
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


def get_settings() -> Settings:
    """Get settings instance. Can be overridden for testing."""
    return Settings()
