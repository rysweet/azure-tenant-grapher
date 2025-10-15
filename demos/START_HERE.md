# 🚀 START HERE - Cloud Agent Onboarding

**You are the cloud agent continuing autonomous Azure tenant replication.**

---

## Step 1: Read This (2 minutes)

You need to replicate Azure tenant DefenderATEVET17 → DefenderATEVET12 with 100% fidelity.

**Critical Lesson**: Previous local sessions failed because the agent session ended, killing all background processes. **You must keep your session alive until the objective is achieved.**

---

## Step 2: Read These Documents (10 minutes)

**In this exact order:**

1. **QUICK_START_CLOUD.md** (2 min) - How to launch
2. **MANIFEST_CLOUD_HANDOFF.md** (3 min) - Overview of everything
3. **CLOUD_AGENT_RUNBOOK.md** (5 min) - Detailed procedures

Optional but recommended:
- OBJECTIVE.md - Full success criteria
- CLOUD_HANDOFF_2025-10-15.md - Complete context

---

## Step 3: Execute (30 seconds)

```bash
cd /Users/ryan/src/msec/atg-0723/azure-tenant-grapher

# Launch autonomous systems
screen -dmS atg_loop bash -c "uv run python scripts/autonomous_replication_loop.py"
screen -dmS atg_monitor bash -c "uv run python scripts/monitor_autonomous_loop.py"

# Enter monitoring mode (STAY HERE)
while true; do
    if grep -q "OBJECTIVE ACHIEVED" demos/autonomous_loop.log 2>/dev/null; then
        echo "✅ Done!"
        break
    fi
    ./scripts/status_dashboard.sh 2>/dev/null || sleep 60
    sleep 300
done
```

---

## Step 4: Monitor (12-24 hours)

The loop runs automatically. You just:
- Monitor for errors
- Spawn fix agents when needed
- Send status updates
- **Never exit until objective achieved**

---

## The ONE Rule

**DO NOT END YOUR SESSION UNTIL YOU SEE THIS:**

```
════════════════════════════════════════════════════════════
✅ OBJECTIVE ACHIEVED!
Fidelity: 95.x% (target: 95.0%)
Consecutive successes: 3 (needed: 3)
════════════════════════════════════════════════════════════
```

---

## Quick Reference

| File | Purpose |
|------|---------|
| START_HERE.md | You are here |
| QUICK_START_CLOUD.md | 30-second start guide |
| MANIFEST_CLOUD_HANDOFF.md | Handoff overview |
| CLOUD_AGENT_RUNBOOK.md | Step-by-step procedures |
| OBJECTIVE.md | Success criteria |
| CLOUD_HANDOFF_2025-10-15.md | Complete context |

| Script | Purpose |
|--------|---------|
| scripts/autonomous_replication_loop.py | Main loop (runs forever) |
| scripts/monitor_autonomous_loop.py | Status updates |
| scripts/status_dashboard.sh | Quick status |

| State File | Purpose |
|------------|---------|
| demos/autonomous_state.json | Current iteration, fidelity |
| demos/autonomous_loop.log | Detailed log |
| demos/iteration{N}/ | Generated IaC |

---

**Now go read QUICK_START_CLOUD.md and get started! 🚀**
