# Slurm MCP Server - Capabilities & Interaction Guide

This document describes the full capabilities of the Slurm MCP (Model Context Protocol) server and provides example interactions for LLM agents.

## Overview

The Slurm MCP server enables AI agents to remotely manage HPC (High-Performance Computing) clusters running Slurm. It provides **34 tools** across 6 categories:

| Category | Tools | Description |
|----------|-------|-------------|
| Cluster Status | 5 | Monitor cluster, partitions, nodes, GPUs |
| Job Management | 7 | Submit, cancel, monitor batch jobs |
| Container Images | 2 | List and validate Pyxis/Enroot containers |
| Interactive Sessions | 7 | Manage persistent GPU allocations |
| Profile Management | 3 | Save/load session configurations |
| Directory & Files | 10 | Browse, read, write cluster files |

---

## 1. Cluster Status Tools

### Tools Available
| Tool | Description |
|------|-------------|
| `get_cluster_status` | Overview of all partitions with availability |
| `get_partition_info` | Detailed information about specific partitions |
| `get_node_info` | Information about cluster nodes |
| `get_gpu_info` | GPU resources by partition and type |
| `get_gpu_availability` | Check if specific GPU count is available |

### Example Interactions

**User:** "What's the current cluster status?"

**LLM calls:** `get_cluster_status()`

**Response:**
```
Cluster Status:

  batch_block1 (default): up
    Nodes: 14/992 available
    CPUs: 10008/222208 available, GPUs: 480/7936
    Max Time: 4:00:00
    GPU Types: h100

  interactive: up
    Nodes: 61/996 available
    CPUs: 13688/223104 available, GPUs: 488/7968
    Max Time: 4:00:00
    GPU Types: h100
```

---

**User:** "How many GPUs are available right now?"

**LLM calls:** `get_gpu_info()`

**Response:**
```
GPU Information:

Total GPUs: 71,488
Allocated: 67,152
Available: 4,336

By GPU Type:
  h100: 4,336/71,488 available

By Partition:
  interactive: 488/7,968 available (h100)
  batch_block1: 480/7,936 available (h100)
  batch_large: 480/7,936 available (h100)
```

---

**User:** "Can I get 16 GPUs on the interactive partition?"

**LLM calls:** `get_gpu_availability(partition="interactive", min_gpus=16)`

**Response:**
```
GPU Availability: 488/7968 GPUs free
✓ 16 GPUs are available
```

---

**User:** "Show me idle nodes with GPUs"

**LLM calls:** `get_node_info(state="idle")`

**Response:**
```
Found 61 nodes:

  pool0-01438: idle
    CPUs: 224/224 available
    Memory: 2096128MB/2096128MB available, GPUs: h100:8
    Partitions: interactive, admin

  pool0-02919: idle
    CPUs: 224/224 available
    Memory: 2096128MB/2096128MB available, GPUs: h100:8
    Partitions: interactive, admin
```

---

## 2. Job Management Tools

### Tools Available
| Tool | Description |
|------|-------------|
| `list_jobs` | List jobs in the queue (with filters) |
| `get_job_details` | Detailed info about a specific job |
| `submit_job` | Submit a batch job |
| `cancel_job` | Cancel a running/pending job |
| `hold_job` | Put a pending job on hold |
| `release_job` | Release a held job |
| `get_job_history` | Get job accounting history |

### Example Interactions

**User:** "What jobs do I have running?"

**LLM calls:** `list_jobs(user="username")`

**Response:**
```
Found 2 jobs:

  Job 2986269: training-gpt
    User: username, State: RUNNING
    Partition: batch_block1, Nodes: 4, CPUs: 896, GPUs: 32
    Time: 2:30:00 / 8:00:00

  Job 2986301: data-preprocessing
    User: username, State: PENDING
    Partition: batch_short, Nodes: 1, CPUs: 32
    Time: N/A / 1:00:00
    Reason: Resources
```

---

**User:** "Submit a training job with 8 GPUs using PyTorch"

**LLM calls:** `submit_job(
    script_content="python train.py --epochs 100",
    job_name="my-training",
    partition="batch_block1",
    account="your_project",
    nodes=1,
    gpus=8,
    time_limit="4:00:00",
    container_image="/lustre/users/username/images/pytorch.sqsh",
    container_mounts="/lustre/users/username/data:/data"
)`

**Response:**
```
Job submitted successfully. Job ID: 2986350
```

---

**User:** "Cancel job 2986350"

**LLM calls:** `cancel_job(job_id=2986350)`

