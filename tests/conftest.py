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


@pytest.fixture
def settings():
    """Get settings from environment - shared fixture."""
    from slurm_mcp.config import get_settings
    return get_settings()


@pytest.fixture
async def ssh_client(settings):
    """Create and connect SSH client - shared fixture."""
    from slurm_mcp.ssh_client import SSHClient
    
    client = SSHClient(settings)
    await client.connect()
    yield client
    await client.disconnect()


@pytest.fixture
async def slurm(ssh_client, settings):
    """Create Slurm commands wrapper - shared fixture."""
    from slurm_mcp.slurm_commands import SlurmCommands
    return SlurmCommands(ssh_client, settings)


@pytest.fixture
async def dir_manager(ssh_client, settings):
    """Create directory manager - shared fixture."""
    from slurm_mcp.directories import DirectoryManager
    return DirectoryManager(ssh_client, settings)


@pytest.fixture
async def profile_manager(ssh_client, settings):
    """Create profile manager - shared fixture."""
    from slurm_mcp.profiles import ProfileManager
    return ProfileManager(ssh_client, settings)


@pytest.fixture
async def session_manager(ssh_client, slurm, settings):
    """Create interactive session manager - shared fixture."""
    from slurm_mcp.interactive import InteractiveSessionManager
    return InteractiveSessionManager(ssh_client, slurm, settings)
