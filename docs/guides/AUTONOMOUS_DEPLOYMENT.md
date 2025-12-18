# Autonomous Deployment with Goal-Seeking Agent

This guide explains how to use the goal-seeking deployment agent for autonomous Infrastructure-as-Code deployments that automatically recover from errors.

## Overview

The goal-seeking deployment agent is an AI-powered autonomous deployment system that iterates until deployment succeeds or maximum attempts are reached. Instead of failing on the first error, the agent analyzes failures, generates fixes, and retries deployment automatically.

**Key Benefits:**
- Autonomous error recovery without manual intervention
- AI-powered failure analysis and fix generation
- Comprehensive deployment reports with full iteration history
- Works with all IaC formats (Terraform, Bicep, ARM)
- Configurable iteration limits and timeouts

## Quick Start

Deploy with autonomous error recovery:

```bash
# Basic autonomous deployment
atg deploy --agent

# With custom iteration limit
atg deploy --agent --max-iterations 10

# With custom timeout per operation
atg deploy --agent --timeout 600

# Dry run to see what would be deployed
atg deploy --agent --dry-run
```

## How It Works

### The Autonomous Loop

When you enable agent mode with `--agent`, the deployment process follows this autonomous loop:

```
1. Attempt Deployment
   ↓
2. Deployment Succeeds? → DONE (Generate Report)
   ↓ NO
3. Analyze Failure (AI)
   ↓
4. Generate Fix (AI)
   ↓
5. Apply Fix to IaC
   ↓
6. Reached Max Iterations? → STOP (Generate Report)
   ↓ NO
7. Go to Step 1
```

**Default Limits:**
- Maximum iterations: 5
- Timeout per operation: 6000 seconds (100 minutes)
- Works with existing deployment backends (Terraform, Bicep, ARM)

### What the Agent Does

**On Each Iteration:**
1. Executes deployment using configured backend (terraform apply, bicep deploy, etc.)
2. Captures complete stdout/stderr output
3. If failure occurs:
   - Sends error output to Claude SDK AutoMode
   - AI analyzes root cause of failure
   - AI generates targeted fix (modify templates, adjust configuration)
   - Applies fix to IaC files
   - Retries deployment

**Success Criteria:**
- Deployment completes with exit code 0
- All resources successfully created/updated
- No critical errors in output

**Failure Handling:**
- Preserves all iteration history
- Never loses original IaC files (creates iteration backups)
- Generates comprehensive report even on failure
- Logs all AI decisions and fixes

## Command-Line Options

### Required Options

When using `--agent`, no additional options are required. The agent uses existing configuration from your IaC generation:

```bash
atg deploy --agent
```

### Optional Flags

#### `--max-iterations N`
Maximum number of deployment attempts (default: 20)

```bash
# Try up to 10 times before giving up
atg deploy --agent --max-iterations 10
```

**When to adjust:**
- Large deployments with complex dependencies: increase to 7-10
- Quick validation runs: decrease to 2-3
- Production deployments: keep default (5)

#### `--timeout SECONDS`
Timeout for each deployment operation in seconds (default: 6000)

```bash
# Allow 10 minutes per deployment attempt
atg deploy --agent --timeout 600
```

**When to adjust:**
- Large tenants (100+ resources): 600-900 seconds
- Small test deployments: 120-180 seconds
- Complex resource dependencies: 600+ seconds

#### `--dry-run`
Preview deployment without executing (shows what agent would do)

```bash
atg deploy --agent --dry-run
```

**Use cases:**
- Validate deployment plan before actual execution
- Check resource dependencies
- Review what the agent would attempt

#### `--format [terraform|bicep|arm]`
Specify IaC format (usually detected automatically)

```bash
atg deploy --agent --format terraform
```

**Note:** The agent auto-detects format from generated IaC, so this is rarely needed.

## Typical Usage Scenarios

### Scenario 1: First-Time Cross-Tenant Deployment

You're deploying a scanned tenant to a new Azure environment.

```bash
# Generate IaC for cross-tenant deployment
atg generate-iac --target-tenant-id <TARGET_TENANT_ID>

# Deploy with agent mode (handles missing providers, SKU issues, etc.)
atg deploy --agent
```

**Common issues the agent handles:**
- Missing Azure resource providers
- Invalid SKU/sizes in target region
- Network configuration conflicts
- Role assignment failures

