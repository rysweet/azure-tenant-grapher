# ATG Iteration Workflow Improvements

**Status**: Design Proposal
**Date**: 2025-10-17
**Context**: OBJECTIVE.md iteration workflow (demos/iteration178-182+)

## Problem Statement

The current iteration workflow requires many ad-hoc bash commands and manual orchestration:
- Manual terraform validation parsing
- Ad-hoc Python scripts for Neo4j monitoring
- Manual fidelity calculations
- Manual iteration numbering
- Manual PR creation and CI monitoring
- No built-in deployment orchestration
- No multi-tenant Azure authentication management

**User Feedback**: "I see you keep running a lot of bash commands - I want you to use the subagents and tools we have available to think about whether there are agents or tools or features of atg that should be added in order to make all of this easier and more repeatable"

## Proposed ATG Commands

### 1. `atg iterate` - Iteration Workflow Orchestrator

**Purpose**: Automate the full generate → validate → analyze → fix cycle.

```bash
# Basic usage - auto-increments from last iteration
uv run atg iterate --subscription-id <SUB_ID>

# Specify iteration number
uv run atg iterate --subscription-id <SUB_ID> --iteration 183

# Continue until N consecutive passes
uv run atg iterate --subscription-id <SUB_ID> --until-stable --threshold 3

# Full objective workflow
uv run atg iterate --subscription-id <SUB_ID> \
  --until-stable \
  --auto-deploy \
  --target-subscription <TARGET_SUB_ID> \
  --min-fidelity 95
```

