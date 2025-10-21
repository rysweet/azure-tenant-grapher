#!/usr/bin/env python3
"""
Autonomous Continuous Executor for Azure Tenant Grapher
This script runs continuously until the objective is achieved.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher")
DEMOS_DIR = PROJECT_ROOT / "demos"
IMESS_TOOL = Path.home() / ".local/bin/imessR"


def send_imessage(message: str):
    """Send iMessage update"""
    try:
        subprocess.run([str(IMESS_TOOL), message], check=False, timeout=10)
    except Exception as e:
        print(f"Failed to send iMessage: {e}")


def run_cypher_query(query: str) -> dict:
    """Run a Cypher query against Neo4j"""
    try:
        result = subprocess.run(
            ["cypher-shell", "-u", "neo4j", "-p", "password", query],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as e:
        return {"error": str(e)}


def get_resource_counts() -> dict:
    """Get resource counts from Neo4j for both tenants"""
    source_query = """
    MATCH (r:Resource)
    WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16'
    RETURN count(r) as count
    """

    target_query = """
    MATCH (r:Resource)
    WHERE r.subscription_id = 'c190c55a-9ab2-4b1e-92c4-cc8b1a032285'
    RETURN count(r) as count
    """

    source_result = run_cypher_query(source_query)
    target_result = run_cypher_query(target_query)

    # Parse results
    source_count = 0
    target_count = 0

    try:
        if source_result.get("returncode") == 0:
            match = re.search(r"(\d+)", source_result["stdout"])
            if match:
                source_count = int(match.group(1))

        if target_result.get("returncode") == 0:
            match = re.search(r"(\d+)", target_result["stdout"])
            if match:
                target_count = int(match.group(1))
    except Exception as e:
        print(f"Error parsing Neo4j results: {e}")

    return {
        "source": source_count,
        "target": target_count,
        "fidelity": (target_count / source_count * 100) if source_count > 0 else 0,
    }


def get_latest_iteration() -> int:
    """Find the latest iteration number"""
    iterations = list(DEMOS_DIR.glob("iteration*"))
    if not iterations:
        return 0

    max_iter = 0
    for iter_dir in iterations:
        match = re.search(r"iteration(\d+)", iter_dir.name)
        if match:
            max_iter = max(max_iter, int(match.group(1)))

    return max_iter


def check_iteration_status(iteration_num: int) -> dict:
    """Check the status of a specific iteration"""
    iter_dir = DEMOS_DIR / f"iteration{iteration_num}"

    if not iter_dir.exists():
        return {"status": "not_found"}

    # Check if terraform files exist
    tf_json = iter_dir / "main.tf.json"
    if not tf_json.exists():
        return {"status": "no_terraform"}

    # Check if terraform init has been run
    terraform_dir = iter_dir / ".terraform"
    if not terraform_dir.exists():
        return {"status": "not_initialized"}

    # Check if terraform plan exists
    tfplan = iter_dir / "tfplan"
    if not tfplan.exists():
        return {"status": "not_planned"}

    # Check if terraform apply is in progress or complete
    tfstate = iter_dir / "terraform.tfstate"
    if not tfstate.exists():
        return {"status": "not_applied"}

    # Read tfstate to check success
    try:
        with open(tfstate) as f:
            state = json.load(f)
            resources = state.get("resources", [])
            return {"status": "applied", "resource_count": len(resources)}
    except Exception as e:
        return {"status": "apply_error", "error": str(e)}


def spawn_gap_fixer_agent(gap_type: str, details: dict) -> subprocess.Popen:
    """Spawn a copilot subagent to fix a specific gap"""

    # Prepare the prompt based on gap type
    prompt_map = {
        "missing_resource_type": f"""
You are a code fixing agent for Azure Tenant Grapher.

Gap Type: Missing Resource Type Support
Resource Type: {details.get("resource_type")}
Count: {details.get("count")} resources

Your task:
1. Read src/iac/emitters/terraform_emitter.py
2. Add mapping for {details.get("resource_type")} in AZURE_TO_TERRAFORM_MAPPING
3. Implement _generate_resource logic for this type
4. Add tests in tests/iac/test_terraform_emitter.py
5. Commit your changes with message: "feat(iac): add support for {details.get("resource_type")}"

Use the DEFAULT_WORKFLOW.md workflow.
Work quickly and commit when done.
""",
        "terraform_error": f"""
You are a debugging agent for Azure Tenant Grapher.

Gap Type: Terraform Deployment Error
Iteration: {details.get("iteration")}
Error: {details.get("error")}

Your task:
1. Analyze the error in {details.get("log_file")}
2. Identify the root cause in the terraform_emitter.py code
3. Fix the issue
4. Add tests to prevent regression
5. Commit your changes

Use the DEFAULT_WORKFLOW.md workflow.
Work quickly and commit when done.
""",
        "validation_error": f"""
You are a validation fixing agent for Azure Tenant Grapher.

Gap Type: Validation Error
Iteration: {details.get("iteration")}
Check: {details.get("check_name")}
Error: {details.get("error")}

