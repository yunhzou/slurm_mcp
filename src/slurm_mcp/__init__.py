"""Slurm MCP Server - Remote Slurm cluster management via MCP protocol."""

__version__ = "0.1.0"

from slurm_mcp.config import ClusterConfig, MultiClusterConfig, Settings
from slurm_mcp.cluster_manager import ClusterManager, get_cluster_manager
from slurm_mcp.models import (
    ClusterDirectories,
    CommandResult,
    ContainerImage,
    FileInfo,
    GPUInfo,
    InteractiveProfile,
    InteractiveSession,
    JobInfo,
    JobSubmission,
    NodeInfo,
    PartitionInfo,
)

__all__ = [
    # Config
    "Settings",
    "ClusterConfig",
    "MultiClusterConfig",
    # Cluster Manager
    "ClusterManager",
    "get_cluster_manager",
    # Models
    "CommandResult",
    "JobInfo",
    "NodeInfo",
    "PartitionInfo",
    "JobSubmission",
    "ContainerImage",
    "GPUInfo",
    "InteractiveSession",
    "InteractiveProfile",
    "ClusterDirectories",
    "FileInfo",
]
