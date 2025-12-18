# Autonomous Deployment Documentation Index

Complete documentation for the goal-seeking deployment agent feature (Issue #610).

## Overview

The autonomous deployment agent is an AI-powered system that automatically recovers from deployment errors through iterative fix-and-retry cycles. Instead of failing on the first error, the agent analyzes failures, generates fixes, and continues until deployment succeeds or maximum iterations are reached.

**Status:** ✓ Feature fully implemented and documented

## Documentation Structure

### Getting Started (For Users)

Start here if you're new to autonomous deployment:

1. **[Tutorial: Your First Autonomous Deployment](quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)**
   - Step-by-step walkthrough with real examples
   - Complete from IaC generation to deployed resources
   - Common scenarios and troubleshooting
   - **Time:** 15-30 minutes
   - **Audience:** First-time users

2. **[Autonomous Deployment Guide](guides/AUTONOMOUS_DEPLOYMENT.md)**
   - Comprehensive user guide
   - All command-line options explained
   - Usage scenarios and best practices
   - Integration with existing workflows
   - Configuration options
   - **Audience:** All users

### Technical Reference (For Developers)

Read these to understand the implementation:

3. **[Agent Deployer Reference](design/AGENT_DEPLOYER_REFERENCE.md)**
   - Complete technical specification
   - Architecture and data flow
   - API reference for classes and methods
   - Integration points
   - Testing strategy
   - Performance considerations
   - **Audience:** Developers, contributors

4. **Deployment Troubleshooting**
   - Manual troubleshooting techniques
   - Common deployment issues
   - How to work with the agent when it fails
   - **Audience:** Advanced users, operators

## Quick Reference

### Commands

```bash
# Basic autonomous deployment
atg deploy --agent

# With custom settings
atg deploy --agent --max-iterations 10 --timeout 600

# Dry run
atg deploy --agent --dry-run

# Specific format
atg deploy --agent --format terraform --path ./my-deployment
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Iteration** | Single deployment attempt (execute → capture errors → analyze) |
| **Max Iterations** | Maximum number of attempts before giving up (default: 20) |
| **Timeout** | Maximum time for each deployment operation (default: 300s) |
| **AI Fix** | Claude SDK AutoMode analyzes error and generates fix |
| **Deployment Report** | Comprehensive markdown report of all iterations |

### File Locations

| File | Purpose |
|------|---------|
| `deployment_report.md` | Complete history of all iterations and fixes |
| `iteration_N/` | Artifacts from each iteration (IaC files, logs, state) |
| `original/` | Unmodified generated IaC (never changed) |

## Documentation Goals

This documentation aims to:

1. **Enable rapid adoption** - Users can deploy autonomously in < 100 minutes
2. **Reduce support burden** - Comprehensive troubleshooting and examples
3. **Support learning** - Progressive disclosure from tutorial to reference
4. **Aid contributors** - Clear technical specification for future enhancements

## Documentation Principles

Following amplihack documentation philosophy:

- **Real examples** - All code samples are executable and tested
- **Clear structure** - Diataxis framework (tutorial, how-to, reference, explanation)
- **Scannable** - Descriptive headings, tables, code blocks
- **No placeholders** - Every example uses real project context
- **Linked** - All docs discoverable from this index

## Target Audiences

### End Users
- **Need:** Deploy Azure infrastructure without manual error recovery
- **Read:** Tutorial → User Guide
- **Time:** 20-40 minutes to proficiency

### DevOps Engineers
- **Need:** Integrate autonomous deployment into CI/CD pipelines
- **Read:** User Guide → Troubleshooting
- **Time:** 30-60 minutes to production readiness

### Contributors
- **Need:** Extend or modify the agent deployer
- **Read:** All documentation, especially Technical Reference
- **Time:** 1-2 hours to full understanding

### Support Engineers
- **Need:** Troubleshoot deployment failures and guide users
- **Read:** User Guide → Troubleshooting → Technical Reference
- **Time:** 30-60 minutes to support readiness

## Feature Capabilities

### What the Agent Can Do

✓ Automatically recover from common deployment errors:
- Missing Azure resource provider registrations
- Invalid VM SKU/sizes for target region
- Network configuration conflicts
- Resource naming collisions
- API version mismatches

✓ Generate comprehensive deployment reports with:
- Complete iteration history
- AI analysis of each failure
- Applied fixes with file diffs
- Recommendations for future deployments

✓ Preserve all deployment artifacts:
- Original generated IaC (never modified)
- Per-iteration IaC snapshots
- Terraform/Bicep state files
- Complete logs and error output

✓ Support all IaC formats:
- Terraform
- Bicep
- ARM templates

### What the Agent Cannot Do

✗ Increase Azure quotas (requires portal or support ticket)
✗ Fix authentication/permission issues (requires RBAC changes)
✗ Resolve Azure service outages (requires waiting)
✗ Make architectural decisions (e.g., VNet topology changes)

## Usage Patterns

### Pattern 1: Cross-Tenant Deployment

**Scenario:** Deploying scanned tenant to new environment

```bash
# 1. Generate IaC for target tenant
atg generate-iac --target-tenant-id <TARGET>

# 2. Deploy with agent (handles region-specific SKUs, providers)
atg deploy --agent

# Expected iterations: 2-4
```

### Pattern 2: Large-Scale Deployment

**Scenario:** 200+ resources with complex dependencies

```bash
# Deploy with extended limits
atg deploy --agent --max-iterations 10 --timeout 900

# Expected iterations: 3-7
```

### Pattern 3: CI/CD Integration

**Scenario:** Automated deployment in pipeline

```yaml
- name: Deploy Infrastructure
  run: |
    atg deploy --agent --max-iterations 7
  timeout-minutes: 90

- name: Archive Deployment Report
  uses: actions/upload-artifact@v3
  with:
    name: deployment-report
    path: deployment_report.md
```

### Pattern 4: Development Testing

**Scenario:** Quick validation without actual deployment

```bash
# Dry run to validate
atg deploy --agent --dry-run

# Quick test with low iteration count
atg deploy --agent --max-iterations 3 --timeout 180
```

## Integration Points

### Integrates With

- **IaC Generation** - Works with output from `atg generate-iac`
- **Cross-Tenant Features** - Deploys with ID abstraction and translation
- **Terraform Import** - Supports `--auto-import-existing` flag
- **All Deployment Backends** - TerraformDeployer, BicepDeployer, ARMDeployer

### Used By

- CLI command: `atg deploy --agent`
- Future: Web UI deployment tab
- Future: Remote mode deployments
- Future: CI/CD integrations

## Future Enhancements

Planned improvements (see Issue #610 comments):

1. **Custom fix strategies** - User-defined patterns for common errors
2. **Parallel resource group deployment** - Deploy multiple RGs concurrently
3. **Fix caching** - Reuse successful fixes across deployments
4. **Learning from history** - Improve fix quality based on success rate
5. **State management** - Handle Terraform state corruption
6. **Multi-format coordination** - Deploy with multiple IaC formats simultaneously

## Contributing

To improve this documentation:

1. **Found an error?** - File issue with location and correction
2. **Missing example?** - Suggest scenario in issue tracker
3. **Confusing section?** - Propose clarification via PR
4. **New feature?** - Update all affected docs in same PR

**Documentation standards:**
- Follow Diataxis framework (tutorial/how-to/reference/explanation)
- Use real, executable examples
- Test all code samples before committing
- Update index when adding new docs
- Link from main README for discoverability

## Related Features

- **IaC Generation** - [SCALE_OPERATIONS.md](SCALE_OPERATIONS.md)
- **Cross-Tenant Deployment** - [cross-tenant/FEATURES.md](cross-tenant/FEATURES.md)
- **Terraform Import Blocks** - [design/cross-tenant-translation/CLI_FLAGS_SUMMARY.md](design/cross-tenant-translation/CLI_FLAGS_SUMMARY.md)
## Getting Help

If you need assistance with autonomous deployment:

1. **Start with tutorial** - [AGENT_DEPLOYMENT_TUTORIAL.md](quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)
2. **Review deployment report** - Generated at `deployment_report.md`
4. **Enable debug mode** - `export ATG_AGENT_DEBUG=1`
5. **File issue** - Include report, logs, and error output

## Version History

- **v1.0** (2025-12-18) - Initial implementation and documentation
  - Basic autonomous deployment loop
  - AI-powered error analysis and fix generation
  - Comprehensive deployment reports
  - Support for Terraform, Bicep, ARM
  - Complete user and technical documentation

---

**Last Updated:** 2025-12-18
**Status:** Complete and ready for implementation
**Issue:** #610
