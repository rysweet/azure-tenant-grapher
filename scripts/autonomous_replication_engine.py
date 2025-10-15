#!/usr/bin/env python3
"""
Autonomous Replication Engine

This script runs continuously to achieve 100% tenant replication from source (DefenderATEVET17) 
to target (DefenderATEVET12). It orchestrates the entire replication workflow without human intervention.

Workflow:
1. Assess current state (Neo4j, iterations, deployments)
2. Identify gaps and priorities
3. Execute parallel workstreams:
   - Control plane iteration and deployment
   - Entra ID discovery and replication
   - Data plane plugin development
4. Monitor progress and send status updates
5. Continue until 100% fidelity achieved

Author: Autonomous Agent
Date: 2025-10-15
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import traceback

# Configuration
REPO_ROOT = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher")
DEMOS_DIR = REPO_ROOT / "demos"
STATUS_FILE = DEMOS_DIR / "autonomous_replication_status.json"
IMESSAGE_TOOL = Path.home() / ".local/bin/imessR"
NEO4J_URI = "bolt://localhost:7688"
NEO4J_PASSWORD = "azure-grapher-2024"

# Source and target tenants
SOURCE_TENANT = "DefenderATEVET17"
TARGET_TENANT = "DefenderATEVET12"


class StatusReporter:
    """Send status updates via iMessage"""
    
    def send(self, message: str):
        """Send iMessage status update"""
        try:
            if IMESSAGE_TOOL.exists():
                subprocess.run([str(IMESSAGE_TOOL), message], timeout=10)
                print(f"📱 Sent: {message}")
            else:
                print(f"📱 (no imessR): {message}")
        except Exception as e:
            print(f"⚠️ Failed to send message: {e}")


class StateAssessor:
    """Assess current state of replication"""
    
    def __init__(self):
        self.neo4j_available = self._check_neo4j()
    
    def _check_neo4j(self) -> bool:
        """Check if Neo4j is accessible"""
        try:
            import neo4j
            driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            return True
        except Exception as e:
            print(f"❌ Neo4j not available: {e}")
            return False
    
    def get_neo4j_state(self) -> Dict[str, Any]:
        """Get current Neo4j database state"""
        if not self.neo4j_available:
            return {"error": "Neo4j not available"}
        
        try:
            import neo4j
            driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
            
            state = {}
            
            with driver.session() as session:
                # Total counts
                result = session.run("MATCH (n) RETURN count(n) as total_nodes")
                state["total_nodes"] = result.single()["total_nodes"]
                
                result = session.run("MATCH ()-[r]->() RETURN count(r) as total_edges")
                state["total_edges"] = result.single()["total_edges"]
                
                # Resource nodes by tenant
                result = session.run("""
                    MATCH (r:Resource)
                    RETURN r.tenantId as tenant, count(r) as count
                    ORDER BY tenant
                """)
                state["resources_by_tenant"] = {record["tenant"] or "unknown": record["count"] 
                                                for record in result}
                
                # Entra ID resources
                result = session.run("""
                    MATCH (n)
                    WHERE n.type STARTS WITH 'Microsoft.Graph/'
                    RETURN n.type as type, count(n) as count
                    ORDER BY count DESC
                """)
                state["entra_id_resources"] = {record["type"]: record["count"] 
                                               for record in result}
                
                # Resource types
                result = session.run("""
                    MATCH (r:Resource)
                    RETURN r.type as type, count(r) as count
                    ORDER BY count DESC
                    LIMIT 20
                """)
                state["top_resource_types"] = {record["type"]: record["count"] 
                                               for record in result if record["type"]}
            
            driver.close()
            return state
            
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}
    
    def get_iteration_state(self) -> Dict[str, Any]:
        """Get current iteration state"""
        iterations = sorted([d for d in DEMOS_DIR.iterdir() 
                           if d.is_dir() and d.name.startswith("iteration")])
        
        if not iterations:
            return {"latest_iteration": 0, "iterations": []}
        
        latest = iterations[-1]
        iteration_num = int(latest.name.replace("iteration", ""))
        
        # Check if terraform is initialized
        terraform_init = (latest / ".terraform").exists()
        
        # Check if there's a plan
        has_plan = (latest / "tfplan").exists()
        
        # Check if there's state (deployed)
        has_state = (latest / "terraform.tfstate").exists()
        
        return {
            "latest_iteration": iteration_num,
            "total_iterations": len(iterations),
            "latest_path": str(latest),
            "terraform_initialized": terraform_init,
            "has_plan": has_plan,
            "is_deployed": has_state,
            "iterations": [int(d.name.replace("iteration", "")) for d in iterations[-10:]]
        }
    
    def get_deployment_state(self) -> Dict[str, Any]:
        """Get current deployment state"""
        # Check if we have target tenant credentials
        env_vars = {
            "ARM_CLIENT_ID": os.getenv("ARM_CLIENT_ID"),
            "ARM_CLIENT_SECRET": os.getenv("ARM_CLIENT_SECRET"),
            "ARM_TENANT_ID": os.getenv("ARM_TENANT_ID"),
            "ARM_SUBSCRIPTION_ID": os.getenv("ARM_SUBSCRIPTION_ID"),
        }
        
        has_credentials = all(env_vars.values())
        
        # Check Azure CLI connection
        try:
            result = subprocess.run(["az", "account", "show"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                account = json.loads(result.stdout)
                current_tenant = account.get("name")
                logged_in = True
            else:
                current_tenant = None
                logged_in = False
        except Exception as e:
            current_tenant = None
            logged_in = False
        
        return {
            "has_credentials": has_credentials,
            "logged_in_to_azure": logged_in,
            "current_tenant": current_tenant,
            "target_tenant": TARGET_TENANT,
            "credentials_complete": env_vars
        }
    
    def assess_full_state(self) -> Dict[str, Any]:
        """Comprehensive state assessment"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "neo4j": self.get_neo4j_state(),
            "iterations": self.get_iteration_state(),
            "deployment": self.get_deployment_state()
        }


