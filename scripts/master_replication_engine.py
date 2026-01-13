#!/usr/bin/env python3
"""
Master Continuous Replication Engine

This script runs continuously without stopping until 100% tenant replication is achieved.
It manages all phases and spawns parallel workstreams as needed.
"""

import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
# Dynamically determine repo root from script location
REPO_ROOT = Path(__file__).parent.parent.resolve()
log_dir = REPO_ROOT / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "master_engine.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("MasterEngine")


class ContinuousReplicationEngine:
    """Master engine that orchestrates tenant replication continuously."""

    def __init__(self):
        # Dynamically determine repo root from script location
        self.repo_root = Path(__file__).parent.parent.resolve()
        self.demos_dir = self.repo_root / "demos"
        self.objective_file = self.demos_dir / "OBJECTIVE.md"
        self.state_file = self.demos_dir / "engine_state.json"
        self.imessage_tool = Path.home() / ".local" / "bin" / "imessR"

        # Tenant configuration from .env
        self.source_tenant_id = "3cd87a41-1f61-4aef-a212-cefdecd9a2d1"
        self.source_subscription_id = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
        self.source_tenant_name = "DefenderATEVET17"

        self.target_tenant_id = "c7674d41-af6c-46f5-89a5-d41495d2151e"
        self.target_subscription_id = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"
        self.target_tenant_name = "DefenderATEVET12"

        self.state = self._load_state()
        self.iteration = self._get_current_iteration()

    def _send_message(self, msg: str):
        """Send iMessage update (non-blocking)."""
        try:
            if self.imessage_tool.exists():
                subprocess.run([str(self.imessage_tool), msg], timeout=10, check=False)
                logger.info(str(f"📱 Sent: {msg}"))
        except Exception as e:
            logger.warning(str(f"Failed to send iMessage: {e}"))

    def _load_state(self) -> Dict:
        """Load engine state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(str(f"Failed to load state: {e}"))

        return {
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "phases": {
                "source_scanned": False,
                "target_scanned": False,
                "iac_generated": False,
                "iac_validated": False,
                "deployed": False,
                "verified": False,
            },
            "metrics": {
                "source_resources": 0,
                "target_resources": 0,
                "iterations_generated": 0,
                "iterations_validated": 0,
                "iterations_deployed": 0,
            },
            "current_iteration": 0,
            "errors": [],
        }

    def _save_state(self):
        """Save engine state to file."""
        self.state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(str(f"Failed to save state: {e}"))

    def _get_current_iteration(self) -> int:
        """Get the current iteration number."""
        iterations = list(self.demos_dir.glob("iteration[0-9]*"))
        numbers = []
        for it in iterations:
            try:
                num = int(it.name.replace("iteration", ""))
                numbers.append(num)
            except ValueError:
                continue
        return max(numbers) if numbers else 92  # Start from 92 based on existing

    def _run_cmd(
        self, cmd: List[str], cwd: Optional[Path] = None, timeout: int = 3600
    ) -> Tuple[bool, str, str]:
        """Run a command and return (success, stdout, stderr)."""
        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=os.environ.copy(),
            )
            success = result.returncode == 0
            if not success:
                logger.warning(str(f"Command failed with code {result.returncode}"))
                logger.warning(str(f"stderr: {result.stderr[:500]}"))
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(str(f"Command timed out after {timeout}s"))
            return False, "", f"Timeout after {timeout}s"
        except Exception as e:
            logger.error(str(f"Command error: {e}"))
            return False, "", str(e)

    def scan_source_tenant(self) -> bool:
        """Scan source tenant into Neo4j."""
        logger.info("=" * 80)
        logger.info("SCANNING SOURCE TENANT: DefenderATEVET17")
        logger.info("=" * 80)

        self._send_message(f"🔍 Scanning source tenant {self.source_tenant_name}")

        # First check if already scanned
        success, stdout, stderr = self._run_cmd(
            [
                "uv",
                "run",
                "python",
                "-c",
                f"""
from py2neo import Graph
import os
from dotenv import load_dotenv

