# Demo Tier Selection Guide

## Quick Selection Matrix

| Question | Quick Demo | Standard Demo | Full Demo |
|----------|-----------|---------------|-----------|
| **How much time available?** | 15 minutes | 45 minutes | 2-3 hours |
| **Who is the audience?** | Executives, VPs | Tech leads, architects | Engineers, auditors |
| **Technical depth required?** | High-level overview | Moderate detail | Deep technical dive |
| **Will you deploy to Azure?** | No (dry run only) | No (plan only) | Optional (actual deploy) |
| **Do you need live demos?** | No (use cached) | Yes (some live) | Yes (all live) |
| **Budget for Azure costs?** | $0 | $0 | $500-2000 (if deploying) |
| **Preparation time needed?** | 1 hour | 2-3 hours | 4-6 hours |

---

## Decision Flowchart

```
START: Planning a Demo
│
├─ Question 1: How much time does your audience have?
│  ├─ 15 minutes or less ────────────────────────┐
│  ├─ 30-60 minutes ──────────────────────┐      │
│  └─ 2+ hours ────────────────────┐      │      │
│                                   │      │      │
├─ Question 2: What is their role? │      │      │
│  ├─ Executive/Business ──────────┼──────┼────► QUICK DEMO
│  ├─ Technical Lead/Architect ────┼────► STANDARD DEMO
│  └─ Engineer/Auditor ──────────► FULL DEMO
│                                   │      │
├─ Question 3: Deployment needed?  │      │
│  ├─ Yes (actual deploy) ────────► FULL DEMO
│  ├─ Maybe (show plan) ───────────┼────► STANDARD DEMO
│  └─ No (concepts only) ──────────┼──────────► QUICK DEMO
│                                   │
├─ Question 4: Budget available?   │
│  ├─ $0 ───────────────────────────┼────► STANDARD or QUICK
│  └─ $500+ ──────────────────────► FULL DEMO (with deploy)
│
└─ SELECTED: [YOUR DEMO TIER]
```

---

## Audience Personas

### Persona 1: Executive Sponsor
**Name**: Sarah, VP of Cloud Infrastructure
**Concerns**: ROI, timeline, risk
**Questions**: "How much will this cost?", "When can we use it?", "What are the risks?"
**Recommended Tier**: **QUICK DEMO**
**Focus**: Business value, fidelity metrics, ROI analysis

### Persona 2: Technical Architect
**Name**: David, Cloud Solutions Architect
**Concerns**: Architecture soundness, scalability, integration
**Questions**: "How does this work?", "Can it scale?", "What are the dependencies?"
**Recommended Tier**: **STANDARD DEMO**
**Focus**: Architecture design, Neo4j graph, plugin framework

### Persona 3: DevOps Engineer
**Name**: Maria, Senior DevOps Engineer
**Concerns**: Implementation details, edge cases, troubleshooting
**Questions**: "How do I fix errors?", "What breaks?", "How do I operate this?"
**Recommended Tier**: **FULL DEMO**
**Focus**: End-to-end workflow, failure handling, operational procedures

### Persona 4: Security Auditor
**Name**: James, Security Compliance Lead
**Concerns**: Data protection, access control, audit trail
**Questions**: "How are secrets handled?", "What's the audit trail?", "RBAC?"
**Recommended Tier**: **FULL DEMO**
**Focus**: Security architecture, audit logging, RBAC model

---

## Demo Tier Comparison

### Quick Demo (15 minutes)

**Best For**:
- Executive briefings
- Stakeholder updates
- Go/No-go decisions
- Budget approval presentations

**What You'll Show**:
- ✅ High-level architecture (diagram)
- ✅ Fidelity metrics (numbers)
- ✅ Control plane success (95% fidelity)
- ✅ Data plane gaps (plugin matrix)
- ✅ ROI analysis (cost-benefit)

**What You'll Skip**:
- ❌ Live scanning
- ❌ Neo4j queries
- ❌ Terraform validation
- ❌ Detailed troubleshooting
- ❌ Technical deep dive

**Preparation**:
- Pre-scan both tenants (cache results)
- Generate IaC in advance
- Calculate fidelity beforehand
- Prepare executive summary slide deck
- Time: 1 hour prep