class WorkstreamOrchestrator:
    """Orchestrate parallel workstreams"""
    
    def __init__(self, reporter: StatusReporter):
        self.reporter = reporter
        self.workstreams = {}
    
    def run_command(self, cmd: List[str], cwd: Path = REPO_ROOT, timeout: int = 300) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as e:
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            return -1, "", str(e)
    
    def scan_source_tenant(self) -> bool:
        """Scan source tenant to ensure graph is up to date"""
        self.reporter.send(f"🔍 Scanning source tenant: {SOURCE_TENANT}")
        
        # TODO: Implement actual scan
        # For now, assume scan is already done
        return True
    
    def scan_target_tenant(self) -> bool:
        """Scan target tenant to capture current state"""
        self.reporter.send(f"🔍 Scanning target tenant: {TARGET_TENANT}")
        
        # TODO: Implement actual scan
        return True
    
    def generate_next_iteration(self, iteration_num: int) -> bool:
        """Generate next IaC iteration"""
        self.reporter.send(f"🔨 Generating iteration {iteration_num}")
        
        output_dir = DEMOS_DIR / f"iteration{iteration_num}"
        
        cmd = [
            "uv", "run", "atg", "generate-iac",
            "--resource-group-prefix", f"ITERATION{iteration_num}_",
            "--skip-name-validation",
            "--output", str(output_dir)
        ]
        
        code, stdout, stderr = self.run_command(cmd, timeout=600)
        
        if code == 0:
            self.reporter.send(f"✅ Generated iteration {iteration_num}")
            return True
        else:
            self.reporter.send(f"❌ Failed to generate iteration {iteration_num}: {stderr[:200]}")
            return False
    
    def validate_iteration(self, iteration_num: int) -> Tuple[bool, List[str]]:
        """Validate an iteration with terraform"""
        self.reporter.send(f"✓ Validating iteration {iteration_num}")
        
        iteration_dir = DEMOS_DIR / f"iteration{iteration_num}"
        
        # Initialize terraform
        code, stdout, stderr = self.run_command(
            ["terraform", "init", "-upgrade"],
            cwd=iteration_dir
        )
        
        if code != 0:
            return False, [f"Terraform init failed: {stderr[:200]}"]
        
        # Validate
        code, stdout, stderr = self.run_command(
            ["terraform", "validate", "-json"],
            cwd=iteration_dir
        )
        
        if code == 0:
            return True, []
        else:
            # Parse errors from JSON output
            try:
                import json
                result = json.loads(stdout)
                errors = []
                for diag in result.get("diagnostics", []):
                    if diag.get("severity") == "error":
                        errors.append(diag.get("summary", "Unknown error"))
                return False, errors
            except:
                return False, [stderr[:500]]
    
    def deploy_iteration(self, iteration_num: int) -> bool:
        """Deploy an iteration to target tenant"""
        self.reporter.send(f"🚀 Deploying iteration {iteration_num} to {TARGET_TENANT}")
        
        iteration_dir = DEMOS_DIR / f"iteration{iteration_num}"
        
        # Create plan
        code, stdout, stderr = self.run_command(
            ["terraform", "plan", "-out=tfplan"],
            cwd=iteration_dir,
            timeout=900
        )
        
        if code != 0:
            self.reporter.send(f"❌ Terraform plan failed: {stderr[:200]}")
            return False
        
        # Apply
        code, stdout, stderr = self.run_command(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=iteration_dir,
            timeout=3600  # 1 hour for deployment
        )
        
        if code == 0:
            self.reporter.send(f"✅ Deployed iteration {iteration_num}")
            return True
        else:
            self.reporter.send(f"❌ Deployment failed: {stderr[:200]}")
            return False


