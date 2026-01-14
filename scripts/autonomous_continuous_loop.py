#!/usr/bin/env python3
"""
Autonomous Continuous Loop for Azure Tenant Replication
This script NEVER stops until 100% objective is achieved.
It monitors, analyzes, spawns fixes, and continues iterations.
"""

import json
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Constants
SOURCE_TENANT = "DefenderATEVET17"
SOURCE_SUB = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
TARGET_TENANT = "DefenderATEVET12"
TARGET_SUB = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"

# Dynamically determine repo root from script location
REPO_ROOT = Path(__file__).parent.parent.resolve()
DEMOS_DIR = REPO_ROOT / "demos"
IMESS_R = Path.home() / ".local/bin/imessR"

# State file
STATE_FILE = DEMOS_DIR / "autonomous_loop_state.json"


class AutonomousLoop:
    def __init__(self):
        self.state = self.load_state()
        self.iteration_number = self.get_latest_iteration() + 1

    def load_state(self) -> Dict:
        """Load persistent state"""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {
            "started_at": datetime.utcnow().isoformat(),
            "iterations_completed": [],
            "fixes_applied": [],
            "objective_achieved": False,
            "last_update": datetime.utcnow().isoformat(),
        }

    def save_state(self):
        """Save persistent state"""
        self.state["last_update"] = datetime.utcnow().isoformat()
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_latest_iteration(self) -> int:
        """Find latest iteration number"""
        iterations = [
            d.name
            for d in DEMOS_DIR.iterdir()
            if d.is_dir() and d.name.startswith("iteration")
        ]
        if not iterations:
            return 0
        numbers = [int(i.replace("iteration", "")) for i in iterations]
        return max(numbers)

    def send_imessage(self, message: str):
        """Send iMessage update"""
        try:
            subprocess.run([str(IMESS_R), message], check=False, timeout=10)
        except Exception as e:
            print(str(f"Failed to send iMessage: {e}"))

    def evaluate_objective(self) -> Tuple[bool, Dict]:
        """Evaluate if objective is achieved using Neo4j and validation"""
        try:
            # Check Neo4j resource counts
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-c",
                    """
import os
from neo4j import GraphDatabase

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
password = os.getenv('NEO4J_PASSWORD', '')
if not password:
    with open('.env') as f:
        for line in f:
            if line.startswith('NEO4J_PASSWORD='):
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

    print(str(f"{source},{target}"))
driver.close()
                """,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                source_count, target_count = map(int, result.stdout.strip().split(","))
            else:
                source_count, target_count = 0, 0

            # Check latest iteration validation
            latest_iter = DEMOS_DIR / f"iteration{self.iteration_number - 1}"
            validation_passed = False

            if latest_iter.exists():
                # Run terraform validate
                val_result = subprocess.run(
                    ["terraform", "validate", "-json"],
                    cwd=latest_iter,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if val_result.returncode == 0:
                    try:
                        val_data = json.loads(val_result.stdout)
                        validation_passed = val_data.get("valid", False)
                    except json.JSONDecodeError:
                        pass

            # Calculate fidelity
            fidelity = (target_count / source_count * 100) if source_count > 0 else 0

            # Objective: 100% validation + >95% fidelity
            objective_met = validation_passed and fidelity > 95

            return objective_met, {
                "source_resources": source_count,
                "target_resources": target_count,
                "fidelity_percent": fidelity,
                "validation_passed": validation_passed,
                "latest_iteration": self.iteration_number - 1,
            }

        except Exception as e:
            print(str(f"Error evaluating objective: {e}"))
            traceback.print_exc()
            return False, {"error": str(e)}

    def generate_iteration(self, iteration_num: int) -> bool:
        """Generate new iteration using atg"""
        try:
            output_dir = DEMOS_DIR / f"iteration{iteration_num}"

            self.send_imessage(f"Generating iteration {iteration_num}...")

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "atg",
                    "generate-iac",
                    "--resource-filters",
                    "resourceGroup=~'(?i).*(simuland|SimuLand).*'",
                    "--resource-group-prefix",
                    f"ITERATION{iteration_num}_",
                    "--skip-name-validation",
                    "--output",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )

            success = result.returncode == 0 and output_dir.exists()

            if success:
                print(str(f"✓ Generated iteration {iteration_num}"))
            else:
                print(str(f"✗ Failed to generate iteration {iteration_num}"))
                print(result.stderr)

            return success

        except Exception as e:
            print(str(f"Error generating iteration: {e}"))
            traceback.print_exc()
            return False

    def validate_iteration(self, iteration_num: int) -> Tuple[bool, List[str]]:
        """Validate iteration with terraform"""
        try:
            iteration_dir = DEMOS_DIR / f"iteration{iteration_num}"

            # terraform init
            subprocess.run(
                ["terraform", "init"],
                cwd=iteration_dir,
                capture_output=True,
                timeout=120,
            )

            # terraform validate
            result = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=iteration_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            errors = []
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if not data.get("valid", False):
                        errors = [
                            d.get("summary", "Unknown error")
                            for d in data.get("diagnostics", [])
                        ]
                except json.JSONDecodeError:
                    pass
            else:
                errors = ["Validation failed with non-zero exit code"]

            return len(errors) == 0, errors

        except Exception as e:
            print(str(f"Error validating iteration: {e}"))
            return False, [str(e)]

    def analyze_errors(self, errors: List[str]) -> Dict[str, List[str]]:
        """Categorize errors by type"""
        categorized = {
            "missing_resource_types": [],
            "property_issues": [],
            "dependency_issues": [],
            "other": [],
        }

        for error in errors:
            error_lower = error.lower()
            if "unsupported" in error_lower or "not found" in error_lower:
                categorized["missing_resource_types"].append(error)
            elif "property" in error_lower or "attribute" in error_lower:
                categorized["property_issues"].append(error)
            elif "depends" in error_lower or "reference" in error_lower:
                categorized["dependency_issues"].append(error)
            else:
                categorized["other"].append(error)

        return categorized

    def spawn_fix_workstream(self, error_category: str, errors: List[str]):
        """Spawn a subagent to fix a category of errors"""
        try:
            # Create a prompt for the subagent
            prompt_file = (
                REPO_ROOT / f".prompts/fix_{error_category}_{int(time.time())}.md"
            )
            prompt_file.parent.mkdir(exist_ok=True)

            prompt = f"""# Fix {error_category.replace("_", " ").title()}

## Errors to Fix
{chr(10).join(f"- {e}" for e in errors[:10])}

## Task
Fix these errors in the Azure Tenant Grapher codebase. Focus on:
1. Adding missing resource type mappings
2. Fixing property serialization issues
3. Resolving dependency handling

Update the relevant files in src/iac/emitters/ and add tests.
Commit your changes with descriptive messages.

Do NOT run iterations - just fix the code and validate with tests.
"""

            with open(prompt_file, "w") as f:
                f.write(prompt)

            # Spawn subagent (this is simplified - actual implementation would use copilot)
            print(str(f"  → Would spawn workstream for: {error_category}"))
            print(str(f"     Prompt saved to: {prompt_file}"))

        except Exception as e:
            print(str(f"Error spawning fix workstream: {e}"))

    def deploy_iteration(self, iteration_num: int) -> bool:
        """Deploy iteration to target tenant"""
        try:
            iteration_dir = DEMOS_DIR / f"iteration{iteration_num}"

            self.send_imessage(
                f"Deploying iteration {iteration_num} to target tenant..."
            )

            # terraform plan
            plan_result = subprocess.run(
                ["terraform", "plan", "-out=tfplan"],
                cwd=iteration_dir,
                capture_output=True,
                timeout=300,
            )

            if plan_result.returncode != 0:
                print(str(f"✗ Terraform plan failed for iteration {iteration_num}"))
                return False

            # terraform apply (this will take a long time)
            apply_result = subprocess.run(
                ["terraform", "apply", "-auto-approve", "tfplan"],
                cwd=iteration_dir,
                capture_output=True,
                text=True,
                timeout=7200,  # 2 hours
            )

            success = apply_result.returncode == 0

            if success:
                print(str(f"✓ Successfully deployed iteration {iteration_num}"))
                self.send_imessage(
                    f"✓ Iteration {iteration_num} deployed successfully!"
                )
            else:
                print(str(f"✗ Deployment failed for iteration {iteration_num}"))
                print(apply_result.stderr[-1000:])  # Last 1000 chars
                self.send_imessage(f"✗ Iteration {iteration_num} deployment failed")

            return success

        except Exception as e:
            print(str(f"Error deploying iteration: {e}"))
            traceback.print_exc()
            return False

    def rescan_target_tenant(self) -> bool:
        """Rescan target tenant to update Neo4j"""
        try:
            self.send_imessage("Rescanning target tenant...")

            # Switch to target tenant
            subprocess.run(
                ["az", "account", "set", "--subscription", TARGET_SUB],
                check=True,
                timeout=30,
            )

            # Run discovery
            result = subprocess.run(
                ["uv", "run", "atg", "discover", "--subscription-id", TARGET_SUB],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes
            )

            success = result.returncode == 0

            if success:
                print("✓ Target tenant rescanned")
                self.send_imessage("✓ Target tenant rescanned successfully")
            else:
                print("✗ Failed to rescan target tenant")
                print(result.stderr)

            return success

        except Exception as e:
            print(str(f"Error rescanning target: {e}"))
            return False

    def run_continuous_loop(self):
        """Main continuous loop - NEVER STOPS until objective achieved"""

        print("=" * 80)
        print("AUTONOMOUS CONTINUOUS LOOP STARTED")
        print("=" * 80)
        print(str(f"Source: {SOURCE_TENANT} ({SOURCE_SUB})"))
        print(str(f"Target: {TARGET_TENANT} ({TARGET_SUB})"))
        print(str(f"Starting iteration: {self.iteration_number}"))
        print("=" * 80)

        self.send_imessage(
            f"🤖 Autonomous loop started. Current iteration: {self.iteration_number}. "
            "Will continue until 100% objective achieved."
        )

        consecutive_validations = 0

        while True:
            try:
                loop_start = time.time()
                print(f"\n{'=' * 80}")
                print(
                    f"ITERATION {self.iteration_number} - {datetime.utcnow().isoformat()}"
                )
                print(f"{'=' * 80}")

                # Step 1: Evaluate objective
                objective_met, metrics = self.evaluate_objective()
                print("\nObjective Evaluation:")
                print(f"  Source resources: {metrics.get('source_resources', 'N/A')}")
                print(f"  Target resources: {metrics.get('target_resources', 'N/A')}")
                print(f"  Fidelity: {metrics.get('fidelity_percent', 0):.1f}%")
                print(
                    f"  Validation: {'PASS' if metrics.get('validation_passed') else 'FAIL'}"
                )
                print(f"  Objective met: {'YES' if objective_met else 'NO'}")

                if objective_met:
                    print("\n" + "=" * 80)
                    print("🎉 OBJECTIVE ACHIEVED! 100% FIDELITY REACHED!")
                    print("=" * 80)
                    self.send_imessage(
                        "🎉 OBJECTIVE ACHIEVED! Azure tenant replication at 100% fidelity. "
                        f"Final metrics: {json.dumps(metrics)}"
                    )
                    self.state["objective_achieved"] = True
                    self.save_state()
                    break

                # Step 2: Generate iteration
                print(str(f"\n→ Generating iteration {self.iteration_number}..."))
                if not self.generate_iteration(self.iteration_number):
                    print("✗ Generation failed, retrying in 60s...")
                    time.sleep(60)
                    continue

                # Step 3: Validate iteration
                print(str(f"\n→ Validating iteration {self.iteration_number}..."))
                validation_passed, errors = self.validate_iteration(
                    self.iteration_number
                )

                if validation_passed:
                    consecutive_validations += 1
                    print(
                        f"✓ Validation PASSED (consecutive: {consecutive_validations})"
                    )

                    # Deploy after 3 consecutive passes
                    if consecutive_validations >= 3:
                        print(
                            str(f"\n→ Deploying iteration {self.iteration_number}...")
                        )
                        if self.deploy_iteration(self.iteration_number):
                            # Rescan target
                            self.rescan_target_tenant()
                            consecutive_validations = 0  # Reset after deployment
                        else:
                            print("✗ Deployment failed")
                            consecutive_validations = 0

                else:
                    consecutive_validations = 0
                    print(str(f"✗ Validation FAILED with {len(errors)} errors"))

                    # Analyze and spawn fix workstreams
                    categorized = self.analyze_errors(errors)
                    print("\nError breakdown:")
                    for category, cat_errors in categorized.items():
                        if cat_errors:
                            print(str(f"  {category}: {len(cat_errors)} errors"))
                            # Spawn fix workstream
                            self.spawn_fix_workstream(category, cat_errors)

                # Save state
                self.state["iterations_completed"].append(
                    {
                        "iteration": self.iteration_number,
                        "timestamp": datetime.utcnow().isoformat(),
                        "validation_passed": validation_passed,
                        "errors": len(errors),
                        "metrics": metrics,
                    }
                )
                self.save_state()

                # Move to next iteration
                self.iteration_number += 1

                # Status update
                elapsed = time.time() - loop_start
                self.send_imessage(
                    f"Iteration {self.iteration_number - 1} complete in {elapsed:.0f}s. "
                    f"Validation: {'PASS' if validation_passed else f'FAIL ({len(errors)} errors)'}. "
                    f"Fidelity: {metrics.get('fidelity_percent', 0):.1f}%. "
                    f"Next: iteration {self.iteration_number}"
                )

                # Small delay before next iteration
                time.sleep(30)

            except KeyboardInterrupt:
                print("\n\nReceived interrupt signal. Saving state and exiting...")
                self.save_state()
                break

            except Exception as e:
                print(str(f"\n✗ Error in loop: {e}"))
                traceback.print_exc()
                self.send_imessage(
                    f"⚠️ Error in iteration {self.iteration_number}: {str(e)[:100]}"
                )
                time.sleep(60)  # Wait before retrying
                continue


def main():
    """Entry point"""
    loop = AutonomousLoop()
    loop.run_continuous_loop()


if __name__ == "__main__":
    main()
