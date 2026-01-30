# Multi-Cluster Support for Slurm MCP

## Current Architecture
The MCP server currently supports a single Slurm cluster with:
- One `Settings` instance with SSH connection details
- One `SSHClient` for connection
- Global instances (`_ssh`, `_slurm`, `_sessions`, etc.)

## Proposed Design

### 1. Cluster Configuration (`config.py`)
- Create `ClusterConfig` model for individual cluster settings
- Create `MultiClusterSettings` to manage multiple clusters
- Support configuration via:
  - Environment variables (e.g., `SLURM_CLUSTERS=cluster1,cluster2`)
  - Individual cluster configs: `SLURM_CLUSTER1_SSH_HOST`, `SLURM_CLUSTER2_SSH_HOST`, etc.

### 2. Cluster Manager (`cluster_manager.py` - new file)
- Create `ClusterManager` class to manage multiple clusters
- Each cluster has its own:
  - `SSHClient`
  - `SlurmCommands`
  - `InteractiveSessionManager`
  - `ProfileManager`
  - `DirectoryManager`
- Methods to get instances by cluster name
- Support for "default" cluster

### 3. Tool Updates (`server.py`)
- Add `cluster` parameter to all MCP tools (optional, defaults to "default" cluster)
- Add new tools:
  - `list_clusters()` - List all configured clusters
  - `get_cluster_info(cluster)` - Get info about a specific cluster
  - `set_default_cluster(cluster)` - Set the default cluster for session

### 4. Configuration Format
```
# Multi-cluster configuration
SLURM_CLUSTERS=cluster1,cluster2

# Cluster 1 (uses default SLURM_ prefix for backward compatibility)
SLURM_SSH_HOST=login1.cluster1.example.com
SLURM_SSH_USER=user1
SLURM_USER_ROOT=/lustre/users/user1

# Cluster 2 (uses SLURM_CLUSTER2_ prefix)
SLURM_CLUSTER2_SSH_HOST=login.cluster2.example.com
SLURM_CLUSTER2_SSH_USER=user2
SLURM_CLUSTER2_USER_ROOT=/gpfs/users/user2
```

## Implementation Steps

1. **Update `config.py`**
   - Create `ClusterConfig` dataclass for single cluster settings
   - Create `MultiClusterSettings` class
   - Add backward compatibility (single cluster works as before)

2. **Create `cluster_manager.py`**
   - `ClusterManager` class with lazy initialization
   - Methods: `get_cluster()`, `list_clusters()`, `get_default_cluster()`
   - Connection pooling for SSH clients

3. **Update `server.py`**
   - Refactor `get_instances()` to use `ClusterManager`
   - Add `cluster: Optional[str]` parameter to all tools
   - Add new cluster management tools

4. **Update helper modules**
   - Ensure `ssh_client.py`, `slurm_commands.py`, etc. work with multi-cluster

5. **Update tests**
   - Add multi-cluster test configurations
   - Test cluster switching

6. **Update documentation**
   - Update `.env.example` with multi-cluster examples
   - Update README with multi-cluster usage

## Backward Compatibility
- If `SLURM_CLUSTERS` is not set, assume single cluster mode
- Single cluster uses existing `SLURM_` prefix
- All tools work without `cluster` parameter (uses default)
