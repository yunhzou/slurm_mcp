"""Shared pytest fixtures and configuration.

This module provides common fixtures used across all test modules.
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file at module import time
load_dotenv()


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-expensive",
        action="store_true",
        default=False,
        help="Run expensive tests that allocate cluster resources",
    )


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "expensive: mark test as expensive (allocates cluster resources)",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on options."""
    if config.getoption("--run-expensive"):
        # Don't skip expensive tests
        return
    
    skip_expensive = pytest.mark.skip(reason="need --run-expensive option to run")
    for item in items:
        if "expensive" in item.keywords:
            item.add_marker(skip_expensive)


# =============================================================================
# Shared Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """Return the event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


def create_test_cluster_config() -> "ClusterConfig":
    """Create a test ClusterConfig from environment variables (for backward compat)."""
    import os
    from slurm_mcp.config import ClusterConfig, ClusterNodes
    
    # Build nodes from SLURM_SSH_HOST if provided
    ssh_host = os.environ.get("SLURM_SSH_HOST", "")
    
    return ClusterConfig(
        name="test",
        description="Test cluster for unit tests",
        ssh_port=int(os.environ.get("SLURM_SSH_PORT", "22")),
        ssh_user=os.environ.get("SLURM_SSH_USER", ""),
        ssh_key_path=os.environ.get("SLURM_SSH_KEY_PATH"),
        ssh_password=os.environ.get("SLURM_SSH_PASSWORD"),
        ssh_known_hosts=os.environ.get("SLURM_SSH_KNOWN_HOSTS"),
        nodes=ClusterNodes(
            login=[ssh_host] if ssh_host else [],
            data=[],
            vscode=[],
        ),
        default_node_type="login",
        default_partition=os.environ.get("SLURM_DEFAULT_PARTITION"),
        default_account=os.environ.get("SLURM_DEFAULT_ACCOUNT"),
        command_timeout=int(os.environ.get("SLURM_COMMAND_TIMEOUT", "60")),
        gpu_partitions=os.environ.get("SLURM_GPU_PARTITIONS"),
        cpu_partitions=os.environ.get("SLURM_CPU_PARTITIONS"),
        image_dir=os.environ.get("SLURM_IMAGE_DIR"),
        default_image=os.environ.get("SLURM_DEFAULT_IMAGE"),
        interactive_partition=os.environ.get("SLURM_INTERACTIVE_PARTITION", "interactive"),
        interactive_account=os.environ.get("SLURM_INTERACTIVE_ACCOUNT"),
        interactive_default_time=os.environ.get("SLURM_INTERACTIVE_DEFAULT_TIME", "4:00:00"),
        interactive_default_gpus=int(os.environ.get("SLURM_INTERACTIVE_DEFAULT_GPUS", "8")),
        interactive_session_timeout=int(os.environ.get("SLURM_INTERACTIVE_SESSION_TIMEOUT", "3600")),
        user_root=os.environ.get("SLURM_USER_ROOT", ""),
        dir_datasets=os.environ.get("SLURM_DIR_DATASETS"),
        dir_results=os.environ.get("SLURM_DIR_RESULTS"),
        dir_models=os.environ.get("SLURM_DIR_MODELS"),
        dir_logs=os.environ.get("SLURM_DIR_LOGS"),
        dir_projects=os.environ.get("SLURM_DIR_PROJECTS"),
        dir_scratch=os.environ.get("SLURM_DIR_SCRATCH"),
        dir_home=os.environ.get("SLURM_DIR_HOME"),
        dir_container_root=os.environ.get("SLURM_DIR_CONTAINER_ROOT"),
        gpfs_root=os.environ.get("SLURM_GPFS_ROOT"),
        profiles_path=os.environ.get("SLURM_PROFILES_PATH"),
    )


@pytest.fixture
def cluster_config():
    """Get ClusterConfig from environment - shared fixture."""
    return create_test_cluster_config()


# Alias for backward compatibility with tests that use "settings"
@pytest.fixture
def settings():
    """Get ClusterConfig from environment - alias for backward compatibility."""
    return create_test_cluster_config()


@pytest.fixture
async def ssh_client(cluster_config):
    """Create and connect SSH client - shared fixture."""
    from slurm_mcp.ssh_client import SSHClient
    
    client = SSHClient(cluster_config)
    await client.connect()
    yield client
    await client.disconnect()


@pytest.fixture
async def slurm(ssh_client, cluster_config):
    """Create Slurm commands wrapper - shared fixture."""
    from slurm_mcp.slurm_commands import SlurmCommands
    return SlurmCommands(ssh_client, cluster_config)


@pytest.fixture
async def dir_manager(ssh_client, cluster_config):
    """Create directory manager - shared fixture."""
    from slurm_mcp.directories import DirectoryManager
    return DirectoryManager(ssh_client, cluster_config)


@pytest.fixture
async def profile_manager(ssh_client, cluster_config):
    """Create profile manager - shared fixture."""
    from slurm_mcp.profiles import ProfileManager
    return ProfileManager(ssh_client, cluster_config)


@pytest.fixture
async def session_manager(ssh_client, slurm, cluster_config):
    """Create interactive session manager - shared fixture."""
    from slurm_mcp.interactive import InteractiveSessionManager
    return InteractiveSessionManager(ssh_client, slurm, cluster_config)
