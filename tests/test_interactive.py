"""Unit tests for interactive session tools.

These tests require a configured .env file with valid SSH credentials.
Note: Some tests may allocate actual cluster resources - use with caution.
Run with: pytest tests/test_interactive.py -v
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# removed get_settings import - uses settings fixture from conftest
from slurm_mcp.models import InteractiveSession, InteractiveProfile
from slurm_mcp.ssh_client import SSHClient
from slurm_mcp.slurm_commands import SlurmCommands
from slurm_mcp.interactive import InteractiveSessionManager


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


@pytest.fixture
async def session_manager(ssh_client, slurm, settings):
    """Create interactive session manager."""
    return InteractiveSessionManager(ssh_client, slurm, settings)


# =============================================================================
# Test: InteractiveSession model
# =============================================================================

class TestInteractiveSessionModel:
    """Tests for InteractiveSession model."""
    
    def test_create_session(self):
        """Test creating an InteractiveSession."""
        from datetime import datetime
        
        session = InteractiveSession(
            session_id="abc12345",
            job_id=12345,
            partition="interactive",
            nodes=1,
            gpus_per_node=1,
            start_time=datetime.now(),
            time_limit="4:00:00",
            status="running",
        )
        
        assert session.session_id == "abc12345"
        assert session.job_id == 12345
        assert session.partition == "interactive"
        assert session.nodes == 1
        assert session.gpus_per_node == 1
        assert session.status == "running"
    
    def test_session_with_optional_fields(self):
        """Test creating session with optional fields."""
        from datetime import datetime
        
        session = InteractiveSession(
            session_id="test123",
            job_id=99999,
            partition="gpu",
            nodes=2,
            gpus_per_node=8,
            start_time=datetime.now(),
            time_limit="8:00:00",
            status="running",
            session_name="my-dev-session",
            container_image="/images/pytorch.sqsh",
            container_mounts="/data:/data",
            node_list="node001,node002",
            time_remaining="7:30:00",
        )
        
        assert session.session_name == "my-dev-session"
        assert session.container_image == "/images/pytorch.sqsh"
        assert session.node_list == "node001,node002"
        assert session.time_remaining == "7:30:00"


# =============================================================================
# Test: InteractiveProfile model
# =============================================================================

class TestInteractiveProfileModel:
    """Tests for InteractiveProfile model."""
    
    def test_create_profile(self):
        """Test creating an InteractiveProfile."""
        profile = InteractiveProfile(
            name="dev-gpu",
            description="Development environment with GPU",
            partition="interactive",
            nodes=1,
            gpus_per_node=1,
            time_limit="4:00:00",
        )
        
        assert profile.name == "dev-gpu"
        assert profile.description == "Development environment with GPU"
        assert profile.partition == "interactive"
        assert profile.nodes == 1
        assert profile.gpus_per_node == 1
    
    def test_create_profile_with_container(self):
        """Test creating profile with container settings."""
        profile = InteractiveProfile(
            name="pytorch-dev",
            description="PyTorch development environment",
            partition="gpu",
            nodes=1,
            gpus_per_node=4,
            time_limit="8:00:00",
            container_image="/images/pytorch.sqsh",
            container_mounts="/data:/data,/models:/models",
        )
        
        assert profile.container_image == "/images/pytorch.sqsh"
        assert "/data:/data" in profile.container_mounts


# =============================================================================
# Test: InteractiveSessionManager - list_sessions
# =============================================================================

class TestListSessions:
    """Tests for list_sessions functionality."""
    
    @pytest.mark.asyncio
    async def test_list_sessions_returns_list(self, session_manager):
        """Test that list_sessions returns a list."""
        sessions = await session_manager.list_sessions()
        
        assert isinstance(sessions, list)
        # May be empty if no active sessions


# =============================================================================
# Test: InteractiveSessionManager - get_session
# =============================================================================

class TestGetSession:
    """Tests for get_session functionality."""
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_manager):
        """Test getting a non-existent session."""
        session = await session_manager.get_session("nonexistent-id")
        
        assert session is None


# =============================================================================
# Test: InteractiveSessionManager - end_session
# =============================================================================

class TestEndSession:
    """Tests for end_session functionality."""
    
    @pytest.mark.asyncio
    async def test_end_nonexistent_session(self, session_manager):
        """Test ending a non-existent session."""
        result = await session_manager.end_session("nonexistent-id")
        
        assert result is False


# =============================================================================
# Test: run_command (one-shot)
# Note: This actually allocates resources, so it's marked for manual run
# =============================================================================

class TestRunCommand:
    """Tests for run_command functionality."""
    
    @pytest.mark.asyncio
    @pytest.mark.expensive
    async def test_run_simple_command(self, session_manager, settings):
        """Test running a simple command with resource allocation."""
        if not settings.interactive_partition:
            pytest.fail("interactive_partition not configured")
        
        result = await session_manager.run_command(
            command="hostname",
            partition=settings.interactive_partition,
            account=settings.interactive_account,
            nodes=1,
            time_limit="0:05:00",
            timeout=300,
        )
        
        assert result.success
        assert result.stdout  # Should have hostname output
        print(f"\n  Hostname: {result.stdout.strip()}")


# =============================================================================
# Test: Session lifecycle
# Note: This actually allocates resources, so it's marked for manual run
# =============================================================================

class TestSessionLifecycle:
    """Tests for full session lifecycle."""
    
    @pytest.mark.asyncio
    @pytest.mark.expensive
    async def test_full_session_lifecycle(self, session_manager, slurm, settings):
        """Test starting, using, and ending a session."""
        if not settings.interactive_partition:
            pytest.fail("interactive_partition not configured")
        
        session = None
        job_id = None
        
        try:
            # Start session
            print(f"\n  Starting session on partition '{settings.interactive_partition}'...")
            session = await session_manager.start_session(
                session_name="test-session",
                partition=settings.interactive_partition,
                account=settings.interactive_account,
                nodes=1,
                gpus_per_node=settings.interactive_default_gpus,
                time_limit="0:10:00",
            )
            
            job_id = session.job_id
            print(f"  Session started: {session.session_id}, Job ID: {job_id}")
            
            assert session.session_id
            assert session.job_id > 0
            
            # Wait for session to be ready
            print("  Waiting for job to start...")
            for i in range(30):  # Wait up to 30 seconds
                await asyncio.sleep(1)
                job = await slurm.get_job_details(job_id)
                if job and job.state == "RUNNING":
                    print(f"  Job is running on nodes: {job.nodes}")
                    break
            else:
                print("  Warning: Job may not have started yet")
            
            # Execute command in session
            print("  Executing command in session...")
            result = await session_manager.exec_command(
                session_id=session.session_id,
                command="hostname && echo test_successful",
                timeout=60,
            )
            
            print(f"  Command output: {result.stdout.strip()}")
            assert result.success
            assert "test_successful" in result.stdout or result.stdout.strip()  # Should have output
            
            # List sessions
            sessions = await session_manager.list_sessions()
            assert any(s.session_id == session.session_id for s in sessions)
            print(f"  Session verified in list ({len(sessions)} active sessions)")
            
        finally:
            # Always clean up - end session and cancel job
            if session:
                print(f"  Ending session {session.session_id}...")
                success = await session_manager.end_session(session.session_id)
                print(f"  Session ended: {success}")
            
            # Double-check job is cancelled
            if job_id:
                print(f"  Ensuring job {job_id} is cancelled...")
                await slurm.scancel(job_id)
                print(f"  Job {job_id} cancelled")


# =============================================================================
# Test: Configuration defaults
# =============================================================================

class TestInteractiveConfig:
    """Tests for interactive session configuration."""
    
    def test_interactive_partition_config(self, settings):
        """Test interactive partition configuration."""
        # Interactive partition should be configured or have default
        assert settings.interactive_partition is not None or settings.slurm_default_partition is not None
    
    def test_interactive_defaults(self, settings):
        """Test interactive session defaults."""
        # Check defaults are sensible
        if settings.interactive_default_time:
            assert ":" in settings.interactive_default_time  # Should be time format
    
    def test_container_mounts_generated(self, settings):
        """Test that container mounts are properly generated."""
        mounts = settings.get_container_mounts()
        
        assert isinstance(mounts, str)


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
        manager = InteractiveSessionManager(ssh, slurm, settings)
        
        print("=" * 60)
        print("RUNNING INTERACTIVE SESSION TESTS")
        print("=" * 60)
        
        # Test list_sessions
        print("\n[TEST] list_sessions...")
        sessions = await manager.list_sessions()
        print(f"  ✓ Found {len(sessions)} active sessions")
        
        # Test InteractiveSession model
        print("\n[TEST] InteractiveSession model...")
        from datetime import datetime
        session = InteractiveSession(
            session_id="test",
            job_id=1,
            partition="test",
            nodes=1,
            start_time=datetime.now(),
            time_limit="1:00:00",
            status="test",
        )
        assert session.session_id == "test"
        print("  ✓ InteractiveSession model works")
        
        # Test InteractiveProfile model
        print("\n[TEST] InteractiveProfile model...")
        profile = InteractiveProfile(
            name="test",
            partition="test",
            nodes=1,
        )
        assert profile.name == "test"
        print("  ✓ InteractiveProfile model works")
        
        # Test configuration
        print("\n[TEST] Interactive configuration...")
        print(f"  ✓ Interactive partition: {settings.interactive_partition}")
        print(f"  ✓ Interactive account: {settings.interactive_account}")
        print(f"  ✓ Default time: {settings.interactive_default_time}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("\n⚠ Note: Session lifecycle tests skipped (would allocate resources)")
        print("  Run with: pytest tests/test_interactive.py -v --run-expensive")
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