**Deliverables**:
1. Executive summary (1 page)
2. Fidelity comparison JSON
3. ROI analysis spreadsheet
4. Recommendation slide

---

### Standard Demo (45 minutes)

**Best For**:
- Technical team presentations
- Architecture review boards
- Product management demos
- Vendor evaluations

**What You'll Show**:
- ✅ Live IaC generation
- ✅ Neo4j graph visualization
- ✅ Terraform validation process
- ✅ Fidelity tracking system
- ✅ Data plane architecture
- ✅ Plugin requirement matrix
- ✅ Implementation roadmap

**What You'll Skip**:
- ❌ Full source scan (use cached)
- ❌ Actual Azure deployment
- ❌ Deep troubleshooting session
- ❌ Detailed code walkthrough

**Preparation**:
- Pre-scan source tenant (cache)
- Install demo dependencies
- Prepare Neo4j queries
- Test IaC generation
- Time: 2-3 hours prep

**Deliverables**:
1. Executive summary
2. Technical architecture doc
3. Fidelity metrics (JSON)
4. Plugin requirement matrix
5. Implementation roadmap (Gantt chart)

---

### Full Demo (2-3 hours)

**Best For**:
- Engineering team onboarding
- Security audits
- Deep technical reviews
- Production readiness assessments

**What You'll Show**:
- ✅ Complete live workflow
- ✅ Full source scan (live)
- ✅ Full target scan (live)
- ✅ Neo4j graph queries (live)
- ✅ Terraform validation (live)
- ✅ Terraform plan review (live)
- ✅ Optional: Actual deployment
- ✅ Fidelity calculation (live)
- ✅ Error handling demonstration
- ✅ Gap analysis workshop
- ✅ Technical Q&A session

**What You'll Skip**:
- Nothing (complete demonstration)

**Preparation**:
- Clean Neo4j database
- Verify Azure credentials
- Test all commands
- Prepare rollback plan (if deploying)
- Obtain deployment approval (if deploying)
- Schedule operations team (if deploying)
- Time: 4-6 hours prep

**Deliverables**:
1. Executive summary
2. Technical deep dive report
3. Complete artifact package (tarball)
4. Fidelity history (JSONL)
5. Operational runbook
6. Known issues document
7. Implementation backlog

---

## Special Scenarios

### Scenario 1: Board Presentation
**Situation**: Presenting to board of directors, need C-level approval
**Recommended Tier**: **QUICK DEMO**
**Customization**:
- Focus on ROI and business value
- Use simple language (no technical jargon)
- Emphasize risk mitigation
- Show competitive advantage
- Prepare for budget questions
**Duration**: 10-15 minutes + Q&A

### Scenario 2: Vendor Evaluation
**Situation**: Customer evaluating Azure Tenant Grapher vs competitors
**Recommended Tier**: **STANDARD DEMO**
**Customization**:
- Highlight unique capabilities (Neo4j graph, fidelity tracking)
- Compare with manual processes
- Show automation benefits
- Demonstrate extensibility (plugin framework)
- Address integration questions
**Duration**: 45-60 minutes + Q&A

### Scenario 3: Production Readiness Review
**Situation**: Internal review before production deployment
**Recommended Tier**: **FULL DEMO**
**Customization**:
- Focus on failure modes and recovery
- Show operational procedures
- Demonstrate monitoring and alerting
- Review security controls
- Validate disaster recovery plan
**Duration**: 2-3 hours + workshop

### Scenario 4: Security Audit
**Situation**: Compliance team reviewing for SOC2/ISO27001
**Recommended Tier**: **FULL DEMO**
**Customization**:
- Emphasize audit logging
- Show RBAC implementation
- Demonstrate secret handling
- Review data protection measures
- Provide compliance documentation
**Duration**: 2-3 hours + documentation review

### Scenario 5: Sales Demo
**Situation**: Prospective customer wants to see the tool in action
**Recommended Tier**: **STANDARD DEMO**
**Customization**:
- Focus on value proposition
- Show quick wins (control plane automation)
- Acknowledge gaps honestly (data plane plugins)
- Emphasize roadmap and commitment
- Provide pricing and support options
**Duration**: 30-45 minutes + Q&A

---

## Preparation Checklists

### Quick Demo Preparation