**Expected iterations:** 2-4 for typical deployments

### Scenario 2: Large Tenant with Complex Dependencies

You have 200+ resources with complex networking and RBAC.

```bash
# Deploy with extended timeout and iteration limits
atg deploy --agent --max-iterations 10 --timeout 900

# The agent will:
# - Handle rate limiting errors
# - Resolve circular dependencies
# - Fix resource naming conflicts
# - Adjust parallelism as needed
```

**Expected iterations:** 3-7 depending on complexity

### Scenario 3: Development/Testing Rapid Iteration

You're testing IaC generation improvements.

```bash
# Quick validation with low iteration count
atg deploy --agent --max-iterations 3 --timeout 180

# Or just dry-run to validate
atg deploy --agent --dry-run
```

**Expected iterations:** 1-2 for clean test environments

### Scenario 4: Production Deployment with Validation

You need audit trail and comprehensive reporting.

```bash
# Standard production deployment
atg deploy --agent

# Review deployment report
cat deployment_report.md
```

**The report includes:**
- All iteration attempts
- AI-generated fixes
- Success/failure details
- Resource creation timeline
- Recommendations for future deployments

## Understanding Deployment Reports

After deployment (success or failure), the agent generates `deployment_report.md`:

```markdown
# Deployment Report - [timestamp]

## Summary
- Status: SUCCESS (or FAILURE)
- Total Iterations: 3
- Total Duration: 847 seconds
- Resources Deployed: 156

## Iteration History

### Iteration 1 (FAILED)
**Duration:** 287 seconds
**Error:** ResourceProviderNotRegistered: Microsoft.Network
**AI Analysis:** Missing resource provider registration
**Fix Applied:** Register Microsoft.Network provider
**Files Modified:**
- terraform/main.tf (added provider registration)

### Iteration 2 (FAILED)
**Duration:** 312 seconds
**Error:** InvalidVMSize: Standard_D4s_v3 not available in region
**AI Analysis:** VM SKU unavailable in eastus2
**Fix Applied:** Changed VM size to Standard_D4s_v5
**Files Modified:**
- terraform/compute.tf (line 42: size changed)

### Iteration 3 (SUCCESS)
**Duration:** 248 seconds
**Resources Created:** 156
**Warnings:** 3 role assignments skipped (cross-tenant)

## Recommendations
1. Pre-register providers: Microsoft.Network, Microsoft.Compute, Microsoft.Storage
2. Use Standard_D4s_v5 for VMs in eastus2 region
3. Identity mapping required for role assignments (see cross-tenant docs)
```

## Troubleshooting

### Agent Reaches Max Iterations

**Symptom:** Deployment fails after 5 (or configured) iterations

**Common causes:**
1. Persistent infrastructure issue (quotas, permissions)
2. Configuration issue beyond AI's ability to fix
3. External dependency failure (Azure service outage)

**Solutions:**
```bash
# Review deployment report for patterns
cat deployment_report.md

# Check if it's a quota issue
az vm list-usage --location eastus2

# Check if it's a permission issue
az account show

# Try with higher iteration limit if fixes were progressing
atg deploy --agent --max-iterations 10
```

### Deployment Times Out

**Symptom:** Each iteration times out after 6000 seconds

**Solutions:**
```bash
# Increase timeout for large deployments
atg deploy --agent --timeout 900

# Or split deployment into smaller batches (future feature)
```

### Agent Makes Incorrect Fixes

**Symptom:** AI-generated fixes don't address actual problem

**This shouldn't happen often, but if it does:**
1. Review `deployment_report.md` to see what fix was attempted
2. Check AI analysis section for reasoning
3. File issue with error output and AI decision (helps improve agent)
4. Manual fix: edit IaC files and run `atg deploy --agent` again

### Preserved Original Files

**Where are my original IaC files?**

The agent never modifies your original generated IaC. It creates iteration-specific copies:

```
iac_output/
  terraform/
    original/          # Your original generated IaC (never modified)
    iteration_1/       # First attempt
    iteration_2/       # Second attempt with fixes
    iteration_3/       # Final successful version
  deployment_report.md # Complete history
```

## Configuration Options

### Environment Variables

