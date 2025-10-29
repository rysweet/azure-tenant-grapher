# Autonomous Azure Tenant Replication - Master Execution Prompt

**Date:** 2025-10-15
**Mode:** Autonomous Continuous Iteration
**Source Tenant:** DefenderATEVET17
**Target Tenant:** DefenderATEVET12

## Primary Directive

Execute autonomous, continuous iteration toward complete tenant replication objective as defined in `/demos/OBJECTIVE.md`. Work without stopping unless blocked by external dependencies or critical failures. Make informed decisions autonomously and communicate decisions via iMessage.

## Core Objective (from OBJECTIVE.md)

Achieve faithful replication of DefenderATEVET17 → DefenderATEVET12 including:
1. **Control Plane**: All ARM resources (✅ 100% type coverage achieved)
2. **Entra ID**: Users, groups, service principals, apps
3. **Data Plane**: Key Vaults, storage blobs, critical application data
4. **Graph Parity**: Source and target Neo4j graphs have matching node counts

## Development Philosophy (from PHILOSOPHY.md)

- **Ruthlessly Simple**: Minimal abstractions, clear code
- **Small Tools Combine**: Build modular components that compose
- **Quality Over Speed**: Correctness before rapid implementation
- **Complete at Depth**: Deep implementation over broad and shallow
- **No Stubs/Placeholders**: Full implementation or graceful failure
- **Trust Emergence**: Simple components build complex systems

## Available Agents (in .claude/agents/)

### Core Agents
- **architect**: System design, architecture decisions
- **builder**: Code implementation from specifications
- **tester**: Test creation and validation
- **reviewer**: Code quality review
- **optimizer**: Performance improvements

### Specialized Agents
- **prompt-writer**: Creates high-quality prompts from requirements
- **zen-architect**: Simplification and philosophy compliance
- **database**: Neo4j and data model design
- **security**: Security review and implementation
- **integration**: External system connections
- **cleanup**: Ruthless simplification while preserving requirements

## Execution Strategy

### Phase 1: Full Tenant Discovery (DefenderATEVET17)
**Status:** Needed
**Objective:** Scan complete source tenant into Neo4j

**Tasks:**
1. Run full tenant discovery for DefenderATEVET17
2. Ensure all resource types discovered
3. Verify Entra ID entities captured (users, groups, apps)
4. Validate Neo4j graph completeness
5. Document resource counts and relationships

**Agents to Use:**
- Database agent: Neo4j schema validation
- Architect agent: Discovery strategy

**Success Criteria:**
- All ARM resources in Neo4j
- All Entra ID entities in Neo4j
- No truncated properties (check for >4KB warnings)
- Baseline node counts documented

### Phase 2: Entra ID Replication Implementation
**Status:** Not Yet Implemented
**Objective:** Add Terraform support for Entra ID resources

**Tasks:**
1. Add Terraform mappings for azuread_user, azuread_group, azuread_service_principal
2. Implement password/credential handling (variables, not actual values)
3. Handle group membership relationships
4. Implement app registrations and service principals
5. Test with sample Entra ID objects

**Agents to Use:**
- Architect agent: Design Entra ID replication approach
- Builder agent: Implement Terraform emitters
- Tester agent: Create comprehensive tests
- Security agent: Ensure credential handling is secure

**Success Criteria:**
- Entra ID resource types in AZURE_TO_TERRAFORM_MAPPING
- Test coverage for Entra ID resources
- Generated Terraform includes user/group/app resources
- Passwords represented as variables (terraform.tfvars template)

### Phase 3: Data Plane Completion
**Status:** Key Vault partial, others not started
**Objective:** Complete data plane replication plugins

**Tasks:**
1. Complete Key Vault plugin replication code generation
2. Implement Storage Blob plugin (discovery + replication)
3. Add VM disk handling strategy
4. Handle database schemas/data (documentation approach)
5. Test data plane plugins with real resources

**Agents to Use:**
- Builder agent: Complete plugin implementations
- Database agent: Neo4j storage for data plane metadata
- Security agent: Ensure secret handling is secure
- Tester agent: Plugin validation tests

**Success Criteria:**
- Key Vault plugin generates complete Terraform
- Storage blob plugin discovers and generates code
- Data plane items tracked in Neo4j
- Documentation for manual data migration steps

### Phase 4: Full Tenant Iteration (ITERATION 21+)
**Status:** Ready to start after Phase 1-3
**Objective:** Generate and deploy complete tenant replication

**Tasks:**
1. Generate ITERATION 21 with full DefenderATEVET17 scope
2. Include Entra ID resources
3. Include data plane placeholders/variables
4. Validate comprehensively
5. Deploy to DefenderATEVET12
6. Scan deployed resources back into Neo4j
7. Compare source and target graphs

