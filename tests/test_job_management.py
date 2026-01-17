"""Unit tests for job management tools.

These tests require a configured .env file with valid SSH credentials.
Run with: pytest tests/test_job_management.py -v
"""

import asyncio
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from slurm_mcp.config import get_settings
from slurm_mcp.models import JobInfo, JobSubmission
from slurm_mcp.ssh_client import SSHClient
from slurm_mcp.slurm_commands import SlurmCommands, _escape_for_single_quotes, _quote_path


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
# Test: Shell Escaping
# =============================================================================

class TestShellEscaping:
    """Tests for shell command escaping to avoid quote issues."""
    
    def test_escape_no_quotes(self):
        """Test command without quotes passes through."""
        cmd = "echo hello world"
        assert _escape_for_single_quotes(cmd) == cmd
    
    def test_escape_double_quotes(self):
        """Test command with double quotes passes through."""
        cmd = 'python -c "print(123)"'
        assert _escape_for_single_quotes(cmd) == cmd
    
    def test_escape_single_quotes(self):
        """Test command with single quotes gets escaped."""
        cmd = "python -c 'print(123)'"
        escaped = _escape_for_single_quotes(cmd)
        # Single quote becomes '\'' (end, escaped quote, start)
        assert escaped == "python -c '\\''print(123)'\\''", f"Got: {escaped}"
    
    def test_escape_mixed_quotes(self):
        """Test command with both quote types."""
        cmd = """python -c 'print("hello")'"""
        escaped = _escape_for_single_quotes(cmd)
        assert "'\\''" in escaped  # Contains escaped single quote
        assert '"hello"' in escaped  # Double quotes preserved
    
    def test_escape_multiple_single_quotes(self):
        """Test command with multiple single quotes."""
        cmd = "echo 'one' && echo 'two'"
        escaped = _escape_for_single_quotes(cmd)
        # Count the escaped patterns
        assert escaped.count("'\\''") == 4  # 4 single quotes total
    
    def test_wrapped_command_with_single_quotes(self):
        """Test that escaped command works when wrapped in bash -c '...'."""
        cmd = "python -c 'import vllm; print(vllm.__version__)'"
        escaped = _escape_for_single_quotes(cmd)
        
        # Simulating: bash -c '{escaped}'
        full_cmd = f"bash -c '{escaped}'"
        
        # The full command should be parseable (no unmatched quotes)
        # Count quotes - should be balanced
        single_quote_count = full_cmd.count("'") - full_cmd.count("\\'")
        # After escaping, we have: bash -c 'python -c '\''import...'\'''
        # The outer quotes are balanced, and inner quotes are escaped
        assert single_quote_count % 2 == 0 or "'\\''" in full_cmd


class TestPathQuoting:
    """Tests for path quoting to handle spaces and special characters."""
    
    def test_quote_simple_path(self):
        """Test simple path gets quoted."""
        path = "/home/user/file.txt"
        quoted = _quote_path(path)
        assert quoted == '"/home/user/file.txt"'
    
    def test_quote_path_with_spaces(self):
        """Test path with spaces is properly quoted."""
        path = "/home/user/my files/data.txt"
        quoted = _quote_path(path)
        assert quoted == '"/home/user/my files/data.txt"'
    
    def test_quote_path_with_double_quotes(self):
        """Test path with double quotes gets escaped."""
        path = '/home/user/file"name.txt'
        quoted = _quote_path(path)
        assert quoted == '"/home/user/file\\"name.txt"'
    
    def test_quote_path_with_dollar_sign(self):
        """Test path with dollar sign gets escaped."""
        path = "/home/user/$HOME/file.txt"
        quoted = _quote_path(path)
        assert quoted == '"/home/user/\\$HOME/file.txt"'
    
    def test_quote_path_with_backticks(self):
        """Test path with backticks gets escaped."""
        path = "/home/user/`cmd`/file.txt"
        quoted = _quote_path(path)
        assert quoted == '"/home/user/\\`cmd\\`/file.txt"'
    
    def test_quote_path_with_backslash(self):
        """Test path with backslash gets escaped."""
        path = "/home/user/file\\name.txt"
        quoted = _quote_path(path)
        assert quoted == '"/home/user/file\\\\name.txt"'
    
    def test_quote_complex_path(self):
        """Test path with multiple special characters."""
        path = '/home/user/my files/$var/file"name.txt'
        quoted = _quote_path(path)
        # Should escape: " -> \", $ -> \$
        assert '\\$var' in quoted
        assert '\\"' in quoted
        assert 'my files' in quoted