**Response:**
```
Job 2986350 cancelled successfully.
```

---

**User:** "Show me details of job 2986269"

**LLM calls:** `get_job_details(job_id=2986269)`

**Response:**
```
Job 2986269: training-gpt
  User: username
  State: RUNNING
  Partition: batch_block1
  Nodes: pool0-01438,pool0-01439,pool0-01440,pool0-01441 (4 requested)
  CPUs: 896
  GPUs: 32
  Memory: 512G
  Time Limit: 8:00:00
  Time Used: 2:35:12
  Working Dir: /lustre/users/username/Projects/gpt
  Stdout: /lustre/users/username/logs/2986269.out
  Stderr: /lustre/users/username/logs/2986269.err
  Submitted: 2026-01-16T10:00:00
  Started: 2026-01-16T10:05:23
```

---

**User:** "Show my job history from the past week"

**LLM calls:** `get_job_history(user="username", start_time="now-7days")`

**Response:**
```
JobID        JobName        Partition  State      Elapsed    ExitCode
------------ -------------- ---------- ---------- ---------- --------
2986100      train-v1       batch      COMPLETED  4:00:00    0:0
2986150      eval-model     interactive COMPLETED 0:30:00    0:0
2986200      debug-session  interactive CANCELLED 0:15:00    0:0
2986269      training-gpt   batch      RUNNING    2:35:00    
```

---

## 3. Container Image Tools

### Tools Available
| Tool | Description |
|------|-------------|
| `list_container_images` | List available .sqsh container images |
| `validate_container_image` | Check if a container image exists and is valid |

### Example Interactions

**User:** "What container images are available?"

**LLM calls:** `list_container_images()`

**Response:**
```
Found 23 container images:

  nemo_verl_v2_dev0.8.5.sqsh
    Path: /lustre/.../images/nemo_verl_v2_dev0.8.5.sqsh
    Size: 29.5GB
    Modified: 2025-12-15 14:30

  pytorch_24.08.sqsh
    Path: /lustre/.../images/pytorch_24.08.sqsh
    Size: 18.2GB
    Modified: 2025-11-20 09:15

  nemo_framework_24.07.sqsh
    Path: /lustre/.../images/nemo_framework_24.07.sqsh
    Size: 32.1GB
    Modified: 2025-10-05 16:45
```

---

**User:** "Is the PyTorch container valid?"

**LLM calls:** `validate_container_image(image_path="/lustre/.../images/pytorch_24.08.sqsh")`

**Response:**
```
Container image is valid: /lustre/.../images/pytorch_24.08.sqsh
```

---

## 4. Interactive Session Tools

### Tools Available
| Tool | Description |
|------|-------------|
| `run_interactive_command` | Run a single command with resource allocation |
| `start_interactive_session` | Start a persistent session (salloc) |
| `exec_in_session` | Execute command in existing session |
| `list_interactive_sessions` | List all active sessions |
| `get_interactive_session_info` | Get details of a session |
| `end_interactive_session` | End a session and release resources |

### Example Interactions

**User:** "Run nvidia-smi on a GPU node"

**LLM calls:** `run_interactive_command(
    command="nvidia-smi",
    partition="interactive",
    nodes=1,
    gpus_per_node=1,
    time_limit="0:05:00"
)`

**Response:**
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 550.54.15    Driver Version: 550.54.15    CUDA Version: 12.4     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA H100 80G...  On   | 00000000:18:00.0 Off |                    0 |
| N/A   32C    P0    72W / 700W |      0MiB / 81559MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

---

**User:** "Start a development session with 8 GPUs"

**LLM calls:** `start_interactive_session(
    session_name="dev-session",
    partition="interactive",
    nodes=1,
    gpus_per_node=8,
    time_limit="4:00:00",
    container_image="/lustre/.../images/pytorch_24.08.sqsh"
)`

**Response:**
```
Session 'dev-session' started successfully.
  Session ID: a1b2c3d4
  Job ID: 2986400
  Partition: interactive
  Nodes: 1
  GPUs/Node: 8
  Time Limit: 4:00:00
  Node List: pool0-01438

Use exec_in_session(session_id='a1b2c3d4', command='...') to run commands.
```

---

**User:** "Run 'python train.py' in my session"

**LLM calls:** `exec_in_session(session_id="a1b2c3d4", command="python train.py")`

**Response:**
```
Starting training...
Epoch 1/100: loss=2.345, accuracy=0.45
Epoch 2/100: loss=1.892, accuracy=0.58
...
Training completed successfully.
```

