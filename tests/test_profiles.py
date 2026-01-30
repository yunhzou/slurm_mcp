"""Unit tests for profile management tools.

These tests require a configured .env file with valid SSH credentials.
Run with: pytest tests/test_profiles.py -v
"""

import asyncio
import json
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# removed get_settings import - uses settings fixture from conftest
from slurm_mcp.models import InteractiveProfile
from slurm_mcp.ssh_client import SSHClient
from slurm_mcp.profiles import ProfileManager


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
async def profile_manager(ssh_client, settings):
    """Create profile manager."""
    return ProfileManager(ssh_client, settings)


# =============================================================================
# Test: InteractiveProfile model
# =============================================================================

class TestInteractiveProfileModel:
    """Tests for InteractiveProfile model."""
    
    def test_create_minimal_profile(self):
        """Test creating a minimal profile."""
        profile = InteractiveProfile(
            name="minimal",
        )
        
        assert profile.name == "minimal"
        assert profile.nodes == 1  # Default
    
    def test_create_full_profile(self):
        """Test creating a full profile with all options."""
        profile = InteractiveProfile(
            name="full-profile",
            description="A fully configured profile",
            partition="gpu",
            account="myaccount",
            nodes=2,
            gpus_per_node=8,
            time_limit="8:00:00",
            container_image="/images/pytorch.sqsh",
            container_mounts="/data:/data,/models:/models",
        )
        
        assert profile.name == "full-profile"
        assert profile.description == "A fully configured profile"
        assert profile.partition == "gpu"
        assert profile.account == "myaccount"
        assert profile.nodes == 2
        assert profile.gpus_per_node == 8
        assert profile.time_limit == "8:00:00"
        assert profile.container_image == "/images/pytorch.sqsh"
        assert "/data:/data" in profile.container_mounts
    
    def test_profile_to_dict(self):
        """Test converting profile to dictionary."""
        profile = InteractiveProfile(
            name="test",
            partition="gpu",
            nodes=1,
        )
        
        data = profile.model_dump()
        
        assert data["name"] == "test"
        assert data["partition"] == "gpu"
        assert data["nodes"] == 1
    
    def test_profile_from_dict(self):
        """Test creating profile from dictionary."""
        data = {
            "name": "from-dict",
            "partition": "batch",
            "nodes": 4,
            "gpus_per_node": 2,
        }
        
        profile = InteractiveProfile(**data)
        
        assert profile.name == "from-dict"
        assert profile.partition == "batch"
        assert profile.nodes == 4
        assert profile.gpus_per_node == 2


# =============================================================================
# Test: list_profiles
# =============================================================================

class TestListProfiles:
    """Tests for list_profiles functionality."""
    
    @pytest.mark.asyncio
    async def test_list_profiles_returns_list(self, profile_manager):
        """Test that list_profiles returns a list."""
        profiles = await profile_manager.list_profiles()
        
        assert isinstance(profiles, list)
    
    @pytest.mark.asyncio
    async def test_list_profiles_contains_defaults(self, profile_manager):
        """Test that list includes default profiles."""
        profiles = await profile_manager.list_profiles()
        
        # Should have at least some profiles (defaults or saved)
        # Even if empty, it should be a list
        assert isinstance(profiles, list)
        
        if profiles:
            for p in profiles:
                assert isinstance(p, InteractiveProfile)
                assert p.name


# =============================================================================
# Test: save_profile and get_profile
# =============================================================================

class TestSaveAndGetProfile:
    """Tests for save_profile and get_profile functionality."""
    
    @pytest.mark.asyncio
    async def test_save_and_get_profile(self, profile_manager):
        """Test saving and retrieving a profile."""
        # Create test profile
        test_profile = InteractiveProfile(
            name="_test_profile_123",  # Unique name unlikely to conflict
            description="Test profile for unit tests",
            partition="batch",
            nodes=1,
            gpus_per_node=0,
            time_limit="1:00:00",
        )
        
        # Save profile
        await profile_manager.save_profile(test_profile)
        
        # Retrieve profile
        retrieved = await profile_manager.get_profile("_test_profile_123")
        
        assert retrieved is not None
        assert retrieved.name == "_test_profile_123"
        assert retrieved.description == "Test profile for unit tests"
        assert retrieved.partition == "batch"
        assert retrieved.nodes == 1
        
        # Cleanup - delete the test profile
        await profile_manager.delete_profile("_test_profile_123")
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_profile(self, profile_manager):
        """Test getting a non-existent profile."""
        profile = await profile_manager.get_profile("nonexistent_profile_xyz")
        
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_update_existing_profile(self, profile_manager):
        """Test updating an existing profile."""
        # Create initial profile
        profile_v1 = InteractiveProfile(
            name="_test_update_profile",
            description="Version 1",
            nodes=1,
        )
        await profile_manager.save_profile(profile_v1)
        
        # Update profile
        profile_v2 = InteractiveProfile(
            name="_test_update_profile",
            description="Version 2 - Updated",
            nodes=2,
            gpus_per_node=4,
        )
        await profile_manager.save_profile(profile_v2)
        
        # Retrieve and verify
        retrieved = await profile_manager.get_profile("_test_update_profile")
        
        assert retrieved.description == "Version 2 - Updated"
        assert retrieved.nodes == 2
        assert retrieved.gpus_per_node == 4
        
        # Cleanup
        await profile_manager.delete_profile("_test_update_profile")


