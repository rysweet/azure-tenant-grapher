# Autonomous Deployment FAQ

Frequently asked questions about the goal-seeking deployment agent.

## General Questions

### What is the goal-seeking deployment agent?

The goal-seeking agent is an AI-powered autonomous deployment system that automatically recovers from deployment errors. Instead of failing on the first error, it analyzes the failure, generates a fix, applies it, and retries deployment. This cycle continues until deployment succeeds or maximum iterations are reached.

### Why would I use agent mode instead of standard deployment?

**Use agent mode when:**
- Deploying to a new environment with unknown configurations
- Cross-tenant deployments where SKUs, regions, or settings differ
- Time-constrained deployments where manual troubleshooting is costly
- Learning deployment patterns (the reports are educational)

**Use standard mode when:**
- Production deployments with strict change control
- Testing IaC generation logic (agent might mask bugs)
- You need deterministic, reproducible deployments
- You want to understand and fix each error manually

### How does the agent compare to manual deployment?

| Aspect | Manual Deployment | Agent Mode |
|--------|------------------|------------|
| **Time to fix errors** | 5-30 min per error | < 1 min per error |
| **Iterations needed** | Manual retry each time | Automatic until success |
| **Learning curve** | Steep (Azure knowledge) | Gentle (agent handles details) |
| **Reproducibility** | Manual steps may vary | Documented in report |
| **Control** | Full manual control | AI-guided with transparency |
| **Best for** | Production, precise control | Dev/test, rapid deployment |

### Is agent mode safe for production?

The agent mode is designed with safety in mind:
- ✓ Never modifies your original generated IaC
- ✓ Preserves complete history of all changes
- ✓ Generates detailed reports for audit trails
- ✓ All fixes are transparent and logged

**Recommendation:** Test agent mode in dev/test environments first. Review deployment reports before using in production. For production, consider:
1. Run agent in dry-run mode first
2. Review generated fixes
3. Apply manually if needed
4. Or run agent and review report before approving

## Technical Questions

### What AI model powers the agent?

The agent uses **Claude SDK AutoMode** which leverages Anthropic's Claude models for error analysis and fix generation. The specific model used depends on your Claude SDK configuration.

### What kinds of errors can the agent fix?

**Automatically fixable:**
- ✓ Missing Azure resource provider registrations
- ✓ Invalid VM SKU/sizes for target region
- ✓ Resource naming conflicts
- ✓ Network CIDR range adjustments
- ✓ API version compatibility issues
- ✓ Resource property validation errors

**Cannot automatically fix:**
- ✗ Azure quota limitations (requires portal/support)
- ✗ Authentication/permission errors (requires RBAC changes)
- ✗ Azure service outages (requires waiting)
- ✗ Architectural design issues (requires human decisions)

### How many iterations does a typical deployment need?

**Statistics from testing:**
- **Simple deployments (< 50 resources):** 1-2 iterations
- **Medium deployments (50-150 resources):** 2-4 iterations
- **Complex deployments (150+ resources):** 3-7 iterations
- **Cross-tenant with environmental differences:** 3-5 iterations

**First iteration success rate:** ~40% for cross-tenant, ~70% for same-tenant deployments.

### What happens if the agent reaches max iterations?

The agent stops attempting deployment and:
1. Generates final deployment report with all iteration history
2. Includes AI analysis of why deployment failed
3. Provides recommendations for manual fixes
4. Exits with non-zero exit code (failure)

You can then:
- Review the report to identify persistent issues
- Fix root cause manually (quotas, permissions, etc.)
- Run agent again with `atg deploy --agent`

### Can I customize the AI's behavior?

Currently, the agent uses a generic AI-driven approach without pre-defined fix strategies. This keeps the implementation simple and flexible.