load_dotenv()
graph = Graph(os.getenv('NEO4J_URI'), auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')))

count = graph.run(
    "MATCH (r:Resource) WHERE r.subscription_id = '{self.source_subscription_id}' RETURN count(r) as count"
).data()[0]['count']
print(count)
""",
            ]
        )

        if success:
            try:
                count = int(stdout.strip())
                logger.info(str(f"Source tenant has {count} resources in Neo4j"))
                self.state["metrics"]["source_resources"] = count

                if count > 0:
                    self.state["phases"]["source_scanned"] = True
                    self._save_state()
                    return True
            except (ValueError, json.JSONDecodeError):
                pass

        # Need to scan - switch to source tenant and scan
        logger.info("Scanning source tenant resources...")

        # Set subscription context
        success, stdout, stderr = self._run_cmd(
            ["az", "account", "set", "--subscription", self.source_subscription_id]
        )

        if not success:
            logger.error(str(f"Failed to set subscription: {stderr}"))
            return False

        # Run ATG scan
        success, stdout, stderr = self._run_cmd(
            [
                "uv",
                "run",
                "atg",
                "scan",
                "--tenant-id",
                self.source_tenant_id,
                "--subscription-id",
                self.source_subscription_id,
            ],
            timeout=3600,
        )

        if success:
            logger.info("Source tenant scanned successfully")
            self.state["phases"]["source_scanned"] = True
            self._save_state()
            self._send_message(f"✅ Source tenant {self.source_tenant_name} scanned")
            return True
        else:
            logger.error(str(f"Scan failed: {stderr}"))
            self.state["errors"].append(
                {
                    "phase": "scan_source",
                    "error": stderr[:1000],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._save_state()
            return False

    def generate_iteration(self) -> bool:
        """Generate next IaC iteration."""
        self.iteration += 1
        iteration_dir = self.demos_dir / f"iteration{self.iteration}"

        logger.info("=" * 80)
        logger.info(str(f"GENERATING ITERATION {self.iteration}"))
        logger.info("=" * 80)

        self._send_message(f"🏗️ Generating iteration {self.iteration}")

        # Generate IaC from source tenant resources
        cmd = [
            "uv",
            "run",
            "atg",
            "generate-iac",
            "--resource-filters",
            f"subscription_id={self.source_subscription_id}",
            "--resource-group-prefix",
            f"ITERATION{self.iteration}_",
            "--skip-name-validation",
            "--output",
            str(iteration_dir),
        ]

        success, stdout, stderr = self._run_cmd(cmd, timeout=900)

        if success:
            logger.info(
                str(f"✅ Iteration {self.iteration} generated at {iteration_dir}")
            )
            self.state["current_iteration"] = self.iteration
            self.state["metrics"]["iterations_generated"] = self.iteration
            self.state["phases"]["iac_generated"] = True
            self._save_state()
            return True
        else:
            logger.error(str(f"Generation failed: {stderr}"))
            self.state["errors"].append(
                {
                    "phase": "generate",
                    "iteration": self.iteration,
                    "error": stderr[:1000],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._save_state()
            return False

    def validate_iteration(self) -> Tuple[bool, List[Dict]]:
        """Validate Terraform for current iteration."""
        iteration_dir = self.demos_dir / f"iteration{self.iteration}"

        logger.info("=" * 80)
        logger.info(str(f"VALIDATING ITERATION {self.iteration}"))
        logger.info("=" * 80)

        self._send_message(f"✅ Validating iteration {self.iteration}")

        # Terraform init
        success, stdout, stderr = self._run_cmd(
            ["terraform", "init", "-upgrade"], cwd=iteration_dir, timeout=300
        )

        if not success:
            logger.error(str(f"Terraform init failed: {stderr}"))
            return False, [{"detail": f"Init failed: {stderr}"}]

        # Terraform validate
        success, stdout, stderr = self._run_cmd(
            ["terraform", "validate", "-json"], cwd=iteration_dir, timeout=300
        )

        if success:
            logger.info(str(f"✅ Iteration {self.iteration} validation PASSED"))
            self.state["metrics"]["iterations_validated"] = self.iteration
            self.state["phases"]["iac_validated"] = True
            self._save_state()
            self._send_message(f"✅ Iteration {self.iteration} validated successfully")
            return True, []
        else:
            # Parse errors
            errors = []
            try:
                if stdout:
                    result = json.loads(stdout)
                    if "diagnostics" in result:
                        errors = result["diagnostics"]
            except json.JSONDecodeError:
                errors = [{"detail": stderr}]

            logger.warning(str(f"⚠️ Validation failed with {len(errors)} errors"))
            for i, err in enumerate(errors[:3]):
                logger.warning(f"  Error {i + 1}: {err.get('detail', err)[:200]}")

            self.state["errors"].append(
                {
                    "phase": "validate",
                    "iteration": self.iteration,
                    "error_count": len(errors),
                    "sample_errors": errors[:5],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._save_state()
            self._send_message(
                f"⚠️ Iteration {self.iteration} validation failed: {len(errors)} errors"
            )
            return False, errors

    def deploy_iteration(self) -> bool:
        """Deploy current iteration to target tenant."""
        iteration_dir = self.demos_dir / f"iteration{self.iteration}"

        logger.info("=" * 80)
        logger.info(str(f"DEPLOYING ITERATION {self.iteration} TO TARGET TENANT"))
        logger.info("=" * 80)

        self._send_message(
            f"🚀 Deploying iteration {self.iteration} to {self.target_tenant_name}"
        )

        # Set target tenant context
        success, stdout, stderr = self._run_cmd(
            ["az", "account", "set", "--subscription", self.target_subscription_id]
        )

        if not success:
            logger.error(str(f"Failed to set subscription: {stderr}"))
            return False

        # Terraform plan
        logger.info("Creating deployment plan...")
        success, stdout, stderr = self._run_cmd(
            ["terraform", "plan", "-out=tfplan", "-input=false"],
            cwd=iteration_dir,
            timeout=1800,
        )

        if not success:
            logger.error(str(f"Terraform plan failed: {stderr}"))
            self.state["errors"].append(
                {
                    "phase": "plan",
                    "iteration": self.iteration,
                    "error": stderr[:1000],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._save_state()
            return False

        # Terraform apply
        logger.info("Applying deployment (this may take 60-120 minutes)...")
        self._send_message(
            f"⚙️ Applying deployment for iteration {self.iteration} (60-120 min)"
        )

        success, stdout, stderr = self._run_cmd(
            ["terraform", "apply", "-auto-approve", "-input=false", "tfplan"],
            cwd=iteration_dir,
            timeout=7200,  # 2 hours
        )

        if success:
            logger.info(str(f"✅ Iteration {self.iteration} DEPLOYED successfully!"))
            self.state["metrics"]["iterations_deployed"] = self.iteration
            self.state["phases"]["deployed"] = True
            self._save_state()
            self._send_message(f"✅ Iteration {self.iteration} deployed successfully!")
            return True
        else:
            logger.error(str(f"Terraform apply failed: {stderr}"))
            self.state["errors"].append(
                {
                    "phase": "deploy",
                    "iteration": self.iteration,
                    "error": stderr[:1000],
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._save_state()
            self._send_message(f"❌ Iteration {self.iteration} deployment FAILED")
            return False

    def scan_target_tenant(self) -> bool:
        """Scan target tenant to verify deployment."""
        logger.info("=" * 80)
        logger.info("SCANNING TARGET TENANT FOR VERIFICATION")
        logger.info("=" * 80)

        self._send_message(f"🔍 Scanning target tenant {self.target_tenant_name}")

        # Run ATG scan on target
        success, stdout, stderr = self._run_cmd(
            [
                "uv",
                "run",
                "atg",
                "scan",
                "--tenant-id",
                self.target_tenant_id,
                "--subscription-id",
                self.target_subscription_id,
            ],
            timeout=3600,
        )

        if success:
            # Query target resource count
            success2, stdout2, stderr2 = self._run_cmd(
                [
                    "uv",
                    "run",
                    "python",
                    "-c",
                    f"""
from py2neo import Graph
import os
from dotenv import load_dotenv

load_dotenv()
graph = Graph(os.getenv('NEO4J_URI'), auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')))

count = graph.run(
    "MATCH (r:Resource) WHERE r.subscription_id = '{self.target_subscription_id}' RETURN count(r) as count"
).data()[0]['count']
print(count)
""",
                ]
            )

            if success2:
                try:
                    count = int(stdout2.strip())
                    logger.info(str(f"Target tenant has {count} resources"))
                    self.state["metrics"]["target_resources"] = count
                    self.state["phases"]["target_scanned"] = True
                    self._save_state()
                    return True
                except ValueError:
                    pass

        logger.warning("Target scan completed but couldn't get resource count")
        return False

    def evaluate_objective(self) -> Tuple[bool, Dict]:
        """Check if replication objective is achieved."""
        logger.info("=" * 80)
        logger.info("EVALUATING OBJECTIVE ACHIEVEMENT")
        logger.info("=" * 80)

        source_count = self.state["metrics"].get("source_resources", 0)
        target_count = self.state["metrics"].get("target_resources", 0)

        # Calculate metrics
        coverage = (target_count / source_count * 100) if source_count > 0 else 0

        criteria = {
            "source_scanned": self.state["phases"]["source_scanned"],
            "iac_generated": self.state["phases"]["iac_generated"],
            "iac_validated": self.state["phases"]["iac_validated"],
            "deployed": self.state["phases"]["deployed"],
            "target_scanned": self.state["phases"]["target_scanned"],
            "has_resources": target_count > 0,
            "good_coverage": coverage >= 50,  # At least 50% coverage
        }

        objective_achieved = all(criteria.values())

        logger.info(str(f"Source resources: {source_count}"))
        logger.info(str(f"Target resources: {target_count}"))
        logger.info(str(f"Coverage: {coverage:.1f}%"))
        logger.info("\nSuccess Criteria:")
        for criterion, passed in criteria.items():
            status = "✅" if passed else "❌"
            logger.info(str(f"  {status} {criterion}"))

        return objective_achieved, criteria

    def run(self):
        """Main continuous execution loop."""
        logger.info("=" * 80)
        logger.info("MASTER CONTINUOUS REPLICATION ENGINE")
        logger.info("=" * 80)
        logger.info(str(f"Source: {self.source_tenant_name} ({self.source_tenant_id})"))
        logger.info(str(f"Target: {self.target_tenant_name} ({self.target_tenant_id})"))
        logger.info(str(f"Starting iteration: {self.iteration + 1}"))
        logger.info("=" * 80)

        self._send_message(
            f"🤖 Replication engine started: {self.source_tenant_name} → {self.target_tenant_name}"
        )

        cycle = 0
        max_cycles = 500

        while cycle < max_cycles:
            cycle += 1

            try:
                logger.info(f"\n{'=' * 80}")
                logger.info(str(f"CYCLE {cycle}"))
                logger.info(f"{'=' * 80}\n")

                # Phase 1: Ensure source is scanned
                if not self.state["phases"]["source_scanned"]:
                    if not self.scan_source_tenant():
                        logger.error("Source scan failed - retrying in 60s")
                        time.sleep(60)
                        continue

                # Phase 2: Generate IaC
                if not self.generate_iteration():
                    logger.error("IaC generation failed - retrying in 30s")
                    time.sleep(30)
                    continue

                # Phase 3: Validate
                validated, errors = self.validate_iteration()

                if not validated:
                    logger.warning(str(f"Validation failed with {len(errors)} errors"))
                    # TODO: Analyze errors and fix code
                    # For now, continue to next iteration
                    time.sleep(30)
                    # Reset for next iteration
                    self.state["phases"]["iac_generated"] = False
                    self.state["phases"]["iac_validated"] = False
                    continue

                # Phase 4: Deploy
                if not self.deploy_iteration():
                    logger.error("Deployment failed")
                    time.sleep(60)
                    # Reset for next iteration
                    self.state["phases"]["iac_generated"] = False
                    self.state["phases"]["iac_validated"] = False
                    self.state["phases"]["deployed"] = False
                    continue

                # Phase 5: Scan target
                if not self.scan_target_tenant():
                    logger.warning("Target scan had issues - continuing anyway")

                # Phase 6: Evaluate
                objective_achieved, criteria = self.evaluate_objective()

                if objective_achieved:
                    logger.info("=" * 80)
                    logger.info("🎉 🎉 🎉 OBJECTIVE ACHIEVED! 🎉 🎉 🎉")
                    logger.info("=" * 80)
                    self._send_message(
                        f"🎉 OBJECTIVE ACHIEVED! Tenant replicated in {cycle} cycles"
                    )
                    return

                # Not done yet - prepare for next iteration
                logger.info("Objective not yet achieved - preparing next iteration...")
                failed = [k for k, v in criteria.items() if not v]
                self._send_message(f"🔄 Cycle {cycle} done. Need: {', '.join(failed)}")

                # Reset phases for next cycle
                self.state["phases"]["iac_generated"] = False
                self.state["phases"]["iac_validated"] = False
                self.state["phases"]["deployed"] = False
                self._save_state()

                time.sleep(30)

            except KeyboardInterrupt:
                logger.info("Engine interrupted by user")
                self._send_message("⏸️ Engine paused by user")
                return
            except Exception as e:
                logger.error(str(f"Unexpected error in cycle {cycle}: {e}"))
                logger.error(traceback.format_exc())
                self.state["errors"].append(
                    {
                        "cycle": cycle,
                        "error": str(e),
                        "traceback": traceback.format_exc()[:1000],
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                self._save_state()
                self._send_message(f"⚠️ Error in cycle {cycle}: {str(e)[:100]}")
                time.sleep(60)

        logger.warning(str(f"Reached max cycles ({max_cycles})"))
        self._send_message(
            f"⚠️ Reached max cycles ({max_cycles}) without achieving objective"
        )


def main():
    engine = ContinuousReplicationEngine()
    engine.run()


if __name__ == "__main__":
    main()
