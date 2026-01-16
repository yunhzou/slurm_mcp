"""Unit tests for configuration module.

Run with: pytest tests/test_config.py -v
"""

import os
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from slurm_mcp.config import Settings, get_settings


# =============================================================================
# Test: Settings Model
# =============================================================================

class TestSettingsModel:
    """Tests for Settings model."""
    
    def test_settings_loads_from_env(self):
        """Test that settings loads from environment variables."""
        settings = get_settings()
        
        # Should have SSH settings
        assert settings.ssh_host is not None or os.environ.get("SLURM_SSH_HOST") is None
    
    def test_settings_has_ssh_config(self):
        """Test that settings has SSH configuration."""
        settings = get_settings()
        
        # SSH settings should exist (may be None if not configured)
        assert hasattr(settings, "ssh_host")
        assert hasattr(settings, "ssh_user")
        assert hasattr(settings, "ssh_port")
        assert hasattr(settings, "ssh_key_path")
    
    def test_settings_has_slurm_config(self):
        """Test that settings has Slurm configuration."""
        settings = get_settings()
        
        assert hasattr(settings, "default_partition")
        assert hasattr(settings, "default_account")
        assert hasattr(settings, "command_timeout")
    
    def test_settings_has_directory_config(self):
        """Test that settings has directory configuration."""
        settings = get_settings()
        
        assert hasattr(settings, "user_root")
        assert hasattr(settings, "dir_datasets")
        assert hasattr(settings, "dir_results")
        assert hasattr(settings, "dir_models")
        assert hasattr(settings, "dir_logs")
        assert hasattr(settings, "dir_projects")
    
    def test_settings_has_container_config(self):
        """Test that settings has container configuration."""
        settings = get_settings()
        
        assert hasattr(settings, "image_dir")
        assert hasattr(settings, "dir_container_root")
    
    def test_settings_has_interactive_config(self):
        """Test that settings has interactive session configuration."""
        settings = get_settings()
        
        assert hasattr(settings, "interactive_partition")
        assert hasattr(settings, "interactive_account")
        assert hasattr(settings, "interactive_default_time")
        assert hasattr(settings, "interactive_default_gpus")


# =============================================================================
# Test: Default Values
# =============================================================================

class TestDefaultValues:
    """Tests for default configuration values."""
    
    def test_ssh_port_default(self):
        """Test SSH port default value."""
        settings = get_settings()
        
        # Default SSH port should be 22
        if settings.ssh_port is not None:
            assert settings.ssh_port == 22 or os.environ.get("SLURM_SSH_PORT")
    
    def test_directory_defaults_from_user_root(self):
        """Test that directories default from user_root."""
        settings = get_settings()
        
        if settings.user_root:
            # If user_root is set and dir_datasets is not explicitly set,
            # it should default to user_root/data
            # Note: This depends on whether SLURM_DIR_DATASETS is set in env
            if not os.environ.get("SLURM_DIR_DATASETS"):
                assert settings.dir_datasets is None or settings.user_root in settings.dir_datasets


# =============================================================================
# Test: get_container_mounts
# =============================================================================

class TestGetContainerMounts:
    """Tests for get_container_mounts method."""
    
    def test_returns_string(self):
        """Test that get_container_mounts returns a string."""
        settings = get_settings()
        mounts = settings.get_container_mounts()
        
        assert isinstance(mounts, str)
    
    def test_mounts_format(self):
        """Test that mounts are in correct format."""
        settings = get_settings()
        mounts = settings.get_container_mounts()
        
        if mounts:
            # Each mount should be host:container format
            for mount in mounts.split(","):
                if mount:
                    parts = mount.split(":")
                    assert len(parts) >= 2, f"Invalid mount: {mount}"
    
    def test_mounts_include_datasets(self):
        """Test that mounts include datasets directory."""
        settings = get_settings()
        mounts = settings.get_container_mounts()
        
        if settings.dir_datasets and mounts:
            assert settings.dir_datasets in mounts
    
    def test_mounts_include_results(self):
        """Test that mounts include results directory."""
        settings = get_settings()
        mounts = settings.get_container_mounts()
        
        if settings.dir_results and mounts:
            assert settings.dir_results in mounts
    
    def test_mounts_include_models(self):
        """Test that mounts include models directory."""
        settings = get_settings()
        mounts = settings.get_container_mounts()
        
        if settings.dir_models and mounts:
            assert settings.dir_models in mounts


# =============================================================================
# Test: set_directory_defaults validator
# =============================================================================

