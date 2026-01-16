# Slurm MCP Server Implementation Plan

## Overview

Build an MCP server using `fastmcp` that allows AI agents to interact with a remote Slurm cluster via SSH. The server will provide tools for job management, cluster monitoring, and file operations.

### Key Features

- **SSH-based remote access** to Slurm login nodes
- **GPU and CPU node support** with resource discovery and allocation
- **Pyxis/enroot container support** for running containerized workloads
- **Container image discovery** from configured directories
- **Full job lifecycle management** (submit, monitor, cancel, hold/release)

---

## Cluster Architecture Support

### GPU and CPU Nodes

The cluster has both GPU and CPU compute nodes. The MCP server will:

1. **Distinguish partition types**: Track which partitions have GPU vs CPU-only nodes
2. **GPU resource discovery**: Query available GPU types (A100, V100, H100, etc.) and counts per node
3. **Smart resource suggestions**: Help agents choose appropriate partitions based on job requirements
4. **GPU availability tracking**: Show current GPU utilization to help with scheduling decisions

### Pyxis/Enroot Container Support

The cluster uses [NVIDIA Pyxis](https://github.com/NVIDIA/pyxis) (a Slurm plugin) with [enroot](https://github.com/NVIDIA/enroot) for containerized workloads.

**How it works:**
- Container images are stored as `.sqsh` (squashfs) files on the cluster
- Jobs specify container images using Slurm's `--container-image` flag
- Pyxis handles container lifecycle within Slurm jobs

**MCP server support:**
- Discover available `.sqsh` images in configured directories
- Validate image paths before job submission
- Generate appropriate `#SBATCH --container-*` directives
- Support container mounts, environment variables, and working directories

**Example Pyxis job submission:**
```bash
#SBATCH --container-image=/path/to/pytorch-24.01.sqsh
#SBATCH --container-mounts=/data:/data:ro,/scratch:/scratch
#SBATCH --container-workdir=/workspace
```

### Interactive Node Support

The cluster has an "interactive" partition for quick development sessions. The MCP server provides two approaches:

**Approach 1: On-demand command execution (Recommended for agents)**
- Use `srun` to execute individual commands with interactive-like resources
- No persistent session needed - each command gets allocated, runs, and releases
- Simpler and more reliable for agent workflows
- Slight overhead per command but very robust

**Approach 2: Persistent interactive session**
- Allocate resources with `salloc` and maintain the allocation
- Run multiple commands within the same allocation
- More efficient for many sequential commands
- Requires session management (timeout, cleanup)

**Example interactive launch script (user's current workflow):**
```bash
#!/bin/bash
PARTITION=interactive
IMAGE=$YIHOME/data/models/images/nvidian+nemo+verl_v2_enroot_dev0.8.5.sqsh

srun -A nvr_lpr_agentic -N1 -J swdl-job:dev -p $PARTITION -t 4:00:00 \
    --container-image="$IMAGE" \
    --no-container-mount-home \
    --gpus-per-node=8 \
    --container-mounts="$HOME:/home/,$GPFS:/lustre/,$RESULTS:/results,$ROOT:/root,$DATA:/datasets/,$PROJECTS:/Projects" \
    --pty bash
```

**MCP server implementation:**
- Store interactive session profiles (partition, image, mounts, account, etc.)
- `run_interactive_command` - Execute a command with interactive resources
- `start_interactive_session` - Allocate and maintain a persistent session
- `exec_in_session` - Run commands in an existing session
- `end_interactive_session` - Release the allocation

---

## Project Structure

```
slurm_mcp/
├── pyproject.toml              # Project configuration and dependencies
├── README.md                   # Documentation
├── src/
│   └── slurm_mcp/
│       ├── __init__.py
│       ├── server.py           # Main MCP server with tool definitions
│       ├── ssh_client.py       # SSH connection management
│       ├── slurm_commands.py   # Slurm command wrappers
│       ├── config.py           # Configuration management
│       ├── models.py           # Pydantic models for data structures
│       ├── interactive.py      # Interactive session manager
│       ├── profiles.py         # Session profile storage and management
│       └── directories.py      # Cluster directory management and file operations
└── tests/
    ├── __init__.py
    ├── test_ssh_client.py
    ├── test_slurm_commands.py
    ├── test_interactive.py
    ├── test_directories.py
    └── test_server.py
```

---

## Step 1: Create `pyproject.toml`

Dependencies:
- `fastmcp>=2.12.4` - MCP server framework
- `asyncssh>=2.14.0` - Async SSH client (preferred over subprocess SSH)
- `pydantic>=2.0` - Data validation and settings management
- `pydantic-settings>=2.0` - Environment-based configuration
- `python>=3.10`

Define entry point for stdio transport:

```toml
[project.scripts]
slurm-mcp = "slurm_mcp.server:main"
```

---

## Step 2: Create Configuration Module

**File: `src/slurm_mcp/config.py`**

Create a Pydantic Settings class to manage configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `SLURM_SSH_HOST` | Remote Slurm login node hostname | Required |
| `SLURM_SSH_PORT` | SSH port | 22 |
| `SLURM_SSH_USER` | SSH username | Required |
| `SLURM_SSH_KEY_PATH` | Path to SSH private key | Optional |
| `SLURM_SSH_PASSWORD` | SSH password (for key passphrase or password auth) | Optional |
| `SLURM_SSH_KNOWN_HOSTS` | Path to known_hosts file | Optional |
| `SLURM_DEFAULT_PARTITION` | Default partition for job submission | Optional |
| `SLURM_COMMAND_TIMEOUT` | Command timeout in seconds | 60 |
| `SLURM_WORK_DIR` | Default working directory on the cluster | Optional |
| `SLURM_IMAGE_DIR` | Directory containing .sqsh container images | Optional |
| `SLURM_DEFAULT_IMAGE` | Default container image (.sqsh file path) | Optional |
| `SLURM_GPU_PARTITIONS` | Comma-separated list of GPU partition names | Optional |
| `SLURM_CPU_PARTITIONS` | Comma-separated list of CPU partition names | Optional |
| `SLURM_INTERACTIVE_PARTITION` | Partition for interactive jobs | "interactive" |
| `SLURM_INTERACTIVE_ACCOUNT` | Account/project for interactive jobs | Optional |
| `SLURM_INTERACTIVE_DEFAULT_TIME` | Default time limit for interactive sessions | "4:00:00" |
| `SLURM_INTERACTIVE_DEFAULT_GPUS` | Default GPUs for interactive sessions | 8 |
| `SLURM_INTERACTIVE_SESSION_TIMEOUT` | Idle timeout for persistent sessions (seconds) | 3600 |

### Cluster Directory Structure

| Variable | Description | Default | Container Mount |
|----------|-------------|---------|-----------------|
| `SLURM_USER_ROOT` | User's root directory on cluster (base for other dirs) | Required | - |
| `SLURM_DIR_DATASETS` | Directory for training datasets | `$SLURM_USER_ROOT/data` | `/datasets` |
| `SLURM_DIR_RESULTS` | Directory for job outputs/results | `$SLURM_USER_ROOT/results` | `/results` |
| `SLURM_DIR_MODELS` | Directory for model checkpoints/weights | `$SLURM_USER_ROOT/models` | `/models` |
| `SLURM_DIR_LOGS` | Directory for job stdout/stderr logs | `$SLURM_USER_ROOT/logs` | `/logs` |
| `SLURM_DIR_PROJECTS` | Directory for project source code | `$SLURM_USER_ROOT/Projects` | `/projects` |
| `SLURM_DIR_SCRATCH` | Scratch/temp directory for jobs | Optional | `/scratch` |
| `SLURM_DIR_HOME` | User home directory on cluster | Optional | `/home` |
| `SLURM_DIR_CONTAINER_ROOT` | Custom root overlay for containers | `$SLURM_USER_ROOT/root` | `/root` |
| `SLURM_GPFS_ROOT` | Root of GPFS/Lustre filesystem | Optional | `/lustre` |

**Example configuration (minimal - just set user root):**
```bash
SLURM_USER_ROOT="/lustre/fsw/portfolios/nvr/users/yidong"
SLURM_GPFS_ROOT="/lustre"
# Other directories default to subdirectories of SLURM_USER_ROOT
```

**Example configuration (explicit paths):**
```bash
SLURM_USER_ROOT="/lustre/fsw/portfolios/nvr/users/yidong"
SLURM_DIR_DATASETS="/lustre/fsw/portfolios/nvr/users/yidong/data"
SLURM_DIR_RESULTS="/lustre/fsw/portfolios/nvr/users/yidong/results"
SLURM_DIR_MODELS="/lustre/fsw/portfolios/nvr/users/yidong/models"
SLURM_DIR_LOGS="/lustre/fsw/portfolios/nvr/users/yidong/logs"
SLURM_DIR_PROJECTS="/lustre/fsw/portfolios/nvr/users/yidong/Projects"
SLURM_DIR_CONTAINER_ROOT="/lustre/fsw/portfolios/nvr/users/yidong/root"
SLURM_GPFS_ROOT="/lustre"
```

**Auto-generated container mounts:**
```
$SLURM_DIR_DATASETS:/datasets,$SLURM_DIR_RESULTS:/results,$SLURM_DIR_MODELS:/models,$SLURM_DIR_LOGS:/logs,...
```

---

## Step 3: Create Data Models

**File: `src/slurm_mcp/models.py`**

Define Pydantic models for structured data:

1. **JobInfo**: Job details (job_id, name, user, state, partition, nodes, time_used, time_limit, gpus, container_image, etc.)
2. **NodeInfo**: Node information (node_name, state, cpus, memory, partitions, gpus, gpu_type, etc.)
3. **PartitionInfo**: Partition details (name, state, nodes, max_time, default, has_gpus, gpu_types, etc.)
4. **JobSubmission**: Job submission parameters (script_content, job_name, partition, nodes, cpus_per_task, memory, time_limit, output_file, error_file, array, gpus, gpu_type, container_image, container_mounts, etc.)
5. **CommandResult**: Command execution result (stdout, stderr, return_code, success)
6. **ContainerImage**: Container image info (name, path, size, modified_time, description)
7. **GPUInfo**: GPU resource details (gpu_type, count, memory, available)
8. **InteractiveSession**: Session info (session_id, job_id, partition, nodes, gpus, container_image, mounts, start_time, status, time_remaining)
9. **InteractiveProfile**: Reusable session config (name, partition, account, nodes, gpus, time_limit, container_image, container_mounts, env_vars)
10. **ClusterDirectories**: Configured directory paths (user_root, datasets, results, models, logs, projects, scratch, container_root, home)
11. **FileInfo**: File/directory info (name, path, size, modified_time, is_dir, permissions)
12. **DirectoryListing**: Directory contents (path, files, subdirs, total_size)

---

## Step 4: Implement SSH Client

**File: `src/slurm_mcp/ssh_client.py`**

Create an `SSHClient` class using `asyncssh`:

```python
class SSHClient:
    """Manages SSH connections to the Slurm login node."""
    
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def execute(self, command: str, timeout: float = None) -> CommandResult
    async def upload_file(self, local_path: str, remote_path: str) -> None
    async def download_file(self, remote_path: str, local_path: str) -> None
    async def write_remote_file(self, content: str, remote_path: str) -> None
    async def read_remote_file(self, remote_path: str) -> str
```

Key implementation details:
- Use connection pooling or persistent connections for efficiency
- Implement automatic reconnection on connection loss
- Handle SSH authentication (key-based and password-based)
- Implement proper timeout handling
- Add logging for debugging

---

## Step 5: Implement Slurm Command Wrappers

**File: `src/slurm_mcp/slurm_commands.py`**

Create a `SlurmCommands` class that wraps Slurm commands:

```python
class SlurmCommands:
    """Wrapper for Slurm commands executed via SSH."""
    
    def __init__(self, ssh_client: SSHClient): ...
    
    # Cluster status
    async def sinfo(self, partition: str = None, format: str = None) -> str
    async def get_partitions(self) -> list[PartitionInfo]
    async def get_nodes(self, partition: str = None) -> list[NodeInfo]
    
    # Job management
    async def squeue(self, user: str = None, partition: str = None, job_id: int = None) -> str
    async def get_jobs(self, user: str = None, partition: str = None) -> list[JobInfo]
    async def sbatch(self, script_path: str) -> int  # Returns job_id
    async def scancel(self, job_id: int, signal: str = None) -> bool
    async def scontrol_show_job(self, job_id: int) -> JobInfo
    async def scontrol_hold(self, job_id: int) -> bool
    async def scontrol_release(self, job_id: int) -> bool
    
    # Job history/accounting
    async def sacct(self, job_id: int = None, user: str = None, start_time: str = None) -> str
    
    # GPU-specific queries
    async def get_gpu_nodes(self, partition: str = None) -> list[NodeInfo]
    async def get_gpu_availability(self, partition: str = None, gpu_type: str = None) -> dict
    async def get_gres_info(self) -> str  # Generic resource info including GPUs
    
    # Container image discovery
    async def list_sqsh_images(self, directory: str, pattern: str = None) -> list[ContainerImage]
    async def validate_image(self, image_path: str) -> bool
    
    # Utility
    async def submit_job_script(self, job: JobSubmission) -> int
    async def generate_sbatch_script(self, job: JobSubmission) -> str  # Generate script with GPU/container directives
```

**Parsing strategies:**
- Use `--json` flag where available (newer Slurm versions support JSON output for sinfo, squeue)
- Fall back to `--format` with custom delimiters for parsing
- Handle different Slurm versions gracefully

**GPU resource parsing:**
- Parse GRES (Generic RESource) information from `sinfo` and `scontrol`
- Extract GPU type and count from GRES strings like `gpu:a100:4`
- Track allocated vs available GPUs per node

**Container image discovery:**
- Use `find` or `ls` commands to list `.sqsh` files
- Parse file metadata (size, modification time)
- Optionally read image metadata/labels if available

**Interactive session management:**
- Track active sessions with their salloc job IDs
- Use `srun --jobid=<jobid>` to execute commands in existing allocations
- Monitor session health and time remaining
- Auto-cleanup sessions on timeout or disconnect

---

## Step 5b: Implement Interactive Session Manager

**File: `src/slurm_mcp/interactive.py`**

Create an `InteractiveSessionManager` class to handle persistent sessions:

```python
class InteractiveSessionManager:
    """Manages persistent interactive Slurm sessions."""
    
    def __init__(self, ssh_client: SSHClient, config: Settings): ...
    
    # Session lifecycle
    async def start_session(
        self,
        partition: str,
        account: str | None,
        nodes: int,
        gpus_per_node: int | None,
        time_limit: str,
        container_image: str | None,
        container_mounts: str | None,
        **kwargs
    ) -> InteractiveSession:
        """Start a new interactive session via salloc."""
        
    async def exec_command(
        self,
        session_id: str,
        command: str,
        working_dir: str | None,
        timeout: int | None
    ) -> CommandResult:
        """Execute command in existing session via srun --jobid."""
        
    async def end_session(self, session_id: str) -> bool:
        """Cancel the salloc allocation."""
        
    async def get_session(self, session_id: str) -> InteractiveSession | None:
        """Get session info and verify it's still active."""
        
    async def list_sessions(self) -> list[InteractiveSession]:
        """List all active sessions."""
        
    async def cleanup_stale_sessions(self) -> int:
        """Remove sessions that have ended or timed out."""
    
    # One-shot execution (no persistent session)
    async def run_command(
        self,
        command: str,
        partition: str,
        account: str | None,
        nodes: int,
        gpus_per_node: int | None,
        time_limit: str,
        container_image: str | None,
        container_mounts: str | None,
        working_dir: str | None,
        timeout: int | None
    ) -> CommandResult:
        """Execute a single command via srun (allocate, run, release)."""
```

**Implementation approach for persistent sessions:**

1. **Starting a session:**
   ```bash
   # Use salloc to get an allocation (runs in background, tracks job ID)
   salloc -A account -p interactive -N1 --gpus-per-node=8 -t 4:00:00 \
       --no-shell --job-name=mcp-session-{uuid}
   ```
   - Parse the job ID from salloc output
   - Store session metadata (job_id, start_time, config)

2. **Executing commands in session:**
   ```bash
   # Use srun with --jobid to run in existing allocation
   srun --jobid={job_id} --container-image={image} --container-mounts={mounts} \
       --no-container-mount-home bash -c "cd {workdir} && {command}"
   ```

3. **Session health monitoring:**
   - Periodically check `squeue -j {job_id}` to verify allocation is active
   - Track time remaining
   - Auto-cleanup when allocation ends

**Implementation approach for one-shot commands:**

```bash
# Single srun that allocates, runs, and releases
srun -A account -p interactive -N1 --gpus-per-node=8 -t 4:00:00 \
    --container-image={image} --container-mounts={mounts} \
    --no-container-mount-home bash -c "cd {workdir} && {command}"
```

---

## Step 5c: Implement Profile Manager

**File: `src/slurm_mcp/profiles.py`**

```python
class ProfileManager:
    """Manages saved interactive session profiles."""
    
    def __init__(self, storage_path: str): ...
    
    async def save_profile(self, profile: InteractiveProfile) -> None:
        """Save a profile to persistent storage."""
        
    async def get_profile(self, name: str) -> InteractiveProfile | None:
        """Retrieve a profile by name."""
        
    async def list_profiles(self) -> list[InteractiveProfile]:
        """List all saved profiles."""
        
    async def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
```

**Storage:** JSON file in user's config directory or cluster home directory.

**Default profiles to create:**
- `dev-8gpu`: 8 GPUs, 4 hours, interactive partition, default container
- `dev-1gpu`: 1 GPU, 2 hours, for quick debugging
- `cpu-only`: CPU partition, no GPUs, for data processing

---

## Step 5d: Implement Directory Manager

**File: `src/slurm_mcp/directories.py`**

```python
class DirectoryManager:
    """Manages cluster directory structure and file operations."""
    
    def __init__(self, ssh_client: SSHClient, config: Settings): ...
    
    # Directory resolution
    def resolve_path(self, path: str, directory_type: str | None) -> str:
        """Resolve a path, optionally relative to a directory type."""
        
    def get_container_mounts(self) -> str:
        """Generate container mount string from configured directories."""
        
    # Listing operations
    async def list_dir(
        self, path: str, pattern: str | None, recursive: bool, max_depth: int | None
    ) -> DirectoryListing: ...
    
    async def find_files(
        self, pattern: str, path: str, file_type: str | None, 
        min_size: str | None, max_age: str | None
    ) -> list[FileInfo]: ...
    
    # File operations
    async def read_file(
        self, path: str, tail: int | None, head: int | None, encoding: str
    ) -> str: ...
    
    async def write_file(
        self, path: str, content: str, append: bool, make_dirs: bool
    ) -> None: ...
    
    async def delete(self, path: str, recursive: bool) -> None: ...
    
    async def get_info(self, path: str) -> FileInfo: ...
    
    async def get_disk_usage(self, path: str) -> dict: ...
    
    # Convenience methods for specific directories
    async def list_datasets(self, pattern: str | None) -> list[FileInfo]: ...
    async def list_checkpoints(self, model: str | None, pattern: str | None) -> list[FileInfo]: ...
    async def list_logs(self, job_id: int | None, job_name: str | None) -> list[FileInfo]: ...
    async def list_results(self, experiment: str | None, pattern: str | None) -> list[FileInfo]: ...
```

**Path resolution examples:**
```python
# directory_type="datasets", path="imagenet" -> $SLURM_DIR_DATASETS/imagenet
# directory_type="models", path="llama/checkpoint-1000" -> $SLURM_DIR_MODELS/llama/checkpoint-1000
# directory_type=None, path="/absolute/path" -> /absolute/path
```

**Directory defaults based on user root:**
```python
def _resolve_directory(self, explicit_value: str | None, default_subdir: str) -> str:
    """Resolve directory path, defaulting to user_root/subdir if not explicitly set."""
    if explicit_value:
        return explicit_value
    return f"{self.config.user_root}/{default_subdir}"

# Example usage in config initialization:
# dir_datasets = _resolve_directory(config.dir_datasets, "data")
# dir_results = _resolve_directory(config.dir_results, "results")
# dir_models = _resolve_directory(config.dir_models, "models")
# etc.
```

**Auto-generated container mounts:**
```python
def get_container_mounts(self) -> str:
    mounts = []
    if self.config.dir_datasets:
        mounts.append(f"{self.config.dir_datasets}:/datasets")
    if self.config.dir_results:
        mounts.append(f"{self.config.dir_results}:/results")
    if self.config.dir_models:
        mounts.append(f"{self.config.dir_models}:/models")
    if self.config.dir_logs:
        mounts.append(f"{self.config.dir_logs}:/logs")
    if self.config.dir_projects:
        mounts.append(f"{self.config.dir_projects}:/projects")
    if self.config.dir_container_root:
        mounts.append(f"{self.config.dir_container_root}:/root")
    if self.config.dir_home:
        mounts.append(f"{self.config.dir_home}:/home")
    if self.config.gpfs_root:
        mounts.append(f"{self.config.gpfs_root}:/lustre")
    return ",".join(mounts)
```

---

## Step 6: Implement MCP Server with Tools

**File: `src/slurm_mcp/server.py`**

Create the main MCP server using FastMCP:

```python
from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field

mcp_server = FastMCP("slurm-mcp")

# Initialize SSH and Slurm clients at startup
@mcp_server.on_startup()
async def startup():
    # Initialize SSH connection
    pass
```

### MCP Tools to Implement

#### 1. get_cluster_status

```python
@mcp_server.tool()
async def get_cluster_status(
    partition: Annotated[str | None, Field(description="Filter by partition name")] = None
) -> str:
    """Get the current status of the Slurm cluster including partitions and node availability."""
```

#### 2. get_partition_info

```python
@mcp_server.tool()
async def get_partition_info(
    partition_name: Annotated[str | None, Field(description="Specific partition name, or None for all")] = None
) -> str:
    """Get detailed information about cluster partitions."""
```

#### 3. list_jobs

```python
@mcp_server.tool()
async def list_jobs(
    user: Annotated[str | None, Field(description="Filter by username")] = None,
    partition: Annotated[str | None, Field(description="Filter by partition")] = None,
    state: Annotated[str | None, Field(description="Filter by job state (PENDING, RUNNING, etc.)")] = None
) -> str:
    """List jobs in the Slurm queue."""
```

#### 4. get_job_details

```python
@mcp_server.tool()
async def get_job_details(
    job_id: Annotated[int, Field(description="The Slurm job ID")]
) -> str:
    """Get detailed information about a specific job."""
```

#### 5. submit_job

```python
@mcp_server.tool()
async def submit_job(
    script_content: Annotated[str, Field(description="The SBATCH script content (commands to run)")],
    job_name: Annotated[str | None, Field(description="Job name")] = None,
    partition: Annotated[str | None, Field(description="Partition to submit to")] = None,
    nodes: Annotated[int | None, Field(description="Number of nodes")] = None,
    ntasks: Annotated[int | None, Field(description="Number of tasks")] = None,
    cpus_per_task: Annotated[int | None, Field(description="CPUs per task")] = None,
    memory: Annotated[str | None, Field(description="Memory per node (e.g., '4G', '4000M')")] = None,
    time_limit: Annotated[str | None, Field(description="Time limit (e.g., '1:00:00', '1-00:00:00')")] = None,
    output_file: Annotated[str | None, Field(description="Output file path")] = None,
    error_file: Annotated[str | None, Field(description="Error file path")] = None,
    working_directory: Annotated[str | None, Field(description="Working directory on cluster")] = None,
    # GPU options
    gpus: Annotated[int | None, Field(description="Number of GPUs per node (e.g., 4)")] = None,
    gpus_per_task: Annotated[int | None, Field(description="Number of GPUs per task")] = None,
    gpu_type: Annotated[str | None, Field(description="Specific GPU type (e.g., 'a100', 'v100', 'h100')")] = None,
    # Pyxis/enroot container options
    container_image: Annotated[str | None, Field(description="Path to container .sqsh image file")] = None,
    container_mounts: Annotated[str | None, Field(description="Container bind mounts (e.g., '/data:/data,/scratch:/scratch')")] = None,
    container_workdir: Annotated[str | None, Field(description="Working directory inside container")] = None,
    container_env: Annotated[str | None, Field(description="Environment variables for container (e.g., 'VAR1=val1,VAR2=val2')")] = None
) -> str:
    """Submit a batch job to the Slurm cluster. Supports GPU allocation and Pyxis containers. Returns the job ID on success."""
```

The tool will generate appropriate SBATCH directives including:
- `#SBATCH --gres=gpu:TYPE:COUNT` for GPU requests
- `#SBATCH --container-image=/path/to/image.sqsh` for Pyxis
- `#SBATCH --container-mounts=...` for container bind mounts

#### 6. cancel_job

```python
@mcp_server.tool()
async def cancel_job(
    job_id: Annotated[int, Field(description="The Slurm job ID to cancel")],
    signal: Annotated[str | None, Field(description="Signal to send (e.g., 'SIGTERM', 'SIGKILL')")] = None
) -> str:
    """Cancel a running or pending job."""
```

#### 7. hold_job

```python
@mcp_server.tool()
async def hold_job(
    job_id: Annotated[int, Field(description="The Slurm job ID to hold")]
) -> str:
    """Put a pending job on hold."""
```

#### 8. release_job

```python
@mcp_server.tool()
async def release_job(
    job_id: Annotated[int, Field(description="The Slurm job ID to release")]
) -> str:
    """Release a held job."""
```

#### 9. get_job_history

```python
@mcp_server.tool()
async def get_job_history(
    job_id: Annotated[int | None, Field(description="Specific job ID")] = None,
    user: Annotated[str | None, Field(description="Filter by username")] = None,
    start_time: Annotated[str | None, Field(description="Start time (e.g., '2024-01-01', 'now-7days')")] = None,
    end_time: Annotated[str | None, Field(description="End time")] = None
) -> str:
    """Get job accounting/history information."""
```

#### 10. get_node_info

```python
@mcp_server.tool()
async def get_node_info(
    node_name: Annotated[str | None, Field(description="Specific node name")] = None,
    partition: Annotated[str | None, Field(description="Filter by partition")] = None,
    state: Annotated[str | None, Field(description="Filter by state (idle, allocated, down, etc.)")] = None
) -> str:
    """Get information about cluster nodes."""
```

#### 11. read_job_output

```python
@mcp_server.tool()
async def read_job_output(
    file_path: Annotated[str, Field(description="Path to the output file on the cluster")],
    tail_lines: Annotated[int | None, Field(description="Only read last N lines")] = None
) -> str:
    """Read the output file of a job from the cluster."""
```

#### 12. upload_file

```python
@mcp_server.tool()
async def upload_file(
    content: Annotated[str, Field(description="File content to upload")],
    remote_path: Annotated[str, Field(description="Destination path on the cluster")]
) -> str:
    """Upload a file to the cluster."""
```

#### 13. run_shell_command

```python
@mcp_server.tool()
async def run_shell_command(
    command: Annotated[str, Field(description="Shell command to execute")],
    working_directory: Annotated[str | None, Field(description="Working directory")] = None,
    timeout: Annotated[int | None, Field(description="Timeout in seconds")] = None
) -> str:
    """Execute a shell command on the Slurm login node. Use with caution."""
```

#### 14. list_container_images

```python
@mcp_server.tool()
async def list_container_images(
    image_dir: Annotated[str | None, Field(description="Directory to search for .sqsh images (uses default if not specified)")] = None,
    pattern: Annotated[str | None, Field(description="Filter images by name pattern (e.g., 'pytorch*', '*cuda12*')")] = None
) -> str:
    """List available container images (.sqsh files) for Pyxis/enroot. Returns image names, paths, sizes, and modification times."""
```

#### 15. get_gpu_info

```python
@mcp_server.tool()
async def get_gpu_info(
    partition: Annotated[str | None, Field(description="Filter by partition")] = None,
    gpu_type: Annotated[str | None, Field(description="Filter by GPU type (e.g., 'a100', 'v100')")] = None
) -> str:
    """Get information about available GPU resources in the cluster, including GPU types, counts, and availability per partition/node."""
```

#### 16. get_gpu_availability

```python
@mcp_server.tool()
async def get_gpu_availability(
    partition: Annotated[str | None, Field(description="Filter by partition")] = None,
    gpu_type: Annotated[str | None, Field(description="Filter by GPU type")] = None,
    min_gpus: Annotated[int | None, Field(description="Minimum number of GPUs needed")] = None
) -> str:
    """Check current GPU availability - how many GPUs are free vs allocated. Useful for deciding when/where to submit GPU jobs."""
```

#### 17. validate_container_image

```python
@mcp_server.tool()
async def validate_container_image(
    image_path: Annotated[str, Field(description="Path to the .sqsh container image")]
) -> str:
    """Validate that a container image exists and is readable. Returns image metadata if valid."""
```

---

### Interactive Session Tools

#### 18. run_interactive_command

```python
@mcp_server.tool()
async def run_interactive_command(
    command: Annotated[str, Field(description="Command to execute")],
    # Resource options
    partition: Annotated[str | None, Field(description="Partition (default: interactive)")] = None,
    account: Annotated[str | None, Field(description="Account/project for billing")] = None,
    nodes: Annotated[int | None, Field(description="Number of nodes")] = 1,
    gpus_per_node: Annotated[int | None, Field(description="GPUs per node")] = None,
    time_limit: Annotated[str | None, Field(description="Time limit (e.g., '4:00:00')")] = None,
    # Container options
    container_image: Annotated[str | None, Field(description="Container .sqsh image path")] = None,
    container_mounts: Annotated[str | None, Field(description="Container mounts (e.g., '/src:/dst,/src2:/dst2')")] = None,
    no_container_mount_home: Annotated[bool, Field(description="Don't mount home in container")] = True,
    # Execution options
    working_directory: Annotated[str | None, Field(description="Working directory for command")] = None,
    timeout: Annotated[int | None, Field(description="Command timeout in seconds")] = None
) -> str:
    """Execute a single command with interactive-partition resources. 
    
    This allocates resources via srun, runs the command, and releases resources.
    Best for one-off commands or agent workflows where each command is independent.
    
    Example: Run 'python train.py' on a GPU node with a container.
    """
```

#### 19. start_interactive_session

```python
@mcp_server.tool()
async def start_interactive_session(
    session_name: Annotated[str | None, Field(description="Name for this session")] = None,
    # Resource options  
    partition: Annotated[str | None, Field(description="Partition (default: interactive)")] = None,
    account: Annotated[str | None, Field(description="Account/project for billing")] = None,
    nodes: Annotated[int | None, Field(description="Number of nodes")] = 1,
    gpus_per_node: Annotated[int | None, Field(description="GPUs per node")] = None,
    time_limit: Annotated[str | None, Field(description="Time limit (e.g., '4:00:00')")] = None,
    # Container options
    container_image: Annotated[str | None, Field(description="Container .sqsh image path")] = None,
    container_mounts: Annotated[str | None, Field(description="Container mounts")] = None,
    no_container_mount_home: Annotated[bool, Field(description="Don't mount home in container")] = True
) -> str:
    """Start a persistent interactive session using salloc.
    
    The session stays allocated until explicitly ended or times out.
    Use exec_in_session() to run commands within this session.
    Returns session_id for subsequent commands.
    """
```

#### 20. exec_in_session

```python
@mcp_server.tool()
async def exec_in_session(
    session_id: Annotated[str, Field(description="Session ID from start_interactive_session")],
    command: Annotated[str, Field(description="Command to execute")],
    working_directory: Annotated[str | None, Field(description="Working directory")] = None,
    timeout: Annotated[int | None, Field(description="Command timeout in seconds")] = None
) -> str:
    """Execute a command in an existing interactive session.
    
    The command runs within the already-allocated resources.
    Much faster than run_interactive_command for sequential operations.
    """
```

#### 21. list_interactive_sessions

```python
@mcp_server.tool()
async def list_interactive_sessions() -> str:
    """List all active interactive sessions managed by this MCP server.
    
    Returns session IDs, job IDs, resources, time remaining, and status.
    """
```

#### 22. end_interactive_session

```python
@mcp_server.tool()
async def end_interactive_session(
    session_id: Annotated[str, Field(description="Session ID to terminate")]
) -> str:
    """End an interactive session and release its resources.
    
    Equivalent to exiting from salloc or canceling the allocation.
    """
```

#### 23. get_interactive_session_info

```python
@mcp_server.tool()
async def get_interactive_session_info(
    session_id: Annotated[str, Field(description="Session ID")]
) -> str:
    """Get detailed information about an interactive session.
    
    Returns allocated resources, container info, time remaining, and recent command history.
    """
```

#### 24. save_interactive_profile

```python
@mcp_server.tool()
async def save_interactive_profile(
    profile_name: Annotated[str, Field(description="Name for this profile")],
    partition: Annotated[str | None, Field(description="Partition")] = None,
    account: Annotated[str | None, Field(description="Account")] = None,
    nodes: Annotated[int | None, Field(description="Number of nodes")] = None,
    gpus_per_node: Annotated[int | None, Field(description="GPUs per node")] = None,
    time_limit: Annotated[str | None, Field(description="Time limit")] = None,
    container_image: Annotated[str | None, Field(description="Container image")] = None,
    container_mounts: Annotated[str | None, Field(description="Container mounts")] = None
) -> str:
    """Save an interactive session profile for quick reuse.
    
    Profiles store common configurations like 'dev-8gpu', 'debug-1gpu', etc.
    """
```

#### 25. list_interactive_profiles

```python
@mcp_server.tool()
async def list_interactive_profiles() -> str:
    """List saved interactive session profiles."""
```

#### 26. start_session_from_profile

```python
@mcp_server.tool()
async def start_session_from_profile(
    profile_name: Annotated[str, Field(description="Profile name to use")],
    session_name: Annotated[str | None, Field(description="Optional session name")] = None,
    time_limit: Annotated[str | None, Field(description="Override time limit")] = None
) -> str:
    """Start an interactive session using a saved profile."""
```

---

### Cluster Directory Tools

#### 27. get_cluster_directories

```python
@mcp_server.tool()
async def get_cluster_directories() -> str:
    """Get the configured cluster directory structure.
    
    Returns paths for datasets, results, models, logs, projects, and their container mount points.
    """
```

#### 28. list_directory

```python
@mcp_server.tool()
async def list_directory(
    path: Annotated[str, Field(description="Directory path to list (absolute or relative to a known dir)")],
    directory_type: Annotated[str | None, Field(description="Directory type: 'datasets', 'results', 'models', 'logs', 'projects', or None for absolute path")] = None,
    pattern: Annotated[str | None, Field(description="Filter by glob pattern (e.g., '*.pt', 'checkpoint-*')")] = None,
    recursive: Annotated[bool, Field(description="List recursively")] = False,
    max_depth: Annotated[int | None, Field(description="Max recursion depth")] = None
) -> str:
    """List contents of a directory on the cluster.
    
    Can use directory_type for convenience: list_directory("checkpoints", directory_type="models")
    resolves to $SLURM_DIR_MODELS/checkpoints
    """
```

#### 29. list_datasets

```python
@mcp_server.tool()
async def list_datasets(
    pattern: Annotated[str | None, Field(description="Filter by pattern")] = None
) -> str:
    """List available datasets in the datasets directory."""
```

#### 30. list_model_checkpoints

```python
@mcp_server.tool()
async def list_model_checkpoints(
    model_name: Annotated[str | None, Field(description="Filter by model name/directory")] = None,
    pattern: Annotated[str | None, Field(description="Filter by pattern (e.g., '*.pt', '*.safetensors')")] = None
) -> str:
    """List model checkpoints in the models directory."""
```

#### 31. list_job_logs

```python
@mcp_server.tool()
async def list_job_logs(
    job_id: Annotated[int | None, Field(description="Filter by job ID")] = None,
    job_name: Annotated[str | None, Field(description="Filter by job name pattern")] = None,
    recent: Annotated[int | None, Field(description="Only show N most recent logs")] = None
) -> str:
    """List job log files (stdout/stderr) in the logs directory."""
```

#### 32. list_results

```python
@mcp_server.tool()
async def list_results(
    experiment_name: Annotated[str | None, Field(description="Filter by experiment name")] = None,
    pattern: Annotated[str | None, Field(description="Filter by pattern")] = None
) -> str:
    """List experiment results in the results directory."""
```

#### 33. read_file

```python
@mcp_server.tool()
async def read_file(
    path: Annotated[str, Field(description="File path (absolute or relative)")],
    directory_type: Annotated[str | None, Field(description="Base directory type")] = None,
    tail_lines: Annotated[int | None, Field(description="Only read last N lines")] = None,
    head_lines: Annotated[int | None, Field(description="Only read first N lines")] = None,
    encoding: Annotated[str | None, Field(description="File encoding")] = "utf-8"
) -> str:
    """Read contents of a file on the cluster."""
```

#### 34. write_file

```python
@mcp_server.tool()
async def write_file(
    path: Annotated[str, Field(description="File path (absolute or relative)")],
    content: Annotated[str, Field(description="File content")],
    directory_type: Annotated[str | None, Field(description="Base directory type")] = None,
    append: Annotated[bool, Field(description="Append instead of overwrite")] = False,
    make_dirs: Annotated[bool, Field(description="Create parent directories if needed")] = True
) -> str:
    """Write content to a file on the cluster."""
```

#### 35. get_file_info

```python
@mcp_server.tool()
async def get_file_info(
    path: Annotated[str, Field(description="File or directory path")],
    directory_type: Annotated[str | None, Field(description="Base directory type")] = None
) -> str:
    """Get detailed information about a file or directory (size, permissions, modified time)."""
```

#### 36. find_files

```python
@mcp_server.tool()
async def find_files(
    pattern: Annotated[str, Field(description="Search pattern (glob or name)")],
    directory_type: Annotated[str | None, Field(description="Directory to search in")] = None,
    path: Annotated[str | None, Field(description="Specific path to search in")] = None,
    file_type: Annotated[str | None, Field(description="Filter by type: 'file', 'dir', 'link'")] = None,
    min_size: Annotated[str | None, Field(description="Minimum size (e.g., '1G', '100M')")] = None,
    max_age: Annotated[str | None, Field(description="Maximum age (e.g., '7d', '24h')")] = None
) -> str:
    """Search for files across cluster directories."""
```

#### 37. delete_file

```python
@mcp_server.tool()
async def delete_file(
    path: Annotated[str, Field(description="File or directory path")],
    directory_type: Annotated[str | None, Field(description="Base directory type")] = None,
    recursive: Annotated[bool, Field(description="Delete directories recursively")] = False,
    confirm: Annotated[bool, Field(description="Confirm deletion (must be True)")] = False
) -> str:
    """Delete a file or directory on the cluster. Requires confirm=True for safety."""
```

#### 38. get_disk_usage

```python
@mcp_server.tool()
async def get_disk_usage(
    directory_type: Annotated[str | None, Field(description="Check specific directory type")] = None,
    path: Annotated[str | None, Field(description="Check specific path")] = None
) -> str:
    """Get disk usage for cluster directories or a specific path."""
```

---

## Step 7: Add Main Entry Point

**File: `src/slurm_mcp/server.py`** (continued)

```python
def main():
    """Entry point for the MCP server."""
    import asyncio
    asyncio.run(mcp_server.run())

if __name__ == "__main__":
    main()
```

Support multiple transport modes:
- **stdio**: For local CLI usage (`slurm-mcp`)
- **SSE/HTTP**: For remote usage via HTTP

---

## Step 8: Create README Documentation

**File: `README.md`**

Include:
1. Overview and features
2. Installation instructions
3. Configuration (environment variables)
4. Usage examples with Cursor/Claude
5. MCP configuration for clients (stdio and HTTP modes)
6. Available tools and their parameters
7. Security considerations (SSH keys, permissions)
8. Troubleshooting guide

MCP configuration example for clients:

```json
{
  "mcpServers": {
    "slurm": {
      "command": "slurm-mcp",
      "env": {
        "SLURM_SSH_HOST": "login.cluster.example.com",
        "SLURM_SSH_USER": "username",
        "SLURM_SSH_KEY_PATH": "~/.ssh/id_rsa"
      }
    }
  }
}
```

---

## Step 9: Write Tests

**File: `tests/test_ssh_client.py`**
- Test connection handling
- Test command execution
- Test file operations
- Test error handling and reconnection

**File: `tests/test_slurm_commands.py`**
- Test output parsing for each command
- Test error handling
- Mock SSH responses

**File: `tests/test_server.py`**
- Test each MCP tool
- Test parameter validation
- Test error responses

---

## Implementation Order

### Phase 1 - Foundation (Create project structure)
- `pyproject.toml`
- `src/slurm_mcp/__init__.py`
- `src/slurm_mcp/config.py`
- `src/slurm_mcp/models.py`

### Phase 2 - SSH Layer
- `src/slurm_mcp/ssh_client.py`
- Basic tests for SSH

### Phase 3 - Slurm Commands
- `src/slurm_mcp/slurm_commands.py`
- Command parsing tests

### Phase 4 - MCP Server (Core)
- `src/slurm_mcp/server.py`
- Implement core tools (get_cluster_status, list_jobs, submit_job, cancel_job)
- GPU info and container image tools

### Phase 5 - Interactive Sessions
- `src/slurm_mcp/interactive.py` - Session manager
- `src/slurm_mcp/profiles.py` - Profile storage
- Interactive tools (run_interactive_command, start/exec/end session)
- Profile management tools
- Tests for interactive functionality

### Phase 6 - Directory Management
- `src/slurm_mcp/directories.py` - Directory manager
- Directory listing and navigation tools
- File read/write/delete tools
- Disk usage and search tools
- Tests for directory operations

### Phase 7 - Extended Features
- Additional Slurm tools (hold/release jobs)
- Error handling improvements
- `README.md` with full documentation

### Phase 8 - Testing & Polish
- Complete test coverage
- Documentation
- Example scripts
- Default profiles for common use cases
- Integration testing with real cluster (if available)

---

## Security Considerations

1. **SSH Key Management**: Recommend key-based auth over passwords
2. **Command Injection**: Sanitize all user inputs before constructing shell commands
3. **File Path Validation**: Prevent path traversal attacks
4. **Timeout Enforcement**: Prevent hanging commands
5. **Logging**: Log all operations for audit trail (without sensitive data)
6. **Permissions**: Document principle of least privilege for the SSH user
7. **Interactive Session Limits**: 
   - Limit max concurrent sessions per user
   - Enforce maximum session duration
   - Auto-cleanup orphaned sessions
8. **Resource Quotas**: Respect cluster account quotas and fairshare policies
9. **Container Security**: Only allow images from approved directories
10. **Command Allowlisting**: Optionally restrict which commands can be run interactively
11. **Directory Access Control**:
    - Restrict file operations to configured directories only
    - Prevent access outside GPFS/project directories
    - Validate paths to prevent traversal attacks (e.g., `../../etc/passwd`)
    - Require explicit confirmation for delete operations
12. **Sensitive File Protection**: Block access to SSH keys, credentials, and config files

---

## Example Usage Scenarios

### Scenario 1: Submit a GPU Training Job with Container

```
User: Submit a PyTorch training job using 4 A100 GPUs for 24 hours

Agent workflow:
1. list_container_images(pattern="pytorch*") - Find available PyTorch images
2. get_gpu_availability(gpu_type="a100", min_gpus=4) - Check A100 availability
3. submit_job with:
   - script_content: "python train.py --epochs 100"
   - partition: "gpu"
   - gpus: 4
   - gpu_type: "a100"
   - time_limit: "24:00:00"
   - container_image: "/images/pytorch-24.01.sqsh"
   - container_mounts: "/data:/data,/scratch:/scratch"
```

### Scenario 2: Find and Use Container Images

```
User: What container images are available for CUDA 12?

Agent uses:
1. list_container_images(pattern="*cuda12*")
2. Returns list of matching .sqsh files with details
3. User can then reference these in job submissions
```

### Scenario 3: Check GPU Cluster Status

```
User: How many GPUs are available right now?

Agent uses:
1. get_gpu_info() - Get overview of GPU types in cluster
2. get_gpu_availability() - Get current free vs allocated GPUs
3. get_cluster_status() - Overall cluster health
4. Summarizes: "32 A100s available (64 total), 16 V100s available (32 total)"
```

### Scenario 4: Submit CPU-only Data Processing Job

```
User: Run a data preprocessing job that needs 64 cores and 256GB RAM

Agent uses:
1. get_partition_info() - Find CPU partitions with enough resources
2. submit_job with:
   - script_content: "python preprocess.py --workers 64"
   - partition: "cpu"
   - nodes: 1
   - cpus_per_task: 64
   - memory: "256G"
   - time_limit: "4:00:00"
   (no container or GPU options needed)
```

### Scenario 5: Monitor Running Jobs

```
User: Check the status of my running jobs

Agent uses:
1. list_jobs(user="current_user", state="RUNNING")
2. get_job_details(job_id=...) for specific jobs
3. read_job_output(...) to check progress
```

### Scenario 6: Debug Failed Job

```
User: My job 12345 failed, help me debug it

Agent uses:
1. get_job_details(job_id=12345)
2. get_job_history(job_id=12345) for exit codes
3. read_job_output(...) for stdout/stderr
4. Analyzes and suggests fixes
```

### Scenario 7: Container Image Discovery

```
User: I need to run a TensorFlow job, what images do you have?

Agent uses:
1. list_container_images(pattern="*tensorflow*")
2. list_container_images(pattern="*tf*")
3. Presents options: "Found 3 TensorFlow images:
   - /images/tensorflow-24.01.sqsh (2.4GB, updated Jan 15)
   - /images/tf-nightly.sqsh (2.6GB, updated Jan 14)
   - /images/tensorflow-horovod.sqsh (3.1GB, updated Dec 20)"
```

### Scenario 8: Quick Interactive Command (One-shot)

```
User: Run "nvidia-smi" on a GPU node to check the GPU configuration

Agent uses:
1. run_interactive_command(
     command="nvidia-smi",
     partition="interactive",
     gpus_per_node=8,
     container_image="/path/to/dev.sqsh",
     time_limit="0:10:00"
   )
2. Returns GPU info output directly
```

### Scenario 9: Persistent Interactive Development Session

```
User: I need to do some development work on the cluster for the next few hours

Agent workflow:
1. list_interactive_profiles() - Show available configs
2. start_session_from_profile(profile_name="dev-8gpu", session_name="my-dev-session")
   - Returns: "Session 'my-dev-session' started (session_id: abc123, job_id: 456789)
              Resources: 1 node, 8 GPUs, 4:00:00 remaining
              Container: /path/to/dev.sqsh"

User: Install a package and check it works

3. exec_in_session(session_id="abc123", command="pip install transformers")
4. exec_in_session(session_id="abc123", command="python -c 'import transformers; print(transformers.__version__)'")

User: I'm done for now

5. end_interactive_session(session_id="abc123")
```

### Scenario 10: Debug Code Interactively

```
User: My training script fails, help me debug it interactively

Agent workflow:
1. start_interactive_session(
     partition="interactive",
     gpus_per_node=8,
     container_image="/path/to/pytorch.sqsh",
     container_mounts="/data:/data,/Projects:/Projects",
     time_limit="2:00:00"
   )

2. exec_in_session(session_id="...", command="cd /Projects/myproject && ls -la")

3. exec_in_session(session_id="...", command="python train.py --debug 2>&1 | head -100")
   - Sees error output

4. exec_in_session(session_id="...", command="python -c 'import torch; print(torch.cuda.is_available())'")
   - Checks CUDA availability

5. Agent analyzes output and suggests fixes
6. exec_in_session(session_id="...", command="python train.py --fixed-flag")
   - Tests the fix

7. end_interactive_session(session_id="...")
```

### Scenario 11: Save Custom Profile for Team

```
User: Save my current dev setup as a profile called "ml-research"

Agent uses:
1. save_interactive_profile(
     profile_name="ml-research",
     partition="interactive",
     account="nvr_lpr_agentic",
     nodes=1,
     gpus_per_node=8,
     time_limit="4:00:00",
     container_image="/lustre/fsw/.../nvidian+nemo+verl_v2_enroot_dev0.8.5.sqsh",
     container_mounts="/home/yidong:/home,/lustre:/lustre,..."
   )
2. Returns: "Profile 'ml-research' saved successfully"

Later:
3. start_session_from_profile(profile_name="ml-research")
```

### Scenario 12: Explore Cluster Directory Structure

```
User: What directories are set up on the cluster?

Agent uses:
1. get_cluster_directories()
2. Returns:
   "Cluster Directory Structure:
    User Root:  /lustre/fsw/portfolios/nvr/users/yidong
    
    Configured Directories (host path -> container mount):
    - Datasets:       /lustre/fsw/.../yidong/data      -> /datasets
    - Results:        /lustre/fsw/.../yidong/results   -> /results
    - Models:         /lustre/fsw/.../yidong/models    -> /models
    - Logs:           /lustre/fsw/.../yidong/logs      -> /logs
    - Projects:       /lustre/fsw/.../yidong/Projects  -> /projects
    - Container Root: /lustre/fsw/.../yidong/root      -> /root
    - GPFS Root:      /lustre                          -> /lustre"
```

### Scenario 13: Find and Check Model Checkpoints

```
User: What checkpoints do we have for the llama training run?

Agent uses:
1. list_model_checkpoints(model_name="llama", pattern="checkpoint-*")
2. Returns:
   "Found 5 checkpoints in /models/llama:
    - checkpoint-1000/  (4.2GB, Jan 14 10:30)
    - checkpoint-2000/  (4.2GB, Jan 14 14:45)
    - checkpoint-3000/  (4.2GB, Jan 14 19:00)
    - checkpoint-4000/  (4.2GB, Jan 15 00:15)
    - checkpoint-5000/  (4.2GB, Jan 15 04:30)"

User: Check the training metrics from checkpoint-5000

3. read_file("llama/checkpoint-5000/trainer_state.json", directory_type="models")
```

### Scenario 14: Check Job Logs for Failed Job

```
User: Show me the logs for job 12345

Agent uses:
1. list_job_logs(job_id=12345)
   Returns: "Found logs: job-12345.out, job-12345.err"

2. read_file("job-12345.err", directory_type="logs", tail_lines=100)
   Returns last 100 lines of error output

3. Analyzes errors and suggests fixes
```

### Scenario 15: Check Disk Usage

```
User: How much space am I using?

Agent uses:
1. get_disk_usage()
2. Returns:
   "Disk Usage:
    - Datasets:  245GB / 1TB (24.5%)
    - Results:   89GB / 500GB (17.8%)
    - Models:    1.2TB / 2TB (60%)
    - Logs:      12GB / 100GB (12%)
    - Projects:  34GB / 200GB (17%)"
```

### Scenario 16: Find Large Old Files to Clean Up

```
User: Find model checkpoints older than 30 days that are taking up space

Agent uses:
1. find_files(
     pattern="checkpoint-*",
     directory_type="models",
     file_type="dir",
     min_size="1G",
     max_age="30d"
   )
2. Returns list of old checkpoints with sizes
3. User can decide which to delete

4. delete_file("old_experiment/checkpoint-1000", directory_type="models", recursive=True, confirm=True)
```

### Scenario 17: Set Up New Experiment

```
User: Create directory structure for a new experiment called "rlhf-v2"

Agent uses:
1. write_file("rlhf-v2/.gitkeep", "", directory_type="results", make_dirs=True)
2. write_file("rlhf-v2/checkpoints/.gitkeep", "", directory_type="models", make_dirs=True)

3. Returns: "Created experiment directories:
    - /results/rlhf-v2/
    - /models/rlhf-v2/checkpoints/"
```