**Future enhancements** (see Issue #610) will add:
- Custom fix strategy definitions
- Priority ordering for fix attempts
- Manual review gates for specific fix types

### How long does each iteration take?

**Time per iteration depends on:**
- Number of resources to deploy
- Azure region performance
- Resource dependencies (parallel vs sequential)
- Timeout configuration

**Typical timings:**
- **Small deployments (< 50 resources):** 2-5 minutes
- **Medium deployments (50-150 resources):** 5-10 minutes
- **Large deployments (150+ resources):** 10-20 minutes

**Total deployment time** = iterations × time-per-iteration

### What gets preserved in iteration artifacts?

Each iteration creates a snapshot directory containing:
```
iteration_N/
  ├── *.tf (or *.bicep)    # IaC files with applied fixes
  ├── terraform.tfstate     # State file (Terraform)
  ├── deployment.log        # Full stdout/stderr
  ├── error_analysis.json   # AI analysis of errors
  └── fix_instructions.json # AI-generated fix details
```

**Artifacts are useful for:**
- Debugging deployment failures
- Understanding what fixes were applied
- Auditing changes for compliance
- Learning from AI decisions

## Operational Questions

### Can I resume a failed deployment?

Yes, with Terraform deployments. The agent preserves state files, so resources successfully deployed in previous iterations won't be recreated:

```bash
# Failed after iteration 3
# Resume by running agent again
cd my-deployment
atg deploy --agent

# Terraform will:
# - Skip already-deployed resources
# - Continue from where it left off
# - Apply any new fixes
```

For Bicep/ARM, idempotency depends on Azure's deployment API.

### How do I debug when the agent makes wrong fixes?

1. **Review deployment report:**
   ```bash
   cat deployment_report.md
   ```
   Look at "AI Analysis" and "Fix Applied" sections

2. **Enable debug mode:**
   ```bash
   export ATG_AGENT_DEBUG=1
   atg deploy --agent
   ```
   This logs full AI prompts and responses

3. **Examine iteration artifacts:**
   ```bash
   # Compare original vs fixed IaC
   diff -u original/main.tf iteration_2/main.tf
   ```

4. **File issue with:**
   - Deployment report
   - Error output
   - AI-generated fix
   - What the correct fix should be

This feedback helps improve the agent over time.

### Can I use agent mode with CI/CD pipelines?

Yes, the agent is designed for automation:

```yaml
# GitHub Actions example
- name: Deploy Infrastructure
  run: |
    atg deploy --agent --max-iterations 7 --timeout 600
  timeout-minutes: 90

- name: Check Deployment Status
  run: |
    if [ $? -eq 0 ]; then
      echo "Deployment succeeded"
    else
      echo "Deployment failed - review report"
      cat deployment_report.md
      exit 1
    fi

- name: Archive Deployment Report
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: deployment-report
    path: deployment_report.md
```

**Best practices:**
- Set appropriate timeouts for pipeline execution
- Archive deployment reports as artifacts
- Use higher iteration limits (7-10) for complex deployments
- Consider approval gates before actual deployment

### How do I handle authentication for long deployments?

**Problem:** Azure CLI tokens expire after ~1 hour. Long deployments with multiple iterations might exceed this.

**Solutions:**

1. **Use service principal authentication (recommended):**
   ```bash
   az login --service-principal \
     -u <APP_ID> \
     -p <PASSWORD> \
     --tenant <TENANT_ID>

   atg deploy --agent
   ```

2. **Use managed identity (in Azure VMs):**
   ```bash
   az login --identity
   atg deploy --agent
   ```

3. **Pre-authenticate and monitor:**
   ```bash
   az login --tenant <TENANT_ID>
   atg deploy --agent --timeout 900
   # Use shorter timeouts to detect token expiry faster
   ```

### What's the cost of running the agent?

**Azure costs:**
- Standard deployment costs (resource creation)
- No additional Azure charges for agent mode

**AI API costs (Claude SDK):**
- ~1-5 API calls per iteration
- Each call analyzes error output (~1-5KB)
- Typical cost: $0.01-0.10 per iteration
- **Total deployment cost:** $0.05-0.50 for typical deployments

**Cost vs benefit:**
- Manual troubleshooting: 15-60 minutes per error
- Agent mode: < 1 minute per error
- Time savings: 2-10 hours for complex deployments

## Configuration Questions

### How do I change the default iteration limit?

**Command-line:**
```bash
atg deploy --agent --max-iterations 10
```

**Environment variable:**
```bash
export ATG_DEPLOY_MAX_ITERATIONS=10
atg deploy --agent
```

**Config file (future):**
```yaml
# .atg/deploy_config.yaml
agent:
  max_iterations: 10
```

### How do I adjust timeout for slow deployments?

**Command-line:**
```bash
atg deploy --agent --timeout 900  # 15 minutes per iteration
```

**Environment variable:**
```bash
export ATG_DEPLOY_TIMEOUT=900
atg deploy --agent
```

**Guidelines:**
- Small deployments: 180-300 seconds
- Medium deployments: 300-600 seconds
- Large deployments: 600-900 seconds
- Very large/complex: 900+ seconds

### Can I disable specific types of fixes?

Not currently supported. The agent uses a generic AI-driven approach that analyzes each error contextually.

**Future enhancement** (Issue #610) will add fix strategy configuration:
```yaml
agent:
  fix_strategies:
    - name: provider_registration
      enabled: true
      auto_apply: true
    - name: sku_adjustment
      enabled: true
      manual_review: true
    - name: network_changes
      enabled: false
```

## Comparison Questions

### Agent mode vs Terraform `-auto-approve`?

**`terraform apply -auto-approve`:**
- Applies deployment without confirmation
- Fails on first error
- Requires manual fix and retry
- Standard Terraform behavior

**Agent mode:**
- Uses `-auto-approve` internally
- Automatically fixes and retries errors
- AI-powered error analysis
- Continues until success or max iterations
- Generates comprehensive reports

**Think of it as:** Agent mode = Terraform with automatic error recovery

### Agent mode vs Azure DevOps retry logic?

**Azure DevOps retry logic:**
- Retries same deployment on transient failures
- No modification of deployment templates
- Simple retry with exponential backoff

**Agent mode:**
- Analyzes errors and modifies templates
- Generates targeted fixes for specific issues
- Retries with corrections applied
- Learning-based approach

**Agent mode is more sophisticated** - it adapts the deployment to fix issues, not just retry the same thing.

### Agent mode vs manual scripting with error handling?

**Manual scripting:**
```bash
# Custom bash script
terraform apply -auto-approve || handle_error_manually
```

**Agent mode:**
- AI analyzes error contextually
- Generates fixes you might not think of
- Comprehensive reporting
- Works across multiple IaC formats
- Maintained and improved over time

**Agent mode saves you from writing custom error handling** for every deployment scenario.

## Troubleshooting Questions

### Why does the agent keep trying the same fix?

**Possible causes:**
1. **AI misunderstands error:** Enable debug mode to see AI reasoning
2. **Fix is correct but insufficient:** Error requires multiple fixes
3. **Persistent infrastructure issue:** Beyond agent's ability to fix

**Solutions:**
1. Review deployment report for patterns
2. Check if iteration count is increasing (agent is making progress)
3. Look at last few iterations - are errors changing?
4. If stuck on same error: stop agent, fix manually, retry

### The agent makes unnecessary changes to my IaC. Why?

**Common reasons:**
1. **Over-optimization:** AI sometimes suggests improvements beyond the error fix
2. **Resource dependencies:** AI adjusts related resources to fix primary issue
3. **Best practices:** AI applies Azure best practices while fixing

**Solutions:**
1. Review deployment report to understand reasoning
2. Check if changes are actually needed for deployment success
3. If changes are unwanted: file issue with specific example
4. Revert to original IaC and deploy with standard mode

### How do I cancel a running agent deployment?

**Interrupt with Ctrl+C:**
```bash
# Press Ctrl+C once
^C
Stopping deployment gracefully...
Finalizing current iteration...
Generating deployment report...
```

The agent will:
- Complete the current iteration (don't interrupt mid-deployment)
- Generate report with progress so far
- Exit cleanly

**Force stop (not recommended):**
```bash
# Press Ctrl+C twice
^C^C
Forcing immediate stop...
```

This might leave Terraform state in inconsistent state.

### Where do I find help if something goes wrong?

1. **Check deployment report:**
   ```bash
   cat deployment_report.md
   ```

2. **Review troubleshooting guide:**
   - [Deployment Troubleshooting](../DEPLOYMENT_TROUBLESHOOTING.md)

3. **Enable debug mode:**
   ```bash
   export ATG_AGENT_DEBUG=1
   atg deploy --agent 2>&1 | tee debug.log
   ```

4. **File issue with:**
   - Deployment report
   - Debug log (if enabled)
   - Error output
   - Expected vs actual behavior

5. **Check related documentation:**
   - [Autonomous Deployment Guide](AUTONOMOUS_DEPLOYMENT.md)
   - [Agent Deployer Reference](../design/AGENT_DEPLOYER_REFERENCE.md)

## Feature Requests

### Can the agent deploy to multiple regions simultaneously?

Not currently. Each `atg deploy --agent` call handles one deployment.

**Workaround:**
```bash
# Deploy to multiple regions in sequence
for region in eastus westus centralus; do
  atg generate-iac --location $region --output ./deploy-$region
  atg deploy --agent --path ./deploy-$region
done
```

**Future enhancement:** Parallel regional deployments with per-region agents.

### Can the agent learn from previous deployments?

Not currently. Each deployment is independent.

**Future enhancement** (Issue #610):
- Fix caching: Reuse successful fixes
- Pattern learning: Improve fix quality over time
- History analysis: Suggest preemptive fixes based on past deployments

### Can I preview what the agent would do without deploying?

Yes, use dry-run mode:

```bash
atg deploy --agent --dry-run

# Shows:
# - What would be deployed
# - Estimated iteration count
# - Potential issues detected
# - No actual deployment occurs
```

### Will agent mode support other IaC formats?

The agent currently supports:
- ✓ Terraform
- ✓ Bicep
- ✓ ARM templates

**Future formats:**
- Pulumi (if requested)
- CDK for Terraform (if requested)
- Custom IaC formats via plugin system

File an issue if you need support for a specific format.

## Still Have Questions?

If your question isn't answered here:

1. Check the [Autonomous Deployment Guide](AUTONOMOUS_DEPLOYMENT.md)
2. Review the [Tutorial](../quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)
3. Read the [Technical Reference](../design/AGENT_DEPLOYER_REFERENCE.md)
4. File an issue with your question (we'll update this FAQ)

---

**Last Updated:** 2025-12-18
**Maintainers:** Azure Tenant Grapher team