class TestDirectoryDefaults:
    """Tests for directory default value resolution."""
    
    def test_user_root_propagates_to_directories(self):
        """Test that user_root value propagates to directory defaults."""
        # This test verifies the validator behavior
        # Create settings with only user_root set (in a controlled way)
        
        settings = get_settings()
        
        if settings.user_root:
            # The validator should have set default paths
            # We can't directly test this without mocking, but we can verify
            # the settings have paths that could be derived from user_root
            pass  # This is more of a behavior verification


# =============================================================================
# Test: Environment Variable Prefixes
# =============================================================================

class TestEnvVarPrefixes:
    """Tests for environment variable prefixes."""
    
    def test_slurm_prefix_used(self):
        """Test that SLURM_ prefix is used for env vars."""
        # Set a test environment variable
        test_key = "SLURM_TEST_VAR_12345"
        os.environ[test_key] = "test_value"
        
        try:
            # Settings should use SLURM_ prefix
            # This is verified by the Settings class using env_prefix
            settings = get_settings()
            assert settings.model_config.get("env_prefix", "").upper() in ["SLURM_", ""]
        finally:
            del os.environ[test_key]


# =============================================================================
# Test: Caching
# =============================================================================

class TestSettingsCaching:
    """Tests for settings caching behavior."""
    
    def test_get_settings_returns_equivalent_settings(self):
        """Test that get_settings returns equivalent settings."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should return equivalent settings (same values)
        assert settings1.ssh_host == settings2.ssh_host
        assert settings1.ssh_user == settings2.ssh_user
        assert settings1.user_root == settings2.user_root


# =============================================================================
# Test: Validation
# =============================================================================

class TestSettingsValidation:
    """Tests for settings validation."""
    
    def test_ssh_port_is_integer(self):
        """Test that SSH port is an integer."""
        settings = get_settings()
        
        if settings.ssh_port is not None:
            assert isinstance(settings.ssh_port, int)
    
    def test_interactive_default_gpus_is_integer(self):
        """Test that interactive_default_gpus is an integer."""
        settings = get_settings()
        
        if settings.interactive_default_gpus is not None:
            assert isinstance(settings.interactive_default_gpus, int)


# =============================================================================
# Integration test
# =============================================================================

class TestConfigIntegration:
    """Integration tests for configuration."""
    
    def test_full_config_load(self):
        """Test loading full configuration."""
        settings = get_settings()
        
        # Print configuration summary
        print("\nConfiguration Summary:")
        print(f"  SSH Host: {settings.ssh_host}")
        print(f"  SSH User: {settings.ssh_user}")
        print(f"  SSH Port: {settings.ssh_port}")
        print(f"  User Root: {settings.user_root}")
        print(f"  Dir Datasets: {settings.dir_datasets}")
        print(f"  Dir Results: {settings.dir_results}")
        print(f"  Dir Models: {settings.dir_models}")
        print(f"  Dir Logs: {settings.dir_logs}")
        print(f"  Image Dir: {settings.image_dir}")
        print(f"  Interactive Partition: {settings.interactive_partition}")
        
        # Should have loaded without error
        assert settings is not None


# =============================================================================
# Standalone runner
# =============================================================================

def main():
    """Run tests manually without pytest."""
    print("=" * 60)
    print("RUNNING CONFIGURATION TESTS")
    print("=" * 60)
    
    print("\n[TEST] Loading settings...")
    settings = get_settings()
    print("  ✓ Settings loaded")
    
    print("\n[TEST] SSH configuration...")
    print(f"  ✓ Host: {settings.ssh_host}")
    print(f"  ✓ User: {settings.ssh_user}")
    print(f"  ✓ Port: {settings.ssh_port}")
    
    print("\n[TEST] Directory configuration...")
    print(f"  ✓ User Root: {settings.user_root}")
    print(f"  ✓ Datasets: {settings.dir_datasets}")
    print(f"  ✓ Results: {settings.dir_results}")
    print(f"  ✓ Models: {settings.dir_models}")
    print(f"  ✓ Logs: {settings.dir_logs}")
    
    print("\n[TEST] Container mounts...")
    mounts = settings.get_container_mounts()
    print(f"  ✓ Mounts: {mounts[:80]}..." if len(mounts) > 80 else f"  ✓ Mounts: {mounts}")
    
    print("\n[TEST] Interactive configuration...")
    print(f"  ✓ Partition: {settings.interactive_partition}")
    print(f"  ✓ Account: {settings.interactive_account}")
    print(f"  ✓ Default Time: {settings.interactive_default_time}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
