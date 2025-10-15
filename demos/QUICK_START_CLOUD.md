# Quick Start Guide for Cloud Agent

## Critical Success Factor
**The agent session MUST remain active until the objective is achieved. The loop cannot stop.**

## 30-Second Start

```bash
cd /Users/ryan/src/msec/atg-0723/azure-tenant-grapher

# 1. Verify environment (2 min)
uv run python --version
az account show

# 2. Check current state (1 min)
ls -ld demos/iteration* | tail -3
cat demos/autonomous_state.json 2>/dev/null || echo "No previous state"

# 3. Launch autonomous loop (NOW IT RUNS FOREVER)
screen -dmS atg_loop bash -c "uv run python scripts/autonomous_replication_loop.py"
screen -dmS atg_monitor bash -c "uv run python scripts/monitor_autonomous_loop.py"

# 4. Monitor (STAY IN THIS LOOP)
while true; do
    clear
    ./scripts/status_dashboard.sh
    sleep 300  # Check every 5 min
done
```

## What This Does

1. **Generates** IaC from Neo4j source tenant data
2. **Validates** Terraform configuration
3. **Deploys** to target tenant
4. **Rescans** target tenant
5. **Checks** fidelity
6. **Repeats** until >= 95% fidelity with 3 consecutive successes

## The Loop Will Run For

Estimated: 12-24 hours

| Hour | Expected Progress |
|------|-------------------|
| 1 | First iteration complete |
| 4 | 4-5 iterations, patterns emerge |
| 8 | 80% fidelity |
| 12 | 95% fidelity |
| 16 | 3 consecutive successes → DONE |

## Full Documentation

1. **CLOUD_HANDOFF_2025-10-15.md** - Complete context (16KB)
2. **CLOUD_AGENT_RUNBOOK.md** - Operational procedures (25KB)
3. **OBJECTIVE.md** - Success criteria (8KB)

## Emergency Commands

```bash
# Check status
screen -r atg_loop  # View main loop (Ctrl+A D to detach)

# Check logs
tail -f demos/autonomous_loop.log

# Stop everything
screen -X -S atg_loop quit
screen -X -S atg_monitor quit

# Restart
screen -dmS atg_loop bash -c "uv run python scripts/autonomous_replication_loop.py"
```

## The ONE Thing to Remember

**DO NOT END THE SESSION UNTIL THE LOOP REPORTS OBJECTIVE ACHIEVED**

The loop will print:
```
════════════════════════════════════════════════════════════
✅ OBJECTIVE ACHIEVED!
Fidelity: 95.x% (target: 95.0%)
Consecutive successes: 3 (needed: 3)
════════════════════════════════════════════════════════════
```

Only then can the session end.

Until then, the agent must monitor, fix issues in parallel agents, and keep the main loop running.