- [ ] Pre-scan source tenant (cache results)
- [ ] Pre-calculate fidelity metrics
- [ ] Generate executive summary
- [ ] Prepare 5-slide deck:
  - Slide 1: Title and objective
  - Slide 2: Architecture overview
  - Slide 3: Fidelity results (95% control plane)
  - Slide 4: Data plane gaps (plugin matrix)
  - Slide 5: ROI and recommendations
- [ ] Test laptop/projector connection
- [ ] Print handouts (1-pager summary)
- [ ] Prepare answers to budget questions

**Total Prep Time**: 1 hour

---

### Standard Demo Preparation

- [ ] Pre-scan source tenant (cache results)
- [ ] Clean demo environment
- [ ] Verify Neo4j container running
- [ ] Test Azure credentials
- [ ] Prepare Neo4j queries (copy-paste ready)
- [ ] Test IaC generation command
- [ ] Generate plugin requirement matrix
- [ ] Create architecture diagrams
- [ ] Prepare technical FAQ document
- [ ] Test all commands in dry-run mode
- [ ] Set up screen sharing
- [ ] Prepare demo script with timings

**Total Prep Time**: 2-3 hours

---

### Full Demo Preparation

- [ ] Clean Neo4j database (backup first)
- [ ] Verify Azure credentials (source + target)
- [ ] Test all CLI commands end-to-end
- [ ] Prepare rollback plan (if deploying)
- [ ] Obtain deployment approval (if deploying)
- [ ] Set up cost monitoring (if deploying)
- [ ] Schedule operations team (if deploying)
- [ ] Prepare detailed technical documentation
- [ ] Set up monitoring dashboard
- [ ] Prepare failure scenario demonstrations
- [ ] Create artifact collection script
- [ ] Test complete workflow in staging
- [ ] Prepare operational runbook
- [ ] Set up recording (with permission)
- [ ] Prepare comprehensive Q&A document

**Total Prep Time**: 4-6 hours

---

## Risk Assessment by Tier

### Quick Demo Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cached data outdated | Low | Medium | Verify scan timestamps |
| Metrics misinterpreted | Medium | Medium | Provide clear definitions |
| Budget questions unanswered | Medium | High | Prepare cost analysis |
| Technical questions beyond scope | High | Low | Defer to Standard demo |

**Overall Risk**: LOW

---

### Standard Demo Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| IaC generation fails | Low | High | Test beforehand, have cached fallback |
| Neo4j connection issues | Low | High | Verify container before demo |
| Azure auth expires mid-demo | Low | Medium | Refresh tokens before starting |
| Audience wants full deployment | Medium | Medium | Set expectations upfront |
| Deep technical questions | High | Low | Prepare technical FAQ |

**Overall Risk**: LOW-MEDIUM

---

### Full Demo Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Deployment failures | High | High | Have rollback plan, test in staging |
| Azure quota limits hit | Medium | High | Request quota increases beforehand |
| Demo exceeds time budget | High | Medium | Have checkpoint breaks, can stop early |
| Network issues during deployment | Low | Critical | Have mobile hotspot backup |
| Cost overruns | Medium | High | Set spending limits, monitor actively |

**Overall Risk**: MEDIUM-HIGH (if deploying), LOW (if dry-run)

---

## Success Metrics by Tier

### Quick Demo Success
- [ ] Stakeholders understand value proposition
- [ ] Budget/timeline questions answered
- [ ] Approval to proceed (or clear next steps)
- [ ] No major concerns raised
- [ ] Positive feedback received

**Success Rate**: 90%+ (highly controlled, low risk)

---

### Standard Demo Success
- [ ] Technical architecture understood
- [ ] IaC generation demonstrated successfully
- [ ] Fidelity tracking system explained
- [ ] Data plane gaps acknowledged
- [ ] Implementation roadmap agreed
- [ ] Technical team engaged and asking questions

**Success Rate**: 80%+ (some variability, moderate risk)

---

### Full Demo Success
- [ ] Complete workflow executed successfully
- [ ] Fidelity ≥85% achieved (if deploying)
- [ ] All gaps documented with priorities
- [ ] Operational procedures validated
- [ ] Engineering team confident in implementation
- [ ] Security/compliance concerns addressed
- [ ] Clear backlog created with estimates

**Success Rate**: 60-70% (high complexity, higher risk, but most valuable)

---