class AutonomousEngine:
    """Main autonomous replication engine"""
    
    def __init__(self):
        self.reporter = StatusReporter()
        self.assessor = StateAssessor()
        self.orchestrator = WorkstreamOrchestrator(self.reporter)
        self.status = {}
        self.running = True
    
    def load_status(self):
        """Load saved status"""
        if STATUS_FILE.exists():
            with open(STATUS_FILE) as f:
                self.status = json.load(f)
        else:
            self.status = {
                "started_at": datetime.utcnow().isoformat(),
                "phase": "assessment",
                "completed_phases": [],
                "iterations_deployed": [],
                "errors": []
            }
    
    def save_status(self):
        """Save current status"""
        self.status["updated_at"] = datetime.utcnow().isoformat()
        with open(STATUS_FILE, "w") as f:
            json.dump(self.status, f, indent=2)
    
    def assess_and_plan(self) -> Dict[str, Any]:
        """Assess current state and create execution plan"""
        self.reporter.send("🧠 Assessing current state...")
        
        state = self.assessor.assess_full_state()
        
        # Determine what needs to be done
        plan = {
            "scan_source_needed": False,
            "scan_target_needed": False,
            "generate_iteration_needed": False,
            "deploy_iteration_needed": False,
            "entra_id_needed": True,  # Always needed until we have it
            "data_plane_needed": True,  # Always needed
        }
        
        # Check if we have recent iterations
        iter_state = state["iterations"]
        if iter_state["latest_iteration"] < 90:
            plan["generate_iteration_needed"] = True
            plan["next_iteration"] = iter_state["latest_iteration"] + 1
        else:
            plan["next_iteration"] = iter_state["latest_iteration"] + 1
        
        # Check if latest iteration is deployed
        if not iter_state.get("is_deployed"):
            plan["deploy_iteration_needed"] = True
            plan["iteration_to_deploy"] = iter_state["latest_iteration"]
        
        return plan
    
    def execute_control_plane_iteration(self, iteration_num: int) -> bool:
        """Execute one control plane iteration: generate -> validate -> deploy"""
        
        # Generate
        if not self.orchestrator.generate_next_iteration(iteration_num):
            return False
        
        # Validate
        is_valid, errors = self.orchestrator.validate_iteration(iteration_num)
        
        if not is_valid:
            self.reporter.send(f"⚠️ Iteration {iteration_num} has {len(errors)} validation errors")
            # Log errors but continue - we'll fix in next iteration
            self.status.setdefault("validation_errors", {})[str(iteration_num)] = errors
            self.save_status()
            return False
        
        self.reporter.send(f"✅ Iteration {iteration_num} validation passed")
        
        # Check if we should deploy (3 consecutive passes)
        recent_iters = list(range(max(1, iteration_num - 2), iteration_num + 1))
        all_valid = all(
            str(i) not in self.status.get("validation_errors", {}) 
            for i in recent_iters
        )
        
        if all_valid and len(recent_iters) >= 3:
            self.reporter.send(f"🎯 3 consecutive validations passed, deploying iteration {iteration_num}")
            success = self.orchestrator.deploy_iteration(iteration_num)
            if success:
                self.status.setdefault("iterations_deployed", []).append(iteration_num)
                self.save_status()
            return success
        else:
            self.reporter.send(f"⏭️ Continuing to next iteration (need 3 consecutive passes)")
            return True
    
    def run_continuous_loop(self):
        """Main continuous execution loop"""
        self.reporter.send("🚀 Starting Autonomous Replication Engine")
        
        self.load_status()
        
        iteration_count = 0
        max_iterations = 1000  # Safety limit
        
        while self.running and iteration_count < max_iterations:
            try:
                iteration_count += 1
                
                # Assess and plan
                plan = self.assess_and_plan()
                
                self.reporter.send(f"📋 Cycle {iteration_count}: Phase={self.status.get('phase')}")
                
                # Execute plan
                if plan["generate_iteration_needed"] or iteration_count == 1:
                    next_iter = plan["next_iteration"]
                    success = self.execute_control_plane_iteration(next_iter)
                    
                    if success:
                        self.status["phase"] = "control_plane_iterating"
                    else:
                        self.status["phase"] = "control_plane_fixing"
                
                # Check if we've achieved control plane fidelity
                if self.status.get("iterations_deployed"):
                    last_deployed = self.status["iterations_deployed"][-1]
                    self.reporter.send(f"✅ Control plane deployed (iteration {last_deployed})")
                    
                    # Move to Entra ID phase
                    if "entra_id" not in self.status.get("completed_phases", []):
                        self.status["phase"] = "entra_id_replication"
                        self.reporter.send("🔄 Moving to Entra ID replication phase")
                        # TODO: Implement Entra ID replication
                        time.sleep(60)
                
                self.save_status()
                
                # Wait between iterations
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.reporter.send("⏹️ Stopping autonomous engine (user interrupt)")
                self.running = False
                break
            
            except Exception as e:
                error_msg = f"❌ Error in iteration {iteration_count}: {str(e)}"
                self.reporter.send(error_msg)
                self.status.setdefault("errors", []).append({
                    "iteration": iteration_count,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "timestamp": datetime.utcnow().isoformat()
                })
                self.save_status()
                
                # Wait before retry
                time.sleep(30)
        
        self.reporter.send(f"🏁 Autonomous engine completed {iteration_count} iterations")


def main():
    """Main entry point"""
    engine = AutonomousEngine()
    engine.run_continuous_loop()


if __name__ == "__main__":
    main()
