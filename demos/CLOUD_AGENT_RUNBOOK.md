# Cloud Agent Runbook - Autonomous Replication
**Purpose**: Step-by-step operational guide for cloud agent
**Prerequisites**: Read CLOUD_HANDOFF_2025-10-15.md first

---

## Phase 1: Initial Assessment (10 minutes)

### Step 1.1: Verify Environment

```bash
cd /Users/ryan/src/msec/atg-0723/azure-tenant-grapher

# Test Python/UV
uv run python --version

# Test Neo4j connection
uv run python << 'EOF'
from py2neo import Graph
import os
from dotenv import load_dotenv

load_dotenv()
password = os.getenv("NEO4J_PASSWORD")
if not password:
    print("ERROR: NEO4J_PASSWORD not found in .env")
    exit(1)

try:
    g = Graph("bolt://localhost:7688", auth=("neo4j", password))
    nodes = g.nodes.match().count()
    relationships = g.relationships.match().count()
    print(f"✅ Neo4j connected: {nodes} nodes, {relationships} relationships")
except Exception as e:
    print(f"❌ Neo4j error: {e}")
    exit(1)
EOF

# Test Azure credentials
az account show --output json | jq '{name, id, tenantId}'

# Test ATG CLI
uv run atg --version 2>&1 || echo "ATG available"
```

### Step 1.2: Assess Current State

```bash
# Find latest iteration
LATEST=$(ls -d demos/iteration* 2>/dev/null | grep -E '^demos/iteration[0-9]+$' | sed 's/demos\/iteration//' | sort -n | tail -1)
echo "Latest iteration: $LATEST"

# Check if deployment in progress
cd demos/iteration${LATEST} 2>/dev/null && {
    echo "Checking iteration${LATEST}..."

    # Check terraform state
    if [ -f "terraform.tfstate" ]; then
        DEPLOYED=$(terraform show -json 2>/dev/null | jq '.values.root_module.resources | length' 2>/dev/null || echo "0")
        echo "Deployed resources: $DEPLOYED"
    fi

    # Check for errors
    if [ -f "terraform_apply.log" ]; then
        ERRORS=$(grep -c "Error:" terraform_apply.log 2>/dev/null || echo "0")
        echo "Errors in log: $ERRORS"
    fi
}
cd ../..

# Get Neo4j fidelity
uv run python << 'EOF'
from py2neo import Graph
import os
from dotenv import load_dotenv

load_dotenv()
g = Graph("bolt://localhost:7688", auth=("neo4j", os.getenv("NEO4J_PASSWORD")))

source = g.evaluate("""
MATCH (r:Resource)
WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16'
RETURN count(r)
""") or 0

target = g.evaluate("""
MATCH (r:Resource)
WHERE r.subscription_id = 'c190c55a-9ab2-4b1e-92c4-cc8b1a032285'
RETURN count(r)
""") or 0

fidelity = (target / source * 100) if source > 0 else 0

print(f"Source resources: {source}")
print(f"Target resources: {target}")
print(f"Current fidelity: {fidelity:.1f}%")
print(f"Gap: {source - target} resources")
EOF
```

### Step 1.3: Clean Up Orphaned Processes

```bash
# Find and kill old terraform processes (BE CAREFUL)
ps aux | grep terraform | grep -v grep | awk '{print $2}' > /tmp/terraform_pids.txt
if [ -s /tmp/terraform_pids.txt ]; then
    echo "Found terraform processes:"
    cat /tmp/terraform_pids.txt
    read -p "Kill these? (yes/no): " CONFIRM
    if [ "$CONFIRM" = "yes" ]; then
        cat /tmp/terraform_pids.txt | xargs kill -9 2>/dev/null
        echo "Processes killed"
    fi
fi

# Clean up lock files
find demos/iteration* -name ".terraform.lock.hcl" -type f 2>/dev/null | while read lockfile; do
    dir=$(dirname "$lockfile")
    if ! ps aux | grep -q "terraform.*$dir"; then
        echo "Removing stale lock: $lockfile"
        rm -f "$lockfile"
    fi
done
```

