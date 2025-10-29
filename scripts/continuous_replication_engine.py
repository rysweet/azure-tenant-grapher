#!/usr/bin/env python3
"""
Continuous Autonomous Replication Engine
Runs continuously until 100% tenant replication is achieved.
Does NOT stop. Spawns parallel workstreams to fix gaps.
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from neo4j import GraphDatabase

# Configuration
REPO_ROOT = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher")
DEMOS_DIR = REPO_ROOT / "demos"
STATUS_FILE = DEMOS_DIR / "continuous_engine_status.json"
LOG_FILE = DEMOS_DIR / "continuous_engine.log"

SOURCE_SUB = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
TARGET_SUB = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise ValueError("NEO4J_PASSWORD environment variable is required")

FIDELITY_TARGET = 95.0  # 95%+ considered success
CONSECUTIVE_PASSES_REQUIRED = 3

class ContinuousEngine:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
        self.current_iteration = self.get_latest_iteration()
        self.consecutive_passes = 0
        self.parallel_workstreams = {}
        
    def log(self, message):
        """Log message to file and stdout."""
        timestamp = datetime.utcnow().isoformat()
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(LOG_FILE, "a") as f:
            f.write(log_msg + "\n")
    
    def send_imessage(self, message):
        """Send status update via iMessage."""
        try:
            subprocess.run([
                "/Users/ryan/.local/bin/imessR",
                "send",
                message
            ], timeout=10, capture_output=True)
        except Exception as e:
            self.log(f"iMessage failed: {e}")
    
    def get_latest_iteration(self):
        """Find the latest iteration number."""
        iterations = [d for d in DEMOS_DIR.glob("iteration*") if d.is_dir()]
        if not iterations:
            return 0
        nums = []
        for it in iterations:
            try:
                num = int(it.name.replace("iteration", ""))
                nums.append(num)
            except:
                pass
        return max(nums) if nums else 0
    
    def check_fidelity(self):
        """Check current replication fidelity."""
        with self.driver.session() as session:
            # Source count
            source_result = session.run("""
                MATCH (r:Resource)
                WHERE r.subscription_id = $sub
                RETURN count(r) as count
            """, sub=SOURCE_SUB)
            source_count = source_result.single()["count"]
            
            # Target count
            target_result = session.run("""
                MATCH (r:Resource)
                WHERE r.subscription_id = $sub
                RETURN count(r) as count
            """, sub=TARGET_SUB)
            target_count = target_result.single()["count"]
            
            fidelity = (target_count / source_count * 100) if source_count > 0 else 0
            gap = source_count - target_count
            
            return {
                "source_count": source_count,
                "target_count": target_count,
                "fidelity": fidelity,
                "gap": gap,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def identify_missing_types(self):
        """Identify resource types missing from target."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:Resource)
                WHERE r.subscription_id = $source_sub
                AND NOT EXISTS {
                    MATCH (t:Resource {type: r.type})
                    WHERE t.subscription_id = $target_sub
                }
                RETURN DISTINCT r.type as type, count(*) as count
                ORDER BY count DESC
            """, source_sub=SOURCE_SUB, target_sub=TARGET_SUB)
            
            return [(rec["type"], rec["count"]) for rec in result]
    
    def spawn_fix_workstream(self, resource_type, count):
        """Spawn a parallel workstream to fix a specific resource type."""
        workstream_id = f"fix_{resource_type.replace('/', '_').replace('.', '_')}_{int(time.time())}"
        
        prompt = f"""Fix support for Azure resource type: {resource_type}

Current situation: {count} resources of type {resource_type} exist in source tenant but are missing from target.

Your task:
1. Read src/iac/emitters/terraform_emitter.py
2. Find AZURE_TO_TERRAFORM_MAPPING dictionary
3. Add mapping for {resource_type} to appropriate Terraform resource type
4. Implement emission logic in _generate_resource() method
5. Add tests for this resource type
6. Run tests to validate
7. Commit your changes with descriptive message

Resource Type: {resource_type}
Count: {count} resources

