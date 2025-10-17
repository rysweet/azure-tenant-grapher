#!/usr/bin/env python3
"""
Continuous monitoring script that polls deployment status and sends updates.
Runs forever until explicitly stopped.
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

IMESSAGE_TOOL = Path.home() / ".local" / "bin" / "imessR"
ITERATION_DIR = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/demos")
CURRENT_ITERATION = 97


def send_update(msg):
    """Send iMessage update"""
    try:
        if IMESSAGE_TOOL.exists():
            subprocess.run([str(IMESSAGE_TOOL), msg], timeout=10, capture_output=True)
    except Exception as e:
        print(f"Failed to send update: {e}")


def check_terraform_status(iteration):
    """Check terraform deployment status"""
    iter_dir = ITERATION_DIR / f"iteration{iteration}"
    state_file = iter_dir / "terraform.tfstate"

    if not state_file.exists():
        return {"status": "not_started", "resources": 0}

    try:
        with open(state_file) as f:
            state = json.load(f)
            resource_count = len(state.get("resources", []))
            return {"status": "running", "resources": resource_count}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_process_running(pid):
    """Check if a process is still running"""
    try:
        result = subprocess.run(["ps", "-p", str(pid)], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def main():
    print("Starting continuous monitoring...")
    print(f"Monitoring iteration {CURRENT_ITERATION}")

    last_resource_count = 0
    last_update_time = time.time()
    update_interval = 300  # 5 minutes

    while True:
        # Check terraform status
        status = check_terraform_status(CURRENT_ITERATION)

        # Check if terraform process is running
        terraform_running = False
        try:
            result = subprocess.run(
                ["pgrep", "-f", "terraform apply"], capture_output=True, timeout=5
            )
            terraform_running = result.returncode == 0
        except:
            pass

        current_time = time.time()
        resource_count = status.get("resources", 0)

        # Send update if significant change or time elapsed
        should_update = (
            resource_count != last_resource_count
            or (current_time - last_update_time) >= update_interval
        )

        if should_update:
            if terraform_running:
                msg = f"🔄 Deployment ACTIVE: {resource_count} resources created in iteration {CURRENT_ITERATION}"
            elif resource_count > 0:
                msg = f"✅ Deployment COMPLETE: {resource_count} resources in iteration {CURRENT_ITERATION}"
            else:
                msg = f"⏳ Deployment PENDING for iteration {CURRENT_ITERATION}"

            print(f"{datetime.now().isoformat()} - {msg}")
            send_update(msg)

            last_resource_count = resource_count
            last_update_time = current_time

        # If deployment complete and terraform not running, we're done
        if resource_count > 0 and not terraform_running:
            print("\n✓ Deployment completed!")
            send_update(
                f"🎉 Iteration {CURRENT_ITERATION} deployment finished with {resource_count} resources!"
            )
            break

        # Brief pause before next check
        time.sleep(30)

    print("Monitoring complete")


if __name__ == "__main__":
    main()
