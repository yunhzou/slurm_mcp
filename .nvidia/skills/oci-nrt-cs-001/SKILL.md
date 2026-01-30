# oci-nrt-cs-001 Cluster Skill

NVIDIA Slurm cluster located in Oracle Cloud Infrastructure (OCI) - Narita, Japan region.

## Trigger Keywords
- oci-nrt-cs-001
- nrt cluster
- narita cluster
- japan cluster

## Cluster Access

**Username:** NVIDIA username (not email)
**Password:** NVIDIA password
**Access:** On-site or VPN required

## Node Types & Workload Patterns

### Login Nodes (Code editing, light debugging, job submission)
| Node | Hostname | Notes |
|------|----------|-------|
| Login 01 | `oci-nrt-cs-001-login-01.nvidia.com` | Often oversubscribed |
| Login 02 | `oci-nrt-cs-001-login-02.nvidia.com` | **Recommended** |
| Login 03 | `oci-nrt-cs-001-login-03.nvidia.com` | **Recommended** |

**Restrictions:**
- NO heavy data transfers
- NO VS Code
- Violations will be killed

### Data Copier Nodes (Large data transfers)
| Node | Hostname | Notes |
|------|----------|-------|
| DC 01 | `oci-nrt-cs-001-dc-01.nvidia.com` | Often oversubscribed |
| DC 02 | `oci-nrt-cs-001-dc-02.nvidia.com` | **Recommended** |
| DC 03 | `oci-nrt-cs-001-dc-03.nvidia.com` | **Recommended** |

**Restrictions:**
- NO VS Code (use dedicated VS Code nodes)

### VS Code Nodes (IDE sessions)
| Node | Hostname | Notes |
|------|----------|-------|
| VSCode 01 | `oci-nrt-cs-001-vscode-01.nvidia.com` | VS Code / Cursor |
| VSCode 02 | `oci-nrt-cs-001-vscode-02.nvidia.com` | VS Code / Cursor |

## Storage

### Access Groups
- **Access DL:** Access-NVResearch-Storage
- **Unix Group:** nvresearch

### Paths
| Type | Path | Quota | Use Case |
|------|------|-------|----------|
| Home | `/home/<username>` | 10 GB | Scripts, configs, small files |
| Lustre | `/lustre/fsw/portfolios/<portfolio>/users/<username>` | 50 TB | Datasets, checkpoints, ML workloads |

## Quick SSH Commands

```bash
# Login (recommended node)
ssh oci-nrt-cs-001-login-02.nvidia.com

# Data transfer
ssh oci-nrt-cs-001-dc-02.nvidia.com

# VS Code / Cursor
ssh oci-nrt-cs-001-vscode-01.nvidia.com
```

## Typical Workload Patterns

### Interactive Development
```bash
# SSH to login node for light work
ssh oci-nrt-cs-001-login-02.nvidia.com

# Request interactive GPU session
srun --pty --gres=gpu:1 --time=2:00:00 bash
```

### Batch Job Submission
```bash
# Submit from login node
sbatch my_training_job.sh
```

### Large Data Transfer
```bash
# Use data copier node
ssh oci-nrt-cs-001-dc-02.nvidia.com
rsync -avP /source/data /lustre/fsw/portfolios/<portfolio>/users/<username>/
```

## Support

- Check [Helios](https://helios.nvidia.com/) for access DL membership
- Use [dlrequest](https://dlrequest/GroupID/Requests/Index#RequestInbox) to request access

## Resources

- [Slurm 101 (NVLearn)](https://nvlearn.csod.com/ui/lms-learner-playlist/PlaylistDetails?playlistId=1540f39d-231d-4d7f-8007-5bac4380181f)
- [MARS Cluster Docs](https://confluence.nvidia.com/x/WZKkUg)
- [Quick Start Guide](https://confluence.nvidia.com/x/ge7b0Q)
- [Best Practices](https://confluence.nvidia.com/x/x3yKtQ)
- [Maintenance Calendar](https://aihub.nvidia.com/allocations/calendar)
