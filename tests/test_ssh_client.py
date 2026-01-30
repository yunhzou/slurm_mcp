"""Unit tests for SSH client.

These tests require a configured .env file with valid SSH credentials.
Run with: pytest tests/test_ssh_client.py -v
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# removed get_settings import - uses settings fixture from conftest
from slurm_mcp.models import CommandResult
from slurm_mcp.ssh_client import SSHClient, SSHCommandError


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


# =============================================================================
# Test: SSH Connection
# =============================================================================

class TestSSHConnection:
    """Tests for SSH connection management."""
    
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, settings):
        """Test connecting and disconnecting from SSH."""
        client = SSHClient(settings)
        
        # Should not be connected initially
        assert not client.is_connected
        
        # Connect
        await client.connect()
        assert client.is_connected
        
        # Disconnect
        await client.disconnect()
        assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_reconnect(self, settings):
        """Test reconnecting after disconnect."""
        client = SSHClient(settings)
        
        # First connection
        await client.connect()
        assert client.is_connected
        
        # Disconnect
        await client.disconnect()
        assert not client.is_connected
        
        # Reconnect
        await client.connect()
        assert client.is_connected
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_connect_calls(self, settings):
        """Test that multiple connect calls are safe."""
        client = SSHClient(settings)
        
        await client.connect()
        await client.connect()  # Should not error
        
        assert client.is_connected
        
        await client.disconnect()


# =============================================================================
# Test: Command Execution
# =============================================================================

class TestCommandExecution:
    """Tests for SSH command execution."""
    
    @pytest.mark.asyncio
    async def test_execute_simple_command(self, ssh_client):
        """Test executing a simple command."""
        result = await ssh_client.execute("echo 'Hello World'")
        
        assert isinstance(result, CommandResult)
        assert result.success
        assert result.return_code == 0
        assert "Hello World" in result.stdout
    
    @pytest.mark.asyncio
    async def test_execute_command_with_exit_code(self, ssh_client):
        """Test command that returns non-zero exit code."""
        result = await ssh_client.execute("exit 42")
        
        assert not result.success
        assert result.return_code == 42
    
    @pytest.mark.asyncio
    async def test_execute_command_with_stderr(self, ssh_client):
        """Test command that writes to stderr."""
        result = await ssh_client.execute("echo 'Error message' >&2")
        
        assert "Error message" in result.stderr
    
    @pytest.mark.asyncio
    async def test_execute_command_with_both_outputs(self, ssh_client):
        """Test command that writes to both stdout and stderr."""
        result = await ssh_client.execute("echo 'stdout'; echo 'stderr' >&2")
        
        assert "stdout" in result.stdout
        assert "stderr" in result.stderr
    
    @pytest.mark.asyncio
    async def test_execute_command_with_working_directory(self, ssh_client):
        """Test command execution in specific directory."""
        result = await ssh_client.execute("pwd", working_directory="/tmp")
        
        assert result.success
        assert "/tmp" in result.stdout
    
    @pytest.mark.asyncio
    async def test_execute_multiline_command(self, ssh_client):
        """Test executing a multiline command."""
        result = await ssh_client.execute("""
            for i in 1 2 3; do
                echo "Line $i"
            done
        """)
        
        assert result.success
        assert "Line 1" in result.stdout
        assert "Line 2" in result.stdout
        assert "Line 3" in result.stdout
    
    @pytest.mark.asyncio
    async def test_execute_command_with_timeout(self, ssh_client):
        """Test command execution with timeout."""
        # Command should complete within timeout
        result = await ssh_client.execute("sleep 1", timeout=30)
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_execute_command_timeout_exceeded(self, ssh_client):
        """Test command that exceeds timeout."""
        from slurm_mcp.ssh_client import SSHCommandError
        with pytest.raises(SSHCommandError, match="timed out"):
            await ssh_client.execute("sleep 30", timeout=2)


# =============================================================================
# Test: File Operations
# =============================================================================

class TestFileOperations:
    """Tests for SSH file operations."""
    
    @pytest.mark.asyncio
    async def test_write_and_read_file(self, ssh_client, settings):
        """Test writing and reading a file."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_path = f"{settings.user_root}/.ssh_client_test.txt"
        test_content = "Test content from SSH client test"
        
        # Write file (note: content first, then path)
        await ssh_client.write_remote_file(test_content, test_path)
        
        # Read file
        content = await ssh_client.read_remote_file(test_path)
        
        assert test_content in content
        
        # Cleanup
        await ssh_client.execute(f"rm -f {test_path}")
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, ssh_client):
        """Test reading a non-existent file."""
        with pytest.raises(SSHCommandError):
            await ssh_client.read_remote_file("/nonexistent/path/file.txt")
    
    @pytest.mark.asyncio
    async def test_list_directory(self, ssh_client, settings):
        """Test listing a directory."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        files = await ssh_client.list_directory(settings.user_root)
        
        assert isinstance(files, list)
    
    @pytest.mark.asyncio
    async def test_delete_file(self, ssh_client, settings):
        """Test deleting a file."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_path = f"{settings.user_root}/.ssh_delete_test.txt"
        
        # Create file (note: content first, then path)
        await ssh_client.write_remote_file("to delete", test_path)
        
        # Delete file
        await ssh_client.delete_file(test_path)
        
        # Verify deletion
        result = await ssh_client.execute(f"test -f {test_path}")
        assert not result.success  # File should not exist


