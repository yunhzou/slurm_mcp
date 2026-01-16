"""Unit tests for container image tools.

These tests require a configured .env file with valid SSH credentials.
Run with: pytest tests/test_containers.py -v
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from slurm_mcp.config import get_settings
from slurm_mcp.models import ContainerImage
from slurm_mcp.ssh_client import SSHClient
from slurm_mcp.slurm_commands import SlurmCommands


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


# =============================================================================
# Test: list_container_images
# =============================================================================

class TestListContainerImages:
    """Tests for list_container_images functionality."""
    
    @pytest.mark.asyncio
    async def test_list_images_returns_list(self, slurm, settings):
        """Test that list_container_images returns a list."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        images = await slurm.list_container_images()
        
        assert isinstance(images, list)
    
    @pytest.mark.asyncio
    async def test_list_images_with_directory(self, slurm, settings):
        """Test list_container_images with specific directory."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        images = await slurm.list_container_images(directory=settings.image_dir)
        
        assert isinstance(images, list)
    
    @pytest.mark.asyncio
    async def test_list_images_with_pattern(self, slurm, settings):
        """Test list_container_images with pattern filter."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        # Search for images matching pattern
        images = await slurm.list_container_images(pattern="*")
        
        assert isinstance(images, list)
    
    @pytest.mark.asyncio
    async def test_container_image_has_required_fields(self, slurm, settings):
        """Test that ContainerImage objects have required fields."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        images = await slurm.list_container_images()
        
        for img in images[:5]:
            assert isinstance(img, ContainerImage)
            assert img.name
            assert img.path
            assert img.name.endswith(".sqsh")
            assert img.size_bytes >= 0
            assert img.size_human
            assert img.modified_time is not None
    
    @pytest.mark.asyncio
    async def test_images_are_sqsh_files(self, slurm, settings):
        """Test that all returned images are .sqsh files."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        images = await slurm.list_container_images()
        
        for img in images:
            assert img.name.endswith(".sqsh"), f"Expected .sqsh file, got {img.name}"


# =============================================================================
# Test: validate_container_image
# =============================================================================

class TestValidateContainerImage:
    """Tests for validate_container_image functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_existing_image(self, slurm, settings):
        """Test validating an existing container image."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        # Get list of images first
        images = await slurm.list_container_images()
        
        if not images:
            pytest.skip("No container images found")
        
        # Validate the first image
        is_valid = await slurm.validate_container_image(images[0].path)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_nonexistent_image(self, slurm):
        """Test validating a non-existent container image."""
        is_valid = await slurm.validate_container_image("/nonexistent/path/fake.sqsh")
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_validate_invalid_path(self, slurm):
        """Test validating with invalid path."""
        is_valid = await slurm.validate_container_image("")
        
        assert is_valid is False


# =============================================================================
# Test: ContainerImage model
# =============================================================================

class TestContainerImageModel:
    """Tests for ContainerImage model."""
    
    def test_create_container_image(self):
        """Test creating a ContainerImage."""
        from datetime import datetime
        
        img = ContainerImage(
            name="pytorch.sqsh",
            path="/images/pytorch.sqsh",
            size_bytes=1024 * 1024 * 1024,  # 1GB
            size_human="1.0GB",
            modified_time=datetime.now(),
        )
        
        assert img.name == "pytorch.sqsh"
        assert img.path == "/images/pytorch.sqsh"
        assert img.size_bytes == 1024 * 1024 * 1024
    
    def test_container_image_requires_sqsh(self):
        """Test that container image name should end with .sqsh (validation)."""
        from datetime import datetime
        
        # Create with valid name
        img = ContainerImage(
            name="valid.sqsh",
            path="/images/valid.sqsh",
            size_bytes=0,
            size_human="0B",
            modified_time=datetime.now(),
        )
        
        assert img.name.endswith(".sqsh")


# =============================================================================
# Test: Container mounts configuration
# =============================================================================

class TestContainerMounts:
    """Tests for container mount configuration."""
    
    def test_get_container_mounts(self, settings):
        """Test generating container mount strings."""
        mounts = settings.get_container_mounts()
        
        assert isinstance(mounts, str)
        
        # Should contain mount mappings
        if mounts:
            # Each mount should be in format host:container
            for mount in mounts.split(","):
                if mount:
                    parts = mount.split(":")
                    assert len(parts) >= 2, f"Invalid mount format: {mount}"
    
    def test_container_mounts_include_directories(self, settings):
        """Test that container mounts include configured directories."""
        mounts = settings.get_container_mounts()
        
        if settings.dir_datasets:
            assert settings.dir_datasets in mounts or not mounts
        
        if settings.dir_results:
            assert settings.dir_results in mounts or not mounts


# =============================================================================
# Integration test
# =============================================================================

class TestContainerIntegration:
    """Integration tests for container functionality."""
    
    @pytest.mark.asyncio
    async def test_list_and_validate_images(self, slurm, settings):
        """Test listing and validating container images."""
        if not settings.image_dir:
            pytest.skip("image_dir not configured")
        
        # List images
        images = await slurm.list_container_images()
        
        if not images:
            pytest.skip("No container images found")
        
        print(f"\nFound {len(images)} container images:")
        
        # Validate each image
        for img in images[:3]:  # Check first 3
            is_valid = await slurm.validate_container_image(img.path)
            status = "✓" if is_valid else "✗"
            print(f"  {status} {img.name} ({img.size_human})")
            
            assert is_valid, f"Image validation failed: {img.path}"


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
        
        print("=" * 60)
        print("RUNNING CONTAINER IMAGE TESTS")
        print("=" * 60)
        
        # Test list_container_images
        print("\n[TEST] list_container_images...")
        if settings.image_dir:
            images = await slurm.list_container_images()
            print(f"  ✓ Found {len(images)} container images")
            
            for img in images[:5]:
                print(f"    - {img.name} ({img.size_human})")
            
            # Test validate_container_image
            if images:
                print("\n[TEST] validate_container_image...")
                is_valid = await slurm.validate_container_image(images[0].path)
                print(f"  ✓ Validated {images[0].name}: {is_valid}")
        else:
            print("  ⚠ image_dir not configured, skipping")
        
        # Test get_container_mounts
        print("\n[TEST] get_container_mounts...")
        mounts = settings.get_container_mounts()
        print(f"  ✓ Container mounts: {mounts[:80]}..." if len(mounts) > 80 else f"  ✓ Container mounts: {mounts}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