Your task:
1. Analyze the validation failure
2. Fix the code that generates incorrect IaC
3. Add tests for this validation
4. Commit your changes

Use the DEFAULT_WORKFLOW.md workflow.
Work quickly and commit when done.
""",
    }

    prompt = prompt_map.get(gap_type, f"Fix gap: {gap_type} - {details}")

    # Write prompt to temp file
    prompt_file = (
        PROJECT_ROOT / f".claude/prompts/gap_{gap_type}_{int(time.time())}.txt"
    )
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt)

    # Spawn copilot agent
    cmd = ["copilot", "--allow-all-tools", "-p", prompt]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=PROJECT_ROOT
    )

    return process


def evaluate_objective() -> dict:
    """Evaluate if the objective has been achieved"""
    counts = get_resource_counts()
    latest_iter = get_latest_iteration()

    # Check objective criteria
    fidelity_achieved = counts["fidelity"] >= 95.0

    # Check last 3 iterations for validation success
    consecutive_passes = 0
    for i in range(latest_iter, max(0, latest_iter - 3), -1):
        status = check_iteration_status(i)
        if status.get("status") == "applied":
            consecutive_passes += 1
        else:
            break

    objective_achieved = fidelity_achieved and consecutive_passes >= 3

    return {
        "achieved": objective_achieved,
        "fidelity": counts["fidelity"],
        "source_resources": counts["source"],
        "target_resources": counts["target"],
        "latest_iteration": latest_iter,
        "consecutive_passes": consecutive_passes,
        "criteria": {
            "fidelity_95_percent": fidelity_achieved,
            "three_consecutive_passes": consecutive_passes >= 3,
        },
    }


def main():
    """Main continuous execution loop"""
    send_imessage("🚀 Autonomous executor started - working until objective achieved")

    iteration_count = 0
    active_gap_fixers = []

    while True:
        iteration_count += 1
        timestamp = datetime.now().isoformat()

        print(f"\n{'=' * 80}")
        print(f"Iteration {iteration_count} at {timestamp}")
        print(f"{'=' * 80}")

        # 1. Evaluate objective
        objective_eval = evaluate_objective()
        print(
            f"Objective Status: {'✅ ACHIEVED' if objective_eval['achieved'] else '🔄 In Progress'}"
        )
        print(
            f"Fidelity: {objective_eval['fidelity']:.1f}% ({objective_eval['target_resources']}/{objective_eval['source_resources']})"
        )
        print(f"Latest Iteration: {objective_eval['latest_iteration']}")
        print(f"Consecutive Passes: {objective_eval['consecutive_passes']}")

        if objective_eval["achieved"]:
            send_imessage(
                f"🎉 OBJECTIVE ACHIEVED! Fidelity: {objective_eval['fidelity']:.1f}%"
            )
            print("\n🎉 OBJECTIVE ACHIEVED - Stopping execution")
            sys.exit(0)

        # 2. Check active gap fixers
        completed_fixers = []
        for i, (fixer, gap_type, details) in enumerate(active_gap_fixers):
            poll = fixer.poll()
            if poll is not None:
                completed_fixers.append(i)
                print(f"✅ Gap fixer completed: {gap_type}")
                send_imessage(f"✅ Gap fixer completed: {gap_type}")

        # Remove completed fixers
        for i in reversed(completed_fixers):
            active_gap_fixers.pop(i)

        # 3. Check latest iteration status
        latest_iter = objective_eval["latest_iteration"]
        if latest_iter > 0:
            iter_status = check_iteration_status(latest_iter)
            print(f"Iteration {latest_iter} status: {iter_status.get('status')}")

            # If iteration is complete, generate next one
            if iter_status.get("status") == "applied":
                print(f"Generating iteration {latest_iter + 1}...")

                # Generate next iteration
                cmd = [
                    "uv",
                    "run",
                    "atg",
                    "generate-iac",
                    "--resource-filters",
                    "resourceGroup=~'(?i).*(simuland|SimuLand).*'",
                    "--resource-group-prefix",
                    f"ITERATION{latest_iter + 1}_",
                    "--skip-name-validation",
                    "--output",
                    f"demos/iteration{latest_iter + 1}",
                ]

                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        cwd=PROJECT_ROOT,
                    )
                    print(f"✅ Generated iteration {latest_iter + 1}")
                    send_imessage(f"✅ Generated iteration {latest_iter + 1}")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to generate iteration: {e}")
                    send_imessage(f"❌ Failed to generate iteration {latest_iter + 1}")

        # 4. Send periodic status update
        if iteration_count % 10 == 0:
            send_imessage(
                f"🔄 Autonomous executor cycle {iteration_count}\n"
                f"Fidelity: {objective_eval['fidelity']:.1f}%\n"
                f"Active fixers: {len(active_gap_fixers)}\n"
                f"Iteration: {latest_iter}"
            )

        # 5. Wait before next iteration
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏸️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        send_imessage(f"❌ Autonomous executor error: {e}")
        print(f"Error: {e}")
        sys.exit(1)
