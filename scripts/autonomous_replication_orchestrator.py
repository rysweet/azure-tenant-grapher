#!/usr/bin/env python3
"""
Autonomous Replication Orchestrator

This script runs continuously until the Azure tenant replication objective is achieved.
It coordinates all phases: scanning, IaC generation, validation, deployment, and verification.
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Dynamically determine repo root from script location
REPO_ROOT = Path(__file__).parent.parent.resolve()
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "autonomous_orchestrator.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class AutonmousReplicationOrchestrator:
    """Orchestrates continuous tenant replication until objective is achieved."""

    def __init__(self):
        # Use the global REPO_ROOT defined at module level
        self.repo_root = REPO_ROOT
        self.demos_dir = self.repo_root / "demos"
        self.objective_file = self.demos_dir / "OBJECTIVE.md"
        self.status_file = self.demos_dir / "orchestrator_status.json"
        self.imessage_tool = Path.home() / ".local" / "bin" / "imessR"

        self.source_tenant = "DefenderATEVET17"
        self.target_tenant = "DefenderATEVET12"

        self.current_iteration = self._get_latest_iteration_number()
        self.status = self._load_status()

    def _send_imessage(self, message: str):
        """Send iMessage update."""
        try:
            if self.imessage_tool.exists():
                subprocess.run(
                    [str(self.imessage_tool), message], timeout=10, check=False
                )
        except Exception as e:
            logger.warning(str(f"Failed to send iMessage: {e}"))

    def _load_status(self) -> Dict:
        """Load orchestrator status from file."""
        if self.status_file.exists():
            with open(self.status_file) as f:
                return json.load(f)
        return {
            "started_at": datetime.now().isoformat(),
            "current_iteration": self.current_iteration,
            "phases_completed": [],
            "errors": [],
            "metrics": {},
        }

    def _save_status(self):
        """Save orchestrator status to file."""
        self.status["last_updated"] = datetime.now().isoformat()
        with open(self.status_file, "w") as f:
            json.dump(self.status, f, indent=2)

    def _get_latest_iteration_number(self) -> int:
        """Get the latest iteration number from demos directory."""
        iterations = list(self.demos_dir.glob("iteration*"))
        numbers = []
        for it in iterations:
            try:
                num = int(it.name.replace("iteration", ""))
                numbers.append(num)
            except ValueError:
                continue
        return max(numbers) if numbers else 0

    def _run_command(
        self, cmd: List[str], cwd: Optional[Path] = None, timeout: int = 3600
    ) -> tuple:
        """Run a command and return (success, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            return False, "", "Timeout"
        except Exception as e:
            logger.error(str(f"Command failed: {e}"))
            return False, "", str(e)

    def phase1_scan_source_tenant(self) -> bool:
        """Phase 1: Scan source tenant into Neo4j."""
        logger.info("=" * 80)
        logger.info("PHASE 1: Scanning Source Tenant (DefenderATEVET17)")
        logger.info("=" * 80)

        self._send_imessage(f"🔍 Phase 1: Scanning source tenant {self.source_tenant}")

        # Check if source tenant is already scanned
        success, stdout, stderr = self._run_command(
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
graph = Graph(os.getenv('NEO4J_URI', 'bolt://localhost:7688'),
              auth=(os.getenv('NEO4J_USER', 'neo4j'),
                    os.getenv('NEO4J_PASSWORD')))

count = graph.run(
    "MATCH (r:Resource) WHERE r.tenantId CONTAINS '{self.source_tenant}' RETURN count(r) as count"
).data()[0]['count']
print(str(f"SOURCE_RESOURCES={{count}}"))
""",
            ]
        )

        if success and "SOURCE_RESOURCES=" in stdout:
            source_count = int(stdout.split("SOURCE_RESOURCES=")[1].strip())
            logger.info(str(f"Source tenant has {source_count} resources in Neo4j"))

            if source_count == 0:
                # Need to scan source tenant
                logger.info("Scanning source tenant...")
                scan_cmd = [
                    "uv",
                    "run",
                    "atg",
                    "scan",
                    "--tenant-id",
                    self.source_tenant,
                ]
                logger.info(f"Executing: {' '.join(scan_cmd)}")
                scan_success, scan_stdout, scan_stderr = self._run_command(
                    scan_cmd, timeout=3600
                )
                if not scan_success:
                    logger.error(f"Source tenant scan failed: {scan_stderr}")
                    return False
                logger.info("Source tenant scan completed successfully")

            self.status["metrics"]["source_resources"] = source_count
            self.status["phases_completed"].append("scan_source")
            self._save_status()
            return True

        return False

    def phase2_generate_iac(self) -> bool:
        """Phase 2: Generate IaC from Neo4j graph."""
        self.current_iteration += 1
        iteration_dir = self.demos_dir / f"iteration{self.current_iteration}"

        logger.info("=" * 80)
        logger.info(
            str(f"PHASE 2: Generating IaC for Iteration {self.current_iteration}")
        )
        logger.info("=" * 80)

        self._send_imessage(f"🏗️ Phase 2: Generating iteration {self.current_iteration}")

        # Generate IaC
        cmd = [
            "uv",
            "run",
            "atg",
            "generate-iac",
            "--resource-filters",
            "tenantId=~'.*DefenderATEVET17.*'",
            "--resource-group-prefix",
            f"ITERATION{self.current_iteration}_",
            "--skip-name-validation",
            "--output",
            str(iteration_dir),
        ]

        success, stdout, stderr = self._run_command(cmd, timeout=600)

        if success:
            logger.info(str(f"IaC generated successfully in {iteration_dir}"))
            self.status["current_iteration"] = self.current_iteration
            self.status["phases_completed"].append(
                f"generate_iac_{self.current_iteration}"
            )
            self._save_status()
            return True
        else:
            logger.error(str(f"IaC generation failed: {stderr}"))
            self.status["errors"].append(
                {
                    "phase": "generate_iac",
                    "iteration": self.current_iteration,
                    "error": stderr,
                }
            )
            self._save_status()
            return False

    def phase3_validate_terraform(self) -> tuple:
        """Phase 3: Validate Terraform configuration."""
        iteration_dir = self.demos_dir / f"iteration{self.current_iteration}"

        logger.info("=" * 80)
        logger.info(
            f"PHASE 3: Validating Terraform for Iteration {self.current_iteration}"
        )
        logger.info("=" * 80)

        self._send_imessage(
            f"✅ Phase 3: Validating iteration {self.current_iteration}"
        )

        # Init terraform
        success, stdout, stderr = self._run_command(
            ["terraform", "init"], cwd=iteration_dir
        )

        if not success:
            logger.error(str(f"Terraform init failed: {stderr}"))
            return False, []

        # Validate terraform
        success, stdout, stderr = self._run_command(
            ["terraform", "validate", "-json"], cwd=iteration_dir
        )

        if success:
            logger.info("Terraform validation passed!")
            self.status["phases_completed"].append(f"validate_{self.current_iteration}")
            self._save_status()
            return True, []
        else:
            # Parse errors
            errors = []
            try:
                result = json.loads(stdout) if stdout else {}
                if "diagnostics" in result:
                    errors = result["diagnostics"]
            except json.JSONDecodeError:
                errors = [{"detail": stderr}]

            logger.warning(str(f"Terraform validation found {len(errors)} errors"))
            for err in errors[:5]:  # Log first 5 errors
                logger.warning(f"  - {err.get('detail', err)}")

            self.status["errors"].append(
                {
                    "phase": "validate",
                    "iteration": self.current_iteration,
                    "error_count": len(errors),
                    "errors": errors[:10],  # Save first 10
                }
            )
            self._save_status()
            return False, errors

    def phase4_deploy_terraform(self) -> bool:
        """Phase 4: Deploy Terraform to target tenant."""
        iteration_dir = self.demos_dir / f"iteration{self.current_iteration}"

        logger.info("=" * 80)
        logger.info(
            f"PHASE 4: Deploying to Target Tenant (Iteration {self.current_iteration})"
        )
        logger.info("=" * 80)

        self._send_imessage(
            f"🚀 Phase 4: Deploying iteration {self.current_iteration} to {self.target_tenant}"
        )

        # Plan
        logger.info("Running terraform plan...")
        success, stdout, stderr = self._run_command(
            ["terraform", "plan", "-out=tfplan"],
            cwd=iteration_dir,
            timeout=1800,  # 30 minutes
        )

        if not success:
            logger.error(str(f"Terraform plan failed: {stderr}"))
            self.status["errors"].append(
                {"phase": "plan", "iteration": self.current_iteration, "error": stderr}
            )
            self._save_status()
            return False

        # Apply
        logger.info("Running terraform apply...")
        self._send_imessage("⚙️ Applying terraform (this takes ~60 minutes)...")

        success, stdout, stderr = self._run_command(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=iteration_dir,
            timeout=7200,  # 2 hours
        )

        if success:
            logger.info("Terraform apply succeeded!")
            self.status["phases_completed"].append(f"deploy_{self.current_iteration}")
            self._save_status()
            self._send_imessage(
                f"✅ Iteration {self.current_iteration} deployed successfully!"
            )
            return True
        else:
            logger.error(str(f"Terraform apply failed: {stderr}"))
            self.status["errors"].append(
                {"phase": "apply", "iteration": self.current_iteration, "error": stderr}
            )
            self._save_status()
            self._send_imessage(
                f"❌ Iteration {self.current_iteration} deployment failed"
            )
            return False

    def phase5_scan_target_tenant(self) -> bool:
        """Phase 5: Scan target tenant after deployment."""
        logger.info("=" * 80)
        logger.info("PHASE 5: Scanning Target Tenant (DefenderATEVET12)")
        logger.info("=" * 80)

        self._send_imessage(f"🔍 Phase 5: Scanning target tenant {self.target_tenant}")

        # Scan target tenant
        scan_cmd = [
            "uv",
            "run",
            "atg",
            "scan",
            "--tenant-id",
            self.target_tenant,
        ]
        logger.info(f"Executing: {' '.join(scan_cmd)}")
        scan_success, scan_stdout, scan_stderr = self._run_command(
            scan_cmd, timeout=3600
        )
        if not scan_success:
            logger.error(f"Target tenant scan failed: {scan_stderr}")
            return False
        logger.info("Target tenant scan completed successfully")

        # Query current state after scan
        success, stdout, stderr = self._run_command(
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
graph = Graph(os.getenv('NEO4J_URI', 'bolt://localhost:7688'),
              auth=(os.getenv('NEO4J_USER', 'neo4j'),
                    os.getenv('NEO4J_PASSWORD')))

count = graph.run(
    "MATCH (r:Resource) WHERE r.tenantId CONTAINS '{self.target_tenant}' RETURN count(r) as count"
).data()[0]['count']
print(str(f"TARGET_RESOURCES={{count}}"))
""",
            ]
        )

        if success and "TARGET_RESOURCES=" in stdout:
            target_count = int(stdout.split("TARGET_RESOURCES=")[1].strip())
            logger.info(str(f"Target tenant has {target_count} resources in Neo4j"))

            self.status["metrics"]["target_resources"] = target_count
            self.status["phases_completed"].append("scan_target")
            self._save_status()
            return True

        return False

    def phase6_evaluate_objective(self) -> tuple:
        """Phase 6: Evaluate if objective is achieved."""
        logger.info("=" * 80)
        logger.info("PHASE 6: Evaluating Objective Achievement")
        logger.info("=" * 80)

        # Calculate metrics
        source_count = self.status["metrics"].get("source_resources", 0)
        target_count = self.status["metrics"].get("target_resources", 0)

        # Calculate coverage (accounting for iteration prefixes)
        # Each iteration creates a copy of resources, so we expect target > source
        coverage = (target_count / source_count * 100) if source_count > 0 else 0

        logger.info(str(f"Source resources: {source_count}"))
        logger.info(str(f"Target resources: {target_count}"))
        logger.info(str(f"Coverage: {coverage:.1f}%"))

        # Check success criteria
        criteria = {
            "terraform_validated": f"validate_{self.current_iteration}"
            in self.status["phases_completed"],
            "terraform_deployed": f"deploy_{self.current_iteration}"
            in self.status["phases_completed"],
            "target_scanned": "scan_target" in self.status["phases_completed"],
            "resources_exist": target_count > 0,
        }

        all_passed = all(criteria.values())

        logger.info("Success Criteria:")
        for criterion, passed in criteria.items():
            logger.info(f"  - {criterion}: {'✅' if passed else '❌'}")

        self.status["metrics"]["coverage"] = coverage
        self.status["success_criteria"] = criteria
        self._save_status()

        return all_passed, criteria

    def run_continuous_loop(self):
        """Run the continuous replication loop until objective is achieved."""
        logger.info("=" * 80)
        logger.info("AUTONOMOUS REPLICATION ORCHESTRATOR STARTED")
        logger.info("=" * 80)
        logger.info(str(f"Source Tenant: {self.source_tenant}"))
        logger.info(str(f"Target Tenant: {self.target_tenant}"))
        logger.info(str(f"Starting from Iteration: {self.current_iteration + 1}"))
        logger.info("=" * 80)

        self._send_imessage(
            f"🤖 Autonomous replication started: {self.source_tenant} → {self.target_tenant}"
        )

        max_iterations = 200  # Safety limit
        iteration_count = 0

        while iteration_count < max_iterations:
            iteration_count += 1

            try:
                logger.info(f"\n{'=' * 80}")
                logger.info(str(f"BEGINNING ITERATION CYCLE {iteration_count}"))
                logger.info(f"{'=' * 80}\n")

                # Phase 1: Ensure source tenant is scanned
                if "scan_source" not in self.status["phases_completed"]:
                    if not self.phase1_scan_source_tenant():
                        logger.error("Phase 1 failed - retrying in 60 seconds...")
                        time.sleep(60)
                        continue

                # Phase 2: Generate IaC
                if not self.phase2_generate_iac():
                    logger.error("Phase 2 failed - skipping this iteration")
                    time.sleep(30)
                    continue

                # Phase 3: Validate Terraform
                validated, errors = self.phase3_validate_terraform()

                if not validated:
                    logger.warning(str(f"Validation failed with {len(errors)} errors"))
                    self._send_imessage(
                        f"⚠️ Iteration {self.current_iteration} validation failed: {len(errors)} errors"
                    )

                    # Analyze errors and log detailed information
                    error_types = {}
                    for err in errors:
                        err_detail = err.get("detail", "Unknown error")
                        err_summary = err.get("summary", "")

                        # Categorize error types
                        if "subnet" in err_detail.lower() or "address" in err_detail.lower():
                            error_types["network"] = error_types.get("network", 0) + 1
                        elif "resource" in err_detail.lower() and "not found" in err_detail.lower():
                            error_types["missing_resource"] = error_types.get("missing_resource", 0) + 1
                        elif "invalid" in err_detail.lower():
                            error_types["invalid_config"] = error_types.get("invalid_config", 0) + 1
                        else:
                            error_types["other"] = error_types.get("other", 0) + 1

                        logger.error(f"  Terraform error: {err_summary}: {err_detail}")

                    logger.info(f"Error breakdown: {error_types}")
                    self.status["errors"].append({
                        "iteration": self.current_iteration,
                        "error_count": len(errors),
                        "error_types": error_types,
                        "timestamp": datetime.now().isoformat()
                    })
                    self._save_status()

                    # Continue to next iteration to try improvements
                    time.sleep(30)
                    continue

                # Phase 4: Deploy (only if validated)
                if not self.phase4_deploy_terraform():
                    logger.error("Deployment failed - analyzing errors...")
                    time.sleep(60)
                    continue

                # Phase 5: Scan target tenant
                if not self.phase5_scan_target_tenant():
                    logger.warning("Target scan failed - continuing...")

                # Phase 6: Evaluate objective
                objective_achieved, criteria = self.phase6_evaluate_objective()

                if objective_achieved:
                    logger.info("=" * 80)
                    logger.info("🎉 OBJECTIVE ACHIEVED! 🎉")
                    logger.info("=" * 80)
                    self._send_imessage(
                        f"🎉 OBJECTIVE ACHIEVED! Tenant replicated successfully in {iteration_count} iterations"
                    )
                    break
                else:
                    logger.info("Objective not yet achieved - continuing...")
                    failed = [k for k, v in criteria.items() if not v]
                    self._send_imessage(
                        f"🔄 Iteration {self.current_iteration} complete. Still need: {', '.join(failed)}"
                    )

                # Wait before next iteration
                time.sleep(30)

            except KeyboardInterrupt:
                logger.info("Orchestrator interrupted by user")
                self._send_imessage("⏸️ Orchestrator paused by user")
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error in iteration {iteration_count}: {e}",
                    exc_info=True,
                )
                self.status["errors"].append(
                    {"iteration_cycle": iteration_count, "error": str(e)}
                )
                self._save_status()
                time.sleep(60)

        if iteration_count >= max_iterations:
            logger.warning("Reached maximum iteration limit")
            self._send_imessage(f"⚠️ Reached maximum iteration limit ({max_iterations})")

        logger.info("=" * 80)
        logger.info("ORCHESTRATOR FINISHED")
        logger.info("=" * 80)


def main():
    orchestrator = AutonmousReplicationOrchestrator()
    orchestrator.run_continuous_loop()


if __name__ == "__main__":
    main()
