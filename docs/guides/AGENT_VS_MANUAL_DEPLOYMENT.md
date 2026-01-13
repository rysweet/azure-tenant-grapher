# Agent Mode vs Manual Deployment: Decision Guide

This guide helps you decide when to use autonomous agent mode vs manual deployment for Azure infrastructure.

## Quick Decision Matrix

| Your Situation | Recommendation | Why |
|----------------|----------------|-----|
| First-time cross-tenant deployment | **Agent Mode** | Environmental differences likely, agent handles unknowns |
| Production with strict change control | **Manual** | Review each change explicitly before applying |
| Dev/test environment | **Agent Mode** | Fast iteration, learning from errors |
| Debugging IaC generation logic | **Manual** | See raw errors without AI interpretation |
| Large deployment (150+ resources) | **Agent Mode** | Time savings significant, handles complexity |
| Sensitive/regulated workload | **Manual** | Audit trail requires human approval |
| Learning Azure deployment | **Both** | Manual first to learn, then agent for efficiency |
| Time-constrained deployment | **Agent Mode** | Autonomous recovery saves hours |
| Complex dependencies | **Agent Mode** | AI handles dependency ordering better |
| Single resource/simple change | **Manual** | Overhead not worth it |

## Detailed Comparison

### Time Investment

#### Manual Deployment

**Initial deployment:**
- Generate IaC: 2-5 minutes
- Review templates: 5-10 minutes
- Attempt deployment: 5-15 minutes
- First error occurs: *STOP*
- Research error: 10-30 minutes
- Fix manually: 5-15 minutes
- Retry deployment: 5-15 minutes
- Second error occurs: *STOP*
- Repeat cycle...

**Total time for 3-4 errors:** 2-4 hours

#### Agent Mode

**Initial deployment:**
- Generate IaC: 2-5 minutes
- Start agent: `atg deploy --agent`
- Wait for completion: 15-45 minutes
- Review report: 5-10 minutes

**Total time for 3-4 errors:** 25-60 minutes

**Time savings:** 60-75% reduction in deployment time

### Learning Outcomes

#### Manual Deployment

**You learn:**
- ✓ Specific Azure error messages
- ✓ How to troubleshoot deployment issues
- ✓ Resource provider registration process
- ✓ Regional SKU availability
- ✓ Azure portal investigation techniques

**Best for:**
- Azure beginners
- Learning deployment mechanics
- Understanding infrastructure dependencies

#### Agent Mode

**You learn:**
- ✓ Common deployment error patterns
- ✓ Automated fix strategies
- ✓ Cross-environment compatibility issues
- ✓ Best practices from AI recommendations

**Best for:**
- Experienced Azure users
- Time-constrained projects
- Learning from AI-generated solutions

**Hybrid approach:** Use manual deployment first to learn basics, then agent mode for efficiency.

### Control and Predictability

#### Manual Deployment

**Control level:** FULL
- You see every error immediately
- You decide every fix
- You control deployment order
- You manage state explicitly

**Predictability:** HIGH
- Same inputs → same outputs
- Reproducible deployments
- No AI surprises
- Deterministic behavior

**Best for:**
- Production deployments
- Compliance requirements
- Audit trail needs
- Deterministic environments

#### Agent Mode

**Control level:** DELEGATED
- Agent makes fix decisions
- You review afterwards
- AI determines optimal fixes
- Automated retry logic

**Predictability:** MEDIUM
- AI may choose different fixes
- Non-deterministic behavior
- Results may vary between runs
- Learning-based improvements

**Best for:**
- Dev/test environments
- Exploratory deployments
- Time-constrained situations
- Cross-environment deployments

### Cost Comparison

#### Manual Deployment

**Azure costs:**
- Standard resource deployment: $X
- Failed deployments: $0 (no resources created)

**Human costs:**
- Troubleshooting time: 2-4 hours @ $Y/hour
- Retry deployments: 30-60 minutes
- Documentation: 15-30 minutes

**Total cost:** $X + (2-5 hours × $Y)

#### Agent Mode

**Azure costs:**
- Standard resource deployment: $X
- Failed iterations: $0 (resources rolled back)

