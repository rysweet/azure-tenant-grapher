# When to Add Complexity - Decision Tree

**Philosophy**: Start minimal, add complexity ONLY when proven necessary

---

## Decision Tree

```
┌───────────────────────────────────────────────────┐
│  START: Simple HTTP + WebSocket Implementation   │
│  - No Redis queue                                 │
│  - 60-minute HTTP timeout                        │
│  - 2 environments (dev + integration)            │
│  - Azure Container Instances (64GB RAM)          │
└─────────────────────┬─────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  MONITOR for 2 weeks in dev │
        └─────────────┬───────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ QUESTION 1: Are operations timing out?                   │
│ Evidence: >20% of scans exceed 60 minutes                │
└───┬──────────────────────────────────────────────┬────────┘
    │                                              │
   YES                                            NO
    │                                              │
    ▼                                              ▼
┌────────────────────────────────┐     ┌──────────────────┐
│  ADD: Redis Job Queue          │     │  CONTINUE        │
│  Reason: Need longer ops       │     │  monitoring      │
│  Cost: +1 container, +code     │     │                  │
│  Benefit: Ops >60 min          │     │                  │
└────────────────────────────────┘     └──────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────┐
│ QUESTION 2: Need >3 concurrent scans?                    │
│ Evidence: Frequently hitting max_concurrent_ops limit     │
└───┬──────────────────────────────────────────────┬────────┘
    │                                              │
   YES                                            NO
    │                                              │
    ▼                                              ▼
┌────────────────────────────────┐     ┌──────────────────┐
│  ADD: Redis Job Queue          │     │  CONTINUE        │
│  Reason: Better concurrency    │     │  monitoring      │
│  Cost: +1 container, +code     │     │                  │
│  Benefit: Queue management     │     │                  │
└────────────────────────────────┘     └──────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────┐
│ QUESTION 3: ACI 64GB unavailable?                        │
│ Evidence: az container create --memory 64 fails          │
└───┬──────────────────────────────────────────────┬────────┘
    │                                              │
   YES                                            NO
    │                                              │
    ▼                                              ▼
┌────────────────────────────────┐     ┌──────────────────┐
│  CONSIDER: Container Apps      │     │  CONTINUE        │
│  Reason: Higher resource limit │     │  with ACI        │
│  Cost: Higher complexity       │     │                  │
│  Benefit: 128GB+ RAM           │     │                  │
└────────────────────────────────┘     └──────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────┐
│ QUESTION 4: User requests production deployment?         │
│ Evidence: Explicit user request + prerequisites met      │
└───┬──────────────────────────────────────────────┬────────┘
    │                                              │
   YES                                            NO
    │                                              │
    ▼                                              ▼
┌────────────────────────────────┐     ┌──────────────────┐
│  ADD: Production Environment   │     │  CONTINUE        │
│  Reason: User explicitly asked │     │  with 2 envs     │
│  Prerequisites: Security audit │     │                  │
│  Cost: +33% infrastructure     │     │                  │
└────────────────────────────────┘     └──────────────────┘
```

---

## Detailed Decision Criteria

### 1. Add Redis Job Queue

**Evidence Required** (ANY of these):

| Metric | Threshold | How to Measure |
|--------|-----------|----------------|
| Operation timeout rate | >20% exceed 60 min | Log all scan durations, calculate percentage |
| Concurrent scan requests | >3 simultaneous | Track active operation count |
| Service restart impact | >5 restarts/month lose work | Count operations lost to restarts |
| User complaints | >10 timeout reports | Support ticket analysis |

**Measurement Commands**:
```bash
# Track operation durations
grep "Scan duration:" logs/atg-service.log | awk '{print $3}' | sort -n

# Calculate timeout rate
total=$(grep "Scan duration:" logs/atg-service.log | wc -l)
timeouts=$(grep "Scan duration:" logs/atg-service.log | awk '$3 > 3600' | wc -l)
echo "Timeout rate: $(($timeouts * 100 / $total))%"

# Track concurrent operations
grep "Active operations:" logs/atg-service.log | awk '{print $3}' | sort -rn | head -1
```

**Decision**:
- If ANY threshold exceeded → Add Redis queue
- If ALL below threshold → Continue simple approach

**Implementation Cost**:
- +1 Redis container (4GB RAM)
- +200 lines of job queue code
- +50 lines of polling logic
- +2 API endpoints (job status, job result)
- +1 week implementation time

### 2. Add Production Environment

**Prerequisites** (ALL required):

- [ ] User explicitly requests production deployment
- [ ] Production tenant ready (Target Tenant B configured)
- [ ] Dev and integration stable (4+ weeks, no critical bugs)
- [ ] Security audit completed
- [ ] Disaster recovery plan documented
- [ ] Backup strategy verified
- [ ] Team trained on production runbook

**Verification Checklist**:
```bash
# Check dev/integration stability
gh issue list --label "critical,bug" --state open --repo yourorg/atg

# Verify no critical issues in last 4 weeks
gh issue list --label "critical" --created ">$(date -d '4 weeks ago' +%Y-%m-%d)" --state closed

# Check security audit completion
ls -la docs/security/audit_report.pdf

# Verify backup strategy
az storage blob list --container-name neo4j-backups --account-name atgstorage | jq '.[] | select(.name | contains("prod"))'
```

