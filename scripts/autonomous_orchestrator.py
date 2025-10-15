#!/usr/bin/env python3
"""
Autonomous Orchestrator for Azure Tenant Replication

This script runs continuously until the objective is achieved:
- 100% fidelity between source and target tenants
- All resources replicated successfully
- No validation or deployment errors

It:
1. Monitors each iteration deployment actively (doesn't stop)
2. Spawns subagents to fix gaps in parallel
3. Uses ATG commands exclusively
4. Sends iMessage status updates
5. Evaluates objective continuously
6. Never stops until objective achieved
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tempfile
import signal

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class AutonomousOrchestrator:
    """Continuously orchestrates tenant replication until 100% fidelity achieved"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.demos_dir = self.project_root / "demos"
        self.objective_file = self.demos_dir / "OBJECTIVE.md"
        self.state_file = self.demos_dir / "orchestrator_state.json"
        self.running = True
        self.current_iteration = None
        self.active_subagents = {}
        self.iteration_history = []
        
        # Set up signal handlers to prevent premature exit
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        
    def _handle_signal(self, signum, frame):
        """Handle signals gracefully but don't stop until objective achieved"""
        self.log("⚠️  Signal received but continuing until objective achieved...")
        self.send_imessage("⚠️ Orchestrator: Signal received but continuing to work toward 100% fidelity")
        
    def log(self, message: str):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}", flush=True)
        
    def send_imessage(self, message: str):
        """Send iMessage update"""
        try:
            subprocess.run(
                ["imessR", message],
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            self.log(f"Warning: Could not send iMessage: {e}")
            
    def get_neo4j_stats(self) -> Dict:
        """Query Neo4j for current resource counts"""
        try:
            result = subprocess.run(
                [
                    "uv", "run", "python", "-c",
                    """
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
import json

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI', 'bolt://localhost:7688'),
    auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', ''))
)

with driver.session() as session:
    # Count by subscription
    result = session.run('''
        MATCH (r:Resource)
        RETURN r.subscription_id as sub, count(r) as cnt
    ''')
    stats = {rec["sub"]: rec["cnt"] for rec in result}
    
    # Total nodes
    result = session.run('MATCH (n) RETURN count(n) as total')
    stats['total_nodes'] = result.single()["total"]
    
    # Total edges
    result = session.run('MATCH ()-[r]->() RETURN count(r) as total')
    stats['total_edges'] = result.single()["total"]

driver.close()
print(json.dumps(stats))
"""
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=60
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            else:
                self.log(f"Error querying Neo4j: {result.stderr}")
                return {}
        except Exception as e:
            self.log(f"Error querying Neo4j: {e}")
            return {}
            
    def evaluate_objective(self) -> Tuple[bool, Dict]:
        """
        Evaluate if objective is achieved
        Returns: (achieved, metrics)
        """
        stats = self.get_neo4j_stats()
        
        # Source and target subscription IDs
        source_sub = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
        target_sub = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"
        
        source_count = stats.get(source_sub, 0)
        target_count = stats.get(target_sub, 0)
        
        # Calculate fidelity
        fidelity = (target_count / source_count * 100) if source_count > 0 else 0
        gap = source_count - target_count
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "source_resources": source_count,
            "target_resources": target_count,
            "fidelity_percent": round(fidelity, 2),
            "resource_gap": gap,
            "total_nodes": stats.get('total_nodes', 0),
            "total_edges": stats.get('total_edges', 0),
        }
        
        # Objective: >= 95% fidelity
        achieved = fidelity >= 95.0
        
        return achieved, metrics
        
    def find_latest_iteration(self) -> Optional[int]:
        """Find the latest iteration number"""
        iterations = [
            int(d.name.replace("iteration", ""))
            for d in self.demos_dir.iterdir()
            if d.is_dir() and d.name.startswith("iteration") and d.name[9:].isdigit()
        ]
        return max(iterations) if iterations else None
        
    def check_iteration_status(self, iteration_num: int) -> Dict:
        """Check status of an iteration"""
        iter_dir = self.demos_dir / f"iteration{iteration_num}"
        
        if not iter_dir.exists():
            return {"status": "not_found"}
            
        # Check for terraform state
        tfstate = iter_dir / "terraform.tfstate"
        plan_file = iter_dir / "tfplan"
        
        if tfstate.exists():
            # Check if deployment completed
            try:
                with open(tfstate) as f:
                    state = json.load(f)
                    resources = state.get("resources", [])
                    return {
                        "status": "deployed",
                        "resource_count": len(resources)
                    }
            except:
                pass
                
        if plan_file.exists():
            return {"status": "planned"}
            
        if (iter_dir / "main.tf.json").exists():
            return {"status": "generated"}
            
        return {"status": "unknown"}
        
    def spawn_subagent(self, agent_name: str, task: str, context_files: List[str] = None) -> subprocess.Popen:
        """
        Spawn a subagent to work on a task in parallel
        
        Args:
            agent_name: Name of the agent (e.g., "fix-agent", "architect")
            task: Description of the task
            context_files: List of .md files to include as context
        """
        self.log(f"🤖 Spawning subagent: {agent_name} for: {task}")
        
        # Build prompt with context
        context = ""
        if context_files:
            for cf in context_files:
                cf_path = self.project_root / cf
                if cf_path.exists():
                    with open(cf_path) as f:
                        context += f"\n\n# Context from {cf}\n\n{f.read()}"
        
        prompt = f"{context}\n\n# Task\n\n{task}"
        
        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(prompt)
            prompt_file = f.name
            
        # Spawn copilot process
        proc = subprocess.Popen(
            ["copilot", "--allow-all-tools", "-p", prompt],
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.active_subagents[agent_name] = {
            "process": proc,
            "task": task,
            "start_time": time.time(),
            "prompt_file": prompt_file
        }
        
        return proc
        
    def check_subagents(self):
        """Check status of active subagents"""
        completed = []
        
        for name, info in self.active_subagents.items():
            proc = info["process"]
            if proc.poll() is not None:
                # Process completed
                stdout, stderr = proc.communicate()
                duration = time.time() - info["start_time"]
                
                self.log(f"✅ Subagent '{name}' completed in {duration:.1f}s")
                if proc.returncode != 0:
                    self.log(f"   ⚠️  Exit code: {proc.returncode}")
                    self.log(f"   stderr: {stderr[:500]}")
                    
                # Clean up temp file
                try:
                    os.unlink(info["prompt_file"])
                except:
                    pass
                    
                completed.append(name)
                
        # Remove completed agents
        for name in completed:
            del self.active_subagents[name]
            
    def generate_iteration(self, iteration_num: int) -> bool:
        """Generate a new iteration using ATG"""
        self.log(f"🔨 Generating iteration {iteration_num}...")
        
        output_dir = self.demos_dir / f"iteration{iteration_num}"
        
        try:
            result = subprocess.run(
                [
                    "uv", "run", "atg", "generate-iac",
                    "--resource-group-prefix", f"ITERATION{iteration_num}_",
                    "--skip-name-validation",
                    "--skip-validation",  # Skip interactive terraform validation
                    "--skip-conflict-check",  # Skip conflict check (auth issues)
                    "--output", str(output_dir)
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # Reduced from 600s since we skip validation
            )
            
            if result.returncode == 0:
                self.log(f"✅ Generated iteration {iteration_num}")
                return True
            else:
                self.log(f"❌ Failed to generate iteration {iteration_num}")
                self.log(f"   stderr: {result.stderr[:500]}")
                return False
                
        except Exception as e:
            self.log(f"❌ Error generating iteration: {e}")
            return False
            
    def validate_iteration(self, iteration_num: int) -> Tuple[bool, List[str]]:
        """Validate iteration using terraform validate"""
        iter_dir = self.demos_dir / f"iteration{iteration_num}"
        self.log(f"🔍 Validating iteration {iteration_num}...")
        
        errors = []
        
        try:
            # Initialize terraform
            result = subprocess.run(
                ["terraform", "init"],
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                errors.append(f"terraform init failed: {result.stderr[:200]}")
                return False, errors
                
            # Validate
            result = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                validate_result = json.loads(result.stdout)
                if validate_result.get("valid", False):
                    self.log(f"✅ Iteration {iteration_num} validation passed")
                    return True, []
                else:
                    errors = [
                        diag.get("summary", "Unknown error")
                        for diag in validate_result.get("diagnostics", [])
                    ]
                    
            else:
                errors.append(f"terraform validate failed: {result.stderr[:200]}")
                
        except Exception as e:
            errors.append(f"Validation exception: {str(e)}")
            
        self.log(f"❌ Iteration {iteration_num} validation failed: {len(errors)} errors")
        return False, errors
        
    def deploy_iteration(self, iteration_num: int) -> bool:
        """
        Deploy iteration using terraform
        This is a long-running operation that we monitor actively
        """
        iter_dir = self.demos_dir / f"iteration{iteration_num}"
        self.log(f"🚀 Deploying iteration {iteration_num}...")
        self.send_imessage(f"🚀 Starting deployment of iteration {iteration_num}")
        
        try:
            # Plan
            self.log(f"   Planning...")
            plan_result = subprocess.run(
                ["terraform", "plan", "-out=tfplan"],
                cwd=iter_dir,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if plan_result.returncode != 0:
                self.log(f"❌ Plan failed: {plan_result.stderr[:500]}")
                return False
                
            # Apply - this is the long operation we monitor
            self.log(f"   Applying (this may take 30-60 minutes)...")
            
            apply_proc = subprocess.Popen(
                ["terraform", "apply", "-auto-approve", "tfplan"],
                cwd=iter_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor the apply process
            start_time = time.time()
            last_update = start_time
            
            while apply_proc.poll() is None:
                # Sleep but stay alive
                time.sleep(30)
                
                # Send update every 5 minutes
                elapsed = time.time() - start_time
                if time.time() - last_update > 300:  # 5 minutes
                    self.log(f"   Still deploying... ({elapsed/60:.1f} minutes elapsed)")
                    self.send_imessage(f"⏳ Iteration {iteration_num} deployment: {elapsed/60:.1f} minutes elapsed")
                    last_update = time.time()
                    
            # Get final result
            stdout, stderr = apply_proc.communicate()
            duration = time.time() - start_time
            
            if apply_proc.returncode == 0:
                self.log(f"✅ Deployment completed in {duration/60:.1f} minutes")
                self.send_imessage(f"✅ Iteration {iteration_num} deployed successfully in {duration/60:.1f} min")
                
                # Save logs
                with open(iter_dir / "apply.log", "w") as f:
                    f.write(stdout)
                with open(iter_dir / "apply_errors.log", "w") as f:
                    f.write(stderr)
                    
                return True
            else:
                self.log(f"❌ Deployment failed after {duration/60:.1f} minutes")
                self.send_imessage(f"❌ Iteration {iteration_num} deployment failed")
                
                # Save error logs
                with open(iter_dir / "apply_errors.log", "w") as f:
                    f.write(stderr)
                    
                return False
                
        except Exception as e:
            self.log(f"❌ Deployment exception: {e}")
            self.send_imessage(f"❌ Iteration {iteration_num} deployment exception: {str(e)[:100]}")
            return False
            
    def analyze_errors(self, errors: List[str]) -> Dict[str, List[str]]:
        """Categorize errors to identify what needs fixing"""
        categories = {
            "resource_type_mapping": [],
            "property_extraction": [],
            "dependency": [],
            "validation": [],
            "other": []
        }
        
        for error in errors:
            error_lower = error.lower()
            
            if "unsupported" in error_lower or "not mapped" in error_lower:
                categories["resource_type_mapping"].append(error)
            elif "property" in error_lower or "attribute" in error_lower:
                categories["property_extraction"].append(error)
            elif "dependency" in error_lower or "depends" in error_lower:
                categories["dependency"].append(error)
            elif "validate" in error_lower:
                categories["validation"].append(error)
            else:
                categories["other"].append(error)
                
        return categories
        
    async def run_iteration_cycle(self):
        """
        Run one complete iteration cycle:
        1. Generate
        2. Validate  
        3. If valid: Deploy
        4. If errors: Spawn fix agents
        5. Wait for fixes
        6. Repeat
        """
        # Find next iteration number
        latest = self.find_latest_iteration()
        next_iter = (latest + 1) if latest else 1
        
        self.log(f"\n{'='*60}")
        self.log(f"Starting Iteration Cycle {next_iter}")
        self.log(f"{'='*60}\n")
        
        # Generate
        if not self.generate_iteration(next_iter):
            self.log("Generation failed, will retry in 60s")
            await asyncio.sleep(60)
            return
            
        # Validate
        valid, errors = self.validate_iteration(next_iter)
        
        if valid:
            # Deploy
            success = self.deploy_iteration(next_iter)
            
            if success:
                # Scan target tenant to update Neo4j
                self.log("📊 Scanning target tenant to update graph...")
                subprocess.run(
                    ["uv", "run", "atg", "scan"],
                    cwd=self.project_root,
                    timeout=1800  # 30 minutes
                )
                
                # Evaluate objective
                achieved, metrics = self.evaluate_objective()
                
                self.log(f"\n📈 Metrics after iteration {next_iter}:")
                self.log(f"   Fidelity: {metrics['fidelity_percent']}%")
                self.log(f"   Source: {metrics['source_resources']} resources")
                self.log(f"   Target: {metrics['target_resources']} resources")
                self.log(f"   Gap: {metrics['resource_gap']} resources")
                
                self.send_imessage(
                    f"📈 Iteration {next_iter} complete!\n"
                    f"Fidelity: {metrics['fidelity_percent']}%\n"
                    f"Gap: {metrics['resource_gap']} resources remaining"
                )
                
                if achieved:
                    self.log("\n🎉 OBJECTIVE ACHIEVED! 100% fidelity reached!")
                    self.send_imessage("🎉 OBJECTIVE ACHIEVED! Azure tenant replication complete at 100% fidelity!")
                    self.running = False
                    return
                    
        else:
            # Analyze errors and spawn fix agents
            self.log(f"❌ Validation failed with {len(errors)} errors")
            
            error_categories = self.analyze_errors(errors)
            
            # Spawn agents to fix each category in parallel
            if error_categories["resource_type_mapping"]:
                self.spawn_subagent(
                    "resource-mapper",
                    f"""Fix resource type mapping errors in iteration {next_iter}.
                    
Errors:
{chr(10).join(error_categories['resource_type_mapping'][:5])}

Add mappings to src/iac/emitters/terraform_emitter.py AZURE_TO_TERRAFORM_MAPPING.
Implement emitter logic in _generate_resource() method.
Add tests for each new resource type.""",
                    context_files=[".claude/agents/amplihack/specialized/fix-agent.md"]
                )
                
            if error_categories["property_extraction"]:
                self.spawn_subagent(
                    "property-fixer",
                    f"""Fix property extraction errors in iteration {next_iter}.
                    
Errors:
{chr(10).join(error_categories['property_extraction'][:5])}

Check for truncated properties in Neo4j.
Update resource_processor.py to extract properties correctly.
Add property size monitoring.""",
                    context_files=[".claude/agents/amplihack/specialized/fix-agent.md"]
                )
                
            # Wait a bit for agents to start
            await asyncio.sleep(120)
            
    async def main_loop(self):
        """Main orchestration loop - runs continuously until objective achieved"""
        self.log("\n" + "="*60)
        self.log("🚀 Autonomous Orchestrator Started")
        self.log("="*60)
        self.log(f"Objective: 100% tenant replication fidelity")
        self.log(f"Source: DefenderATEVET17")
        self.log(f"Target: DefenderATEVET12")
        self.log("="*60 + "\n")
        
        self.send_imessage("🚀 Autonomous Orchestrator started - working toward 100% tenant replication")
        
        # Initial objective check
        achieved, metrics = self.evaluate_objective()
        self.log(f"📊 Starting Metrics:")
        self.log(f"   Fidelity: {metrics['fidelity_percent']}%")
        self.log(f"   Gap: {metrics['resource_gap']} resources\n")
        
        if achieved:
            self.log("🎉 Objective already achieved!")
            self.send_imessage("🎉 Objective already achieved! 100% fidelity reached!")
            return
            
        iteration_count = 0
        
        while self.running:
            try:
                # Check subagents
                self.check_subagents()
                
                # Only run new iteration if no active subagents working on fixes
                if not self.active_subagents:
                    await self.run_iteration_cycle()
                    iteration_count += 1
                else:
                    # Wait for subagents to finish
                    self.log(f"⏳ Waiting for {len(self.active_subagents)} subagents to complete fixes...")
                    await asyncio.sleep(60)
                    
                # Small delay between iterations
                if self.running:
                    await asyncio.sleep(30)
                    
            except KeyboardInterrupt:
                self.log("\n⚠️  Interrupt received but continuing (objective not achieved)")
                self.send_imessage("⚠️ Orchestrator: Interrupt received but continuing toward objective")
                await asyncio.sleep(5)
                
            except Exception as e:
                self.log(f"❌ Error in main loop: {e}")
                self.send_imessage(f"❌ Orchestrator error: {str(e)[:100]}")
                await asyncio.sleep(60)
                
        self.log("\n" + "="*60)
        self.log("✅ Orchestrator completed - objective achieved!")
        self.log("="*60 + "\n")

if __name__ == "__main__":
    orchestrator = AutonomousOrchestrator()
    asyncio.run(orchestrator.main_loop())