**AI API costs:**
- Claude SDK calls: $0.05-0.50 per deployment
- Negligible compared to time savings

**Human costs:**
- Review time: 15-30 minutes @ $Y/hour
- Monitoring: 5-10 minutes

**Total cost:** $X + $0.05-0.50 + (20-40 minutes × $Y)

**Cost savings:** 75-90% reduction in human time costs

### Error Handling Capabilities

#### Manual Deployment

**You handle:**
- Provider registration errors → Register manually via portal/CLI
- SKU availability errors → Research available SKUs, update templates
- Network conflicts → Analyze CIDR ranges, adjust manually
- Naming conflicts → Rename resources, update references
- API version errors → Find compatible versions, update templates

**Error resolution time:** 10-30 minutes per error

#### Agent Mode

**Agent handles:**
- ✓ Provider registration → Auto-register in IaC
- ✓ SKU availability → Auto-select compatible SKU
- ✓ Network conflicts → Adjust CIDR ranges
- ✓ Naming conflicts → Generate unique names
- ✓ API version errors → Update to compatible versions

**Error resolution time:** < 1 minute per error (automated)

**Limitations:**
- ✗ Cannot fix quotas (requires portal/support)
- ✗ Cannot fix permissions (requires RBAC)
- ✗ Cannot fix service outages (requires waiting)

### Audit Trail and Compliance

#### Manual Deployment

**Audit trail:**
- Manual logs of commands run
- Git commits for template changes
- Azure activity logs
- Self-documented (you know what you did)

**Compliance:**
- ✓ Full human review before changes
- ✓ Explicit approval gates
- ✓ Known and controlled modifications
- ✓ Reproducible from version control

**Best for:**
- Regulated industries
- SOX/HIPAA compliance
- Change advisory boards
- Auditable deployments

#### Agent Mode

**Audit trail:**
- Comprehensive deployment report (markdown)
- Complete iteration history
- AI analysis and fix reasoning
- Before/after diffs for all changes
- Preserved artifacts per iteration

**Compliance:**
- ✓ Transparent AI decision-making
- ✓ Full change documentation
- ⚠ Requires post-deployment review
- ⚠ Changes applied before human approval

**Best for:**
- Dev/test (no compliance requirements)
- Internal projects
- Rapid prototyping
- Post-review acceptable

### Risk Assessment

#### Manual Deployment

**Risks:**
- Human error in fixes (typos, wrong values)
- Inconsistent fixes across iterations
- Missed dependencies
- Time pressure leading to mistakes

**Mitigation:**
- Code review before deployment
- Thorough testing
- Documentation
- Peer review

**Risk level:** MEDIUM (human error)

#### Agent Mode

**Risks:**
- AI makes incorrect fix
- Unintended side effects
- Over-optimization
- Non-deterministic behavior

**Mitigation:**
- Review deployment report
- Test in non-production first
- Revert to manual if issues
- File issues to improve agent

**Risk level:** MEDIUM (AI decision quality)

**Both approaches have risks** - choose based on risk tolerance and review capabilities.

## Real-World Scenarios

### Scenario 1: Production Deployment for Regulated Workload

**Context:**
- Healthcare application (HIPAA compliance)
- 200+ resources
- Multi-region deployment
- Change advisory board approval required

**Recommendation: MANUAL**

**Workflow:**
```bash
# 1. Generate IaC
atg generate-iac --target-tenant-id <PROD_TENANT>

# 2. Review templates (code review)
git add .
git commit -m "Generated production IaC"
git push
# Open PR for CAB review

# 3. After approval, deploy manually
cd iac_output
terraform plan -out=tfplan
# Review plan with CAB
terraform apply tfplan

# 4. Monitor and document each error
# Fix manually with explicit approval
# Document in change log
```

**Why manual:**
- Compliance requires human approval
- CAB needs to review changes
- Audit trail must show explicit decisions
- Risk mitigation requires human oversight

### Scenario 2: Dev Environment for Testing New Features

**Context:**
- Development sandbox
- Testing cross-tenant replication
- Rapid iteration needed
- No compliance requirements

**Recommendation: AGENT MODE**

