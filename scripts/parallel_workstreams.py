#!/usr/bin/env python3
"""
Parallel Workstream Orchestrator

Manages multiple parallel workstreams to achieve the objective:
1. Source tenant full scan (control plane + Entra ID)
2. Entra ID resource mapping and IaC generation
3. Data plane plugin development
4. Deployment of validated iteration

Each workstream runs independently and reports progress.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
WORKSTREAM_STATUS_FILE = PROJECT_ROOT / "demos" / "workstream_status.json"


class WorkstreamOrchestrator:
    """Orchestrate parallel workstreams."""

    def __init__(self):
        self.status = self._load_status()
        self.threads = []

    def _load_status(self) -> Dict:
        """Load workstream status from disk."""
        if WORKSTREAM_STATUS_FILE.exists():
            with open(WORKSTREAM_STATUS_FILE) as f:
                return json.load(f)
        return {"workstreams": {}, "start_time": datetime.now().isoformat()}

    def _save_status(self):
        """Save workstream status to disk."""
        WORKSTREAM_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(WORKSTREAM_STATUS_FILE, "w") as f:
            json.dump(self.status, f, indent=2)

    def _send_imessage(self, message: str):
        """Send iMessage status update."""
        try:
            subprocess.run(
                [os.path.expanduser("~/.local/bin/imessR"), message],
                capture_output=True,
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Failed to send iMessage: {e}")

    def _run_command(
        self, cmd: List[str], workstream: str, timeout: int = 600
    ) -> tuple[bool, str]:
        """
        Run a command and capture output.

        Returns:
            (success, output)
        """
        try:
            result = subprocess.run(
                cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr

        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout}s"
        except Exception as e:
            return False, str(e)

    def workstream_full_scan(self):
        """Workstream 1: Full tenant scan (ARM + Entra ID)."""
        workstream_name = "full_scan"
        logger.info(f"[{workstream_name}] Starting full tenant scan...")

        self.status["workstreams"][workstream_name] = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": [],
        }
        self._save_status()

        # Step 1: Scan ARM resources
        logger.info(f"[{workstream_name}] Scanning ARM resources...")
        success, output = self._run_command(
            ["uv", "run", "atg", "scan", "--include-entra-id"],
            workstream_name,
            timeout=1800,  # 30 minutes for full scan
        )

        if success:
            self.status["workstreams"][workstream_name]["progress"].append(
                {
                    "step": "arm_scan",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self._send_imessage(f"✅ [{workstream_name}] ARM scan completed")
        else:
            self.status["workstreams"][workstream_name]["status"] = "failed"
            self.status["workstreams"][workstream_name]["error"] = output[-200:]
            self._send_imessage(
                f"❌ [{workstream_name}] ARM scan failed: {output[-100:]}"
            )
            self._save_status()
            return

        # Mark as completed
        self.status["workstreams"][workstream_name]["status"] = "completed"
        self.status["workstreams"][workstream_name]["end_time"] = (
            datetime.now().isoformat()
        )
        self._save_status()

        logger.info(f"[{workstream_name}] ✅ Full scan completed")

    def workstream_entra_id_mapping(self):
        """Workstream 2: Entra ID resource mapping."""
        workstream_name = "entra_id_mapping"
        logger.info(f"[{workstream_name}] Starting Entra ID mapping...")

        self.status["workstreams"][workstream_name] = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": [],
        }
        self._save_status()

        # For now, this is a placeholder - Entra ID mapping needs to be implemented
        # This workstream would:
        # 1. Query Neo4j for User, Group, ServicePrincipal, Application nodes
        # 2. Generate azuread_* Terraform resources
        # 3. Handle group memberships and role assignments

        logger.info(f"[{workstream_name}] Querying Entra ID resources from Neo4j...")
        time.sleep(5)  # Placeholder

        self.status["workstreams"][workstream_name]["status"] = "pending_implementation"
        self.status["workstreams"][workstream_name]["note"] = (
            "Entra ID mapping needs implementation in terraform_emitter.py"
        )
        self._save_status()

        logger.info(f"[{workstream_name}] ⏳ Pending implementation")

    def workstream_data_plane_plugins(self):
        """Workstream 3: Data plane plugin development."""
        workstream_name = "data_plane_plugins"
        logger.info(f"[{workstream_name}] Starting data plane plugin development...")

        self.status["workstreams"][workstream_name] = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": [],
        }
        self._save_status()

        # Check if data plane plugin infrastructure exists
        plugin_dir = PROJECT_ROOT / "src" / "iac" / "data_plane_plugins"

        if plugin_dir.exists():
            logger.info(f"[{workstream_name}] Data plane plugin infrastructure found")
            self.status["workstreams"][workstream_name]["status"] = (
                "infrastructure_ready"
            )
        else:
            logger.info(
                f"[{workstream_name}] Creating data plane plugin infrastructure..."
            )
            plugin_dir.mkdir(parents=True, exist_ok=True)

            # Create __init__.py
            (plugin_dir / "__init__.py").write_text("# Data plane plugins\n")

            # Create base plugin
            base_plugin_code = '''"""