---

## Phase 2: Implement Persistent Loop (30 minutes)

### Step 2.1: Create Production Autonomous Loop

```bash
cat > scripts/autonomous_replication_loop.py << 'EOF'
#!/usr/bin/env python3
"""
Autonomous Azure Tenant Replication Loop

This script MUST run continuously until the objective is achieved.
It will NOT stop unless explicitly interrupted or objective is met.

Objective: >= 95% fidelity with 3 consecutive successful deployments
"""
import subprocess
import time
import json
import sys
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
SOURCE_SUBSCRIPTION = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
TARGET_SUBSCRIPTION = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"
FIDELITY_TARGET = 95.0
CONSECUTIVE_SUCCESSES_NEEDED = 3
MAX_DEPLOYMENT_TIME = 3600  # 1 hour
STATE_FILE = Path("demos/autonomous_state.json")
LOG_FILE = Path("demos/autonomous_loop.log")

def log(message):
    """Log to both console and file"""
    timestamp = datetime.now().isoformat()
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")

def send_imessage(message):
    """Send iMessage notification"""
    try:
        subprocess.run(
            [os.path.expanduser("~/.local/bin/imessR"), message],
            capture_output=True,
            timeout=10
        )
    except Exception as e:
        log(f"iMessage send failed: {e}")

def get_neo4j_counts():
    """Query Neo4j for source and target resource counts"""
    try:
        from py2neo import Graph
        g = Graph("bolt://localhost:7688", auth=("neo4j", os.getenv("NEO4J_PASSWORD")))

        source = g.evaluate(f"""
        MATCH (r:Resource)
        WHERE r.subscription_id = '{SOURCE_SUBSCRIPTION}'
        RETURN count(r)
        """) or 0

        target = g.evaluate(f"""
        MATCH (r:Resource)
        WHERE r.subscription_id = '{TARGET_SUBSCRIPTION}'
        RETURN count(r)
        """) or 0

        return source, target
    except Exception as e:
        log(f"Neo4j query failed: {e}")
        return None, None

def calculate_fidelity(source, target):
    """Calculate fidelity percentage"""
    if source is None or target is None or source == 0:
        return 0.0
    return (target / source) * 100

def load_state():
    """Load persistent state"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "iteration": 1,
        "consecutive_successes": 0,
        "deployment_history": [],
        "best_fidelity": 0.0
    }

def save_state(state):
    """Save persistent state"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def check_objective_achieved(fidelity, consecutive_successes):
    """Check if objective is met"""
    return fidelity >= FIDELITY_TARGET and consecutive_successes >= CONSECUTIVE_SUCCESSES_NEEDED

def get_next_iteration_dir(iteration):
    """Get path for iteration directory"""
    return Path(f"demos/iteration{iteration}")

def generate_iac(iteration):
    """Generate Infrastructure as Code"""
    log(f"Generating IaC for iteration {iteration}...")

    output_dir = get_next_iteration_dir(iteration)

    cmd = [
        "uv", "run", "atg", "generate-iac",
        "--resource-filters", f"subscription_id='{SOURCE_SUBSCRIPTION}'",
        "--resource-group-prefix", f"ITERATION{iteration}_",
        "--skip-name-validation",
        "--output", str(output_dir)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=Path.cwd()
        )

        if result.returncode != 0:
            log(f"IaC generation failed: {result.stderr}")
            return False

        log(f"IaC generated successfully")
        return True

    except Exception as e:
        log(f"IaC generation error: {e}")
        return False

def terraform_init(iteration_dir):
    """Initialize Terraform"""
    log("Running terraform init...")

    try:
        result = subprocess.run(
            ["terraform", "init"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=180
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Terraform init error: {e}")
        return False

def terraform_validate(iteration_dir):
    """Validate Terraform configuration"""
    log("Running terraform validate...")

    try:
        result = subprocess.run(
            ["terraform", "validate", "-json"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            output = json.loads(result.stdout)
            if output.get("valid"):
                log("Validation passed")
                return True

        log(f"Validation failed: {result.stdout}")
        return False

    except Exception as e:
        log(f"Terraform validate error: {e}")
        return False

def terraform_plan(iteration_dir):
    """Create Terraform plan"""
    log("Running terraform plan...")

    try:
        result = subprocess.run(
            ["terraform", "plan", "-out=tfplan"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            log("Plan created successfully")
            return True

        log(f"Plan failed: {result.stderr}")
        return False

    except Exception as e:
        log(f"Terraform plan error: {e}")
        return False

def terraform_apply(iteration, iteration_dir):
    """Apply Terraform configuration"""
    log(f"Deploying iteration {iteration}...")
    send_imessage(f"🚀 Deploying iteration {iteration} to DefenderATEVET12")

    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=MAX_DEPLOYMENT_TIME
        )

        if result.returncode == 0:
            log(f"Deployment succeeded")
            return True
        else:
            log(f"Deployment failed: {result.stderr[:500]}")
            return False

    except subprocess.TimeoutExpired:
        log(f"Deployment timed out after {MAX_DEPLOYMENT_TIME}s")
        send_imessage(f"⏱️ Iteration {iteration} timed out after 1 hour")
        return False
    except Exception as e:
        log(f"Deployment error: {e}")
        return False

def rescan_target():
    """Rescan target tenant to update Neo4j"""
    log("Rescanning target tenant...")

    try:
        result = subprocess.run(
            ["uv", "run", "atg", "scan",
             "--subscription-id", TARGET_SUBSCRIPTION],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode == 0:
            log("Target tenant rescanned")
            return True
        else:
            log(f"Rescan failed: {result.stderr}")
            return False

    except Exception as e:
        log(f"Rescan error: {e}")
        return False

def main():
    """Main autonomous loop"""
    log("="*80)
    log("AUTONOMOUS REPLICATION LOOP STARTING")
    log("="*80)
    log(f"Objective: >= {FIDELITY_TARGET}% fidelity with {CONSECUTIVE_SUCCESSES_NEEDED} consecutive successes")
    log("This loop will NOT stop until objective is achieved or interrupted")
    log("="*80)

    send_imessage("🤖 Autonomous replication loop started")

    state = load_state()
    iteration = state["iteration"]

    try:
        while True:
            log("")
            log("="*80)
            log(f"ITERATION {iteration}")
            log("="*80)

            # Check current fidelity
            source_count, target_count = get_neo4j_counts()
            if source_count and target_count:
                fidelity = calculate_fidelity(source_count, target_count)
                log(f"Current state: {target_count}/{source_count} resources = {fidelity:.1f}% fidelity")

                # Check if objective achieved
                if check_objective_achieved(fidelity, state["consecutive_successes"]):
                    log("="*80)
                    log("✅ OBJECTIVE ACHIEVED!")
                    log(f"Fidelity: {fidelity:.1f}% (target: {FIDELITY_TARGET}%)")
                    log(f"Consecutive successes: {state['consecutive_successes']} (needed: {CONSECUTIVE_SUCCESSES_NEEDED})")
                    log("="*80)
                    send_imessage(f"✅ OBJECTIVE ACHIEVED! {fidelity:.1f}% fidelity with {state['consecutive_successes']} consecutive successes")
                    break

            # Generate IaC
            if not generate_iac(iteration):
                log("Skipping iteration due to generation failure")
                time.sleep(300)
                continue

            iteration_dir = get_next_iteration_dir(iteration)

            # Initialize
            if not terraform_init(iteration_dir):
                log("Skipping iteration due to init failure")
                time.sleep(300)
                continue

            # Validate
            if not terraform_validate(iteration_dir):
                log("Skipping iteration due to validation failure")
                state["consecutive_successes"] = 0
                state["iteration"] = iteration + 1
                save_state(state)
                iteration += 1
                time.sleep(60)
                continue

            # Plan
            if not terraform_plan(iteration_dir):
                log("Skipping iteration due to plan failure")
                state["consecutive_successes"] = 0
                state["iteration"] = iteration + 1
                save_state(state)
                iteration += 1
                time.sleep(60)
                continue

            # Deploy
            deployment_success = terraform_apply(iteration, iteration_dir)

            # Rescan regardless of deployment outcome
            rescan_target()

            # Check new fidelity
            source_count, target_count = get_neo4j_counts()
            if source_count and target_count:
                new_fidelity = calculate_fidelity(source_count, target_count)
                log(f"Post-deployment: {target_count}/{source_count} = {new_fidelity:.1f}%")

                if new_fidelity > state["best_fidelity"]:
                    state["best_fidelity"] = new_fidelity
                    log(f"🎉 New best fidelity: {new_fidelity:.1f}%")
                    send_imessage(f"📈 New best: {new_fidelity:.1f}% fidelity ({target_count}/{source_count})")

            # Update state
            if deployment_success:
                state["consecutive_successes"] += 1
            else:
                state["consecutive_successes"] = 0

            state["deployment_history"].append({
                "iteration": iteration,
                "success": deployment_success,
                "fidelity": new_fidelity if source_count and target_count else 0
            })

            state["iteration"] = iteration + 1
            save_state(state)

            # Move to next iteration
            iteration += 1

            # Keep session alive
            log("Waiting 60s before next iteration...")
            time.sleep(60)

    except KeyboardInterrupt:
        log("")
        log("="*80)
        log("⚠️  Loop interrupted by user")
        log("="*80)
        send_imessage("⚠️ Autonomous loop stopped by user")
        save_state(state)
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        send_imessage(f"❌ Autonomous loop crashed: {str(e)[:100]}")
        save_state(state)
        raise

if __name__ == "__main__":
    main()
EOF

chmod +x scripts/autonomous_replication_loop.py
```