**Workflow:**
```bash
# 1. Generate IaC
atg generate-iac --target-tenant-id <DEV_TENANT>

# 2. Deploy with agent
atg deploy --agent --max-iterations 10

# 3. Review report
cat deployment_report.md

# 4. Iterate on issues
# Agent handles most errors automatically
# Only intervene if agent gets stuck
```

**Why agent:**
- Speed is critical
- No compliance requirements
- Learning from AI fixes is valuable
- Manual troubleshooting is time-consuming

### Scenario 3: Cross-Tenant Migration (300+ Resources)

**Context:**
- Moving from old tenant to new tenant
- 300+ resources with complex dependencies
- Different region (eastus → westus2)
- Time-constrained (weekend migration window)

**Recommendation: AGENT MODE (with preparation)**

**Workflow:**
```bash
# FRIDAY (Preparation)
# 1. Test in dev first
atg generate-iac --target-tenant-id <DEV_TENANT>
atg deploy --agent
# Review what issues agent encountered

# 2. Pre-register providers in production
az provider register --namespace Microsoft.Network --wait
az provider register --namespace Microsoft.Compute --wait
# (Based on dev deployment report)

# SATURDAY (Migration)
# 3. Generate production IaC
atg generate-iac --target-tenant-id <PROD_TENANT>

# 4. Deploy with agent (extended timeout)
atg deploy --agent --max-iterations 10 --timeout 900

# 5. Monitor progress
# Agent handles regional differences automatically

# 6. Review report and validate
cat deployment_report.md
# Verify resources in Azure portal
```

**Why agent:**
- Time-constrained window
- Complex cross-region dependencies
- Agent handles SKU/region differences
- Preparation in dev reduces risk

**Risk mitigation:**
- Test in dev first
- Pre-register known requirements
- Extended monitoring
- Rollback plan available

### Scenario 4: Learning Azure Deployment

**Context:**
- Junior engineer learning Azure
- Simple deployment (10-20 resources)
- Educational goal
- No time pressure

**Recommendation: MANUAL FIRST, then AGENT**

**Workflow:**
```bash
# WEEK 1: Manual Learning
# 1. Deploy manually to understand errors
atg generate-iac
cd iac_output
terraform apply

# 2. Encounter error: provider not registered
# Research: What is a resource provider?
# Fix: az provider register --namespace Microsoft.Network

# 3. Retry, encounter error: invalid SKU
# Research: How to find available SKUs?
# Fix: az vm list-skus --location eastus

# 4. Learn from each error

# WEEK 2: Agent Learning
# 5. Now try with agent to compare
atg deploy --agent

# 6. Review deployment report
cat deployment_report.md

# 7. Compare agent fixes to your manual fixes
# Learn: What did agent do differently?
# Understand: Why is that fix better/worse?
```

**Why this approach:**
- Manual deployment teaches fundamentals
- Agent mode shows best practices
- Comparing approaches deepens understanding
- Builds intuition for when to use each

### Scenario 5: Debugging IaC Generation Bug

**Context:**
- Suspected bug in IaC generation
- Resources not being created correctly
- Need to see raw Azure errors
- Investigating root cause

**Recommendation: MANUAL**

**Workflow:**
```bash
# 1. Generate IaC with suspected bug
atg generate-iac --debug

# 2. Deploy manually (NO agent)
cd iac_output
terraform apply

# 3. Observe raw error
# Error: Resource X depends on Y but Y is not defined

# 4. Analyze IaC templates
cat main.tf
# Found bug: Missing resource definition

# 5. File issue with exact error
# Agent would have masked this bug by fixing the symptom
```

**Why manual:**
- Need to see root cause error
- Agent might fix symptom without revealing bug
- Debugging requires raw error messages
- IaC generation logic needs fixing, not templates

## Hybrid Strategies

### Strategy 1: Agent with Manual Review

Use agent mode but review before final approval:

```bash
# 1. Deploy with agent to staging
atg deploy --agent --path ./staging

# 2. Review deployment report
cat staging/deployment_report.md

# 3. Extract fixes agent made
diff -u staging/original/ staging/iteration_final/

# 4. Apply agent fixes manually to production templates
cp staging/iteration_final/*.tf ./production/

# 5. Deploy production manually
cd production
terraform apply
```

