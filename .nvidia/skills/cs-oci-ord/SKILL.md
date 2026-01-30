# cs-oci-ord Cluster Skill

NVIDIA Slurm cluster located in Oracle Cloud Infrastructure (OCI) - Chicago/Ord region.

## Trigger Keywords
- cs-oci-ord
- ord cluster
- chicago cluster

## Cluster Access

**Username:** NVIDIA username (not email)
**Password:** NVIDIA password
**Access:** On-site or VPN required

## Node Types & Workload Patterns

### Login Nodes (Code editing, light debugging, job submission)
| Node | Hostname | Notes |
|------|----------|-------|
| Login 01 | `cs-oci-ord-login-01.nvidia.com` | Often oversubscribed |
| Login 02 | `cs-oci-ord-login-02.nvidia.com` | **Recommended** |
| Login 03 | `cs-oci-ord-login-03.nvidia.com` | **Recommended** |

**Restrictions:**
- NO heavy data transfers
- NO VS Code
- Violations will be killed

### Data Copier Nodes (Large data transfers)
| Node | Hostname | Notes |
|------|----------|-------|
| DC 01 | `cs-oci-ord-dc-01.nvidia.com` | Often oversubscribed |
| DC 02 | `cs-oci-ord-dc-02.nvidia.com` | **Recommended** |
| DC 03 | `cs-oci-ord-dc-03.nvidia.com` | **Recommended** |

**Restrictions:**
- NO VS Code (use NVPark instead)

### VS Code Nodes (IDE sessions)
| Node | Hostname | Usage |
|------|----------|-------|
| VSCode 01 | `cs-oci-ord-vscode-01.nvidia.com` | Cursor |
| VSCode 02 | `cs-oci-ord-vscode-02.nvidia.com` | Cursor |

**For VS Code:** Use [NVPark](https://cisd.gitlab-master-pages.nvidia.com/park/clusters/cs-clusters)

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
ssh cs-oci-ord-login-02.nvidia.com

# Data transfer
ssh cs-oci-ord-dc-02.nvidia.com

# Cursor/IDE
ssh cs-oci-ord-vscode-01.nvidia.com
```

## Support

- **Slack:** [#nv-oci-ord-cs-support](https://nvidia.slack.com/archives/C06845ATK9R) (tag @cs-oci-ord-support)
- **Bot:** Tag @ADLR Infra Bot for quick answers
- **Jira:** [Submit ticket](https://requests-navigator.atlassian.net/servicedesk/customer/portal/11/group/48/create/111)

## Resources

- [Slurm 101 (NVLearn)](https://nvlearn.csod.com/ui/lms-learner-playlist/PlaylistDetails?playlistId=1540f39d-231d-4d7f-8007-5bac4380181f)
- [MARS Cluster Docs](https://confluence.nvidia.com/x/WZKkUg)
- [Quick Start Guide](https://confluence.nvidia.com/x/ge7b0Q)
- [cs-oci-ord Info](https://confluence.nvidia.com/x/MhIskQ)
- [Partitions](https://confluence.nvidia.com/x/84kZkg)
- [FAQs/Troubleshooting](https://confluence.nvidia.com/x/HnKNjg)
- [Best Practices](https://confluence.nvidia.com/x/x3yKtQ)
- [Maintenance Calendar](https://aihub.nvidia.com/allocations/calendar)
