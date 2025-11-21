# Deployment Fix Loop Agent

## Goal

Autonomously achieve a complete, error-free Azure tenant replica deployment through iterative deployment, error assessment, and parallel bug fixing.

## Success Criteria

- [ ] Zero deployment errors (all resources deploy successfully)
- [ ] All resource types supported that can be supported
- [ ] All bugs discovered are fixed and committed
- [ ] Complete deployment report generated
- [ ] VM role assignments verified (source vs target comparison)

## Domain

Deployment automation + Bug fixing + Infrastructure-as-Code

## Complexity

Complex (5+ phases, multiple iterations, parallel execution)

## Execution Plan

### Phase 1: Generate IaC (INITIAL)
**Duration**: 2-5 minutes
**Capabilities**: neo4j-query, iac-generation, terraform-emit
**Dependencies**: None
**Parallel Safe**: No (must complete before deployment)
**Success Indicators**:
- IaC files generated successfully
- Generation report shows resource counts
- No fatal generation errors

**Actions**:
```bash
uv run atg generate-iac \
  --tenant-id cdf98c99-1fed-451f-a521-d5f5bd31dfa4 \
  --format terraform \
  --output /tmp/iac_iteration_N
```

### Phase 2: Deploy IaC (ITERATIVE)
**Duration**: 5-15 minutes
**Capabilities**: terraform-apply, azure-auth, deployment-monitoring
**Dependencies**: Phase 1
**Parallel Safe**: No (must complete before assessment)
**Success Indicators**:
- Terraform apply completes (success or failure)
- Deployment log captured
- Resource count in Azure counted

**Actions**:
```bash
uv run atg deploy \
  --iac-dir /tmp/iac_iteration_N \
  --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
  --resource-group atg-replica-rg \
  --subscription-id c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --location eastus \
  2>&1 | tee /tmp/deploy_iteration_N.log
```

### Phase 3: Assess Errors (ITERATIVE)
**Duration**: 1-3 minutes
**Capabilities**: log-analysis, error-categorization, pattern-matching
**Dependencies**: Phase 2
**Parallel Safe**: No (must analyze before fixing)
**Success Indicators**:
- All errors extracted and categorized
- Error patterns identified
- Fixable vs unfixable errors classified

**Actions**:
```bash
# Count and categorize errors
grep -c "Error:" /tmp/deploy_iteration_N.log

# Categorize by type
grep "Error:" /tmp/deploy_iteration_N.log | \
  grep -oE "Error: [^│]+" | \
  sort | uniq -c | sort -rn
```

### Phase 4: Fix Bugs in Parallel (ITERATIVE)
**Duration**: 5-20 minutes
**Capabilities**: code-editing, git-commit, parallel-execution, builder-agents
**Dependencies**: Phase 3
**Parallel Safe**: YES (multiple bugs fixed simultaneously)
**Success Indicators**:
- All identified bugs have fix attempts
- Fixes are committed to git
- Tests pass for fixed code

**Actions**:
- Launch builder agents in parallel (one per bug category)
- Each agent writes code to fix their bug type
- Commit all fixes together with comprehensive message

**Bug Categories to Fix in Parallel**:
1. Field name mismatches (e.g., application_id vs client_id)
2. Validation errors (e.g., UPN format, storage account naming)
3. Missing required fields (e.g., SKU blocks, configuration blocks)
4. Resource references (e.g., workspace IDs, VNet names)
5. Global naming conflicts (add unique suffixes)

### Phase 5: Loop Decision (ITERATIVE)
**Duration**: < 1 minute
**Capabilities**: decision-making, state-tracking
**Dependencies**: Phase 4
**Parallel Safe**: No (decision point)
**Success Indicators**:
- Clear decision: CONTINUE loop or SUCCESS
- Iteration count tracked
- Progress tracked (error count reduction)

**Decision Logic**:
```python
if error_count == 0:
    return "SUCCESS"  # Exit loop
elif iteration > MAX_ITERATIONS (20):
    return "ESCALATE"  # Max attempts reached
elif error_count >= previous_error_count:
    return "ESCALATE"  # No progress
else:
    iteration += 1
    return "CONTINUE"  # Loop back to Phase 1
```

## Constraints

- Maximum 20 iterations (prevent infinite loops)
- Each iteration must reduce error count
- All fixes must be committed before redeploying
- No manual intervention required during loop
- Must handle 6,000+ errors gracefully

## State Tracking

```python
state = {
    "iteration": 0,
    "error_history": [],  # Track error counts per iteration
    "bugs_fixed": [],     # Track fixed bugs
    "current_errors": 0,
    "resources_deployed": 0,
    "iac_dir": None,
    "deploy_log": None,
}
```

## Iteration Loop