## Customization Options

### Add-ons for Quick Demo
- **+5 min**: Live fidelity calculation
- **+5 min**: Neo4j graph visualization (pre-loaded)
- **+5 min**: Terraform validation demo (pre-run)

### Add-ons for Standard Demo
- **+10 min**: Live source scan (if time allows)
- **+10 min**: Deep dive on plugin architecture
- **+15 min**: Interactive Q&A workshop

### Reductions for Full Demo
- **-30 min**: Skip actual deployment, show plan only
- **-20 min**: Use cached source scan
- **-15 min**: Skip data plane gap analysis (if not needed)

---

## Post-Demo Follow-Up

### After Quick Demo
1. Send executive summary (1 page)
2. Schedule Standard demo if interest high
3. Provide ROI analysis spreadsheet
4. Answer follow-up questions via email
5. Set up next checkpoint meeting

### After Standard Demo
1. Send technical architecture document
2. Provide complete artifact package
3. Schedule implementation planning meeting
4. Create shared workspace (Git repo, wiki)
5. Assign technical point of contact

### After Full Demo
1. Send complete demo package (tarball)
2. Provide operational runbook
3. Create backlog in project management tool
4. Schedule sprint planning session
5. Set up ongoing communication channels
6. Provide training materials
7. Assign implementation team

---

## Recommended Tier by Context

| Context | Recommended Tier | Rationale |
|---------|------------------|-----------|
| **Initial stakeholder briefing** | Quick | Gauge interest, get approval |
| **Technical evaluation** | Standard | Validate architecture |
| **Production readiness** | Full | Complete validation |
| **Security audit** | Full | Demonstrate compliance |
| **Sales presentation** | Standard | Show capabilities, acknowledge gaps |
| **Board presentation** | Quick | Business focus, high-level |
| **Engineering onboarding** | Full | Complete understanding |
| **Vendor comparison** | Standard | Detailed but time-bounded |
| **Budget approval** | Quick | Focus on ROI |
| **Deployment planning** | Full | Understand operational reality |

---

## Decision Support Table

Rate each factor from 1-5 (1=low, 5=high), then calculate total:

| Factor | Weight | Your Rating (1-5) | Weighted Score |
|--------|--------|-------------------|----------------|
| Time Available | 3x | ___ | ___ |
| Technical Audience | 2x | ___ | ___ |
| Budget for Deployment | 2x | ___ | ___ |
| Need for Detail | 2x | ___ | ___ |
| Risk Tolerance | 1x | ___ | ___ |
| **TOTAL** | | | ___ |

**Scoring**:
- **10-20**: Quick Demo
- **21-35**: Standard Demo
- **36-50**: Full Demo

---

## Final Recommendation Algorithm

```python
def select_demo_tier(time_minutes, audience_technical_level, deployment_needed, budget_dollars):
    """
    Select appropriate demo tier based on constraints.

    Args:
        time_minutes: Available time (int)
        audience_technical_level: 1-5 (1=business, 5=engineer)
        deployment_needed: Boolean
        budget_dollars: Available budget for Azure costs

    Returns:
        str: "quick", "standard", or "full"
    """
    score = 0

    # Time factor
    if time_minutes >= 120:
        score += 10
    elif time_minutes >= 45:
        score += 5
    else:
        score += 1

    # Audience factor
    score += audience_technical_level * 2

    # Deployment factor
    if deployment_needed and budget_dollars >= 500:
        score += 10
    elif deployment_needed:
        score += 5

    # Select tier
    if score >= 20:
        return "full"
    elif score >= 10:
        return "standard"
    else:
        return "quick"

# Examples:
# select_demo_tier(15, 1, False, 0) → "quick"
# select_demo_tier(60, 4, False, 0) → "standard"
# select_demo_tier(180, 5, True, 1000) → "full"
```

---

## Conclusion

Use this guide to select the appropriate demo tier based on:

1. **Available time**
2. **Audience expertise**
3. **Deployment requirements**
4. **Budget constraints**
5. **Risk tolerance**

When in doubt, **start with Standard Demo** - it provides good balance of depth and duration, and can be abbreviated (Quick) or extended (Full) based on audience engagement.

**Remember**: The goal is to demonstrate value and build confidence, not to show every feature. Pick the tier that best serves your audience's needs.
