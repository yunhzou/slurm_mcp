# Slurm MCP - Tool Definitions for LLM Context

This document shows the exact tool definitions that are presented to LLMs when they connect to the Slurm MCP server.

**Total Tools: 34**

---

## Cluster Status Tools

### get_cluster_status

**Description:** Get the current status of the Slurm cluster including partitions and node availability.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by partition name"
    }
  }
}
```

---

### get_partition_info

**Description:** Get detailed information about cluster partitions.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "partition_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Specific partition name, or None for all"
    }
  }
}
```

---

### get_node_info

**Description:** Get information about cluster nodes.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "node_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Specific node name"
    },
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by partition"
    },
    "state": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by state (idle, allocated, down, etc.)"
    }
  }
}
```

---

### get_gpu_info

**Description:** Get information about available GPU resources in the cluster.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by partition"
    },
    "gpu_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by GPU type (e.g., 'a100', 'v100')"
    }
  }
}
```

---

### get_gpu_availability

**Description:** Check current GPU availability - how many GPUs are free vs allocated.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by partition"
    },
    "gpu_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by GPU type"
    },
    "min_gpus": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Minimum number of GPUs needed"
    }
  }
}
```

---

## Job Management Tools

### list_jobs

**Description:** List jobs in the Slurm queue.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "user": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by username"
    },
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by partition"
    },
    "state": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by job state (PENDING, RUNNING, etc.)"
    }
  }
}
```

---

### get_job_details

**Description:** Get detailed information about a specific job.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": "integer",
      "description": "The Slurm job ID"
    }
  },
  "required": ["job_id"]
}
```

---

### submit_job

**Description:** Submit a batch job to the Slurm cluster. Returns the job ID on success.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "script_content": {
      "type": "string",
      "description": "The SBATCH script content (commands to run)"
    },
    "job_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Job name"
    },
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Partition to submit to"
    },
    "account": {
      "type": ["string", "null"],
      "default": null,
      "description": "Account/project for billing"
    },
    "nodes": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Number of nodes"
    },
    "ntasks": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Number of tasks"
    },
    "cpus_per_task": {
      "type": ["integer", "null"],
      "default": null,
      "description": "CPUs per task"
    },
    "memory": {
      "type": ["string", "null"],
      "default": null,
      "description": "Memory per node (e.g., '4G', '4000M')"
    },
    "time_limit": {
      "type": ["string", "null"],
      "default": null,
      "description": "Time limit (e.g., '1:00:00', '1-00:00:00')"
    },
    "output_file": {
      "type": ["string", "null"],
      "default": null,
      "description": "Output file path"
    },
    "error_file": {
      "type": ["string", "null"],
      "default": null,
      "description": "Error file path"
    },
    "working_directory": {
      "type": ["string", "null"],
      "default": null,
      "description": "Working directory on cluster"
    },
    "gpus": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Number of GPUs per node"
    },
    "gpus_per_task": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Number of GPUs per task"
    },
    "gpu_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Specific GPU type (e.g., 'a100', 'v100')"
    },
    "container_image": {
      "type": ["string", "null"],
      "default": null,
      "description": "Path to container .sqsh image file"
    },
    "container_mounts": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container bind mounts"
    },
    "container_workdir": {
      "type": ["string", "null"],
      "default": null,
      "description": "Working directory inside container"
    }
  },
  "required": ["script_content"]
}
```

---

### cancel_job

**Description:** Cancel a running or pending job.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": "integer",
      "description": "The Slurm job ID to cancel"
    },
    "signal": {
      "type": ["string", "null"],
      "default": null,
      "description": "Signal to send (e.g., 'SIGTERM', 'SIGKILL')"
    }
  },
  "required": ["job_id"]
}
```

---

### hold_job

**Description:** Put a pending job on hold.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": "integer",
      "description": "The Slurm job ID to hold"
    }
  },
  "required": ["job_id"]
}
```

---

### release_job

**Description:** Release a held job.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": "integer",
      "description": "The Slurm job ID to release"
    }
  },
  "required": ["job_id"]
}
```

---

### get_job_history

**Description:** Get job accounting/history information.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Specific job ID"
    },
    "user": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by username"
    },
    "start_time": {
      "type": ["string", "null"],
      "default": null,
      "description": "Start time (e.g., '2024-01-01', 'now-7days')"
    },
    "end_time": {
      "type": ["string", "null"],
      "default": null,
      "description": "End time"
    }
  }
}
```