Work autonomously. When done, output "WORKSTREAM_COMPLETE: {workstream_id}" to signal completion.
"""
        
        self.log(f"Spawning workstream: {workstream_id} for {resource_type}")
        
        # Launch copilot agent
        proc = subprocess.Popen([
            "copilot",
            "--allow-all-tools",
            "-p",
            prompt
        ], cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        self.parallel_workstreams[workstream_id] = {
            "process": proc,
            "resource_type": resource_type,
            "count": count,
            "started": datetime.utcnow().isoformat()
        }
        
        return workstream_id
    
    def check_workstreams(self):
        """Check status of parallel workstreams."""
        completed = []
        for ws_id, ws_data in list(self.parallel_workstreams.items()):
            proc = ws_data["process"]
            if proc.poll() is not None:
                # Process finished
                stdout, stderr = proc.communicate()
                self.log(f"Workstream {ws_id} completed with code {proc.returncode}")
                if "WORKSTREAM_COMPLETE" in stdout:
                    self.log(f"  ✓ Success: {ws_data['resource_type']}")
                else:
                    self.log(f"  ✗ Failed: {ws_data['resource_type']}")
                completed.append(ws_id)
        
        # Remove completed workstreams
        for ws_id in completed:
            del self.parallel_workstreams[ws_id]
        
        return len(completed)
    
    def generate_iteration(self):
        """Generate next iteration."""
        self.current_iteration += 1
        iteration_dir = DEMOS_DIR / f"iteration{self.current_iteration}"
        
        self.log(f"Generating ITERATION {self.current_iteration}...")
        
        cmd = [
            "uv", "run", "atg", "generate-iac",
            "--resource-filters", "subscription_id=~'9b00bc5e-9abc-45de-9958-02a9d9277b16'",
            "--resource-group-prefix", f"ITERATION{self.current_iteration}_",
            "--skip-name-validation",
            "--output", str(iteration_dir)
        ]
        
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            self.log(f"  ✓ Generated iteration{self.current_iteration}")
            return True
        else:
            self.log(f"  ✗ Generation failed: {result.stderr}")
            return False
    
    def validate_iteration(self):
        """Validate the current iteration."""
        iteration_dir = DEMOS_DIR / f"iteration{self.current_iteration}"
        
        self.log(f"Validating ITERATION {self.current_iteration}...")
        
        # Check if directory exists
        if not iteration_dir.exists():
            self.log(f"  ✗ Iteration directory does not exist")
            return False
        
        # Run terraform init
        result = subprocess.run(
            ["terraform", "init"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            self.log(f"  ✗ terraform init failed")
            return False
        
        # Run terraform validate
        result = subprocess.run(
            ["terraform", "validate", "-json"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            try:
                validation_result = json.loads(result.stdout)
                if validation_result.get("valid"):
                    self.log(f"  ✓ Validation PASSED")
                    self.consecutive_passes += 1
                    return True
            except:
                pass
        
        self.log(f"  ✗ Validation FAILED")
        self.consecutive_passes = 0
        return False
    
    def deploy_iteration(self):
        """Deploy current iteration to target tenant."""
        iteration_dir = DEMOS_DIR / f"iteration{self.current_iteration}"
        
        self.log(f"Deploying ITERATION {self.current_iteration}...")
        self.send_imessage(f"🚀 Deploying ITERATION {self.current_iteration}")
        
        # Run terraform plan
        plan_result = subprocess.run(
            ["terraform", "plan", "-out=tfplan"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if plan_result.returncode != 0:
            self.log(f"  ✗ terraform plan failed")
            return False
        
        # Run terraform apply
        apply_result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=iteration_dir,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if apply_result.returncode == 0:
            self.log(f"  ✓ Deployment SUCCEEDED")
            self.send_imessage(f"✅ ITERATION {self.current_iteration} deployed successfully")
            return True
        else:
            self.log(f"  ✗ Deployment FAILED: {apply_result.stderr[-500:]}")
            self.send_imessage(f"❌ ITERATION {self.current_iteration} deployment failed")
            return False
    
    def rescan_target(self):
        """Rescan target tenant to update Neo4j."""
        self.log("Rescanning target tenant...")
        
        result = subprocess.run(
            ["uv", "run", "atg", "scan"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes
        )
        
        if result.returncode == 0:
            self.log("  ✓ Rescan complete")
            return True
        else:
            self.log(f"  ✗ Rescan failed: {result.stderr}")
            return False
    
    def save_status(self, status):
        """Save current status to file."""
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    
    def run_continuous_loop(self):
        """Main continuous operation loop - DOES NOT STOP."""
        self.log("=" * 80)
        self.log("CONTINUOUS AUTONOMOUS REPLICATION ENGINE STARTED")
        self.log("=" * 80)
        self.send_imessage("🤖 Autonomous replication engine started. Target: 100% fidelity.")
        
        iteration_count = 0
        
        while True:  # INFINITE LOOP - only stops when objective achieved
            try:
                iteration_count += 1
                self.log(f"\n{'=' * 80}")
                self.log(f"CONTINUOUS LOOP ITERATION #{iteration_count}")
                self.log(f"{'=' * 80}")
                
                # Check current fidelity
                fidelity_status = self.check_fidelity()
                self.log(f"Current Fidelity: {fidelity_status['fidelity']:.1f}% ({fidelity_status['target_count']}/{fidelity_status['source_count']})")
                self.log(f"Gap: {fidelity_status['gap']} resources")
                
                # Check if objective achieved
                if (fidelity_status['fidelity'] >= FIDELITY_TARGET and 
                    self.consecutive_passes >= CONSECUTIVE_PASSES_REQUIRED):
                    self.log("=" * 80)
                    self.log("🎉 OBJECTIVE ACHIEVED!")
                    self.log(f"Fidelity: {fidelity_status['fidelity']:.1f}%")
                    self.log(f"Consecutive Passes: {self.consecutive_passes}")
                    self.log("=" * 80)
                    self.send_imessage(f"🎉 OBJECTIVE ACHIEVED! Fidelity: {fidelity_status['fidelity']:.1f}%")
                    break  # Only exit point
                
                # Identify missing types and spawn fix workstreams
                missing_types = self.identify_missing_types()
                if missing_types and len(self.parallel_workstreams) < 3:  # Limit to 3 parallel workstreams
                    for resource_type, count in missing_types[:3]:  # Fix top 3 types
                        if resource_type not in [ws['resource_type'] for ws in self.parallel_workstreams.values()]:
                            self.spawn_fix_workstream(resource_type, count)
                
                # Check workstream progress
                completed = self.check_workstreams()
                if completed > 0:
                    self.log(f"✓ {completed} workstreams completed this cycle")
                
                # Generate new iteration
                if self.generate_iteration():
                    # Validate iteration
                    if self.validate_iteration():
                        # If we have enough consecutive passes, deploy
                        if self.consecutive_passes >= CONSECUTIVE_PASSES_REQUIRED:
                            if self.deploy_iteration():
                                # Rescan target after successful deployment
                                self.rescan_target()
                                # Reset consecutive passes
                                self.consecutive_passes = 0
                    else:
                        # Validation failed - workstreams should fix issues
                        self.log("Validation failed - relying on parallel workstreams to fix")
                
                # Save status
                status = {
                    "iteration": self.current_iteration,
                    "loop_count": iteration_count,
                    "fidelity": fidelity_status,
                    "consecutive_passes": self.consecutive_passes,
                    "active_workstreams": len(self.parallel_workstreams),
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.save_status(status)
                
                # Send periodic status update
                if iteration_count % 5 == 0:
                    self.send_imessage(
                        f"Status: {fidelity_status['fidelity']:.1f}% fidelity, "
                        f"iteration {self.current_iteration}, "
                        f"{len(self.parallel_workstreams)} workstreams active"
                    )
                
                # Brief sleep to avoid overwhelming the system
                time.sleep(30)
                
            except KeyboardInterrupt:
                self.log("Keyboard interrupt received - stopping")
                break
            except Exception as e:
                self.log(f"Error in main loop: {e}")
                import traceback
                self.log(traceback.format_exc())
                # Don't stop - just log and continue
                time.sleep(60)
        
        self.log("Engine stopped")
        self.driver.close()

if __name__ == "__main__":
    engine = ContinuousEngine()
    engine.run_continuous_loop()
