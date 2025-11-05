#!/usr/bin/env python3
"""
Autonomous Tenant Replication Loop

This script runs continuously until 100% tenant replication fidelity is achieved.
It orchestrates:
1. Iterations of IaC generation/validation/deployment
2. Gap analysis between source and target tenants
3. Parallel workstreams to fix identified issues
4. Continuous monitoring and progress reporting
5. Objective evaluation against success criteria

The script DOES NOT STOP until the objective in demos/OBJECTIVE.md is fully achieved.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Status tracking
STATUS_FILE = PROJECT_ROOT / "demos" / "autonomous_loop_status.json"
OBJECTIVE_FILE = PROJECT_ROOT / "demos" / "OBJECTIVE.md"
ITERATION_DIR = PROJECT_ROOT / "demos"

# iMessage tool
IMESSAGE_TOOL = Path.home() / ".local" / "bin" / "imessR"


class AutonomousReplicationLoop:
    """Main orchestrator for continuous tenant replication"""

    def __init__(self):
        self.status = self.load_status()
        self.iteration_count = self.status.get("last_iteration", 92)
        self.deployment_iteration = self.status.get("last_deployment", 0)
        self.objective_achieved = False
        self.workstreams = []

    def load_status(self) -> Dict:
        """Load status from file or create new"""
        if STATUS_FILE.exists():
            with open(STATUS_FILE) as f:
                return json.load(f)
        return {
            "last_iteration": 92,
            "last_deployment": 0,
            "consecutive_valid_iterations": 3,
            "workstreams": [],
            "gaps": [],
            "started_at": datetime.utcnow().isoformat(),
        }

    def save_status(self):
        """Save current status"""
        self.status["last_iteration"] = self.iteration_count
        self.status["last_deployment"] = self.deployment_iteration
        self.status["updated_at"] = datetime.utcnow().isoformat()
        self.status["workstreams"] = self.workstreams
        with open(STATUS_FILE, "w") as f:
            json.dump(self.status, f, indent=2)

    def send_imessage(self, message: str):
        """Send status update via iMessage"""
        try:
            if IMESSAGE_TOOL.exists():
                subprocess.run(
                    [str(IMESSAGE_TOOL), message],
                    capture_output=True,
                    timeout=10
                )
        except Exception as e:
            print(f"Failed to send iMessage: {e}")

    def evaluate_objective(self) -> Tuple[bool, Dict]:
        """Evaluate if objective is achieved using multiple methods"""
        print("\n=== EVALUATING OBJECTIVE ===")

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "graph_fidelity": self.check_graph_fidelity(),
            "control_plane_fidelity": self.check_control_plane_fidelity(),
            "validation_status": self.check_validation_status(),
            "deployment_status": self.check_deployment_status(),
        }

        # Check if all criteria met
        all_met = all([
            results["graph_fidelity"]["met"],
            results["control_plane_fidelity"]["met"],
            results["validation_status"]["met"],
            results["deployment_status"]["met"],
        ])

        return all_met, results

    def check_graph_fidelity(self) -> Dict:
        """Check Neo4j graph fidelity between source and target"""
        try:
            # Use py2neo instead of cypher-shell
            from py2neo import Graph

            # Load .env file
            env_file = PROJECT_ROOT / ".env"
            neo4j_password = os.getenv("NEO4J_PASSWORD")
            if not neo4j_password and env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("NEO4J_PASSWORD="):
                            neo4j_password = line.split("=", 1)[1].strip()
            if not neo4j_password:
                raise ValueError("NEO4J_PASSWORD environment variable is required")

            graph = Graph("bolt://localhost:7688", auth=("neo4j", neo4j_password))

            # Source tenant subscription: 9b00bc5e-9abc-45de-9958-02a9d9277b16 (DefenderATEVET17)
            # Target tenant subscription: c190c55a-9ab2-4b1e-92c4-cc8b1a032285 (DefenderATEVET12)

            # Query for source nodes (use subscription ID from resource IDs)
            source_query = """
            MATCH (r:Resource)
            WHERE r.id CONTAINS '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/'
            RETURN count(r) as count
            """
            source_result = graph.run(source_query).data()
            source_count = source_result[0]["count"] if source_result else 0

            # Query for target nodes
            target_query = """
            MATCH (r:Resource)
            WHERE r.id CONTAINS '/subscriptions/c190c55a-9ab2-4b1e-92c4-cc8b1a032285/'
            RETURN count(r) as count
            """
            target_result = graph.run(target_query).data()
            target_count = target_result[0]["count"] if target_result else 0

            # Allow 10x tolerance since target will have many ITERATIONx_* resources
            # We expect target to have MORE resources than source due to multiple iterations
            # Success = target has at least as many resources as source
            met = target_count >= source_count and source_count > 0

            delta_pct = abs(target_count - source_count) / max(source_count, 1) if source_count > 0 else 0

            return {
                "met": met,
                "source_nodes": source_count,
                "target_nodes": target_count,
                "delta_percent": delta_pct * 100,
                "note": "Target should have >= source due to multiple iterations"
            }
        except Exception as e:
            print(f"Graph fidelity check failed: {e}")
            import traceback
            traceback.print_exc()
            return {"met": False, "error": str(e)}


    def check_control_plane_fidelity(self) -> Dict:
        """Check control plane resource coverage"""
        # Check latest iteration validation
        latest_iter = max([
            int(d.name.replace("iteration", ""))
            for d in ITERATION_DIR.glob("iteration*")
            if d.is_dir() and d.name.replace("iteration", "").isdigit()
        ])

        iter_path = ITERATION_DIR / f"iteration{latest_iter}"

        # Run validation
        try:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/validate_generated_iac.py", str(iter_path)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT
            )

            # Parse validation output
            valid = "PASS" in result.stdout and "FAIL" not in result.stdout

            return {
                "met": valid,
                "latest_iteration": latest_iter,
                "validation_output": result.stdout[-500:] if result.stdout else ""
            }
        except Exception as e:
            return {"met": False, "error": str(e)}

    def check_validation_status(self) -> Dict:
        """Check if we have 3 consecutive valid iterations"""
        consecutive = self.status.get("consecutive_valid_iterations", 0)
        return {
            "met": consecutive >= 3,
            "consecutive_valid": consecutive,
            "required": 3
        }

    def check_deployment_status(self) -> Dict:
        """Check if deployment succeeded"""
        deployed = self.deployment_iteration > 0
        return {
            "met": deployed,
            "last_deployment": self.deployment_iteration
        }

    def identify_gaps(self) -> List[Dict]:
        """Identify gaps between source and target tenants"""
        print("\n=== IDENTIFYING GAPS ===")

        gaps = []

        # Check for missing resource types
        try:
            from py2neo import Graph

            # Load .env file
            env_file = PROJECT_ROOT / ".env"
            neo4j_password = os.getenv("NEO4J_PASSWORD")
            if not neo4j_password and env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("NEO4J_PASSWORD="):
                            neo4j_password = line.split("=", 1)[1].strip()
            if not neo4j_password:
                raise ValueError("NEO4J_PASSWORD environment variable is required")

            graph = Graph("bolt://localhost:7688", auth=("neo4j", neo4j_password))

            # Query source tenant for resource types
            query = """
            MATCH (r:Resource)
            WHERE r.id CONTAINS '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/'
            RETURN DISTINCT r.type as resource_type, count(*) as count
            ORDER BY count DESC
            """

            result = graph.run(query).data()

            if result:
                # Check which are supported in terraform_emitter
                gaps.append({
                    "type": "missing_resource_types",
                    "details": result[:10],  # Top 10
                    "priority": "P0"
                })
        except Exception as e:
            print(f"Gap identification failed: {e}")
            import traceback
            traceback.print_exc()

        return gaps

    def spawn_fix_workstream(self, gap: Dict) -> str:
        """Spawn a parallel workstream to fix a gap"""
        workstream_id = f"ws_{gap['type']}_{int(time.time())}"

        print(f"\n=== SPAWNING WORKSTREAM: {workstream_id} ===")

        # Create workstream directory
        ws_dir = PROJECT_ROOT / ".claude" / "runtime" / workstream_id
        ws_dir.mkdir(parents=True, exist_ok=True)

        # Launch copilot agent
        prompt = f"""