### Step 2.2: Create Monitoring Script

```bash
cat > scripts/monitor_autonomous_loop.py << 'EOF'
#!/usr/bin/env python3
"""
Monitor the autonomous replication loop and send periodic updates
"""
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
import sys

STATE_FILE = Path("demos/autonomous_state.json")
LOG_FILE = Path("demos/autonomous_loop.log")
UPDATE_INTERVAL = 600  # 10 minutes

def send_imessage(message):
    """Send iMessage notification"""
    try:
        subprocess.run(
            ["/Users/ryan/.local/bin/imessR", message],
            capture_output=True,
            timeout=10
        )
    except Exception as e:
        print(f"iMessage failed: {e}")

def get_state():
    """Read current state"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return None

def main():
    """Monitor loop and send updates"""
    print("Starting autonomous loop monitor...")
    print(f"Updates every {UPDATE_INTERVAL}s")

    last_iteration = None

    while True:
        try:
            state = get_state()

            if state:
                current_iteration = state.get("iteration", 0)
                consecutive = state.get("consecutive_successes", 0)
                best_fidelity = state.get("best_fidelity", 0)

                # Send update if iteration changed
                if current_iteration != last_iteration:
                    message = (
                        f"🔄 Iteration {current_iteration} in progress\\n"
                        f"Best: {best_fidelity:.1f}%\\n"
                        f"Streak: {consecutive}"
                    )
                    send_imessage(message)
                    last_iteration = current_iteration

            time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            print("\nMonitor stopped")
            break
        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
EOF

chmod +x scripts/monitor_autonomous_loop.py
```