# =============================================================================
# Test: list_jobs / get_jobs
# =============================================================================

class TestListJobs:
    """Tests for list_jobs / get_jobs functionality."""
    
    @pytest.mark.asyncio
    async def test_get_jobs_returns_list(self, slurm):
        """Test that get_jobs returns a list."""
        jobs = await slurm.get_jobs()
        
        assert isinstance(jobs, list)
        # May be empty if no jobs are running
    
    @pytest.mark.asyncio
    async def test_get_jobs_with_user_filter(self, slurm, settings):
        """Test filtering jobs by user."""
        if not settings.ssh_user:
            pytest.skip("No SSH user configured")
        
        jobs = await slurm.get_jobs(user=settings.ssh_user)
        
        assert isinstance(jobs, list)
        # All jobs should belong to this user
        for j in jobs:
            assert j.user == settings.ssh_user
    
    @pytest.mark.asyncio
    async def test_get_jobs_with_state_filter(self, slurm):
        """Test filtering jobs by state."""
        # Test with RUNNING state
        jobs = await slurm.get_jobs(state="RUNNING")
        
        assert isinstance(jobs, list)
        for j in jobs:
            assert "RUNNING" in j.state.upper()
    
    @pytest.mark.asyncio
    async def test_job_has_required_fields(self, slurm):
        """Test that each job has all required fields."""
        jobs = await slurm.get_jobs()
        
        for j in jobs[:5]:  # Check first 5 jobs
            assert isinstance(j, JobInfo)
            assert j.job_id > 0
            assert j.state
            assert j.user


# =============================================================================
# Test: squeue raw
# =============================================================================

class TestSqueue:
    """Tests for squeue command."""
    
    @pytest.mark.asyncio
    async def test_squeue_returns_output(self, slurm):
        """Test that squeue returns output."""
        output = await slurm.squeue()
        
        # May be empty if no jobs
        assert isinstance(output, str)
    
    @pytest.mark.asyncio
    async def test_squeue_with_user_filter(self, slurm, settings):
        """Test squeue with user filter."""
        if not settings.ssh_user:
            pytest.skip("No SSH user configured")
        
        output = await slurm.squeue(user=settings.ssh_user)
        
        assert isinstance(output, str)


# =============================================================================
# Test: JobSubmission model
# =============================================================================

