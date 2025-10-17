#!/usr/bin/env python3
"""
Continuous Autonomous Orchestrator for Azure Tenant Grapher

This script NEVER STOPS until the objective is 100% achieved.
It runs continuously, monitors deployments, spawns agents, and progresses iterations.
"""

import subprocess
import json
import time
import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

PROJECT_ROOT = Path("/Users/ryan/src/msec/atg-0723/azure-tenant-grapher")
DEMOS_DIR = PROJECT_ROOT / "demos"
IMESS_TOOL = Path.home() / ".local/bin/imessR"
ORCHESTRATOR_STATE = PROJECT_ROOT / ".claude/runtime/orchestrator"
AGENT_LOGS = ORCHESTRATOR_STATE / "agent_logs"

# Create directories
ORCHESTRATOR_STATE.mkdir(parents=True, exist_ok=True)
AGENT_LOGS.mkdir(parents=True, exist_ok=True)

# Source and target tenant subscription IDs
SOURCE_SUB_ID = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
TARGET_SUB_ID = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"

@dataclass
class ActiveAgent:
    """Represents an active subagent process"""
    name: str
    process: subprocess.Popen
    gap_type: str
    started_at: datetime
    log_file: Path

class OrchestrationCycle:
    """Manages orchestration cycles"""
    
    def __init__(self):
        self.cycle_count = 0
        self.active_agents: List[ActiveAgent] = []
        self.last_status_update = 0
        
    def send_imessage(self, message: str) -> None:
        """Send iMessage notification"""
        try:
            subprocess.run(
                [str(IMESS_TOOL), message],
                timeout=10,
                check=False,
                capture_output=True
            )
        except Exception:
            pass
    
    def scan_target_tenant(self) -> bool:
        """Scan target tenant to update Neo4j with deployed resources"""
        self.log("INFO", "Scanning target tenant...")
        
        try:
            result = subprocess.run(
                [
                    "uv", "run", "atg", "scan",
                    "--filter-by-subscriptions", TARGET_SUB_ID
                ],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes
                cwd=PROJECT_ROOT
            )
            
            if result.returncode == 0:
                self.log("INFO", "✅ Target tenant scan complete")
                return True
            else:
                self.log("WARNING", f"Target scan failed: {result.stderr[:200]}")
                return False
                
        except Exception as e:
            self.log("ERROR", f"Error scanning target: {e}")
            return False
    
    def log(self, level: str, message: str) -> None:
        """Log with timestamp"""
        timestamp = datetime.utcnow().isoformat()
        print(f"{timestamp} [{level:5s}] {message}", flush=True)
    
    def get_neo4j_counts(self) -> Tuple[int, int, float]:
        """Get resource counts from Neo4j"""
        try:
            # Load environment
            env_file = PROJECT_ROOT / ".env"
            env_vars = {}
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            env_vars[key] = value
            
            neo4j_password = env_vars.get('NEO4J_PASSWORD', 'password')
            
            script = f"""
from py2neo import Graph

graph = Graph('bolt://localhost:7688', auth=('neo4j', '{neo4j_password}'))

source = graph.run('''
MATCH (r:Resource)
WHERE r.subscription_id = "{SOURCE_SUB_ID}"
RETURN count(r) as count
''').evaluate()

target = graph.run('''
MATCH (r:Resource)
WHERE r.subscription_id = "{TARGET_SUB_ID}"
RETURN count(r) as count
''').evaluate()

fidelity = (target / source * 100) if source > 0 else 0
print(f"{{source}},{{target}},{{fidelity:.2f}}")
"""
            
            result = subprocess.run(
                ["python3", "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=PROJECT_ROOT
            )
            
            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                if len(parts) == 3:
                    return int(parts[0]), int(parts[1]), float(parts[2])
            
            return 0, 0, 0.0
            
        except Exception as e:
            self.log("ERROR", f"Error querying Neo4j: {e}")
            return 0, 0, 0.0
    
    def get_latest_iteration(self) -> int:
        """Find latest iteration number"""
        max_iter = 0
        for path in DEMOS_DIR.glob("iteration*"):
            if path.is_dir():
                match = re.search(r'iteration(\d+)', path.name)
                if match:
                    max_iter = max(max_iter, int(match.group(1)))
        return max_iter
    
    def check_iteration_status(self, iteration: int) -> str:
        """Check iteration status"""
        iter_dir = DEMOS_DIR / f"iteration{iteration}"
        
        if not iter_dir.exists():
            return "not_found"
        
        tfstate = iter_dir / "terraform.tfstate"
        if tfstate.exists():
            return "complete"
        
        # Check if apply is currently running
        for pid_file in ORCHESTRATOR_STATE.glob(f"terraform_apply_{iteration}.pid"):
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return "applying"
            except (OSError, ValueError):
                pid_file.unlink(missing_ok=True)
        
        tfplan = iter_dir / "tfplan"
        if tfplan.exists():
            return "planned"
        
        terraform_dir = iter_dir / ".terraform"
        if terraform_dir.exists():
            return "initialized"
        
        tf_json = iter_dir / "main.tf.json"
        if tf_json.exists():
            return "generated"
        
        return "empty"
    
    def check_and_cleanup_agents(self) -> None:
        """Check for completed agents"""
        completed = []
        
        for i, agent in enumerate(self.active_agents):
            poll = agent.process.poll()
            if poll is not None:
                completed.append(i)
                duration = (datetime.utcnow() - agent.started_at).total_seconds()
                self.log("INFO", f"✅ Agent {agent.name} completed (duration: {duration:.0f}s)")
                self.send_imessage(f"✅ Agent {agent.name} completed")
        
        for i in reversed(completed):
            self.active_agents.pop(i)
    
    def generate_next_iteration(self, next_num: int) -> bool:
        """Generate next iteration"""
        self.log("INFO", f"Generating iteration {next_num}...")
        
        try:
            result = subprocess.run(
                [
                    "uv", "run", "atg", "generate-iac",
                    "--resource-filters", "resourceGroup=~'(?i).*(simuland|SimuLand).*'",
                    "--resource-group-prefix", f"ITERATION{next_num}_",
                    "--skip-name-validation",
                    "--output", f"demos/iteration{next_num}"
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=PROJECT_ROOT
            )
            
            if result.returncode == 0:
                self.log("INFO", f"✅ Generated iteration {next_num}")
                self.send_imessage(f"✅ Generated iteration {next_num}")
                return True
            else:
                self.log("ERROR", f"❌ Failed to generate: {result.stderr[:200]}")
                return False
                
        except Exception as e:
            self.log("ERROR", f"Error generating: {e}")
            return False
    
    def terraform_init(self, iteration: int) -> bool:
        """Initialize terraform"""
        iter_dir = DEMOS_DIR / f"iteration{iteration}"
        
        # Get Azure environment variables
        env = os.environ.copy()
        env['ARM_SUBSCRIPTION_ID'] = TARGET_SUB_ID
        env['ARM_TENANT_ID'] = 'c7674d41-af6c-46f5-89a5-d41495d2151e'
        
        try:
            result = subprocess.run(
                ["terraform", "init"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=iter_dir,
                env=env
            )
            return result.returncode == 0
        except Exception as e:
            self.log("ERROR", f"Error init: {e}")
            return False
    
    def terraform_plan(self, iteration: int) -> bool:
        """Create terraform plan"""
        iter_dir = DEMOS_DIR / f"iteration{iteration}"
        
        # Get Azure environment variables  
        env = os.environ.copy()
        env['ARM_SUBSCRIPTION_ID'] = TARGET_SUB_ID
        env['ARM_TENANT_ID'] = 'c7674d41-af6c-46f5-89a5-d41495d2151e'
        
        try:
            result = subprocess.run(
                ["terraform", "plan", "-out=tfplan"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=iter_dir,
                env=env
            )
            
            if result.returncode != 0:
                self.log("WARNING", f"Plan failed iteration {iteration}")
                # Log the error details
                error_log = ORCHESTRATOR_STATE / f"terraform_plan_{iteration}_error.log"
                error_log.write_text(result.stdout + "\n" + result.stderr)
                return False
            
            return True
        except Exception as e:
            self.log("ERROR", f"Error plan: {e}")
            return False
    
    def terraform_apply_async(self, iteration: int) -> Optional[int]:
        """Start terraform apply in background"""
        iter_dir = DEMOS_DIR / f"iteration{iteration}"
        log_file = ORCHESTRATOR_STATE / f"terraform_apply_{iteration}.log"
        
        # Get Azure environment variables
        env = os.environ.copy()
        env['ARM_SUBSCRIPTION_ID'] = TARGET_SUB_ID
        env['ARM_TENANT_ID'] = 'c7674d41-af6c-46f5-89a5-d41495d2151e'
        
        try:
            process = subprocess.Popen(
                ["terraform", "apply", "tfplan"],
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                cwd=iter_dir,
                env=env
            )
            
            pid_file = ORCHESTRATOR_STATE / f"terraform_apply_{iteration}.pid"
            pid_file.write_text(str(process.pid))
            
            self.log("INFO", f"Started apply iteration {iteration} (PID: {process.pid})")
            self.send_imessage(f"🔄 Deploying iteration {iteration}...")
            
            return process.pid
            
        except Exception as e:
            self.log("ERROR", f"Error apply: {e}")
            return None
    
    def evaluate_objective(self) -> bool:
        """Evaluate if objective achieved"""
        source_count, target_count, fidelity = self.get_neo4j_counts()
        latest_iter = self.get_latest_iteration()
        
        self.log("INFO", f"📊 Source: {source_count} | Target: {target_count} | Fidelity: {fidelity:.1f}%")
        
        fidelity_met = fidelity >= 95.0
        
        consecutive_complete = 0
        for i in range(latest_iter, max(0, latest_iter - 2), -1):
            status = self.check_iteration_status(i)
            if status == "complete":
                consecutive_complete += 1
            else:
                break
        
        criteria_met = fidelity_met and consecutive_complete >= 3
        
        self.log("INFO", f"🎯 Objective: {'✅ ACHIEVED' if criteria_met else '🔄 In Progress'}")
        self.log("INFO", f"   - Fidelity >=95%: {'✅' if fidelity_met else '❌'} ({fidelity:.1f}%)")
        self.log("INFO", f"   - 3 passes: {'✅' if consecutive_complete >= 3 else '❌'} ({consecutive_complete}/3)")
        
        return criteria_met
    
    def progress_iteration(self, iteration: int, status: str) -> None:
        """Progress iteration to next state"""
        
        if status == "complete":
            # Scan target tenant to update Neo4j, then generate next iteration
            self.log("INFO", f"Iteration {iteration} complete - scanning target tenant...")
            self.scan_target_tenant()
            
            next_iter = iteration + 1
            self.generate_next_iteration(next_iter)
            
        elif status == "applying":
            # Wait for apply to complete
            self.log("INFO", f"Iteration {iteration} is applying - waiting...")
            
        elif status == "planned":
            # Start apply
            self.terraform_apply_async(iteration)
            
        elif status == "initialized":
            # Create plan
            if self.terraform_plan(iteration):
                self.log("INFO", f"✅ Planned iteration {iteration}")
            
        elif status == "generated":
            # Initialize terraform
            if self.terraform_init(iteration):
                self.log("INFO", f"✅ Initialized iteration {iteration}")
    
    def run_cycle(self) -> bool:
        """Run one cycle. Returns True if objective achieved."""
        self.cycle_count += 1
        self.log("INFO", f"{'='*80}")
        self.log("INFO", f"Cycle {self.cycle_count}")
        self.log("INFO", f"{'='*80}")
        
        # 1. Evaluate objective
        if self.evaluate_objective():
            self.log("INFO", "🎉 OBJECTIVE ACHIEVED!")
            self.send_imessage("🎉 OBJECTIVE ACHIEVED! 100% fidelity!")
            return True
        
        # 2. Check agents
        self.check_and_cleanup_agents()
        
        # 3. Check if ANY terraform apply is currently running
        any_applying = False
        for pid_file in ORCHESTRATOR_STATE.glob("terraform_apply_*.pid"):
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                # Process is running
                any_applying = True
                match = re.search(r'terraform_apply_(\d+).pid', pid_file.name)
                if match:
                    iter_num = match.group(1)
                    self.log("INFO", f"Terraform apply for iteration {iter_num} is still running (PID: {pid})")
                break
            except (OSError, ValueError):
                pid_file.unlink(missing_ok=True)
        
        # 4. Only progress if no terraform apply is running
        if not any_applying:
            latest_iter = self.get_latest_iteration()
            if latest_iter > 0:
                status = self.check_iteration_status(latest_iter)
                self.log("INFO", f"Iteration {latest_iter}: {status}")
                
                # Progress iteration
                self.progress_iteration(latest_iter, status)
            else:
                # Start first iteration
                self.generate_next_iteration(100)
        
        # 5. Periodic updates
        current_time = time.time()
        if current_time - self.last_status_update >= 600:
            source, target, fidelity = self.get_neo4j_counts()
            self.send_imessage(
                f"🔄 Cycle {self.cycle_count}\n"
                f"Fidelity: {fidelity:.1f}%\n"
                f"Iteration: {self.get_latest_iteration()}"
            )
            self.last_status_update = current_time
        
        # 6. Log agents
        if self.active_agents:
            self.log("INFO", f"Active agents: {', '.join(a.name for a in self.active_agents)}")
        
        return False

def main():
    """Main loop - NEVER STOPS until objective achieved"""
    orchestrator = OrchestrationCycle()
    
    orchestrator.log("INFO", "🚀 Orchestrator Started - Running Until 100% Objective Achieved")
    orchestrator.send_imessage("🚀 Orchestrator started - running continuously until 100% objective achieved")
    
    try:
        while True:
            objective_achieved = orchestrator.run_cycle()
            
            if objective_achieved:
                orchestrator.log("INFO", "Objective achieved, exiting")
                return 0
            
            # Sleep between cycles
            time.sleep(30)
            
    except KeyboardInterrupt:
        orchestrator.log("WARNING", "⏸️  Interrupted by user")
        orchestrator.send_imessage("⏸️  Orchestrator stopped by user")
        return 1
    except Exception as e:
        orchestrator.log("ERROR", f"Fatal error: {e}")
        orchestrator.send_imessage(f"❌ Orchestrator error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