```bash
# Override default iteration limit
export ATG_DEPLOY_MAX_ITERATIONS=10

# Override default timeout
export ATG_DEPLOY_TIMEOUT=600

# Enable verbose agent debugging
export ATG_AGENT_DEBUG=1
```

### Via Config File

Create `.atg/deploy_config.yaml`:

```yaml
agent:
  max_iterations: 10
  timeout: 600
  retry_on_timeout: true
  preserve_iterations: true  # Keep all iteration artifacts

logging:
  agent_decisions: true
  ai_analysis: true
  verbose: false
```

## Integration with Existing Workflows

### With generate-iac

```bash
# Generate IaC with cross-tenant support
atg generate-iac --target-tenant-id <TARGET_TENANT_ID>

# Deploy with agent mode
atg deploy --agent
```

### With Manual IaC Modifications

If you've manually modified generated IaC:

```bash
# Agent respects manual changes and builds on them
atg deploy --agent

# Your manual changes are preserved in iteration_1/
# Agent fixes are applied incrementally in iteration_2+
```

### With CI/CD Pipelines

```yaml
# Azure DevOps / GitHub Actions example
- name: Deploy with Agent Mode
  run: |
    atg deploy --agent --max-iterations 7 --timeout 600
  timeout-minutes: 90

- name: Upload Deployment Report
  uses: actions/upload-artifact@v3
  with:
    name: deployment-report
    path: deployment_report.md
```

## Best Practices

### Pre-Deployment Checklist

Before running autonomous deployment:
- [ ] Authenticate with target tenant: `az login --tenant <TENANT_ID>`
- [ ] Set correct subscription: `az account set --subscription <SUB_ID>`
- [ ] Verify quotas: `az vm list-usage --location <REGION>`
- [ ] Generate IaC: `atg generate-iac [options]`
- [ ] Review dry-run: `atg deploy --agent --dry-run`

### Iteration Limit Guidelines

- **Small deployments (< 50 resources):** 3-5 iterations
- **Medium deployments (50-150 resources):** 5-7 iterations
- **Large deployments (150+ resources):** 7-10 iterations
- **Complex enterprise (300+ resources):** 10-15 iterations

### Timeout Guidelines

- **Simple resources (storage, networking):** 180-6000 seconds
- **Compute resources (VMs, AKS):** 300-600 seconds
- **Complex dependencies (RBAC, policies):** 600-900 seconds
- **Large-scale deployments:** 900+ seconds

### When NOT to Use Agent Mode

**Don't use agent mode if:**
- You need deterministic, repeatable deployments (use standard deploy)
- You're in production with strict change control (review fixes manually first)
- You want to understand each failure manually (use standard mode and fix yourself)
- You're testing IaC generation logic (agent may hide generation bugs)

**Use agent mode for:**
- Cross-tenant deployments with unknowns
- Exploratory deployments in dev/test
- Time-constrained deployments
- Learning from common deployment issues

## Advanced Topics

### Custom Fix Strategies

Future enhancement: Define custom fix strategies in config:

```yaml
agent:
  fix_strategies:
    - name: provider_registration
      priority: 1
      auto_apply: true
    - name: sku_adjustment
      priority: 2
      manual_review: true
```

### Parallel Deployments

Future enhancement: Deploy multiple resource groups in parallel with per-group agents.

### Integration with Terraform State

The agent works with Terraform state management:
- Preserves state files across iterations
- Handles state locking
- Supports remote state backends
- Auto-recovery from state corruption

## Related Documentation

- [IaC Generation Guide](../SCALE_OPERATIONS.md) - Generate deployable IaC
- [Cross-Tenant Deployment](../cross-tenant/FEATURES.md) - Deploy to different tenants
- [Deployment Troubleshooting](../DEPLOYMENT_TROUBLESHOOTING.md) - Manual troubleshooting
- [Terraform Import Blocks](../design/cross-tenant-translation/CLI_FLAGS_SUMMARY.md) - Auto-import existing resources

## Getting Help

If the agent consistently fails or produces incorrect fixes:

1. Check deployment report for patterns
2. Review AI analysis reasoning
3. Enable debug mode: `export ATG_AGENT_DEBUG=1`
4. File issue with:
   - Deployment report
   - Error output
   - AI-generated fixes
   - Expected vs actual behavior

The agent learns from feedback and improves over time.