---

**User:** "What sessions do I have running?"

**LLM calls:** `list_interactive_sessions()`

**Response:**
```
Active Sessions (1):

  Session a1b2c3d4 (dev-session)
    Job ID: 2986400
    Partition: interactive
    Nodes: 1, GPUs/Node: 8
    Time Remaining: 3:45:00
    Status: active
```

---

**User:** "End my dev session"

**LLM calls:** `end_interactive_session(session_id="a1b2c3d4")`

**Response:**
```
Session a1b2c3d4 ended successfully.
```

---

## 5. Profile Management Tools

### Tools Available
| Tool | Description |
|------|-------------|
| `save_interactive_profile` | Save session configuration for reuse |
| `list_interactive_profiles` | List saved profiles |
| `start_session_from_profile` | Start session using saved profile |

### Example Interactions

**User:** "Save my current setup as a profile"

**LLM calls:** `save_interactive_profile(
    profile_name="ml-training",
    description="ML training with 8 H100 GPUs",
    partition="interactive",
    nodes=1,
    gpus_per_node=8,
    time_limit="8:00:00",
    container_image="/lustre/.../images/pytorch_24.08.sqsh",
    container_mounts="/data:/data,/models:/models"
)`

**Response:**
```
Profile 'ml-training' saved successfully.
```

---

**User:** "What profiles do I have?"

**LLM calls:** `list_interactive_profiles()`

**Response:**
```
Saved Profiles (4):

  dev-8gpu
    Description: Development session with 8 GPUs (4 hours)
    Partition: interactive
    Nodes: 1, GPUs/Node: 8
    Time Limit: 4:00:00
    Container: pytorch_24.08.sqsh

  ml-training
    Description: ML training with 8 H100 GPUs
    Partition: interactive
    Nodes: 1, GPUs/Node: 8
    Time Limit: 8:00:00
    Container: pytorch_24.08.sqsh

  debug-cpu
    Description: CPU-only debugging session
    Partition: batch_short
    Nodes: 1, GPUs/Node: 0
    Time Limit: 1:00:00
```

---

**User:** "Start a session using my ml-training profile"

**LLM calls:** `start_session_from_profile(profile_name="ml-training")`

**Response:**
```
Session started from profile 'ml-training'.
  Session ID: e5f6g7h8
  Job ID: 2986450

Use exec_in_session(session_id='e5f6g7h8', command='...') to run commands.
```

---

## 6. Directory & File Tools

### Tools Available
| Tool | Description |
|------|-------------|
| `get_cluster_directories` | Show configured directory structure |
| `list_directory` | List contents of a directory |
| `list_datasets` | List available datasets |
| `list_model_checkpoints` | List model checkpoints |
| `list_job_logs` | List job log files |
| `read_file` | Read file contents |
| `write_file` | Write content to a file |
| `find_files` | Search for files by pattern |
| `delete_file` | Delete a file (requires confirmation) |
| `get_disk_usage` | Check disk usage |

### Example Interactions

**User:** "What's my directory structure?"

**LLM calls:** `get_cluster_directories()`

**Response:**
```
Cluster Directory Structure:
  User Root: /lustre/users/username/

Configured Directories (host path -> container mount):
  Datasets:       /lustre/.../data -> /datasets
  Results:        /lustre/.../results -> /results
  Models:         /lustre/.../models -> /models
  Logs:           /lustre/.../logs -> /logs
  Projects:       /lustre/.../Projects -> /projects
  Container Root: /lustre/.../root -> /root
  Images:         /lustre/.../images/
```

---

**User:** "List my datasets"

**LLM calls:** `list_datasets()`

**Response:**
```
Datasets (5):

  imagenet/ (1.2TB)
  coco2017/ (25.3GB)
  openwebtext/ (45.6GB)
  custom_dataset.tar.gz (8.9GB)
  processed/ (156.7GB)
```

---

**User:** "Show me recent job logs"

**LLM calls:** `list_job_logs(recent=5)`

**Response:**
```
Job Logs (5):

  2986269.out (125.3KB, 2026-01-16 14:30)
  2986269.err (2.1KB, 2026-01-16 14:30)
  2986200.out (45.2KB, 2026-01-15 18:00)
  2986150.out (12.8KB, 2026-01-15 10:30)
  2986100.out (89.4KB, 2026-01-14 22:00)
```

---

**User:** "Show me the last 50 lines of my training log"

**LLM calls:** `read_file(path="2986269.out", directory_type="logs", tail_lines=50)`