**Features**:
- Auto-increments iteration number from `demos/iterationN/`
- Generates IaC with proper naming (ITERATION###_ prefix)
- Runs terraform validate and parses JSON output
- Tracks consecutive passes
- Stops when threshold met (e.g., 3 consecutive passes)
- Optionally auto-deploys when stable
- Integrates with fidelity tracking

**Implementation**:
- Handler: `src/cli_commands.py:iterate_command_handler()`
- Core logic: `src/iteration_manager.py:IterationManager`
- State tracking: `demos/iteration_state.json`

### 2. `atg deploy` - Deployment Orchestrator

**Purpose**: Handle terraform plan/apply with proper authentication and error recovery.

```bash
# Deploy iteration to target
uv run atg deploy --iteration 182 \
  --target-subscription <TARGET_SUB_ID> \
  --target-tenant-id <TARGET_TENANT_ID>

# Dry-run (plan only)
uv run atg deploy --iteration 182 \
  --target-subscription <TARGET_SUB_ID> \
  --dry-run

# With automatic authentication
uv run atg deploy --iteration 182 \
  --target-subscription <TARGET_SUB_ID> \
  --auto-authenticate
```

**Features**:
- Multi-tenant Azure authentication management
- Automatic `az login` and subscription selection
- Terraform init → plan → apply orchestration
- Error recovery (retry on transient failures)
- Post-deployment validation
- Rollback capability on failure
- Progress tracking and logging

**Implementation**:
- Handler: `src/cli_commands.py:deploy_command_handler()`
- Core logic: `src/deployment_manager.py:DeploymentManager`
- Auth handler: `src/azure_auth_manager.py:AzureAuthManager`

### 3. `atg fidelity` - Fidelity Calculator and Tracker

**Purpose**: Calculate and track replication fidelity between source and target.

```bash
# Calculate current fidelity
uv run atg fidelity \
  --source-subscription <SOURCE_SUB_ID> \
  --target-subscription <TARGET_SUB_ID>

# Track fidelity over iterations
uv run atg fidelity \
  --source-subscription <SOURCE_SUB_ID> \
  --target-subscription <TARGET_SUB_ID> \
  --track \
  --output fidelity_history.json

# Check if objective achieved
uv run atg fidelity \
  --source-subscription <SOURCE_SUB_ID> \
  --target-subscription <TARGET_SUB_ID> \
  --check-objective demos/OBJECTIVE.md
```

**Features**:
- Resource count comparison
- Resource type distribution analysis
- Relationship fidelity (edges)
- Missing resource identification
- Fidelity trending over time
- OBJECTIVE.md compliance checking
- Export to JSON/CSV for analysis

**Output Example**:
```json
{
  "timestamp": "2025-10-17T01:30:00Z",
  "source": {
    "subscription_id": "9b00bc5e-9abc-45de-9958-02a9d9277b16",
    "resources": 1674,
    "relationships": 5614,
    "resource_groups": 182,
    "resource_types": 94
  },
  "target": {
    "subscription_id": "c190c55a-9ab2-4b1e-92c4-cc8b1a032285",
    "resources": 516,
    "relationships": 1823,
    "resource_groups": 58,
    "resource_types": 42
  },
  "fidelity": {
    "overall": 30.8,
    "by_type": {
      "Microsoft.Compute/virtualMachines": 85.2,
      "Microsoft.Network/virtualNetworks": 92.1,
      "Microsoft.Storage/storageAccounts": 67.3
    },
    "missing_resources": 1158,
    "objective_met": false,
    "target_fidelity": 95.0
  }
}
```

**Implementation**:
- Handler: `src/cli_commands.py:fidelity_command_handler()`
- Core logic: `src/fidelity_calculator.py:FidelityCalculator`
- Tracking: `demos/fidelity_history.jsonl`

### 4. `atg compare` - Subscription/Iteration Comparison

**Purpose**: Compare resources between subscriptions or iterations.

```bash
# Compare two subscriptions
uv run atg compare \
  --source <SOURCE_SUB_ID> \
  --target <TARGET_SUB_ID> \
  --output comparison_report.md

# Compare iterations
uv run atg compare-iterations \
  --iterations 180,181,182 \
  --output iteration_comparison.md

# Show what's missing in target
uv run atg compare \
  --source <SOURCE_SUB_ID> \
  --target <TARGET_SUB_ID> \
  --show-missing \
  --format table
```

**Features**:
- Resource-level diff
- Type distribution comparison
- Missing/extra resources
- Configuration differences
- Visual charts (ASCII or HTML)
- Export formats: table, JSON, markdown

**Implementation**:
- Handler: `src/cli_commands.py:compare_command_handler()`
- Core logic: `src/comparison_engine.py:ComparisonEngine`

### 5. Enhanced `atg monitor` (Already Implemented)

**Current Status**: ✅ Implemented in PR #350
**Additional Features Needed**:
- Integration with fidelity tracking
- Notification on stabilization
- Export to Prometheus metrics
- Historical trending

## Proposed Subagents

### 1. Deployment Orchestrator Agent

**Purpose**: Handle full deploy → scan → assess workflow.

**Capabilities**:
- Authenticate to target tenant
- Execute terraform plan/apply
- Monitor deployment progress
- Handle errors and retry logic
- Post-deployment scanning
- Fidelity assessment
- Generate next iteration if needed

**Agent Type**: `deployment-orchestrator`
**Tools Available**: Bash, Read, Write, Grep, Glob
**Invocation**:
```python
Task(
    subagent_type="deployment-orchestrator",
    description="Deploy iteration 182 to target",
    prompt="""
    Deploy iteration 182 to target subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285.

    Steps:
    1. Authenticate to target tenant
    2. Run terraform plan
    3. Review plan for issues
    4. Execute terraform apply
    5. Scan target subscription
    6. Calculate fidelity
    7. Report back with fidelity score
    """
)
```

### 2. CI/PR Management Agent

**Purpose**: Monitor PRs, investigate CI failures, auto-merge when ready.

**Capabilities**:
- Monitor PR CI status
- Investigate test failures
- Apply fixes to feature branches
- Re-run failed checks
- Auto-merge when CI passes
- Notify on completion

**Agent Type**: `ci-pr-manager`
**Tools Available**: Bash, Read, Write, Grep, Glob
**Invocation**:
```python
Task(
    subagent_type="ci-pr-manager",
    description="Monitor PRs #349 and #350",
    prompt="""
    Monitor and manage PRs #349 and #350:

    1. Check CI status for both PRs
    2. If failing, investigate logs
    3. Apply fixes to feature branches
    4. Push changes and wait for CI
    5. Auto-merge when both PRs pass
    6. Report final status
    """
)
```

### 3. Iteration Analysis Agent

**Purpose**: Deep analysis of iteration results and recommendations.

**Capabilities**:
- Parse validation errors
- Identify error patterns
- Recommend fixes
- Generate fix code
- Track error trends across iterations
- Predict convergence

**Agent Type**: `iteration-analyzer`
**Tools Available**: Read, Grep, Glob
**Invocation**:
```python
Task(
    subagent_type="iteration-analyzer",
    description="Analyze iteration 178-182",
    prompt="""
    Analyze iterations 178-182:

    1. Parse all validation results
    2. Identify error patterns
    3. Track how errors were fixed
    4. Generate lessons learned
    5. Recommend improvements to terraform_emitter.py
    6. Create report in docs/ITERATION_ANALYSIS.md
    """
)
```

## Implementation Priority

### Phase 1: Core Commands (Week 1)
1. ✅ `atg monitor` (Already done - PR #350)
2. `atg fidelity` - High value, frequently needed
3. `atg compare` - Useful for analysis

### Phase 2: Workflow Automation (Week 2)
4. `atg iterate` - Automates manual iteration process
5. `atg deploy` - Critical for deployment workflow

### Phase 3: Agents (Week 3)
6. Deployment orchestrator agent
7. CI/PR management agent
8. Iteration analysis agent

## File Structure

```
src/
  cli_commands.py                    # All command handlers
  iteration_manager.py               # NEW - Iteration workflow
  deployment_manager.py              # NEW - Deployment orchestration
  fidelity_calculator.py             # NEW - Fidelity calculations
  comparison_engine.py               # NEW - Comparison logic
  azure_auth_manager.py              # NEW - Multi-tenant auth
  agents/
    deployment_orchestrator_agent.py # NEW - Agent
    ci_pr_manager_agent.py          # NEW - Agent
    iteration_analyzer_agent.py     # NEW - Agent

demos/
  iteration_state.json               # NEW - Tracks iteration state
  fidelity_history.jsonl            # NEW - Time-series fidelity data
  iteration_comparison.md           # Generated by compare command

docs/
  ATG_ITERATION_WORKFLOW.md         # NEW - User documentation
  FIDELITY_TRACKING.md              # NEW - Fidelity docs
```

## Success Metrics

### Commands Success
- All commands have comprehensive tests
- Commands integrate with existing CLI framework
- Documentation complete in docs/
- Usage examples in README.md

### Workflow Improvement
- Reduce manual bash commands by 80%
- Full iteration cycle runs with single command
- Automatic deployment with fidelity tracking
- No manual intervention needed for CI/PRs

### User Experience
- Clear, actionable output
- Progress indicators for long operations
- Error messages with fix suggestions
- Integration with existing atg CLI patterns

## Next Steps

1. **Immediate** (Today):
   - Get user approval for design
   - Create GitHub issues for each command
   - Start with `atg fidelity` implementation

2. **Short-term** (This Week):
   - Implement Phase 1 commands
   - Create tests for new commands
   - Update documentation

3. **Medium-term** (Next Week):
   - Implement Phase 2 workflow automation
   - Add deployment orchestration
   - Create subagents

## References

- OBJECTIVE.md - Defines success criteria
- MONITOR_COMMAND.md - Pattern for new commands
- DEFAULT_WORKFLOW.md - Code contribution process
- demos/iteration180-182/ - Current iteration state
