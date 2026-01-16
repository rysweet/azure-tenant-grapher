"""
Job Spawner Module

Handles spawning deployment processes in the background with proper
environment setup and initial state management.

Philosophy:
- Single responsibility: Process spawning only
- Self-contained and regeneratable
- Uses standard library primitives

Public API:
    JobSpawner: Spawns background deployment processes
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import structlog  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)

__all__ = ["JobSpawner"]


class JobSpawner:
    """
    Spawns deployment processes in the background.

    Handles process creation, environment setup, output redirection,
    and initial job state creation. All spawned processes are detached
    from the parent for true background execution.
    """

    def __init__(self, jobs_dir: Path) -> None:
        """
        Initialize the job spawner.

        Args:
            jobs_dir: Directory for job state storage
        """
        self.jobs_dir = jobs_dir
        self._logger = logger.bind(component="JobSpawner")

    def spawn_deployment(
        self,
        job_id: str,
        iac_dir: Path,
        target_tenant_id: str,
        resource_group: str,
        location: str = "eastus",
        subscription_id: Optional[str] = None,
        iac_format: Optional[str] = None,
        dry_run: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Spawn a deployment in a background process.

        Creates a detached subprocess running the ATG CLI deployment command,
        with all output redirected to a log file. Job state is tracked on disk.

        Args:
            job_id: Unique job identifier for this deployment
            iac_dir: Directory containing IaC files
            target_tenant_id: Target Azure tenant ID
            resource_group: Target resource group name
            location: Azure region (default: eastus)
            subscription_id: Optional subscription ID for bicep/arm deployments
            iac_format: IaC format (terraform/bicep/arm), auto-detected if None
            dry_run: If True, plan/validate only without deploying
            env: Optional environment variables for the deployment process

        Returns:
            dict: Job metadata including job_id, pid, status, and paths

        Raises:
            ValueError: If job_id already exists
            RuntimeError: If process spawning fails

        Example:
            >>> spawner = JobSpawner(Path(".deployments/jobs"))
            >>> job = spawner.spawn_deployment(
            ...     job_id="deploy-123",
            ...     iac_dir=Path("./terraform"),
            ...     target_tenant_id="tenant-id",
            ...     resource_group="my-rg"
            ... )
            >>> print(job['pid'])
            12345
        """
        job_dir = self.jobs_dir / job_id

        # Ensure job doesn't already exist
        if job_dir.exists():
            raise ValueError(f"Job {job_id} already exists at {job_dir}")

        job_dir.mkdir(parents=True, exist_ok=True)

        self._logger.info(
            "Spawning deployment job",
            job_id=job_id,
            iac_dir=str(iac_dir),
            tenant_id=target_tenant_id,
            resource_group=resource_group,
        )

        # Build deployment command
        cmd = self._build_command(
            iac_dir=iac_dir,
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=iac_format,
            dry_run=dry_run,
        )

        # Prepare environment
        process_env = self._prepare_environment(env)

        # Setup files
        log_file = job_dir / "output.log"
        config_file = job_dir / "config.json"
        status_file = job_dir / "status.json"
        pid_file = job_dir / "pid.lock"

        # Save job configuration
        self._save_config(
            config_file=config_file,
            job_id=job_id,
            iac_dir=iac_dir,
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=iac_format,
            dry_run=dry_run,
            cmd=cmd,
        )

        # Initialize status
        initial_status = self._create_initial_status(job_id)
        self._save_status(status_file, initial_status)

        try:
            # Spawn background process with output redirection
            pid = self._spawn_process(
                cmd=cmd,
                log_file=log_file,
                process_env=process_env,
            )

            # Save PID
            self._save_pid(pid_file, pid)

            # Update status with PID
            initial_status["pid"] = pid
            initial_status["status"] = "running"
            initial_status["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_status(status_file, initial_status)

            self._logger.info(
                "Spawned deployment process",
                job_id=job_id,
                pid=pid,
                log_file=str(log_file),
            )

            return {
                "job_id": job_id,
                "pid": pid,
                "status": "running",
                "log_file": str(log_file),
                "status_file": str(status_file),
                "job_dir": str(job_dir),
            }

        except Exception as e:
            # Cleanup on failure
            self._logger.exception(
                "Failed to spawn deployment process", job_id=job_id, error=str(e)
            )

            # Update status to failed
            self._handle_spawn_failure(status_file, initial_status, e)

            raise RuntimeError(f"Failed to spawn deployment process: {e}") from e

    def _build_command(
        self,
        iac_dir: Path,
        target_tenant_id: str,
        resource_group: str,
        location: str,
        subscription_id: Optional[str],
        iac_format: Optional[str],
        dry_run: bool,
    ) -> list[str]:
        """Build the deployment command."""
        cmd = [
            sys.executable,
            "-m",
            "src.cli",
            "deploy",
            "--iac-dir",
            str(iac_dir.absolute()),
            "--target-tenant-id",
            target_tenant_id,
            "--resource-group",
            resource_group,
            "--location",
            location,
        ]

        if subscription_id:
            cmd.extend(["--subscription-id", subscription_id])

        if iac_format:
            cmd.extend(["--format", iac_format])

        if dry_run:
            cmd.append("--dry-run")

        return cmd

    def _prepare_environment(self, env: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Prepare process environment variables."""
        process_env: Dict[str, str] = dict(os.environ)
        if env:
            process_env.update(env)
        return process_env

    def _save_config(
        self,
        config_file: Path,
        job_id: str,
        iac_dir: Path,
        target_tenant_id: str,
        resource_group: str,
        location: str,
        subscription_id: Optional[str],
        iac_format: Optional[str],
        dry_run: bool,
        cmd: list[str],
    ) -> None:
        """Save job configuration to disk."""
        config = {
            "job_id": job_id,
            "iac_dir": str(iac_dir.absolute()),
            "target_tenant_id": target_tenant_id,
            "resource_group": resource_group,
            "location": location,
            "subscription_id": subscription_id,
            "iac_format": iac_format,
            "dry_run": dry_run,
            "command": cmd,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

    def _create_initial_status(self, job_id: str) -> Dict[str, Any]:
        """Create initial job status."""
        return {
            "job_id": job_id,
            "status": "starting",
            "phase": "init",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pid": None,
            "exit_code": None,
            "error": None,
        }

    def _save_status(self, status_file: Path, status: Dict[str, Any]) -> None:
        """Save job status to disk."""
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)

    def _spawn_process(
        self,
        cmd: list[str],
        log_file: Path,
        process_env: Dict[str, str],
    ) -> int:
        """Spawn the background process and return its PID."""
        with open(log_file, "w") as log_handle:
            process = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=process_env,
                cwd=Path.cwd(),
                start_new_session=True,  # Detach from parent
            )
        return process.pid

    def _save_pid(self, pid_file: Path, pid: int) -> None:
        """Save process ID to disk."""
        with open(pid_file, "w") as f:
            f.write(str(pid))

    def _handle_spawn_failure(
        self,
        status_file: Path,
        initial_status: Dict[str, Any],
        error: Exception,
    ) -> None:
        """Handle process spawn failure by updating status."""
        error_status = {
            **initial_status,
            "status": "failed",
            "error": f"Failed to spawn process: {error!s}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(status_file, "w") as f:
            json.dump(error_status, f, indent=2)