**Response:**
```
Epoch 95/100: loss=0.0234, accuracy=0.9812
Epoch 96/100: loss=0.0228, accuracy=0.9815
Epoch 97/100: loss=0.0221, accuracy=0.9820
Epoch 98/100: loss=0.0215, accuracy=0.9823
Epoch 99/100: loss=0.0210, accuracy=0.9825
Epoch 100/100: loss=0.0205, accuracy=0.9828
Training completed!
Saving model to /models/gpt_final.pt
Model saved successfully.
Total training time: 3:58:45
```

---

**User:** "Find all Python files in my project"

**LLM calls:** `find_files(pattern="*.py", directory_type="projects")`

**Response:**
```
Found 23 files:

  /Projects/gpt/train.py (15.2KB)
  /Projects/gpt/model.py (8.9KB)
  /Projects/gpt/data.py (5.6KB)
  /Projects/gpt/utils.py (3.2KB)
  /Projects/gpt/config.py (1.8KB)
  /Projects/eval/evaluate.py (7.4KB)
  ...
```

---

**User:** "Write a config file for my training"

**LLM calls:** `write_file(
    path="config.yaml",
    directory_type="projects",
    content="""
model:
  name: gpt2-medium
  hidden_size: 1024
  num_layers: 24

training:
  batch_size: 32
  learning_rate: 0.0001
  epochs: 100
"""
)`

**Response:**
```
Wrote file successfully.
```

---

**User:** "How much disk space am I using?"

**LLM calls:** `get_disk_usage()`

**Response:**
```
Disk Usage:

  datasets: 1.4TB
    Path: /lustre/.../data
  results: 256.8GB
    Path: /lustre/.../results
  models: 89.3GB
    Path: /lustre/.../models
  logs: 12.5GB
    Path: /lustre/.../logs

Filesystem:
  Total: 50PB
  Used: 32PB
  Available: 18PB
```

---

## 7. Advanced Shell Commands

### Tool Available
| Tool | Description |
|------|-------------|
| `run_shell_command` | Execute arbitrary shell command on login node |

### Example Interactions

**User:** "Check my quota"

**LLM calls:** `run_shell_command(command="quota -s")`

**Response:**
```
Disk quotas for user username:
     Filesystem   space   quota   limit   grace   files   quota   limit
     /lustre      2.1TB   5.0TB   6.0TB           45231   unlimited
```

---

**User:** "What's my current environment?"

**LLM calls:** `run_shell_command(command="module list")`

**Response:**
```
Currently Loaded Modules:
  1) cuda/12.4   2) python/3.11   3) gcc/11.3
```

---

## Complete Workflow Example

Here's how an LLM agent might handle a complete ML training workflow:

### User Request:
"I want to train a GPT model on 8 GPUs. Check if resources are available, start a session, run the training, and monitor it."

### LLM Actions:

**Step 1: Check GPU availability**
```python
get_gpu_availability(partition="interactive", min_gpus=8)
# Response: "✓ 8 GPUs are available"
```

**Step 2: List available containers**
```python
list_container_images(pattern="pytorch*")
# Response: "pytorch_24.08.sqsh (18.2GB)"
```

**Step 3: Start interactive session**
```python
start_interactive_session(
    session_name="gpt-training",
    partition="interactive",
    gpus_per_node=8,
    time_limit="4:00:00",
    container_image="/lustre/.../pytorch_24.08.sqsh"
)
# Response: "Session ID: xyz123, Job ID: 2986500"
```

**Step 4: Run training**
```python
exec_in_session(
    session_id="xyz123",
    command="cd /projects/gpt && python train.py --epochs 100"
)
# Response: "Training started..."
```

**Step 5: Monitor progress**
```python
read_file(path="2986500.out", directory_type="logs", tail_lines=10)
# Response: "Epoch 45/100: loss=0.125, accuracy=0.92"
```

**Step 6: End session when done**
```python
end_interactive_session(session_id="xyz123")
# Response: "Session xyz123 ended successfully."
```

---

## Summary

The Slurm MCP server provides comprehensive cluster management capabilities:

- **34 tools** for full cluster interaction
- **Real-time monitoring** of GPUs, nodes, and jobs
- **Job submission** with container support (Pyxis/Enroot)
- **Interactive sessions** for development and debugging
- **Profile management** for quick session setup
- **File operations** for data and code management

This enables LLM agents to autonomously manage HPC workflows, from checking resource availability to running distributed training jobs.
