# README Section: Autonomous Deployment

> **Note:** This content should be inserted into the main README.md under the "Generate & Deploy IaC" section.

---

### Autonomous Deployment with Goal-Seeking Agent

Deploy IaC with automatic error recovery using the AI-powered goal-seeking agent. The agent iterates until deployment succeeds or maximum attempts are reached, automatically analyzing failures and applying fixes.

```bash
# Basic autonomous deployment
atg deploy --agent

# With custom iteration limit and timeout
atg deploy --agent --max-iterations 10 --timeout 600

# Generate and deploy in one workflow
atg generate-iac --target-tenant-id <TARGET_TENANT_ID>
atg deploy --agent
```

**What the agent does:**
1. Attempts deployment with configured backend (Terraform/Bicep/ARM)
2. If deployment fails:
   - Analyzes error output with Claude SDK
   - Generates targeted fix
   - Applies fix to IaC templates
   - Retries deployment
3. Continues until success or max iterations reached
4. Generates comprehensive deployment report

**Common issues automatically fixed:**
- Missing Azure resource provider registrations
- Invalid VM SKU/sizes for target region
- Network configuration conflicts
- Resource naming collisions
- API version mismatches

**Example output:**
```
Iteration 1: FAILED (45s)
  Error: Provider not registered: Microsoft.Network
  Fix: Register Microsoft.Network provider

Iteration 2: FAILED (178s)
  Error: VM size Standard_D4s_v3 not available in eastus2
  Fix: Changed to Standard_D4s_v5

Iteration 3: SUCCESS (248s)
  ✓ 156 resources deployed

Report generated: deployment_report.md
```

**Command-line options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--agent` | disabled | Enable autonomous deployment mode |
| `--max-iterations N` | 5 | Maximum deployment attempts |
| `--timeout SECONDS` | 300 | Timeout per operation (5 minutes) |
| `--dry-run` | disabled | Preview without executing |
| `--format [terraform\|bicep\|arm]` | auto-detect | IaC format |

**Documentation:**
- **Tutorial:** [Your First Autonomous Deployment](docs/quickstart/AGENT_DEPLOYMENT_TUTORIAL.md) - 15-minute guided walkthrough
- **User Guide:** [Autonomous Deployment Guide](docs/guides/AUTONOMOUS_DEPLOYMENT.md) - Complete usage documentation
- **Reference:** [Agent Deployer Reference](docs/design/AGENT_DEPLOYER_REFERENCE.md) - Technical specification
- **Index:** [Autonomous Deployment Docs](docs/AUTONOMOUS_DEPLOYMENT_INDEX.md) - Complete documentation index

**When to use agent mode:**
- Cross-tenant deployments with environmental differences
- Large deployments with complex dependencies
- Time-constrained deployments requiring minimal manual intervention
- Learning from common deployment patterns

**When NOT to use agent mode:**
- Production deployments with strict change control (review fixes manually first)
- Testing IaC generation logic (agent may mask generation issues)
- Need deterministic, bit-for-bit reproducible deployments

---