---

## Container Image Tools

### list_container_images

**Description:** List available container images (.sqsh files) for Pyxis/enroot.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "image_dir": {
      "type": ["string", "null"],
      "default": null,
      "description": "Directory to search for .sqsh images"
    },
    "pattern": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter images by name pattern (e.g., 'pytorch*')"
    }
  }
}
```

---

### validate_container_image

**Description:** Validate that a container image exists and is readable.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "image_path": {
      "type": "string",
      "description": "Path to the .sqsh container image"
    }
  },
  "required": ["image_path"]
}
```

---

## Interactive Session Tools

### run_interactive_command

**Description:** Execute a single command with interactive-partition resources (one-shot allocation).

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "description": "Command to execute"
    },
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Partition (default: interactive)"
    },
    "account": {
      "type": ["string", "null"],
      "default": null,
      "description": "Account/project for billing"
    },
    "nodes": {
      "type": "integer",
      "default": 1,
      "description": "Number of nodes"
    },
    "gpus_per_node": {
      "type": ["integer", "null"],
      "default": null,
      "description": "GPUs per node"
    },
    "time_limit": {
      "type": ["string", "null"],
      "default": null,
      "description": "Time limit (e.g., '4:00:00')"
    },
    "container_image": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container .sqsh image path"
    },
    "container_mounts": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container mounts"
    },
    "working_directory": {
      "type": ["string", "null"],
      "default": null,
      "description": "Working directory for command"
    },
    "timeout": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Command timeout in seconds"
    }
  },
  "required": ["command"]
}
```

---

### start_interactive_session

**Description:** Start a persistent interactive session using salloc.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "session_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Name for this session"
    },
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Partition (default: interactive)"
    },
    "account": {
      "type": ["string", "null"],
      "default": null,
      "description": "Account/project for billing"
    },
    "nodes": {
      "type": "integer",
      "default": 1,
      "description": "Number of nodes"
    },
    "gpus_per_node": {
      "type": ["integer", "null"],
      "default": null,
      "description": "GPUs per node"
    },
    "time_limit": {
      "type": ["string", "null"],
      "default": null,
      "description": "Time limit (e.g., '4:00:00')"
    },
    "container_image": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container .sqsh image path"
    },
    "container_mounts": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container mounts"
    }
  }
}
```

---

### exec_in_session

**Description:** Execute a command in an existing interactive session.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Session ID from start_interactive_session"
    },
    "command": {
      "type": "string",
      "description": "Command to execute"
    },
    "working_directory": {
      "type": ["string", "null"],
      "default": null,
      "description": "Working directory"
    },
    "timeout": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Command timeout in seconds"
    }
  },
  "required": ["session_id", "command"]
}
```

---

### list_interactive_sessions

**Description:** List all active interactive sessions managed by this MCP server.

**Parameters:**
```json
{
  "type": "object",
  "properties": {}
}
```

---

### end_interactive_session

**Description:** End an interactive session and release its resources.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Session ID to terminate"
    }
  },
  "required": ["session_id"]
}
```

---

### get_interactive_session_info

**Description:** Get detailed information about an interactive session.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Session ID"
    }
  },
  "required": ["session_id"]
}
```

---

## Profile Management Tools

### save_interactive_profile

**Description:** Save an interactive session profile for quick reuse.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "profile_name": {
      "type": "string",
      "description": "Name for this profile"
    },
    "description": {
      "type": ["string", "null"],
      "default": null,
      "description": "Profile description"
    },
    "partition": {
      "type": ["string", "null"],
      "default": null,
      "description": "Partition"
    },
    "account": {
      "type": ["string", "null"],
      "default": null,
      "description": "Account"
    },
    "nodes": {
      "type": "integer",
      "default": 1,
      "description": "Number of nodes"
    },
    "gpus_per_node": {
      "type": ["integer", "null"],
      "default": null,
      "description": "GPUs per node"
    },
    "time_limit": {
      "type": ["string", "null"],
      "default": null,
      "description": "Time limit"
    },
    "container_image": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container image"
    },
    "container_mounts": {
      "type": ["string", "null"],
      "default": null,
      "description": "Container mounts"
    }
  },
  "required": ["profile_name"]
}
```

---

### list_interactive_profiles

**Description:** List saved interactive session profiles.

**Parameters:**
```json
{
  "type": "object",
  "properties": {}
}
```