```
Iteration 1:
  Phase 1: Generate IaC → /tmp/iac_iteration_1
  Phase 2: Deploy → Errors: 6,457
  Phase 3: Assess → Categories: SP (3033), UPN (5), Storage (41), AppGW (14)
  Phase 4: Fix (parallel) → 4 builder agents launched
  Phase 5: Decision → CONTINUE (errors > 0)

Iteration 2:
  Phase 1: Regenerate IaC → /tmp/iac_iteration_2
  Phase 2: Deploy → Errors: 892
  Phase 3: Assess → Categories: AppGW (14), Networking (45), ...
  Phase 4: Fix (parallel) → 3 builder agents launched
  Phase 5: Decision → CONTINUE (errors reduced)

...

Iteration N:
  Phase 1: Regenerate IaC → /tmp/iac_iteration_N
  Phase 2: Deploy → Errors: 0
  Phase 3: Assess → No errors found
  Phase 4: Skip (no bugs to fix)
  Phase 5: Decision → SUCCESS (zero errors)
```

## Error Recovery

**Retry Strategies**:
- Generation failure: Retry with exponential backoff (3 attempts)
- Deployment timeout: Continue monitoring in background
- Fix agent failure: Skip that bug, continue with others

**Alternative Strategies**:
- If builder agent fails: Try different prompting approach
- If error pattern unrecognized: Skip and document for manual fix
- If terraform times out: Use shorter timeout next iteration

**Escalation Criteria**:
- 20 iterations without reaching zero errors
- Error count not decreasing for 3 consecutive iterations
- Same error persisting for 5 iterations
- Critical error that cannot be auto-fixed (requires architecture change)

## Parallel Execution Opportunities

**Phase 4 (Bug Fixing)**:
- Each bug category gets dedicated builder agent
- All builders run simultaneously
- Results aggregated before commit

**Example**:
```python
# Launch 5 builders in parallel for 5 bug categories
agents = [
    Task(subagent_type="builder", prompt=fix_sp_field_name),
    Task(subagent_type="builder", prompt=fix_upn_validation),
    Task(subagent_type="builder", prompt=fix_storage_naming),
    Task(subagent_type="builder", prompt=fix_appgw_blocks),
    Task(subagent_type="builder", prompt=fix_network_refs),
]
# All execute concurrently
```

## Required Skills

1. **iac-generator**: Generate Terraform from Neo4j graph
2. **terraform-deployer**: Execute terraform apply with monitoring
3. **error-analyzer**: Parse deployment logs, categorize errors
4. **parallel-fixer**: Coordinate multiple builder agents for bug fixes
5. **git-committer**: Commit fixes with descriptive messages
6. **progress-tracker**: Monitor error count reduction across iterations

## Monitoring & Reporting

**Per-Iteration Metrics**:
- Error count (total and by category)
- Resources deployed (count)
- Duration (generation + deployment + fixes)
- Bugs fixed (count and types)

**Progress Report**:
```markdown
## Iteration N Progress

- Errors: 6,457 → 892 → 124 → 15 → 0
- Resources: 302 → 1,372 → 2,150 → 3,890 → 4,967
- Bugs Fixed: SP field (3033), UPN (5), Storage (41), AppGW (14), ...
- Duration: Iteration 1 (45min), Iteration 2 (38min), ...
```

## Final Deliverables

1. **Clean IaC**: Error-free Terraform configuration in final iteration directory
2. **Deployment Log**: Complete log of successful deployment
3. **Bug Fix Summary**: List of all bugs discovered and fixed
4. **Comparison Report**: VM role assignment verification (source vs target)
5. **GitHub Issues**: Filed for any unfixable bugs

## Auto-Mode Configuration

```yaml
max_turns: 100  # Complex multi-iteration workflow
initial_prompt: |
  You are the Deployment Fix Loop agent.

  Your goal: Achieve zero-error Azure tenant replica deployment.

  Execute this loop until success:
  1. Generate IaC from Neo4j graph
  2. Deploy to target tenant
  3. Assess errors (categorize by type)
  4. Fix bugs in parallel (use builder agents)
  5. Commit fixes and loop

  Stop when: Error count reaches zero

  Track state:
  - iteration number
  - error count history
  - bugs fixed
  - resources deployed

  Report progress every iteration.

success_criteria:
  - error_count == 0
  - all_resources_deployed
  - all_bugs_committed
  - comparison_report_generated

constraints:
  - max_iterations: 20
  - must_reduce_errors: true
  - parallel_bug_fixing: true
  - no_manual_intervention: true
```

## Launch Command

```bash
# Execute agent in auto-mode
claude-code --agent .claude/agents/deployment-fix-loop.md --auto-mode
```

Or as a slash command:

```bash
# Create slash command
echo "Execute deployment fix loop agent in auto-mode from @.claude/agents/deployment-fix-loop.md" \
  > .claude/commands/deploy-loop.md

# Run it
/deploy-loop
```

---

**Note**: This agent embodies the goal-seeking pattern by:
- Understanding high-level goal (zero-error deployment)
- Planning multi-phase execution
- Adapting to runtime errors
- Self-assessing progress
- Autonomous recovery through parallel bug fixing
