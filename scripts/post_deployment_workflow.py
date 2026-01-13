#!/usr/bin/env python3
"""
Post-Deployment Workflow

This script runs after iteration 91 deployment completes and continues working toward the objective.

Steps:
1. Verify deployment completion
2. Analyze deployment results
3. Scan target tenant to capture new state
4. Compare source vs target fidelity
5. Identify gaps and plan next iteration
6. Continue working until objective achieved
"""

import json
import subprocess
import time
from pathlib import Path

# Dynamically determine repo root from script location
REPO_ROOT = Path(__file__).parent.parent.resolve()
DEMOS_DIR = REPO_ROOT / "demos"
LOGS_DIR = REPO_ROOT / "logs"
IMESSAGE_TOOL = Path.home() / ".local/bin/imessR"


def send_message(msg: str):
    """Send iMessage notification"""
    try:
        if IMESSAGE_TOOL.exists():
            subprocess.run([str(IMESSAGE_TOOL), msg], timeout=10, capture_output=True)
    except Exception:
        pass


def run_command(cmd: list, cwd: Path = REPO_ROOT, timeout: int = 300):
    """Run command and return output"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def wait_for_deployment():
    """Wait for deployment to complete"""
    log_file = LOGS_DIR / "iteration91_apply.log"

    print("Waiting for deployment to complete...")
    send_message("⏳ Waiting for iteration 91 deployment to complete...")

    while True:
        if not log_file.exists():
            time.sleep(60)
            continue

        with open(log_file) as f:
            content = f.read()

        if "Apply complete!" in content:
            # Parse results
            import re

            match = re.search(r"Apply complete! Resources: (\d+) added", content)
            if match:
                added = int(match.group(1))
                send_message(f"✅ Deployment COMPLETE! {added} resources created")
                return True, added, None

        if "Error:" in content and "Apply complete!" not in content:
            # Check if it failed
            errors = content.count("Error:")
            if errors > 10:  # Significant errors
                send_message(
                    f"❌ Deployment may have failed - {errors} errors detected"
                )
                return False, 0, f"{errors} errors"

        time.sleep(120)  # Check every 2 minutes


def analyze_deployment():
    """Analyze deployment results"""
    print("Analyzing deployment results...")
    send_message("🔍 Analyzing deployment results...")

    iteration_dir = DEMOS_DIR / "iteration91"

    # Check terraform state
    code, stdout, stderr = run_command(
        ["terraform", "show", "-json"], cwd=iteration_dir, timeout=60
    )

    if code == 0:
        try:
            state = json.loads(stdout)
            resources = (
                state.get("values", {}).get("root_module", {}).get("resources", [])
            )
            resource_count = len(resources)

            # Count by type
            type_counts = {}
            for res in resources:
                rtype = res.get("type", "unknown")
                type_counts[rtype] = type_counts.get(rtype, 0) + 1

            print(str(f"Deployed {resource_count} resources"))
            print(str(f"Resource types: {len(type_counts)}"))

            return resource_count, type_counts
        except (FileNotFoundError, json.JSONDecodeError):
            return 0, {}

    return 0, {}


def scan_target_tenant():
    """Scan target tenant to capture new state"""
    print("Scanning target tenant...")
    send_message("🔍 Scanning target tenant DefenderATEVET12...")

    # Run ATG scan for target tenant
    code, stdout, stderr = run_command(
        [
            "uv",
            "run",
            "atg",
            "scan",
            "--tenant-id",
            "c7674d41-af6c-46f5-89a5-d41495d2151e",
        ],
        timeout=1800,  # 30 minutes
    )

    if code == 0:
        send_message("✅ Target tenant scan complete")
        return True
    else:
        send_message(f"⚠️ Target tenant scan failed: {stderr[:100]}")
        return False


def compare_tenants():
    """Compare source vs target tenant in Neo4j"""
    print("Comparing source vs target tenants...")
    send_message("📊 Comparing source vs target tenants...")

    # TODO: Implement actual comparison using Neo4j queries
    # For now, just placeholder

    return {
        "source_nodes": 561,  # From earlier query
        "target_nodes": 0,  # Will be updated after scan
        "fidelity_percent": 0,
    }


def main():
    """Main workflow"""
    send_message("🤖 Post-deployment workflow starting...")

    # Step 1: Wait for deployment
    success, resource_count, error = wait_for_deployment()

    if not success:
        send_message(f"❌ Deployment failed: {error}. Manual intervention needed.")
        return

    # Step 2: Analyze deployment
    actual_count, type_counts = analyze_deployment()

    # Step 3: Scan target tenant
    scan_success = scan_target_tenant()

    if not scan_success:
        send_message("⚠️ Target scan failed, but deployment succeeded. Continuing...")

    # Step 4: Compare tenants
    compare_tenants()

    # Step 5: Report results
    send_message(
        f"📊 Deployment Summary:\n"
        f"- Deployed: {resource_count} resources\n"
        f"- Types: {len(type_counts)}\n"
        f"- Next: Generate iteration 92 with fixes"
    )

    # Step 6: Continue iteration (future work)
    print("Post-deployment workflow complete!")
    send_message("✅ Post-deployment workflow complete. Ready for next iteration.")


if __name__ == "__main__":
    main()