**Best of both worlds:**
- Agent speed for error discovery
- Manual control for production deployment
- Learning from AI decisions
- Human review for compliance

### Strategy 2: Manual First Iteration, Agent for Retries

Try manual first, fall back to agent if stuck:

```bash
# 1. Deploy manually
terraform apply

# 2. Hit complex error you don't understand
# Error: InvalidNetworkConfiguration (cryptic details)

# 3. Let agent handle it
cd ..
atg deploy --agent --path ./iac_output

# 4. Review what agent did
cat deployment_report.md
# Learn: Agent adjusted VNet peering configuration

# 5. Understand the fix and continue
```

**Advantages:**
- Learn from simple errors
- Agent handles complex ones
- You maintain control
- Agent is fallback, not primary

### Strategy 3: Parallel Testing

Deploy to dev with agent, to production manually:

```bash
# Deploy to dev with agent
atg generate-iac --target-tenant-id <DEV_TENANT>
atg deploy --agent

# Review agent's deployment report
cat deployment_report.md

# Extract lessons learned
# - Provider X needs registration
# - SKU Y not available, use Z instead

# Apply lessons to production manually
atg generate-iac --target-tenant-id <PROD_TENANT>
# Edit templates with known fixes
cd iac_output
terraform apply
```

**Risk mitigation:**
- Dev catches issues first
- Production deployment is informed
- Agent report guides manual fixes
- No surprises in production

## Decision Framework

Use this decision tree to choose your approach:

```
Is this a production deployment?
├─ YES → Does it require compliance/audit trail?
│  ├─ YES → MANUAL
│  └─ NO → Is time critical?
│     ├─ YES → AGENT (with review)
│     └─ NO → MANUAL (safer)
└─ NO (dev/test) → Is deployment simple (< 20 resources)?
   ├─ YES → MANUAL (not worth agent overhead)
   └─ NO → Is this cross-environment deployment?
      ├─ YES → AGENT (handles differences)
      └─ NO → Either (preference)
```

## Summary Table

| Factor | Manual Deployment | Agent Mode |
|--------|------------------|------------|
| **Time to complete** | 2-4 hours | 30-60 minutes |
| **Human effort** | High | Low |
| **Control** | Full | Delegated |
| **Learning** | Deep Azure knowledge | Pattern recognition |
| **Reproducibility** | High | Medium |
| **Compliance** | Native | Requires review |
| **Error handling** | Manual research | Automated fixes |
| **Cost** | High (human time) | Low (human) + minimal (AI) |
| **Risk** | Human error | AI decision quality |
| **Best for** | Production, learning | Dev/test, cross-env |

## Recommendations by Role

### DevOps Engineer
- **Primary:** Agent mode for dev/test
- **Production:** Manual with agent report as guide
- **Learning:** Start manual, transition to agent

### Cloud Architect
- **Design validation:** Manual (see actual errors)
- **Rapid prototyping:** Agent mode
- **Production:** Manual with change control

### Junior Developer
- **Learning phase:** Manual (understand errors)
- **After basics:** Agent mode (efficiency)
- **Complex issues:** Agent with report review

### Security Engineer
- **Compliance-required:** Manual
- **Testing security controls:** Agent mode
- **Production:** Manual with documented reviews

## Making the Choice

Ask yourself:

1. **Do I need explicit approval for every change?** → Manual
2. **Is time more valuable than control?** → Agent
3. **Am I learning or executing?** → Manual vs Agent
4. **Is this environment critical?** → Manual
5. **Are there many unknowns?** → Agent
6. **Do I need deterministic results?** → Manual
7. **Is this a one-time vs repeated deployment?** → Manual vs Agent

**Remember:** You can always switch approaches mid-deployment or combine strategies.

---

**Next Steps:**
- **Chose Manual?** See [Deployment Troubleshooting](AUTONOMOUS_DEPLOYMENT_FAQ.md)
- **Chose Agent?** See [Autonomous Deployment Tutorial](../quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)
- **Want Both?** Use hybrid strategies above

**Still unsure?** Start with agent mode in dev/test environment to evaluate.
