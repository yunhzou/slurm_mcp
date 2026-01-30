"""Profile manager for interactive session configurations."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from slurm_mcp.config import ClusterConfig
from slurm_mcp.models import InteractiveProfile
from slurm_mcp.ssh_client import SSHClient

logger = logging.getLogger(__name__)


# Default profiles to create for new users
DEFAULT_PROFILES = [
    InteractiveProfile(
        name="dev-8gpu",
        description="Development session with 8 GPUs (4 hours)",
        nodes=1,
        gpus_per_node=8,
        time_limit="4:00:00",
        no_container_mount_home=True,
    ),
    InteractiveProfile(
        name="dev-4gpu",
        description="Development session with 4 GPUs (4 hours)",
        nodes=1,
        gpus_per_node=4,
        time_limit="4:00:00",
        no_container_mount_home=True,
    ),
    InteractiveProfile(
        name="dev-1gpu",
        description="Quick debugging with 1 GPU (2 hours)",
        nodes=1,
        gpus_per_node=1,
        time_limit="2:00:00",
        no_container_mount_home=True,
    ),
    InteractiveProfile(
        name="cpu-only",
        description="CPU-only session for data processing (4 hours)",
        nodes=1,
        gpus_per_node=0,
        time_limit="4:00:00",
        no_container_mount_home=True,
    ),
]


class ProfileManager:
    """Manages saved interactive session profiles.
    
    Profiles are stored as JSON on the remote cluster.
    """
    
    def __init__(self, ssh_client: SSHClient, config: ClusterConfig):
        """Initialize profile manager.
        
        Args:
            ssh_client: SSH client for remote file operations.
            config: Cluster configuration.
        """
        self.ssh = ssh_client
        self.config = config
        self._profiles_path = config.profiles_path
        self._profiles: dict[str, InteractiveProfile] = {}
        self._loaded = False
    
    async def _ensure_loaded(self) -> None:
        """Ensure profiles are loaded from storage."""
        if self._loaded:
            return
        
        await self._load_profiles()
        self._loaded = True
    
    async def _load_profiles(self) -> None:
        """Load profiles from remote storage."""
        if not self._profiles_path:
            logger.warning("No profiles path configured")
            return
        
        try:
            # Check if file exists
            exists = await self.ssh.file_exists(self._profiles_path)
            
            if not exists:
                # Create default profiles
                logger.info("Creating default profiles")
                await self._create_default_profiles()
                return
            
            # Read and parse profiles
            content = await self.ssh.read_remote_file(self._profiles_path)
            data = json.loads(content)
            
            for profile_data in data.get("profiles", []):
                try:
                    profile = InteractiveProfile(**profile_data)
                    self._profiles[profile.name] = profile
                except Exception as e:
                    logger.warning(f"Failed to parse profile: {e}")
            
            logger.info(f"Loaded {len(self._profiles)} profiles")
            
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            # Initialize with defaults
            await self._create_default_profiles()
    
    async def _create_default_profiles(self) -> None:
        """Create default profiles."""
        for profile in DEFAULT_PROFILES:
            # Apply config defaults
            if not profile.partition:
                profile.partition = self.config.interactive_partition
            if not profile.account:
                profile.account = self.config.interactive_account
            if not profile.container_image:
                profile.container_image = self.config.default_image
            if not profile.container_mounts:
                profile.container_mounts = self.config.get_container_mounts()
            
            profile.created_at = datetime.now()
            profile.updated_at = datetime.now()
            
            self._profiles[profile.name] = profile
        
        await self._save_profiles()
    
    async def _save_profiles(self) -> None:
        """Save profiles to remote storage."""
        if not self._profiles_path:
            return
        
        data = {
            "profiles": [
                profile.model_dump(mode="json")
                for profile in self._profiles.values()
            ]
        }
        
        content = json.dumps(data, indent=2, default=str)
        
        try:
            await self.ssh.write_remote_file(
                content,
                self._profiles_path,
                make_dirs=True,
            )
            logger.debug(f"Saved {len(self._profiles)} profiles")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    async def save_profile(self, profile: InteractiveProfile) -> None:
        """Save a profile.
        
        Args:
            profile: Profile to save.
        """
        await self._ensure_loaded()
        
        # Set timestamps
        if profile.name in self._profiles:
            profile.created_at = self._profiles[profile.name].created_at
        else:
            profile.created_at = datetime.now()
        profile.updated_at = datetime.now()
        
        # Apply defaults if not set
        if not profile.partition:
            profile.partition = self.config.interactive_partition
        if not profile.account:
            profile.account = self.config.interactive_account
        if not profile.container_mounts:
            profile.container_mounts = self.config.get_container_mounts()
        
        self._profiles[profile.name] = profile
        await self._save_profiles()
        
        logger.info(f"Saved profile '{profile.name}'")
    
    async def get_profile(self, name: str) -> Optional[InteractiveProfile]:
        """Get a profile by name.
        
        Args:
            name: Profile name.
            
        Returns:
            InteractiveProfile or None if not found.
        """
        await self._ensure_loaded()
        return self._profiles.get(name)
    
    async def list_profiles(self) -> list[InteractiveProfile]:
        """List all profiles.
        
        Returns:
            List of profiles.
        """
        await self._ensure_loaded()
        return list(self._profiles.values())
    
    async def delete_profile(self, name: str) -> bool:
        """Delete a profile.
        
        Args:
            name: Profile name to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        await self._ensure_loaded()
        
        if name not in self._profiles:
            return False
        
        del self._profiles[name]
        await self._save_profiles()
        
        logger.info(f"Deleted profile '{name}'")
        return True
    
    async def update_profile(
        self,
        name: str,
        **updates,
    ) -> Optional[InteractiveProfile]:
        """Update an existing profile.
        
        Args:
            name: Profile name to update.
            **updates: Fields to update.
            
        Returns:
            Updated profile or None if not found.
        """
        await self._ensure_loaded()
        
        if name not in self._profiles:
            return None
        
        profile = self._profiles[name]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now()
        
        await self._save_profiles()
        return profile