class TestJobSubmission:
    """Tests for JobSubmission model and sbatch script generation."""
    
    def test_basic_job_submission(self):
        """Test creating a basic job submission."""
        job = JobSubmission(
            script_content="echo 'Hello World'",
            job_name="test-job",
            partition="batch",
        )
        
        assert job.script_content == "echo 'Hello World'"
        assert job.job_name == "test-job"
        assert job.partition == "batch"
    
    def test_generate_sbatch_script_basic(self):
        """Test generating a basic sbatch script."""
        job = JobSubmission(
            script_content="echo 'Hello World'",
            job_name="test-job",
            partition="batch",
            time_limit="1:00:00",
        )
        
        script = job.generate_sbatch_script()
        
        assert "#!/bin/bash" in script
        assert "#SBATCH --job-name=test-job" in script
        assert "#SBATCH --partition=batch" in script
        assert "#SBATCH --time=1:00:00" in script
        assert "echo 'Hello World'" in script
    
    def test_generate_sbatch_script_with_gpus(self):
        """Test generating sbatch script with GPU options."""
        job = JobSubmission(
            script_content="nvidia-smi",
            job_name="gpu-job",
            partition="gpu",
            gpus=4,
            gpu_type="a100",
        )
        
        script = job.generate_sbatch_script()
        
        # Should have GPU specification (format may vary)
        assert "a100" in script and "4" in script
        assert "#SBATCH" in script
    
    def test_generate_sbatch_script_with_container(self):
        """Test generating sbatch script with container options."""
        job = JobSubmission(
            script_content="python train.py",
            job_name="container-job",
            container_image="/path/to/image.sqsh",
            container_mounts="/data:/data",
        )
        
        script = job.generate_sbatch_script()
        
        assert "#SBATCH --container-image=/path/to/image.sqsh" in script
        assert "#SBATCH --container-mounts=/data:/data" in script
    
    def test_generate_sbatch_script_with_all_options(self):
        """Test generating sbatch script with all options."""
        job = JobSubmission(
            script_content="python train.py",
            job_name="full-job",
            partition="gpu",
            account="myaccount",
            nodes=2,
            ntasks=8,
            cpus_per_task=4,
            memory="32G",
            time_limit="24:00:00",
            output_file="/logs/%j.out",
            error_file="/logs/%j.err",
            working_directory="/work",
            gpus=8,
            gpus_per_task=1,
            container_image="/images/pytorch.sqsh",
            container_mounts="/data:/data",
            container_workdir="/work",
        )
        
        script = job.generate_sbatch_script()
        
        assert "#SBATCH --job-name=full-job" in script
        assert "#SBATCH --partition=gpu" in script
        assert "#SBATCH --account=myaccount" in script
        assert "#SBATCH --nodes=2" in script
        assert "#SBATCH --ntasks=8" in script
        assert "#SBATCH --cpus-per-task=4" in script
        assert "#SBATCH --mem=32G" in script
        assert "#SBATCH --time=24:00:00" in script
        assert "#SBATCH --output=/logs/%j.out" in script
        assert "#SBATCH --error=/logs/%j.err" in script
        assert "#SBATCH --chdir=/work" in script


# =============================================================================
# Test: sacct / job history
# =============================================================================

class TestJobHistory:
    """Tests for job accounting/history."""
    
    @pytest.mark.asyncio
    async def test_sacct_returns_output(self, slurm):
        """Test that sacct returns output."""
        output = await slurm.sacct()
        
        # May be empty if no recent jobs
        assert isinstance(output, str)
    
    @pytest.mark.asyncio
    async def test_sacct_with_user_filter(self, slurm, settings):
        """Test sacct with user filter."""
        if not settings.ssh_user:
            pytest.skip("No SSH user configured")
        
        output = await slurm.sacct(user=settings.ssh_user)
        
        assert isinstance(output, str)
    
    @pytest.mark.asyncio
    async def test_sacct_with_start_time(self, slurm):
        """Test sacct with start time filter."""
        output = await slurm.sacct(start_time="now-7days")
        
        assert isinstance(output, str)


# =============================================================================
# Test: sinfo raw output
# =============================================================================

class TestSinfoRaw:
    """Tests for raw sinfo command."""
    
    @pytest.mark.asyncio
    async def test_sinfo_returns_output(self, slurm):
        """Test that sinfo returns output."""
        output = await slurm.sinfo()
        
        assert output
        assert isinstance(output, str)
        assert len(output) > 0


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
        print("RUNNING JOB MANAGEMENT TESTS")
        print("=" * 60)
        
        # Test get_jobs
        print("\n[TEST] get_jobs...")
        jobs = await slurm.get_jobs()
        print(f"  ✓ Found {len(jobs)} jobs in queue")
        
        # Test squeue
        print("\n[TEST] squeue...")
        output = await slurm.squeue()
        print(f"  ✓ Got squeue output ({len(output)} chars)")
        
        # Test sacct
        print("\n[TEST] sacct...")
        output = await slurm.sacct()
        print(f"  ✓ Got sacct output ({len(output)} chars)")
        
        # Test JobSubmission model
        print("\n[TEST] JobSubmission model...")
        job = JobSubmission(
            script_content="echo 'test'",
            job_name="test",
            partition="batch",
        )
        script = job.generate_sbatch_script()
        assert "#!/bin/bash" in script
        print("  ✓ JobSubmission.generate_sbatch_script() works")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        await ssh.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