---

### start_session_from_profile

**Description:** Start an interactive session using a saved profile.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "profile_name": {
      "type": "string",
      "description": "Profile name to use"
    },
    "session_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Optional session name"
    },
    "time_limit": {
      "type": ["string", "null"],
      "default": null,
      "description": "Override time limit"
    }
  },
  "required": ["profile_name"]
}
```

---

## Directory & File Tools

### get_cluster_directories

**Description:** Get the configured cluster directory structure.

**Parameters:**
```json
{
  "type": "object",
  "properties": {}
}
```

---

### list_directory

**Description:** List contents of a directory on the cluster.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "default": "",
      "description": "Directory path to list"
    },
    "directory_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Directory type: 'datasets', 'results', 'models', 'logs', 'projects'"
    },
    "pattern": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by glob pattern"
    }
  }
}
```

---

### list_datasets

**Description:** List available datasets in the datasets directory.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "pattern": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by pattern"
    }
  }
}
```

---

### list_model_checkpoints

**Description:** List model checkpoints in the models directory.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "model_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by model name/directory"
    },
    "pattern": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by pattern"
    }
  }
}
```

---

### list_job_logs

**Description:** List job log files in the logs directory.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Filter by job ID"
    },
    "job_name": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by job name pattern"
    },
    "recent": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Only show N most recent logs"
    }
  }
}
```

---

### read_file

**Description:** Read contents of a file on the cluster.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "File path"
    },
    "directory_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Base directory type"
    },
    "tail_lines": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Only read last N lines"
    },
    "head_lines": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Only read first N lines"
    }
  },
  "required": ["path"]
}
```

---

### write_file

**Description:** Write content to a file on the cluster.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "File path"
    },
    "content": {
      "type": "string",
      "description": "File content"
    },
    "directory_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Base directory type"
    },
    "append": {
      "type": "boolean",
      "default": false,
      "description": "Append instead of overwrite"
    }
  },
  "required": ["path", "content"]
}
```

---

### find_files

**Description:** Search for files across cluster directories.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "pattern": {
      "type": "string",
      "description": "Search pattern (glob)"
    },
    "directory_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Directory to search in"
    },
    "path": {
      "type": ["string", "null"],
      "default": null,
      "description": "Specific path to search in"
    },
    "file_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Filter by type: 'file', 'dir', 'link'"
    },
    "min_size": {
      "type": ["string", "null"],
      "default": null,
      "description": "Minimum size (e.g., '1G', '100M')"
    },
    "max_age": {
      "type": ["string", "null"],
      "default": null,
      "description": "Maximum age (e.g., '7d', '24h')"
    }
  },
  "required": ["pattern"]
}
```

---

### delete_file

**Description:** Delete a file or directory on the cluster. Requires confirm=True for safety.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "File or directory path"
    },
    "directory_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Base directory type"
    },
    "recursive": {
      "type": "boolean",
      "default": false,
      "description": "Delete directories recursively"
    },
    "confirm": {
      "type": "boolean",
      "default": false,
      "description": "Confirm deletion (must be True)"
    }
  },
  "required": ["path"]
}
```

---

### get_disk_usage

**Description:** Get disk usage for cluster directories.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "directory_type": {
      "type": ["string", "null"],
      "default": null,
      "description": "Check specific directory type"
    },
    "path": {
      "type": ["string", "null"],
      "default": null,
      "description": "Check specific path"
    }
  }
}
```

---

### run_shell_command

**Description:** Execute a shell command on the Slurm login node. Use with caution.

**Parameters:**
```json
{
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "description": "Shell command to execute"
    },
    "working_directory": {
      "type": ["string", "null"],
      "default": null,
      "description": "Working directory"
    },
    "timeout": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Timeout in seconds"
    }
  },
  "required": ["command"]
}
```

---

## Summary

These 34 tools give LLMs complete control over:

| Category | Count | Key Operations |
|----------|-------|----------------|
| Cluster Status | 5 | Monitor nodes, GPUs, partitions |
| Job Management | 7 | Submit, cancel, monitor jobs |
| Container Images | 2 | List and validate .sqsh images |
| Interactive Sessions | 6 | Persistent GPU allocations |
| Profile Management | 3 | Save/load session configs |
| Directory & Files | 11 | Browse, read, write, search files |

All parameters support proper typing with optional/required validation, enabling LLMs to make well-formed API calls.