**Agents to Use:**
- Architect agent: Deployment strategy
- Builder agent: Fix any discovered issues
- Reviewer agent: Pre-deployment validation
- Cleanup agent: Ensure quality before deployment

**Success Criteria:**
- Terraform plan shows expected resource counts
- All validation checks pass
- Deployment succeeds (>95% resources)
- Target tenant graph matches source (±5%)

### Phase 5: Continuous Improvement Loop
**Status:** Ongoing
**Objective:** Iterate until objective fully achieved

**Process:**
1. Deploy iteration N
2. Analyze failures and gaps
3. Fix issues in code
4. Generate iteration N+1
5. Repeat until 100% fidelity

**Agents to Use:**
- Analyzer agent: Understand failures
- Fix-agent: Targeted bug fixes
- Reviewer agent: Ensure no regressions

**Success Criteria:**
- Each iteration improves on previous
- Failure rate decreases iteration over iteration
- Eventually achieve 100% deployment success

## Agent Invocation Pattern

```bash
copilot --allow-all-tools -p "$(cat <<'PROMPT'
[Agent-specific prompt with full context]
PROMPT
)"
```

### Parallel Execution Strategy

Spawn multiple agents simultaneously for independent tasks:
- Agent 1: Entra ID implementation
- Agent 2: Storage blob plugin
- Agent 3: Key Vault completion
- Agent 4: Full tenant scanning

Monitor each agent's output and respawn with adjusted prompts if they fail.

## Decision-Making Framework

When facing decisions, autonomously choose based on:

1. **Alignment with Objective**: Does it move toward tenant replication?
2. **Philosophy Compliance**: Is it ruthlessly simple and complete?
3. **Risk vs Reward**: High-value, low-risk tasks first
4. **Dependencies**: Can it be done now or blocked by prerequisites?
5. **Reversibility**: Can the decision be changed later if wrong?

**Communication Rule:** For significant decisions, send iMessage explaining:
- Decision made
- Reasoning
- Expected outcome
- How to reverse if needed

## Progress Tracking

### Update These Documents Regularly
- `demos/OBJECTIVE.md`: Status section
- `CURRENT_STATUS.md`: Current iteration state
- Create new session summaries in project root
- Update presentation in demos/

### Create New Iterations
- Each iteration in new dir: `demos/iteration_N/`
- Increment iteration prefix: ITERATION21_, ITERATION22_, etc.
- Document learnings in iteration summary

### Use iMessage for Key Milestones
- Phase completions
- Significant decisions
- Blockers encountered
- Success achievements
- Daily progress summaries

## Constraints and Guardrails

### What NOT to Do
- Don't run arbitrary Azure commands that modify resources
- Don't commit secrets or credentials
- Don't skip validation before deployment
- Don't proceed if tests are failing
- Don't ignore philosophy principles

### What TO Do
- Build ATG features to achieve objective
- Write comprehensive tests
- Validate everything before deployment
- Document all decisions and changes
- Iterate continuously until objective achieved

## Error Handling

When encountering issues:
1. **Analyze**: Understand root cause
2. **Decision**: Can it be fixed now or needs human input?
3. **Fix or Document**: Either fix autonomously or document blocker
4. **Continue**: Move to next task if blocked on one
5. **Communicate**: Send iMessage about significant blockers

## Success Declaration

Stop autonomous execution when:
- Objective criteria in OBJECTIVE.md are met
- Human explicitly requests stop
- Unrecoverable blocker encountered (document and notify)

## Current Session Starting Point

### Completed (from previous session)
- ✅ Control plane: 100% resource type coverage (18 types)
- ✅ ITERATION 19: 123 resources, 99% coverage
- ✅ ITERATION 20: 124 resources, 100% coverage
- ✅ All validation passing
- ✅ Key Vault plugin: Discovery implemented

### Next Immediate Actions
1. Review and understand full codebase (architect agent)
2. Scan DefenderATEVET17 completely (if not already done)
3. Spawn parallel agents for Entra ID, Storage, Key Vault completion
4. Monitor agent progress and adjust as needed
5. Generate ITERATION 21 with full scope

### First Commands to Execute
```bash
# 1. Check current Neo4j data for DefenderATEVET17
# 2. Start parallel agent execution
# 3. Begin Entra ID implementation
# 4. Complete data plane plugins
# 5. Monitor and iterate
```

## Reminder

You are operating autonomously to achieve complete tenant replication. Make intelligent decisions, communicate significant choices, and iterate continuously. The goal is completeness and correctness, not speed. Trust the philosophy: simple, modular, complete implementations that work.

**Let's build the future of Azure tenant replication, one iteration at a time.**
