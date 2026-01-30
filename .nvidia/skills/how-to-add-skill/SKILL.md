# How to Add Skills

Skills are custom knowledge modules that provide context-specific information and instructions to Nvidia Code. They're automatically loaded when triggered by keywords or explicitly invoked.

## Trigger Keywords
- add skill
- create skill
- new skill
- skill tutorial

## Quick Start

### 1. Create the Skill Directory

Skills live in `.nvidia/skills/` directories. You can place them in:

| Location | Scope |
|----------|-------|
| `<project>/.nvidia/skills/<skill-name>/` | Project-specific |
| `~/.nvidia-code/skills/<skill-name>/` | Global (all projects) |

```bash
# Project-specific skill
mkdir -p .nvidia/skills/my-skill

# Global skill
mkdir -p ~/.nvidia-code/skills/my-skill
```

### 2. Create SKILL.md

Every skill requires a `SKILL.md` file in its directory:

```bash
touch .nvidia/skills/my-skill/SKILL.md
```

### 3. Write the Skill Content

```markdown
# My Skill Name

Brief description of what this skill provides.

## Trigger Keywords
- keyword1
- keyword2
- related phrase

## Content

Your skill content goes here. Include:
- Instructions
- Code examples
- Reference information
- Best practices
- Links to resources

## Available Reference Files

List any additional files in this skill's directory.
```

## Skill Structure

```
.nvidia/skills/
└── my-skill/
    ├── SKILL.md          # Required: Main skill content
    ├── examples/         # Optional: Example files
    │   ├── config.yaml
    │   └── script.sh
    └── templates/        # Optional: Templates
        └── job.sbatch
```

## Best Practices

### 1. Use Clear Trigger Keywords
Choose keywords that users naturally say when they need this information:
```markdown
## Trigger Keywords
- cluster setup
- configure ssh
- connect to cluster
```

### 2. Structure Content with Headers
Use markdown headers to organize information:
```markdown
## Quick Start
## Configuration
## Troubleshooting
## Reference
```

### 3. Include Code Examples
```markdown
## Example Usage

\`\`\`bash
# Connect to the cluster
ssh user@cluster.example.com

# Submit a job
sbatch my_job.sh
\`\`\`
```

### 4. Add Reference Files
Include templates, configs, or scripts that users can reference:
```markdown
## Available Reference Files

- `templates/job.sbatch` - Example batch job script
- `configs/settings.yaml` - Default configuration
```

### 5. Keep Information Current
- Include last-updated date for time-sensitive information
- Add links to authoritative sources
- Note any prerequisites or access requirements

## Example: Cluster Skill

Here's a complete example for a cluster skill:

```markdown
# my-cluster Cluster Skill

HPC cluster for ML training workloads.

## Trigger Keywords
- my-cluster
- training cluster

## Cluster Access

**Host:** `login.my-cluster.example.com`
**Auth:** SSH key required

## Storage

| Path | Quota | Use Case |
|------|-------|----------|
| `/home/<user>` | 10 GB | Configs |
| `/scratch/<user>` | 1 TB | Datasets |

## Quick Commands

\`\`\`bash
# Login
ssh login.my-cluster.example.com

# Check quota
quota -s

# Submit job
sbatch job.sh
\`\`\`

## Support

- Slack: #cluster-support
- Docs: https://docs.example.com
```

## Invoking Skills

Skills can be invoked in two ways:

### 1. Automatic (Trigger Keywords)
When you mention trigger keywords in conversation, the skill may be automatically loaded.

### 2. Explicit Invocation
Ask directly:
```
"Load the my-cluster skill"
"Use skill my-cluster"
```

Or programmatically via the Skill tool:
```python
Skill(skill="my-cluster")
```

## Tips

1. **One topic per skill** - Keep skills focused on a single topic
2. **Use tables** - Great for structured data like node lists, paths, etc.
3. **Include troubleshooting** - Common issues and solutions
4. **Add support contacts** - Where to get help
5. **Link to docs** - Reference official documentation

## File Naming

- Skill directory: Use lowercase with hyphens (`my-skill-name`)
- Main file: Always `SKILL.md` (case-sensitive)
- Keep names descriptive but concise