**Implementation Cost**:
- +33% infrastructure cost ($200/month)
- +1 environment in CI/CD
- +1 set of secrets/configs
- +1 week setup time

### 3. Switch to Container Apps

**Evidence Required** (ANY of these):

| Evidence | How to Verify |
|----------|--------------|
| ACI 64GB fails | `az container create --memory 64 --dry-run` returns error |
| Need multi-replica | >2 instances required per environment (load balancing) |
| Need advanced networking | Private endpoints, VNet integration required |
| Need auto-scaling | Load varies >300% (peak/trough ratio) |

**Verification Command**:
```bash
# Test ACI 64GB availability
az container create \
  --resource-group test-rg \
  --name test-aci-64gb \
  --cpu 4 \
  --memory 64 \
  --image nginx:latest \
  --location eastus \
  --dry-run

# Expected outcomes:
# SUCCESS → Use ACI (continue current approach)
# FAILURE → Document error, consider Container Apps
```

**Implementation Cost**:
- Higher complexity (Kubernetes-based)
- More expensive (Premium tier)
- +2 weeks migration time
- Requires Kubernetes expertise

**When to Consider**:
- ONLY if ACI verification fails
- ONLY if need features unavailable in ACI
- NOT for "future-proofing"

### 4. Other Complexity Additions

**Branch-Based Deployment** (DEFERRED):
- Current: Tag-based (simple, explicit)
- Add when: Managing >5 environments
- Cost: Branch management complexity

**WebSocket → Polling** (NEVER):
- Current: WebSocket for progress
- Don't change: Polling is more complex, worse UX
- Exception: If Azure Load Balancer blocks WebSocket (verify first)

**Multi-Tenant Service** (DEFERRED):
- Current: One service per target tenant
- Add when: Managing >10 target tenants
- Cost: Tenant isolation complexity

---

## Monitoring Dashboard

Track these metrics to inform decisions:

```python
# Key metrics to log
metrics = {
    "operation_duration_p95": "50 minutes",  # Alert if >50 min
    "timeout_rate": "5%",                    # Alert if >20%
    "concurrent_operations_max": 2,          # Alert if frequently >3
    "service_restart_count": 1,              # Alert if >5/month
    "websocket_disconnection_rate": "2%",    # Alert if >5%
}

# Alert thresholds
alerts = {
    "operation_duration_p95 > 3000": "Consider Redis queue",
    "timeout_rate > 0.20": "Consider Redis queue",
    "concurrent_operations_max > 3": "Consider Redis queue",
    "service_restart_count > 5": "Investigate stability issues",
    "websocket_disconnection_rate > 0.05": "Investigate WebSocket issues",
}
```

**Dashboard URL**: `https://atg-service-dev.azurecontainer.io/metrics`

---

## Philosophy Alignment

### Principles Applied:

1. **"Start minimal, grow as needed"**
   - Begin with simplest approach (HTTP + WebSocket)
   - Add complexity only when metrics prove necessity

2. **"Don't build for hypothetical future requirements"**
   - No Redis queue until proven needed
   - No prod environment until user requests

3. **"Occam's Razor"**
   - Simplest solution that meets current needs
   - Question every abstraction

4. **"Present-moment focus"**
   - Build for current requirements (dev + integration)
   - Add prod when actually needed

### Anti-Patterns to Avoid:

- ❌ "We might need this later" → Wait for evidence
- ❌ "This is industry best practice" → Question if applicable
- ❌ "Let's future-proof this" → Build for now, refactor later
- ❌ "Everyone uses Redis queues" → Only if we need it

---

## Example Scenarios

### Scenario 1: User Reports Timeouts

**Evidence**:
- 25% of scans exceed 60 minutes
- User complaints: "My scan timed out"

**Decision**: ADD Redis job queue
- Threshold exceeded (>20%)
- Clear user impact
- Proven necessity

**Action**:
1. Implement Redis queue (Phase 2.5)
2. Update API to return job_id
3. Add polling endpoints
4. Update client to poll for results

### Scenario 2: User Requests Production

**Evidence**:
- User email: "We need prod environment"
- Dev stable for 6 weeks
- Security audit complete

**Decision**: ADD production environment
- All prerequisites met
- Explicit user request
- Clear business need

**Action**:
1. Create prod Bicep template
2. Configure Target Tenant B
3. Add prod GitHub Actions workflow
4. Deploy and verify

### Scenario 3: ACI 64GB Works

**Evidence**:
- `az container create --memory 64` succeeds
- Dev environment running with 64GB

**Decision**: CONTINUE with ACI
- No evidence of limits
- Current approach works
- No complexity needed

**Action**:
- No action required
- Continue monitoring
- Document successful verification

### Scenario 4: Only 2 Scans Timeout After 4 Weeks

**Evidence**:
- 98% of scans complete within 60 minutes
- Only 2 exceptions (unusual large tenants)

**Decision**: CONTINUE simple approach
- Threshold not exceeded (<20%)
- Rare exceptions acceptable
- No complexity justified

**Action**:
- Document exceptions
- Continue monitoring
- Consider per-request timeout override (simple)

---

## Summary

**Default Position**: Start with simplest implementation

**Complexity Triggers**: Clear evidence, not speculation

**Decision Process**:
1. Measure metrics for 2 weeks
2. Compare against thresholds
3. If threshold exceeded → Add complexity
4. If below threshold → Continue monitoring

**Philosophy**: Ruthless simplicity until proven otherwise