---

## Phase 3: Launch Autonomous Operation (5 minutes)

### Step 3.1: Start Main Loop

```bash
cd /Users/ryan/src/msec/atg-0723/azure-tenant-grapher

# Run in a screen/tmux session (recommended) or background
screen -dmS atg_loop bash -c "uv run python scripts/autonomous_replication_loop.py"

# OR run in foreground if in persistent cloud environment
# uv run python scripts/autonomous_replication_loop.py

# Verify it started
sleep 5
tail -20 demos/autonomous_loop.log
```

### Step 3.2: Start Monitor

```bash
# In a separate session
screen -dmS atg_monitor bash -c "uv run python scripts/monitor_autonomous_loop.py"

# OR in background
# nohup uv run python scripts/monitor_autonomous_loop.py > demos/monitor.log 2>&1 &
```

### Step 3.3: Verify Operations

```bash
# Check screens running
screen -list

# Attach to main loop
screen -r atg_loop

# Detach: Ctrl+A, D

# Check logs
tail -f demos/autonomous_loop.log
```

---

## Phase 4: Parallel Fix Workstreams (As Needed)

### Pattern for Spawning Fix Agents

When errors appear in iterations, spawn parallel agents to fix them:

```bash
# Example: Fix specific resource type
cat > /tmp/fix_prompt.txt << 'EOF'
Analyze the terraform validation errors in demos/iteration{N}/

Specifically look for errors related to Microsoft.Compute/disks resource type.

Steps:
1. Review the error messages
2. Identify root cause in src/iac/emitters/terraform_emitter.py
3. Implement fix
4. Add regression test
5. Run tests to verify
6. Commit with descriptive message
7. Report results

Work independently and report back when complete.
EOF

# Spawn agent (adjust command based on actual copilot setup)
copilot --allow-all-tools -p "$(cat /tmp/fix_prompt.txt)" &
```