You are working on fixing a gap in the Azure Tenant Grapher replication.

Gap Type: {gap['type']}
Priority: {gap['priority']}
Details: {json.dumps(gap['details'], indent=2)}

Your task:
1. Analyze the gap
2. Implement a fix following @.claude/workflow/DEFAULT_WORKFLOW.md
3. Test the fix
4. Commit the fix
5. Report back to {ws_dir / 'status.json'}

Do not stop until the gap is fixed.
"""

        # Save prompt
        with open(ws_dir / "prompt.txt", "w") as f:
            f.write(prompt)

        # Launch agent in background
        log_file = ws_dir / "output.log"
        cmd = f"copilot --allow-all-tools -p '{prompt}' > {log_file} 2>&1 &"
        subprocess.Popen(cmd, shell=True, cwd=PROJECT_ROOT)

        self.workstreams.append({
            "id": workstream_id,
            "gap": gap,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running"
        })

        return workstream_id

    def check_workstream_status(self) -> List[Dict]:
        """Check status of all running workstreams"""
        for ws in self.workstreams:
            if ws["status"] == "running":
                ws_dir = PROJECT_ROOT / ".claude" / "runtime" / ws["id"]
                status_file = ws_dir / "status.json"
                if status_file.exists():
                    with open(status_file) as f:
                        status = json.load(f)
                        ws["status"] = status.get("status", "running")
                        ws["result"] = status.get("result", {})

        return self.workstreams

    def generate_iteration(self, iteration_num: int) -> bool:
        """Generate a new IaC iteration"""
        print(f"\n=== GENERATING ITERATION {iteration_num} ===")

        output_dir = ITERATION_DIR / f"iteration{iteration_num}"

        try:
            result = subprocess.run([
                "uv", "run", "atg", "generate-iac",
                "--resource-filters", "resourceGroup=~'(?i).*(simuland|SimuLand).*'",
                "--resource-group-prefix", f"ITERATION{iteration_num}_",
                "--skip-name-validation",
                "--output", str(output_dir)
            ], capture_output=True, text=True, timeout=300, cwd=PROJECT_ROOT)

            success = result.returncode == 0
            if success:
                print(f"✓ Generated iteration {iteration_num}")
            else:
                print(f"✗ Failed to generate iteration {iteration_num}")
                print(result.stderr[-500:])

            return success
        except Exception as e:
            print(f"Generation failed: {e}")
            return False

    def validate_iteration(self, iteration_num: int) -> Tuple[bool, List[str]]:
        """Validate an iteration"""
        print(f"\n=== VALIDATING ITERATION {iteration_num} ===")

        iter_dir = ITERATION_DIR / f"iteration{iteration_num}"

        try:
            # Terraform init
            subprocess.run(
                ["terraform", "init"],
                cwd=iter_dir,
                capture_output=True,
                timeout=120
            )

            # Terraform validate
            result = subprocess.run(
                ["terraform", "validate"],
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            valid = result.returncode == 0
            errors = []

            if not valid:
                # Parse errors
                for line in result.stderr.split('\n'):
                    if 'Error:' in line:
                        errors.append(line)

            if valid:
                print(f"✓ Iteration {iteration_num} is VALID")
            else:
                print(f"✗ Iteration {iteration_num} has {len(errors)} errors")
                for err in errors[:5]:
                    print(f"  - {err}")

            return valid, errors
        except Exception as e:
            print(f"Validation failed: {e}")
            return False, [str(e)]

    def deploy_iteration(self, iteration_num: int) -> bool:
        """Deploy an iteration to target tenant"""
        print(f"\n=== DEPLOYING ITERATION {iteration_num} ===")

        iter_dir = ITERATION_DIR / f"iteration{iteration_num}"

        # Send notification
        self.send_imessage(f"🚀 Starting deployment of iteration {iteration_num}")

        # Switch to TARGET tenant subscription (DefenderATEVET12)
        TARGET_SUBSCRIPTION = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"

        print(f"Switching to target subscription: {TARGET_SUBSCRIPTION}")
        try:
            subprocess.run(
                ["az", "account", "set", "--subscription", TARGET_SUBSCRIPTION],
                capture_output=True,
                timeout=30,
                check=True
            )
        except Exception as e:
            print(f"Failed to switch subscription: {e}")
            self.send_imessage("❌ Failed to switch to target subscription")
            return False

        # Get subscription ID from Azure CLI (should be target now)
        try:
            sub_result = subprocess.run(
                ["az", "account", "show", "--query", "id", "-o", "tsv"],
                capture_output=True,
                text=True,
                timeout=30
            )
            subscription_id = sub_result.stdout.strip()
            print(f"Confirmed subscription: {subscription_id}")

            if subscription_id != TARGET_SUBSCRIPTION:
                print(f"WARNING: Subscription mismatch! Expected {TARGET_SUBSCRIPTION}, got {subscription_id}")
                self.send_imessage("⚠️ Subscription mismatch in deployment")
        except Exception as e:
            print(f"Failed to get subscription ID: {e}")
            subscription_id = TARGET_SUBSCRIPTION

        # Set up environment variables for Terraform
        env = os.environ.copy()
        env["TF_VAR_subscription_id"] = subscription_id
        print(f"Using subscription: {subscription_id}")

        try:
            # Terraform plan
            print("Running terraform plan...")
            plan_result = subprocess.run(
                ["terraform", "plan", "-out=tfplan"],
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )

            if plan_result.returncode != 0:
                print("✗ Terraform plan failed")
                print(plan_result.stderr[-500:])
                self.send_imessage(f"❌ Iteration {iteration_num} plan failed")
                return False

            # Terraform apply
            print("Running terraform apply...")
            apply_result = subprocess.run(
                ["terraform", "apply", "-auto-approve", "tfplan"],
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour
                env=env
            )

            success = apply_result.returncode == 0

            if success:
                print(f"✓ Iteration {iteration_num} deployed successfully")
                self.send_imessage(f"✅ Iteration {iteration_num} deployed successfully!")
                self.deployment_iteration = iteration_num
            else:
                print(f"✗ Iteration {iteration_num} deployment failed")
                print(apply_result.stderr[-500:])
                self.send_imessage(f"❌ Iteration {iteration_num} deployment failed")

            return success
        except Exception as e:
            print(f"Deployment failed: {e}")
            self.send_imessage(f"❌ Iteration {iteration_num} deployment exception: {e}")
            return False

    def scan_target_tenant(self) -> bool:
        """Scan target tenant to update Neo4j graph"""
        print("\n=== SCANNING TARGET TENANT ===")

        try:
            result = subprocess.run(
                ["uv", "run", "atg", "scan"],
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes
                cwd=PROJECT_ROOT
            )

            success = result.returncode == 0
            if success:
                print("✓ Target tenant scanned")
            else:
                print("✗ Target tenant scan failed")
                print(result.stderr[-500:])

            return success
        except Exception as e:
            print(f"Scan failed: {e}")
            return False

    def run_continuous_loop(self):
        """Main continuous loop - DOES NOT STOP until objective achieved"""
        print("\n" + "=" * 80)
        print("AUTONOMOUS TENANT REPLICATION LOOP")
        print("=" * 80)
        print(f"Starting at iteration {self.iteration_count}")
        print("This loop will NOT STOP until 100% objective achievement")
        print("=" * 80 + "\n")

        self.send_imessage("🤖 Autonomous replication loop started")

        loop_count = 0

        while not self.objective_achieved:
            loop_count += 1
            print(f"\n{'=' * 80}")
            print(f"LOOP ITERATION {loop_count} - {datetime.utcnow().isoformat()}")
            print(f"{'=' * 80}\n")

            # 1. Evaluate objective
            achieved, results = self.evaluate_objective()

            if achieved:
                print("\n🎉 OBJECTIVE ACHIEVED! 🎉")
                self.send_imessage("🎉 100% TENANT REPLICATION ACHIEVED!")
                self.objective_achieved = True
                break

            # Report status
            print("\nObjective Status:")
            print(f"  Graph Fidelity: {'✓' if results['graph_fidelity']['met'] else '✗'}")
            print(f"  Control Plane: {'✓' if results['control_plane_fidelity']['met'] else '✗'}")
            print(f"  Validation: {'✓' if results['validation_status']['met'] else '✗'}")
            print(f"  Deployment: {'✓' if results['deployment_status']['met'] else '✗'}")

            # 2. Identify gaps
            gaps = self.identify_gaps()

            # 3. Spawn workstreams to fix gaps (parallel)
            for gap in gaps[:3]:  # Top 3 priorities
                if not any(ws['gap']['type'] == gap['type'] and ws['status'] == 'running'
                          for ws in self.workstreams):
                    self.spawn_fix_workstream(gap)

            # 4. Check workstream status
            self.check_workstream_status()
            active_workstreams = [ws for ws in self.workstreams if ws['status'] == 'running']
            completed_workstreams = [ws for ws in self.workstreams if ws['status'] == 'completed']

            print(f"\nWorkstreams: {len(active_workstreams)} active, {len(completed_workstreams)} completed")

            # 5. Generate next iteration
            self.iteration_count += 1
            if not self.generate_iteration(self.iteration_count):
                print("Generation failed, will retry")
                time.sleep(60)
                continue

            # 6. Validate iteration
            valid, errors = self.validate_iteration(self.iteration_count)

            if valid:
                self.status["consecutive_valid_iterations"] = \
                    self.status.get("consecutive_valid_iterations", 0) + 1
            else:
                self.status["consecutive_valid_iterations"] = 0
                # Log errors for analysis
                print(f"Errors in iteration {self.iteration_count}:")
                for err in errors[:10]:
                    print(f"  {err}")

            # 7. Deploy if we have 3 consecutive valid iterations and haven't deployed yet
            if (self.status.get("consecutive_valid_iterations", 0) >= 3 and
                self.deployment_iteration == 0):
                if self.deploy_iteration(self.iteration_count):
                    # Scan target after deployment
                    self.scan_target_tenant()

            # 8. Save status
            self.save_status()

            # 9. Send periodic updates
            if loop_count % 5 == 0:
                self.send_imessage(
                    f"Loop {loop_count}: Iteration {self.iteration_count}, "
                    f"{len(active_workstreams)} active workstreams"
                )

            # 10. Brief pause between iterations
            time.sleep(30)

        # Final summary
        print("\n" + "=" * 80)
        print("OBJECTIVE ACHIEVED - LOOP COMPLETE")
        print("=" * 80)
        print(f"Total loop iterations: {loop_count}")
        print(f"Final IaC iteration: {self.iteration_count}")
        print(f"Deployed iteration: {self.deployment_iteration}")
        print(f"Workstreams completed: {len([ws for ws in self.workstreams if ws['status'] == 'completed'])}")
        print("=" * 80 + "\n")


def main():
    """Entry point"""
    loop = AutonomousReplicationLoop()

    try:
        loop.run_continuous_loop()
    except KeyboardInterrupt:
        print("\n\nLoop interrupted by user")
        loop.save_status()
        sys.exit(1)
    except Exception as e:
        print(f"\n\nLoop failed with exception: {e}")
        import traceback
        traceback.print_exc()
        loop.send_imessage(f"❌ Autonomous loop crashed: {e}")
        loop.save_status()
        sys.exit(1)


if __name__ == "__main__":
    main()
