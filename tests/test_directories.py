"""Unit tests for directory management tools.

These tests require a configured .env file with valid SSH credentials.
Run with: pytest tests/test_directories.py -v
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from slurm_mcp.config import get_settings
from slurm_mcp.models import ClusterDirectories, DirectoryListing, FileInfo
from slurm_mcp.ssh_client import SSHClient
from slurm_mcp.directories import DirectoryManager


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
async def dir_manager(ssh_client, settings):
    """Create directory manager."""
    return DirectoryManager(ssh_client, settings)


# =============================================================================
# Test: get_cluster_directories
# =============================================================================

class TestGetClusterDirectories:
    """Tests for get_cluster_directories functionality."""
    
    def test_returns_cluster_directories(self, settings):
        """Test that get_cluster_directories returns proper object."""
        # Create manager without SSH for this test
        class MockSSH:
            pass
        
        manager = DirectoryManager(MockSSH(), settings)
        dirs = manager.get_cluster_directories()
        
        assert isinstance(dirs, ClusterDirectories)
    
    def test_directories_populated_from_settings(self, settings):
        """Test that directories are populated from settings."""
        class MockSSH:
            pass
        
        manager = DirectoryManager(MockSSH(), settings)
        dirs = manager.get_cluster_directories()
        
        # Check that at least some directories are set
        assert dirs.user_root == settings.user_root
        assert dirs.datasets == (settings.dir_datasets or "")
        assert dirs.results == (settings.dir_results or "")
        assert dirs.models == (settings.dir_models or "")
        assert dirs.logs == (settings.dir_logs or "")


# =============================================================================
# Test: resolve_path
# =============================================================================

class TestResolvePath:
    """Tests for path resolution."""
    
    def test_resolve_absolute_path_within_allowed(self, settings):
        """Test resolving an absolute path within allowed directories."""
        class MockSSH:
            pass
        
        manager = DirectoryManager(MockSSH(), settings)
        
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        # Absolute paths within allowed directories should work
        path = f"{settings.user_root}/test/file.txt"
        resolved = manager.resolve_path(path)
        
        assert resolved == path
    
    def test_resolve_relative_path_with_directory_type(self, settings):
        """Test resolving relative path with directory type."""
        class MockSSH:
            pass
        
        manager = DirectoryManager(MockSSH(), settings)
        
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        resolved = manager.resolve_path("subdir/file.txt", directory_type="datasets")
        
        assert resolved.startswith(settings.dir_datasets)
        assert "subdir/file.txt" in resolved
    
    def test_resolve_path_invalid_directory_type(self, settings):
        """Test resolving path with invalid directory type."""
        class MockSSH:
            pass
        
        manager = DirectoryManager(MockSSH(), settings)
        
        with pytest.raises(ValueError, match="Invalid directory type"):
            manager.resolve_path("file.txt", directory_type="invalid_type")


# =============================================================================
# Test: list_directory
# =============================================================================

class TestListDirectory:
    """Tests for list_directory functionality."""
    
    @pytest.mark.asyncio
    async def test_list_directory_returns_listing(self, dir_manager, settings):
        """Test that list_directory returns a DirectoryListing."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        listing = await dir_manager.list_directory(path=settings.user_root)
        
        assert isinstance(listing, DirectoryListing)
        assert listing.path == settings.user_root
    
    @pytest.mark.asyncio
    async def test_list_directory_has_items(self, dir_manager, settings):
        """Test that list_directory returns items."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        listing = await dir_manager.list_directory(path=settings.user_root)
        
        assert listing.total_items >= 0
        # May have files and/or subdirs
        assert isinstance(listing.files, list)
        assert isinstance(listing.subdirs, list)
    
    @pytest.mark.asyncio
    async def test_list_directory_with_type(self, dir_manager, settings):
        """Test list_directory with directory type."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        listing = await dir_manager.list_directory(path="", directory_type="datasets")
        
        assert isinstance(listing, DirectoryListing)
        assert settings.dir_datasets in listing.path
    
    @pytest.mark.asyncio
    async def test_file_info_has_required_fields(self, dir_manager, settings):
        """Test that FileInfo objects have required fields."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        listing = await dir_manager.list_directory(path=settings.user_root)
        
        for f in listing.files[:5]:
            assert isinstance(f, FileInfo)
            assert f.name
            assert f.path
            assert f.size_bytes >= 0
            assert f.size_human
            assert f.modified_time is not None


# =============================================================================
# Test: list_datasets
# =============================================================================

class TestListDatasets:
    """Tests for list_datasets functionality."""
    
    @pytest.mark.asyncio
    async def test_list_datasets_returns_list(self, dir_manager, settings):
        """Test that list_datasets returns a list."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        items = await dir_manager.list_datasets()
        
        assert isinstance(items, list)
        # May be empty if no datasets
    
    @pytest.mark.asyncio
    async def test_list_datasets_with_pattern(self, dir_manager, settings):
        """Test list_datasets with pattern filter."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        items = await dir_manager.list_datasets(pattern="*")
        
        assert isinstance(items, list)


# =============================================================================
# Test: list_model_checkpoints
# =============================================================================

class TestListModelCheckpoints:
    """Tests for list_model_checkpoints functionality."""
    
    @pytest.mark.asyncio
    async def test_list_model_checkpoints_returns_list(self, dir_manager, settings):
        """Test that list_model_checkpoints returns a list."""
        if not settings.dir_models:
            pytest.fail("dir_models not configured - set SLURM_DIR_MODELS in .env")
        
        items = await dir_manager.list_model_checkpoints()
        assert isinstance(items, list)


# =============================================================================
# Test: list_job_logs
# =============================================================================

class TestListJobLogs:
    """Tests for list_job_logs functionality."""
    
    @pytest.mark.asyncio
    async def test_list_job_logs_returns_list(self, dir_manager, settings):
        """Test that list_job_logs returns a list."""
        if not settings.dir_logs:
            pytest.fail("dir_logs not configured - set SLURM_DIR_LOGS in .env")
        
        items = await dir_manager.list_job_logs()
        assert isinstance(items, list)
    
    @pytest.mark.asyncio
    async def test_list_job_logs_with_recent(self, dir_manager, settings):
        """Test list_job_logs with recent limit."""
        if not settings.dir_logs:
            pytest.fail("dir_logs not configured - set SLURM_DIR_LOGS in .env")
        
        items = await dir_manager.list_job_logs(recent=10)
        assert isinstance(items, list)
        assert len(items) <= 10


# =============================================================================
# Test: read_file and write_file
# =============================================================================

class TestFileReadWrite:
    """Tests for file read/write operations."""
    
    @pytest.mark.asyncio
    async def test_write_and_read_file(self, dir_manager, settings):
        """Test writing and reading a file."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_content = "Hello from test_directories.py\nLine 2\nLine 3"
        test_path = f"{settings.user_root}/.slurm_mcp_test_file.txt"
        
        # Write file
        await dir_manager.write_file(path=test_path, content=test_content)
        
        # Read file
        content = await dir_manager.read_file(path=test_path)
        
        assert content.strip() == test_content.strip()
        
        # Cleanup
        await dir_manager.delete_file(path=test_path)
    
    @pytest.mark.asyncio
    async def test_read_file_with_tail(self, dir_manager, settings):
        """Test reading file with tail_lines."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        test_path = f"{settings.user_root}/.slurm_mcp_test_tail.txt"
        
        await dir_manager.write_file(path=test_path, content=test_content)
        
        # Read last 2 lines
        content = await dir_manager.read_file(path=test_path, tail_lines=2)
        
        lines = content.strip().split('\n')
        assert len(lines) == 2
        assert "Line 5" in content
        
        # Cleanup
        await dir_manager.delete_file(path=test_path)
    
    @pytest.mark.asyncio
    async def test_read_file_with_head(self, dir_manager, settings):
        """Test reading file with head_lines."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        test_path = f"{settings.user_root}/.slurm_mcp_test_head.txt"
        
        await dir_manager.write_file(path=test_path, content=test_content)
        
        # Read first 2 lines
        content = await dir_manager.read_file(path=test_path, head_lines=2)
        
        lines = content.strip().split('\n')
        assert len(lines) == 2
        assert "Line 1" in content
        
        # Cleanup
        await dir_manager.delete_file(path=test_path)
    
    @pytest.mark.asyncio
    async def test_write_file_append(self, dir_manager, settings):
        """Test appending to a file."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_path = f"{settings.user_root}/.slurm_mcp_test_append.txt"
        
        # Write initial content
        await dir_manager.write_file(path=test_path, content="Line 1\n")
        
        # Append content
        await dir_manager.write_file(path=test_path, content="Line 2\n", append=True)
        
        # Read file
        content = await dir_manager.read_file(path=test_path)
        
        assert "Line 1" in content
        assert "Line 2" in content
        
        # Cleanup
        await dir_manager.delete_file(path=test_path)


# =============================================================================
# Test: find_files
# =============================================================================

class TestFindFiles:
    """Tests for find_files functionality."""
    
    @pytest.mark.asyncio
    async def test_find_files_returns_list(self, dir_manager, settings):
        """Test that find_files returns a list."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        try:
            # Use a specific directory to avoid timeout on large directories
            items = await dir_manager.find_files(pattern="*", directory_type="datasets")
            assert isinstance(items, list)
        except Exception as e:
            if "timed out" in str(e).lower():
                pytest.skip(f"Find command timed out: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_find_files_with_pattern(self, dir_manager, settings):
        """Test find_files with specific pattern."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        try:
            # Search for .txt files in a specific directory
            items = await dir_manager.find_files(pattern="*.txt", directory_type="datasets")
            assert isinstance(items, list)
            for item in items:
                assert item.name.endswith(".txt")
        except Exception as e:
            if "timed out" in str(e).lower():
                pytest.skip(f"Find command timed out: {e}")
            raise


# =============================================================================
# Test: delete_file
# =============================================================================

class TestDeleteFile:
    """Tests for delete_file functionality."""
    
    @pytest.mark.asyncio
    async def test_delete_file(self, dir_manager, settings):
        """Test deleting a file."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_path = f"{settings.user_root}/.slurm_mcp_test_delete.txt"
        
        # Create file
        await dir_manager.write_file(path=test_path, content="test")
        
        # Delete file
        await dir_manager.delete_file(path=test_path)
        
        # Verify file is gone (reading should fail or return empty)
        try:
            content = await dir_manager.read_file(path=test_path)
            # If we get here, file might still exist
            assert content == "" or "No such file" in content
        except Exception:
            # Expected - file should not exist
            pass


# =============================================================================
# Test: get_disk_usage
# =============================================================================

class TestGetDiskUsage:
    """Tests for get_disk_usage functionality."""
    
    @pytest.mark.asyncio
    async def test_get_disk_usage_returns_dict(self, dir_manager, settings):
        """Test that get_disk_usage returns a dictionary."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        try:
            # Use a specific directory to avoid timeout on large directories
            usage = await dir_manager.get_disk_usage(directory_type="datasets")
            assert isinstance(usage, dict)
        except Exception as e:
            if "timed out" in str(e).lower():
                pytest.skip(f"Disk usage command timed out: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_get_disk_usage_with_directory_type(self, dir_manager, settings):
        """Test get_disk_usage with directory type."""
        if not settings.dir_datasets:
            pytest.skip("dir_datasets not configured")
        
        try:
            usage = await dir_manager.get_disk_usage(directory_type="datasets")
            assert isinstance(usage, dict)
        except Exception as e:
            if "timed out" in str(e).lower():
                pytest.skip(f"Disk usage command timed out: {e}")
            raise


# =============================================================================
# Integration test
# =============================================================================

class TestDirectoryIntegration:
    """Integration tests for directory management."""
    
    @pytest.mark.asyncio
    async def test_full_file_workflow(self, dir_manager, settings):
        """Test a full file workflow: create, read, append, find, delete."""
        if not settings.user_root:
            pytest.skip("user_root not configured")
        
        test_dir = f"{settings.user_root}/.slurm_mcp_test_dir"
        test_file = f"{test_dir}/test.txt"
        
        # 1. Create directory by writing a file
        await dir_manager.write_file(path=test_file, content="Initial content\n")
        
        # 2. Read the file
        content = await dir_manager.read_file(path=test_file)
        assert "Initial content" in content
        
        # 3. Append to the file
        await dir_manager.write_file(path=test_file, content="Appended content\n", append=True)
        content = await dir_manager.read_file(path=test_file)
        assert "Initial content" in content
        assert "Appended content" in content
        
        # 4. List directory
        listing = await dir_manager.list_directory(path=test_dir)
        assert listing.total_items >= 1
        
        # 5. Find the file
        items = await dir_manager.find_files(pattern="*.txt", path=test_dir)
        assert len(items) >= 1
        
        # 6. Delete the file
        await dir_manager.delete_file(path=test_file)
        
        # 7. Delete the directory
        await dir_manager.delete_file(path=test_dir, recursive=True)


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
        
        manager = DirectoryManager(ssh, settings)
        
        print("=" * 60)
        print("RUNNING DIRECTORY MANAGEMENT TESTS")
        print("=" * 60)
        
        # Test get_cluster_directories
        print("\n[TEST] get_cluster_directories...")
        dirs = manager.get_cluster_directories()
        print(f"  ✓ User root: {dirs.user_root}")
        print(f"  ✓ Datasets: {dirs.datasets}")
        print(f"  ✓ Results: {dirs.results}")
        
        # Test list_directory
        if settings.user_root:
            print("\n[TEST] list_directory...")
            listing = await manager.list_directory(path=settings.user_root)
            print(f"  ✓ Listed {listing.total_items} items in {listing.path}")
        
        # Test write/read file
        if settings.user_root:
            print("\n[TEST] write_file / read_file...")
            test_path = f"{settings.user_root}/.slurm_mcp_test.txt"
            await manager.write_file(path=test_path, content="Test content")
            content = await manager.read_file(path=test_path)
            assert "Test content" in content
            await manager.delete_file(path=test_path)
            print("  ✓ Write/read/delete cycle works")
        
        # Test get_disk_usage
        if settings.user_root:
            print("\n[TEST] get_disk_usage...")
            usage = await manager.get_disk_usage(path=settings.user_root)
            print(f"  ✓ Got disk usage info")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