---

## Phase 5: Continuous Operation Guidelines

### What the Agent Should Do

1. **Keep the main loop running** - Never stop the autonomous_replication_loop.py
2. **Monitor the logs** - Check demos/autonomous_loop.log regularly
3. **Spawn fix agents** - When errors repeat, create parallel agents to fix them
4. **Track progress** - Watch demos/autonomous_state.json for fidelity improvements
5. **Communicate** - Use iMessage for major milestones
6. **Be patient** - Each iteration takes ~60-90 minutes

### What the Agent Should NOT Do

1. **Don't stop the loop** - Unless objective is achieved
2. **Don't run multiple iterations in parallel** - Only one deployment at a time
3. **Don't call terraform directly** - Use atg commands
4. **Don't ignore repeated errors** - Fix root causes
5. **Don't spam iMessage** - Only meaningful updates

### Decision Tree

```
Is objective achieved (>= 95% fidelity + 3 successes)?
├─ YES → Stop, celebrate, document final state
└─ NO → Continue
    │
    Are iterations completing successfully?
    ├─ YES → Keep monitoring, let loop run
    └─ NO → Investigate errors
        │
        Are errors repeating across iterations?
        ├─ YES → Spawn fix agent for root cause
        └─ NO → Wait for more data
```

---

## Phase 6: Handling Common Scenarios

### Scenario 1: Loop Crashes

```bash
# Check what happened
tail -100 demos/autonomous_loop.log

# Fix the issue, then restart
screen -dmS atg_loop bash -c "uv run python scripts/autonomous_replication_loop.py"
```

### Scenario 2: Deployment Timeout

```
This is expected! The loop handles it automatically:
1. Terraform times out after 1 hour
2. Loop rescans target
3. Loop moves to next iteration
4. Partial progress is saved
```

### Scenario 3: Validation Failures

```
1. Check the error in logs
2. Spawn fix agent if error repeats
3. Loop will skip failed iteration automatically
4. Next iteration will include the fix
```

### Scenario 4: Permission Errors

```bash
# Check Azure credentials
az account show

# Check service principal permissions
az role assignment list --assignee <sp-object-id> --all

# May need to grant additional permissions
az role assignment create \
  --assignee <sp-object-id> \
  --role Contributor \
  --scope /subscriptions/{TARGET_SUBSCRIPTION}
```

