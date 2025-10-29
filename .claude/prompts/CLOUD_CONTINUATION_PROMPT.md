# Azure Tenant Grapher - Cloud Continuation Prompt

**CRITICAL: READ FIRST** → `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/demos/START_HERE.md`

## Mission

Continue autonomous Azure tenant replication from source tenant (DefenderATEVET17) to target tenant (DefenderATEVET12) until 100% fidelity is achieved per the objective defined in `/demos/OBJECTIVE.md`.

## Current State

- **Iteration**: 207 (last deployed iteration)
- **Resource Coverage**: ~54% (57 of 105+ resources from source tenant)
- **Neo4j Database**: 991 nodes, 1876 edges
- **Status**: Iteration 207 deployment completed, ready to scan target and continue

## Your Directive

**You MUST maintain a continuous session and never stop until the objective is achieved.**

### Core Loop (Do Not Stop Until 100% Fidelity)

```
WHILE objective NOT achieved:
    1. Evaluate current state (Neo4j comparison, terraform state, scan results)
    2. Identify gaps (missing resources, failed deployments, data plane gaps)
    3. Spawn parallel fix workstreams using subagents
    4. Generate next iteration with fixes
    5. Validate iteration
    6. Deploy iteration
    7. Monitor deployment (KEEP SESSION ALIVE)
    8. Scan target tenant into Neo4j
    9. Send status update via imessR
    REPEAT
```

### Critical Requirements

1. **Never Stop**: Your session must remain active. Use background monitoring loops with periodic checks.
2. **Fix in Parallel**: Spawn subagents to fix identified gaps while iterations deploy
3. **Use ATG Commands**: Don't run terraform directly - enhance ATG to abstract terraform operations
4. **AI Evaluation**: Use `copilot --allow-all-tools -p "<prompt>"` to spawn evaluation agents
5. **Regular Updates**: Send iMessage updates at each decision point

## Key Files & Tools

### Essential Documentation (Read These)
- `/demos/START_HERE.md` - Quick start guide
- `/demos/CLOUD_HANDOFF_2025-10-15.md` - Complete handoff with all context
- `/demos/CLOUD_AGENT_RUNBOOK.md` - Step-by-step operational procedures
- `/demos/OBJECTIVE.md` - Success criteria and evaluation framework
- `/demos/DOCUMENTATION_INDEX.md` - Navigation guide

### Tools Built This Session
- `/demos/cross_tenant_cli/continuous_iteration_engine.py` - Main orchestration engine
- `/demos/cross_tenant_cli/evaluate_objective.py` - Objective evaluation script
- `/tmp/continuous_monitor.py` - Background monitoring loop

### Agent Framework
- Agents: `.claude/agents/*/*.md`
- Workflows: `.claude/workflows/DEFAULT_WORKFLOW.md`
- Spawn with: `copilot --allow-all-tools -p "<prompt>"`
- Use prompt-writer agent to craft better prompts

## Environment Setup

### Azure Credentials (Already Configured)
```bash
# Source tenant (DefenderATEVET17) - for scanning
export ARM_SUBSCRIPTION_ID_SOURCE=<from .env>
export ARM_TENANT_ID_SOURCE=<from .env>

# Target tenant (DefenderATEVET12) - for deployment
export ARM_SUBSCRIPTION_ID=<from .env>
export ARM_TENANT_ID=<from .env>
export ARM_CLIENT_ID=<from .env>
export ARM_CLIENT_SECRET=<from .env>
```

### Neo4j Database
- URI: bolt://localhost:7688
- Password: from .env (NEO4J_PASSWORD)

## Next Steps (Execute Immediately)

### 1. Resume Autonomous Operation
```bash
# Check current state
cd /Users/ryan/src/msec/atg-0723/azure-tenant-grapher
git pull  # Get latest handoff docs

# Scan target tenant (iteration 207 was just deployed)
uv run atg discover \
  --subscription-id $ARM_SUBSCRIPTION_ID \
  --tenant-id $ARM_TENANT_ID \
  --output demos/iteration207_scan

# Evaluate objective
uv run python demos/cross_tenant_cli/evaluate_objective.py

# Continue autonomous loop
uv run python demos/cross_tenant_cli/continuous_iteration_engine.py
```

### 2. Fix Known Gaps in Parallel

While iteration engine runs, spawn these fix workstreams:

**Gap 1: Missing Resource Types (Priority 1)**
- Microsoft.Web/serverFarms
- Microsoft.Compute/disks
- Microsoft.Compute/virtualMachines/extensions
- Microsoft.OperationalInsights/workspaces
- microsoft.insights/components

**Gap 2: Entra ID Replication (Priority 1)**
- Users, Groups, Service Principals
- RBAC role assignments
- App registrations

**Gap 3: Data Plane Plugins (Priority 2)**
- Key Vault secrets/keys/certificates
- Storage Account blobs/tables/queues
- VM configurations (boot diagnostics, extensions)

**Gap 4: Deployment Validation (Priority 1)**
- Fix permission issues (Microsoft.Insights/dataCollectionRules)
- Enhance validation script
- Add retry logic for transient failures

### 3. Monitoring Pattern

```python
# Keep session alive with active monitoring
while not objective_achieved():
    status = check_deployment_status()
    if status.has_issues():
        spawn_fix_agents(status.issues)

    send_imessage_update(status)
    time.sleep(60)  # Check every minute

    if deployment_complete():
        scan_target_tenant()
        evaluate_objective()
        if not objective_achieved():
            generate_next_iteration()
```

## Common Pitfalls (Avoid These)

1. ❌ **Stopping session** - This kills all background processes
2. ❌ **Running iterations in parallel** - Fix problems first, then test
3. ❌ **Using terraform directly** - Enhance ATG commands instead
4. ❌ **Skipping validation** - Always validate before deploying
5. ❌ **Not spawning fix agents** - Work on multiple gaps in parallel

## Success Criteria

Objective is achieved when:
1. ✅ All source tenant resources replicated (100% coverage)
2. ✅ Neo4j graph comparison shows matching structure
3. ✅ All terraform deployments succeed
4. ✅ All validation checks pass
5. ✅ Data plane plugins replicate critical data
6. ✅ Entra ID objects replicated
7. ✅ AI agent evaluation confirms fidelity

## Philosophy (Zero-BS Policy)

- No placeholders or TODOs in code
- Fail loudly with clear error messages
- Test everything before committing
- Measure progress with metrics
- Fix root causes, not symptoms
- Ruthlessly simple solutions
- Build tools, not one-off scripts

## Immediate Action

**START HERE**: Read `/demos/START_HERE.md` then execute the Next Steps above.

**DO NOT STOP** until you receive explicit instruction or the objective is 100% achieved.

---

**Last Updated**: 2025-10-15 20:34 UTC
**Iteration**: 207
**Commit**: e0c49df
**Status**: Ready for cloud continuation
