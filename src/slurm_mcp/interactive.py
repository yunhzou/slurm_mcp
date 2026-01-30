"""Interactive session manager for persistent Slurm allocations."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Union

from slurm_mcp.config import ClusterConfig, Settings
from slurm_mcp.models import CommandResult, InteractiveSession
from slurm_mcp.slurm_commands import SlurmCommands
from slurm_mcp.ssh_client import SSHClient, SSHCommandError

# Type alias to support both Settings and ClusterConfig
ConfigType = Union[Settings, ClusterConfig]

logger = logging.getLogger(__name__)


class InteractiveSessionManager:
    """Manages persistent interactive Slurm sessions.
    
    This class handles the lifecycle of interactive sessions,
    including creation, command execution, and cleanup.
    """
    
    def __init__(
        self,
        ssh_client: SSHClient,
        slurm: SlurmCommands,
        settings: ConfigType,
    ):
        """Initialize the interactive session manager.
        
        Args:
            ssh_client: SSH client for remote operations.
            slurm: Slurm commands wrapper.
            settings: Configuration settings (Settings or ClusterConfig).
        """
        self.ssh = ssh_client
        self.slurm = slurm
        self.settings = settings
        self._sessions: dict[str, InteractiveSession] = {}
        self._lock = asyncio.Lock()
    
    async def start_session(
        self,
        session_name: Optional[str] = None,
        partition: Optional[str] = None,
        account: Optional[str] = None,
        nodes: int = 1,
        gpus_per_node: Optional[int] = None,
        time_limit: Optional[str] = None,
        container_image: Optional[str] = None,
        container_mounts: Optional[str] = None,
        no_container_mount_home: bool = True,
    ) -> InteractiveSession:
        """Start a new interactive session.
        
        Args:
            session_name: Optional name for the session.
            partition: Partition to use.
            account: Account for billing.
            nodes: Number of nodes.
            gpus_per_node: GPUs per node.
            time_limit: Time limit.
            container_image: Container image path.
            container_mounts: Container mounts.
            no_container_mount_home: Don't mount home in container.
            
        Returns:
            InteractiveSession object.
            
        Raises:
            SSHCommandError: If session creation fails.
        """
        session_id = str(uuid.uuid4())[:8]
        job_name = f"mcp-session-{session_id}"
        
        # Use defaults from settings if not provided
        partition = partition or self.settings.interactive_partition
        account = account or self.settings.interactive_account
        time_limit = time_limit or self.settings.interactive_default_time
        if gpus_per_node is None:
            gpus_per_node = self.settings.interactive_default_gpus
        container_mounts = container_mounts or self.settings.get_container_mounts()
        
        logger.info(f"Starting interactive session {session_id} on partition {partition}")
        
        # Allocate resources
        job_id = await self.slurm.salloc(
            partition=partition,
            account=account,
            nodes=nodes,
            gpus_per_node=gpus_per_node,
            time_limit=time_limit,
            job_name=job_name,
        )
        
        logger.info(f"Session {session_id} allocated job {job_id}")
        
        # Get allocated nodes
        job_info = await self.slurm.get_job_details(job_id)
        node_list = job_info.nodes if job_info else None
        
        # Create session object
        session = InteractiveSession(
            session_id=session_id,
            job_id=job_id,
            session_name=session_name,
            partition=partition,
            nodes=nodes,
            gpus_per_node=gpus_per_node,
            container_image=container_image,
            container_mounts=container_mounts,
            start_time=datetime.now(),
            time_limit=time_limit,
            status="active",
            node_list=node_list,
        )
        
        async with self._lock:
            self._sessions[session_id] = session
        
        return session
    
    async def exec_command(
        self,
        session_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Execute a command in an existing session.
        
        Args:
            session_id: Session ID.
            command: Command to execute.
            working_directory: Working directory.
            timeout: Command timeout.
            
        Returns:
            CommandResult with output.
            
        Raises:
            ValueError: If session not found.
            SSHCommandError: If command fails.
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.status != "active":
            raise ValueError(f"Session {session_id} is not active (status: {session.status})")
        
        logger.debug(f"Executing command in session {session_id}: {command[:50]}...")
        
        result = await self.slurm.srun_in_allocation(
            job_id=session.job_id,
            command=command,
            container_image=session.container_image,
            container_mounts=session.container_mounts,
            working_directory=working_directory,
            timeout=timeout,
        )
        
        # Update last command time
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].last_command_time = datetime.now()
        
        return result
    
    async def end_session(self, session_id: str) -> bool:
        """End an interactive session.
        
        Args:
            session_id: Session ID to end.
            
        Returns:
            True if session was ended successfully.
        """
        async with self._lock:
            if session_id not in self._sessions:
                return False
            
            session = self._sessions[session_id]
        
        logger.info(f"Ending session {session_id} (job {session.job_id})")
        
        # Cancel the allocation
        success = await self.slurm.scancel(session.job_id)
        
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].status = "ended"
                del self._sessions[session_id]
        
        return success
    
    async def get_session(self, session_id: str) -> Optional[InteractiveSession]:
        """Get session info and verify it's still active.
        
        Args:
            session_id: Session ID.
            
        Returns:
            InteractiveSession or None if not found.
        """
        async with self._lock:
            if session_id not in self._sessions:
                return None
            
            session = self._sessions[session_id]
        
        # Verify the job is still running
        job_info = await self.slurm.get_job_details(session.job_id)
        
        if not job_info or job_info.state not in ['RUNNING', 'PENDING']:
            # Session has ended
            async with self._lock:
                if session_id in self._sessions:
                    self._sessions[session_id].status = "ended"
                    del self._sessions[session_id]
            return None
        
        # Update time remaining
        if job_info.time_remaining:
            async with self._lock:
                if session_id in self._sessions:
                    self._sessions[session_id].time_remaining = job_info.time_remaining
                    session = self._sessions[session_id]
        
        return session
    
    async def list_sessions(self) -> list[InteractiveSession]:
        """List all active sessions.
        
        Returns:
            List of active sessions.
        """
        # Refresh all sessions
        sessions = []
        session_ids = list(self._sessions.keys())
        
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    async def cleanup_stale_sessions(self) -> int:
        """Remove sessions that have ended or timed out.
        
        Returns:
            Number of sessions cleaned up.
        """
        cleaned = 0
        session_ids = list(self._sessions.keys())
        
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if not session:
                cleaned += 1
            elif session.last_command_time:
                # Check for idle timeout
                idle_seconds = (datetime.now() - session.last_command_time).total_seconds()
                if idle_seconds > self.settings.interactive_session_timeout:
                    logger.info(f"Session {session_id} timed out after {idle_seconds}s idle")
                    await self.end_session(session_id)
                    cleaned += 1
        
        return cleaned
    
    async def run_command(
        self,
        command: str,
        partition: Optional[str] = None,
        account: Optional[str] = None,
        nodes: int = 1,
        gpus_per_node: Optional[int] = None,
        time_limit: Optional[str] = None,
        container_image: Optional[str] = None,
        container_mounts: Optional[str] = None,
        no_container_mount_home: bool = True,
        working_directory: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Execute a single command with interactive resources (one-shot).
        
        This allocates resources, runs the command, and releases resources.
        No persistent session is created.
        
        Args:
            command: Command to execute.
            partition: Partition to use.
            account: Account for billing.
            nodes: Number of nodes.
            gpus_per_node: GPUs per node.
            time_limit: Time limit.
            container_image: Container image path.
            container_mounts: Container mounts.
            no_container_mount_home: Don't mount home in container.
            working_directory: Working directory.
            timeout: Command timeout.
            
        Returns:
            CommandResult with output.
        """
        return await self.slurm.srun_command(
            command=command,
            partition=partition,
            account=account,
            nodes=nodes,
            gpus_per_node=gpus_per_node,
            time_limit=time_limit,
            container_image=container_image,
            container_mounts=container_mounts,
            no_container_mount_home=no_container_mount_home,
            working_directory=working_directory,
            timeout=timeout,
        )


# Global session manager instance
_session_manager: Optional[InteractiveSessionManager] = None


def get_session_manager(
    ssh_client: Optional[SSHClient] = None,
    slurm: Optional[SlurmCommands] = None,
    settings: Optional[Settings] = None,
) -> InteractiveSessionManager:
    """Get or create the global session manager instance.
    
    Args:
        ssh_client: SSH client (required on first call).
        slurm: Slurm commands wrapper (required on first call).
        settings: Settings (required on first call).
        
    Returns:
        InteractiveSessionManager instance.
    """
    global _session_manager
    
    if _session_manager is None:
        if ssh_client is None or slurm is None or settings is None:
            raise ValueError("ssh_client, slurm, and settings required on first call")
        _session_manager = InteractiveSessionManager(ssh_client, slurm, settings)
    
    return _session_manager


async def reset_session_manager() -> None:
    """Reset the global session manager."""
    global _session_manager
    
    if _session_manager is not None:
        # End all active sessions
        for session_id in list(_session_manager._sessions.keys()):
            try:
                await _session_manager.end_session(session_id)
            except Exception:
                pass
        _session_manager = None