Base class for data plane replication plugins.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class DataPlanePlugin(ABC):
    """Base class for data plane replication plugins."""

    @abstractmethod
    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given resource."""
        pass

    @abstractmethod
    def replicate(self, resource: Dict[str, Any], target_resource_id: str) -> bool:
        """Replicate data plane for the resource."""
        pass
'''
            (plugin_dir / "base.py").write_text(base_plugin_code)

            self.status["workstreams"][workstream_name]["status"] = (
                "infrastructure_created"
            )

        self.status["workstreams"][workstream_name]["end_time"] = (
            datetime.now().isoformat()
        )
        self._save_status()

        logger.info(f"[{workstream_name}] ✅ Infrastructure ready")

    def workstream_deploy_iteration(self):
        """Workstream 4: Deploy validated iteration."""
        workstream_name = "deploy_iteration"
        logger.info(f"[{workstream_name}] Starting deployment preparation...")

        self.status["workstreams"][workstream_name] = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": [],
        }
        self._save_status()

        # Find latest iteration
        iterations = sorted(PROJECT_ROOT.glob("demos/iteration*"))
        if not iterations:
            logger.error(f"[{workstream_name}] No iterations found")
            self.status["workstreams"][workstream_name]["status"] = "failed"
            self.status["workstreams"][workstream_name]["error"] = "No iterations found"
            self._save_status()
            return

        latest = iterations[-1]
        iteration_num = latest.name.replace("iteration", "")

        logger.info(f"[{workstream_name}] Latest iteration: {iteration_num}")

        # Check if we have target tenant credentials
        if not os.getenv("ARM_CLIENT_ID"):
            logger.warning(
                f"[{workstream_name}] No ARM_CLIENT_ID set - deployment requires credentials"
            )
            self.status["workstreams"][workstream_name]["status"] = (
                "pending_credentials"
            )
            self.status["workstreams"][workstream_name]["note"] = (
                "Set ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_TENANT_ID, ARM_SUBSCRIPTION_ID"
            )
            self._save_status()
            return

        # Run terraform plan
        logger.info(f"[{workstream_name}] Running terraform plan...")
        success, output = self._run_command(
            ["terraform", "plan", "-out=tfplan"], workstream_name, timeout=600
        )

        if not success:
            logger.error(f"[{workstream_name}] terraform plan failed: {output[-200:]}")
            self.status["workstreams"][workstream_name]["status"] = "plan_failed"
            self.status["workstreams"][workstream_name]["error"] = output[-200:]
            self._send_imessage(f"❌ [{workstream_name}] terraform plan failed")
            self._save_status()
            return

        self.status["workstreams"][workstream_name]["status"] = "plan_ready"
        self.status["workstreams"][workstream_name]["iteration"] = iteration_num
        self.status["workstreams"][workstream_name]["note"] = (
            "Run 'terraform apply tfplan' to deploy"
        )
        self._save_status()

        self._send_imessage(
            f"✅ [{workstream_name}] Iteration {iteration_num} plan ready for deployment"
        )
        logger.info(
            f"[{workstream_name}] ✅ Plan ready - manual approval required for apply"
        )

    def run_all_workstreams(self):
        """Run all workstreams in parallel."""
        logger.info("Starting all workstreams...")
        self._send_imessage(
            "🚀 Starting 4 parallel workstreams: scan, Entra ID, data plane, deployment"
        )

        # Create threads for each workstream
        workstreams = [
            ("full_scan", self.workstream_full_scan),
            ("entra_id_mapping", self.workstream_entra_id_mapping),
            ("data_plane_plugins", self.workstream_data_plane_plugins),
            ("deploy_iteration", self.workstream_deploy_iteration),
        ]

        for name, func in workstreams:
            thread = threading.Thread(target=func, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)

        # Wait for all threads to complete
        for thread in self.threads:
            thread.join()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("WORKSTREAM SUMMARY")
        logger.info("=" * 60)

        for name, ws in self.status["workstreams"].items():
            status_emoji = {
                "completed": "✅",
                "running": "🔄",
                "failed": "❌",
                "pending_credentials": "⏳",
                "pending_implementation": "⏳",
                "plan_ready": "✅",
                "infrastructure_ready": "✅",
                "infrastructure_created": "✅",
            }.get(ws["status"], "❓")

            logger.info(f"{status_emoji} {name}: {ws['status']}")

        logger.info("=" * 60)

        # Send summary
        completed = sum(
            1
            for ws in self.status["workstreams"].values()
            if ws["status"]
            in [
                "completed",
                "plan_ready",
                "infrastructure_ready",
                "infrastructure_created",
            ]
        )
        total = len(self.status["workstreams"])

        self._send_imessage(
            f"📊 Workstream Summary: {completed}/{total} completed or ready. "
            f"Check demos/workstream_status.json for details."
        )


def main():
    """Main entry point."""
    orchestrator = WorkstreamOrchestrator()

    try:
        orchestrator.run_all_workstreams()
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopped by user")
        orchestrator._send_imessage("🛑 Workstream orchestrator stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        orchestrator._send_imessage(f"💥 Workstream orchestrator error: {str(e)[:100]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