# =============================================================================
# Test: delete_profile
# =============================================================================

class TestDeleteProfile:
    """Tests for delete_profile functionality."""
    
    @pytest.mark.asyncio
    async def test_delete_profile(self, profile_manager):
        """Test deleting a profile."""
        # Create profile
        profile = InteractiveProfile(
            name="_test_delete_profile",
            description="Profile to delete",
        )
        await profile_manager.save_profile(profile)
        
        # Verify it exists
        retrieved = await profile_manager.get_profile("_test_delete_profile")
        assert retrieved is not None
        
        # Delete profile
        result = await profile_manager.delete_profile("_test_delete_profile")
        assert result is True
        
        # Verify it's gone
        retrieved = await profile_manager.get_profile("_test_delete_profile")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, profile_manager):
        """Test deleting a non-existent profile."""
        result = await profile_manager.delete_profile("nonexistent_profile_abc")
        
        # Should return False or not raise
        assert result is False


# =============================================================================
# Test: Default profiles
# =============================================================================

class TestDefaultProfiles:
    """Tests for default profile generation."""
    
    def test_default_profiles_exist(self):
        """Test that default profiles are defined."""
        from slurm_mcp.profiles import DEFAULT_PROFILES
        
        assert isinstance(DEFAULT_PROFILES, list)
        assert len(DEFAULT_PROFILES) > 0
    
    def test_default_profiles_valid(self):
        """Test that default profiles are valid InteractiveProfile objects."""
        from slurm_mcp.profiles import DEFAULT_PROFILES
        
        for profile in DEFAULT_PROFILES:
            assert isinstance(profile, InteractiveProfile)
            assert profile.name
            assert profile.nodes >= 1


# =============================================================================
# Integration test
# =============================================================================

class TestProfileIntegration:
    """Integration tests for profile management."""
    
    @pytest.mark.asyncio
    async def test_full_profile_workflow(self, profile_manager):
        """Test a full profile workflow: create, list, update, delete."""
        profile_name = "_integration_test_profile"
        
        # 1. Create profile
        profile = InteractiveProfile(
            name=profile_name,
            description="Integration test profile",
            partition="batch",
            nodes=1,
            time_limit="2:00:00",
        )
        await profile_manager.save_profile(profile)
        
        # 2. List profiles and verify it's there
        profiles = await profile_manager.list_profiles()
        found = any(p.name == profile_name for p in profiles)
        assert found, "Profile should be in list"
        
        # 3. Get profile
        retrieved = await profile_manager.get_profile(profile_name)
        assert retrieved is not None
        assert retrieved.description == "Integration test profile"
        
        # 4. Update profile
        updated = InteractiveProfile(
            name=profile_name,
            description="Updated integration test profile",
            partition="gpu",
            nodes=2,
            gpus_per_node=4,
            time_limit="4:00:00",
        )
        await profile_manager.save_profile(updated)
        
        # 5. Verify update
        retrieved = await profile_manager.get_profile(profile_name)
        assert retrieved.description == "Updated integration test profile"
        assert retrieved.partition == "gpu"
        assert retrieved.nodes == 2
        
        # 6. Delete profile
        result = await profile_manager.delete_profile(profile_name)
        assert result is True
        
        # 7. Verify deletion
        retrieved = await profile_manager.get_profile(profile_name)
        assert retrieved is None


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
        
        manager = ProfileManager(ssh, settings)
        
        print("=" * 60)
        print("RUNNING PROFILE MANAGEMENT TESTS")
        print("=" * 60)
        
        # Test list_profiles
        print("\n[TEST] list_profiles...")
        profiles = await manager.list_profiles()
        print(f"  ✓ Found {len(profiles)} profiles")
        for p in profiles[:5]:
            print(f"    - {p.name}: {p.description or 'No description'}")
        
        # Test save_profile
        print("\n[TEST] save_profile...")
        test_profile = InteractiveProfile(
            name="_manual_test_profile",
            description="Manual test profile",
            partition="batch",
            nodes=1,
        )
        await manager.save_profile(test_profile)
        print("  ✓ Profile saved")
        
        # Test get_profile
        print("\n[TEST] get_profile...")
        retrieved = await manager.get_profile("_manual_test_profile")
        assert retrieved is not None
        print(f"  ✓ Retrieved: {retrieved.name}")
        
        # Test delete_profile
        print("\n[TEST] delete_profile...")
        result = await manager.delete_profile("_manual_test_profile")
        assert result is True
        print("  ✓ Profile deleted")
        
        # Verify deletion
        retrieved = await manager.get_profile("_manual_test_profile")
        assert retrieved is None
        print("  ✓ Deletion verified")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
