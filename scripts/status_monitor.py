#!/usr/bin/env python3
"""
Session-integrated continuous loop
This script is meant to be monitored BY the Claude session, not run independently
It outputs structured JSON status updates that the session can parse and act on
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Dynamically determine repo root from script location
REPO_ROOT = Path(__file__).parent.parent.resolve()
os.chdir(REPO_ROOT)


def log_status(status_type, data):
    """Output structured JSON status"""
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": status_type,
        "data": data,
    }
    print(f"STATUS_JSON: {json.dumps(status)}", flush=True)


def get_neo4j_counts():
    """Get resource counts from Neo4j"""
    script = """
import os
from neo4j import GraphDatabase

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
password = os.getenv('NEO4J_PASSWORD', '')
if not password:
    with open('.env') as f:
        for line in f:
            if 'NEO4J_PASSWORD=' in line:
                password = line.split('=', 1)[1].strip().strip('"')
                break

driver = GraphDatabase.driver(uri, auth=('neo4j', password))
with driver.session() as session:
    source = session.run(
        "MATCH (r:Resource) WHERE r.subscription_id = $sub RETURN count(r) as count",
        sub='9b00bc5e-9abc-45de-9958-02a9d9277b16'
    ).single()['count']

    target = session.run(
        "MATCH (r:Resource) WHERE r.subscription_id = $sub RETURN count(r) as count",
        sub='c190c55a-9ab2-4b1e-92c4-cc8b1a032285'
    ).single()['count']

    print(f"{source},{target}")
driver.close()
"""

    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            source, target = map(int, result.stdout.strip().split(","))
            return source, target
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return 0, 0


def get_latest_iteration():
    """Get latest iteration number"""
    demos_dir = REPO_ROOT / "demos"
    iterations = [
        d.name
        for d in demos_dir.iterdir()
        if d.is_dir() and d.name.startswith("iteration")
    ]
    if not iterations:
        return 0
    numbers = [int(i.replace("iteration", "")) for i in iterations]
    return max(numbers)


def validate_iteration(iteration_num):
    """Validate an iteration"""
    iter_dir = REPO_ROOT / "demos" / f"iteration{iteration_num}"

    if not iter_dir.exists():
        return False, ["Iteration directory does not exist"]

    # terraform init
    result = subprocess.run(
        ["terraform", "init", "-backend=false"],
        cwd=iter_dir,
        capture_output=True,
        timeout=120,
    )

    if result.returncode != 0:
        return False, ["terraform init failed"]

    # terraform validate
    result = subprocess.run(
        ["terraform", "validate", "-json"],
        cwd=iter_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            if data.get("valid", False):
                return True, []
            else:
                errors = [
                    d.get("summary", "Unknown") for d in data.get("diagnostics", [])
                ]
                return False, errors
        except json.JSONDecodeError:
            return False, ["Failed to parse validation output"]

    return False, ["Validation failed with non-zero exit"]


def main():
    """Main monitoring loop"""
    log_status("started", {"repo": str(REPO_ROOT)})

    check_count = 0
    while True:
        check_count += 1

        # Get current state
        latest_iter = get_latest_iteration()
        source_count, target_count = get_neo4j_counts()
        fidelity = (target_count / source_count * 100) if source_count > 0 else 0.0

        # Validate latest iteration
        validation_passed, errors = validate_iteration(latest_iter)

        # Output status
        log_status(
            "check",
            {
                "check_number": check_count,
                "latest_iteration": latest_iter,
                "source_resources": source_count,
                "target_resources": target_count,
                "fidelity_percent": round(fidelity, 2),
                "validation_passed": validation_passed,
                "validation_errors": errors[:5] if errors else [],
                "objective_achieved": validation_passed and fidelity > 95,
            },
        )

        # Check if objective achieved
        if validation_passed and fidelity > 95:
            log_status(
                "objective_achieved",
                {
                    "fidelity": fidelity,
                    "source_count": source_count,
                    "target_count": target_count,
                },
            )
            break

        # Sleep 2 minutes between checks
        time.sleep(120)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_status("interrupted", {})
        sys.exit(0)
    except Exception as e:
        log_status("error", {"error": str(e)})
        import traceback

        traceback.print_exc()
        sys.exit(1)