# =============================================================================
# Test: CommandResult model
# =============================================================================

class TestCommandResultModel:
    """Tests for CommandResult model."""
    
    def test_create_success_result(self):
        """Test creating a successful command result."""
        result = CommandResult(
            stdout="output",
            stderr="",
            return_code=0,
            success=True,
        )
        
        assert result.success
        assert result.return_code == 0
        assert result.stdout == "output"
    
    def test_create_failure_result(self):
        """Test creating a failed command result."""
        result = CommandResult(
            stdout="",
            stderr="error message",
            return_code=1,
            success=False,
        )
        
        assert not result.success
        assert result.return_code == 1
        assert result.stderr == "error message"


# =============================================================================
# Test: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for SSH error handling."""
    
    @pytest.mark.asyncio
    async def test_command_not_found(self, ssh_client):
        """Test executing a non-existent command."""
        result = await ssh_client.execute("nonexistent_command_xyz123")
        
        assert not result.success
        assert result.return_code != 0
    
    @pytest.mark.asyncio
    async def test_permission_denied(self, ssh_client):
        """Test command that fails due to permission."""
        # Try to read a file we shouldn't have access to
        result = await ssh_client.execute("cat /etc/shadow")
        
        assert not result.success


# =============================================================================
# Integration test
# =============================================================================

class TestSSHClientIntegration:
    """Integration tests for SSH client."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, ssh_client, settings):
        """Test a full SSH workflow."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_dir = f"{settings.user_root}/.ssh_test_dir"
        test_file = f"{test_dir}/test.txt"
        
        # 1. Create directory
        result = await ssh_client.execute(f"mkdir -p {test_dir}")
        assert result.success
        
        # 2. Write file (note: content first, then path)
        await ssh_client.write_remote_file("Test content", test_file)
        
        # 3. Read file
        content = await ssh_client.read_remote_file(test_file)
        assert "Test content" in content
        
        # 4. List directory
        files = await ssh_client.list_directory(test_dir)
        file_names = [f.get("name", f) if isinstance(f, dict) else f for f in files]
        assert "test.txt" in file_names
        
        # 5. Execute command in directory
        result = await ssh_client.execute("ls -la", working_directory=test_dir)
        assert result.success
        assert "test.txt" in result.stdout
        
        # 6. Cleanup
        await ssh_client.execute(f"rm -rf {test_dir}")


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
        
        print("=" * 60)
        print("RUNNING SSH CLIENT TESTS")
        print("=" * 60)
        
        # Test simple command
        print("\n[TEST] Simple command...")
        result = await ssh.execute("echo 'Hello'")
        assert result.success
        assert "Hello" in result.stdout
        print("  ✓ Simple command works")
        
        # Test working directory
        print("\n[TEST] Working directory...")
        result = await ssh.execute("pwd", working_directory="/tmp")
        assert "/tmp" in result.stdout
        print("  ✓ Working directory works")
        
        # Test file operations
        if settings.user_root:
            print("\n[TEST] File operations...")
            test_path = f"{settings.user_root}/.ssh_test.txt"
            await ssh.write_remote_file("Test", test_path)
            content = await ssh.read_remote_file(test_path)
            assert "Test" in content
            await ssh.execute(f"rm -f {test_path}")
            print("  ✓ File operations work")
        
        # Test error handling
        print("\n[TEST] Error handling...")
        result = await ssh.execute("exit 42")
        assert not result.success
        assert result.return_code == 42
        print("  ✓ Error handling works")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