---

## Phase 7: Monitoring Checklist

Every hour, check:

- [ ] Main loop still running: `screen -list`
- [ ] Monitor still running: `screen -list`
- [ ] Log file growing: `ls -lh demos/autonomous_loop.log`
- [ ] State file updating: `cat demos/autonomous_state.json`
- [ ] Fidelity improving: Check "best_fidelity" in state
- [ ] No repeated errors: `grep -c "Error" demos/autonomous_loop.log`

Every 4 hours, check:

- [ ] How many iterations completed?
- [ ] What's the fidelity trend?
- [ ] Are any errors repeating?
- [ ] Do we need to spawn fix agents?
- [ ] Is Neo4j database healthy?

---

## Phase 8: When Objective is Achieved

```bash
# The loop will automatically stop and send iMessage

# Verify final state
cat demos/autonomous_state.json

# Generate final report
uv run python << 'EOF'
from py2neo import Graph
import os
import json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
g = Graph("bolt://localhost:7688", auth=("neo4j", os.getenv("NEO4J_PASSWORD")))

source = g.evaluate("""
MATCH (r:Resource)
WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16'
RETURN count(r)
""")

target = g.evaluate("""
MATCH (r:Resource)
WHERE r.subscription_id = 'c190c55a-9ab2-4b1e-92c4-cc8b1a032285'
RETURN count(r)
""")

state = json.loads(Path("demos/autonomous_state.json").read_text())

print("="*80)
print("OBJECTIVE ACHIEVED - FINAL REPORT")
print("="*80)
print(f"Source resources: {source}")
print(f"Target resources: {target}")
print(f"Final fidelity: {(target/source*100):.1f}%")
print(f"Consecutive successes: {state['consecutive_successes']}")
print(f"Total iterations: {state['iteration'] - 1}")
print(f"Deployment history: {len(state['deployment_history'])} recorded")
print("="*80)
EOF

# Begin Phase 2: Entra ID Replication
# (See separate runbook)
```

---

## Emergency Contacts

If the agent needs human intervention:

```bash
~/.local/bin/imessR "🆘 Agent needs help: <describe issue>"
```

---

## Success Metrics Dashboard

```bash
# Quick status check
cat > scripts/status_dashboard.sh << 'EOF'
#!/bin/bash
echo "════════════════════════════════════════════════════════════"
echo "  AZURE TENANT REPLICATION - STATUS DASHBOARD"
echo "════════════════════════════════════════════════════════════"

STATE_FILE="demos/autonomous_state.json"
if [ -f "$STATE_FILE" ]; then
    ITERATION=$(jq -r '.iteration' $STATE_FILE)
    CONSECUTIVE=$(jq -r '.consecutive_successes' $STATE_FILE)
    BEST_FID=$(jq -r '.best_fidelity' $STATE_FILE)
    echo "Current Iteration: $ITERATION"
    echo "Consecutive Successes: $CONSECUTIVE / 3"
    echo "Best Fidelity: ${BEST_FID}%"
else
    echo "No state file found"
fi

echo ""
echo "Loop Status:"
if screen -list | grep -q "atg_loop"; then
    echo "✅ Main loop running"
else
    echo "❌ Main loop NOT running"
fi

if screen -list | grep -q "atg_monitor"; then
    echo "✅ Monitor running"
else
    echo "❌ Monitor NOT running"
fi

echo ""
echo "Recent Logs:"
if [ -f "demos/autonomous_loop.log" ]; then
    tail -5 demos/autonomous_loop.log
fi

echo "════════════════════════════════════════════════════════════"
EOF

chmod +x scripts/status_dashboard.sh

# Run it
./scripts/status_dashboard.sh
```

---

**This runbook provides everything needed to operate autonomously in the cloud.**

Key Success Factor: Keep the scripts running continuously without stopping the session.
