#!/usr/bin/env python3
"""
Continuous monitoring and fixing loop - DOES NOT STOP until objective achieved.
"""

import json
import os
import subprocess
import sys
import time


def send_message(msg):
    """Send iMessage update"""
    try:
        subprocess.run(
            [os.path.expanduser("~/.local/bin/imessR"), msg],
            capture_output=True,
            timeout=5,
        )
    except:
        pass


def wait_for_iteration(iteration_num, max_wait_seconds=600):
    """Wait for iteration to complete"""
    iter_dir = f"demos/iteration{iteration_num}"
    main_tf = f"{iter_dir}/main.tf.json"

    print(f"⏳ Waiting for ITERATION {iteration_num} to complete...")
    waited = 0
    while waited < max_wait_seconds:
        if os.path.exists(main_tf):
            print(f"✅ ITERATION {iteration_num} files found!")
            return True
        time.sleep(5)
        waited += 5
        if waited % 30 == 0:
            print(f"   Still waiting... ({waited}/{max_wait_seconds}s)")

    print(f"❌ ITERATION {iteration_num} did not complete in time")
    return False


def validate_iteration(iteration_num):
    """Validate Terraform and return (success, errors)"""
    iter_dir = f"demos/iteration{iteration_num}"

    print(f"🔍 Validating ITERATION {iteration_num}...")
    os.chdir(iter_dir)

    # Init
    subprocess.run(["terraform", "init", "-upgrade"], capture_output=True, timeout=120)

    # Validate
    result = subprocess.run(
        ["terraform", "validate", "-json"], capture_output=True, timeout=60
    )
    os.chdir("../..")

    if result.returncode == 0:
        print(f"🎉 ITERATION {iteration_num} PASSED VALIDATION!")
        return True, []

    # Parse errors
    try:
        data = json.loads(result.stdout)
        errors = data.get("diagnostics", [])
        error_summary = []
        for err in errors[:10]:  # First 10 errors
            error_summary.append(
                f"{err.get('severity')}: {err.get('summary')} - {err.get('detail', '')[:100]}"
            )
        return False, error_summary
    except:
        return False, ["Failed to parse validation output"]


def generate_next_iteration(iteration_num):
    """Generate next iteration"""
    iter_dir = f"demos/iteration{iteration_num}"
    log_file = f"logs/iteration{iteration_num}_generation.log"

    print(f"🔨 Generating ITERATION {iteration_num}...")

    # Clean up
    subprocess.run(["rm", "-rf", iter_dir])
    subprocess.run(["mkdir", "-p", iter_dir])

    # Generate
    cmd = [
        "uv",
        "run",
        "atg",
        "generate-iac",
        "--resource-group-prefix",
        f"ITERATION{iteration_num}_",
        "--skip-name-validation",
        "--output",
        iter_dir,
    ]

    with open(log_file, "w") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=600)

    return result.returncode == 0


def main():
    """Main continuous loop"""
    iteration = 25
    max_iterations = 100

    send_message(f"🔄 CONTINUOUS LOOP STARTED - monitoring from ITERATION {iteration}")

    while iteration <= max_iterations:
        print(f"\n{'=' * 60}")
        print(f"ITERATION {iteration}")
        print(f"{'=' * 60}\n")

        # Wait for iteration to complete
        if not wait_for_iteration(iteration):
            # Generation failed - try to generate it
            print(f"Attempting to generate ITERATION {iteration}...")
            if not generate_next_iteration(iteration):
                print(f"❌ Generation failed for ITERATION {iteration}")
                iteration += 1
                continue

            # Wait again
            if not wait_for_iteration(iteration, 300):
                iteration += 1
                continue

        # Validate
        success, errors = validate_iteration(iteration)

        if success:
            print(
                f"\n🎉🎉🎉 SUCCESS! ITERATION {iteration} PASSED VALIDATION! 🎉🎉🎉\n"
            )
            send_message(
                f"🎉 VALIDATION SUCCESS! ITERATION {iteration} is ready to deploy!"
            )

            # TODO: Proceed with deployment
            print("Next step: Deploy to target tenant")
            return 0
        else:
            print(f"\n❌ ITERATION {iteration} failed validation\n")
            print("Errors:")
            for error in errors:
                print(f"  - {error}")

            send_message(
                f"⚠️ ITERATION {iteration} failed. Moving to {iteration + 1}. Errors: {len(errors)}"
            )

            # TODO: Auto-fix errors based on patterns

            # Generate next iteration
            iteration += 1
            if not generate_next_iteration(iteration):
                print(f"❌ Failed to generate ITERATION {iteration}")
                continue

        time.sleep(2)  # Brief pause

    print(f"❌ Reached MAX_ITERATIONS ({max_iterations}) without success")
    send_message(f"⛔ Reached max iterations ({max_iterations})")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⛔ Interrupted by user")
        send_message("⛔ Monitoring loop interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        send_message(f"❌ Fatal error in monitoring loop: {e}")
        sys.exit(1)
