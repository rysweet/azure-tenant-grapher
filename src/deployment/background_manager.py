"""
Background Deployment Manager

Manages background deployment processes with job state tracking, log streaming,
and process lifecycle management. Provides non-blocking deployment execution
with status monitoring and cancellation support.
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class BackgroundDeploymentManager:
    """
    Manages background deployment processes with state tracking and monitoring.

    Provides methods for spawning deployments in background processes,
    monitoring their status, streaming logs, and cancelling running deployments.
    All job state is persisted to disk for reliability across restarts.
    """

    def __init__(self, jobs_dir: Optional[Path] = None) -> None:
        """
        Initialize the background deployment manager.

        Args:
            jobs_dir: Directory for job state storage (default: .deployments/jobs/)
        """
        self.jobs_dir = jobs_dir or Path.cwd() / ".deployments" / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger.bind(component="BackgroundDeploymentManager")
        self._logger.info("Initialized background deployment manager", jobs_dir=str(self.jobs_dir))

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
            >>> manager = BackgroundDeploymentManager()
            >>> job = manager.spawn_deployment(
            ...     job_id="deploy-123",
            ...     iac_dir=Path("./terraform"),
            ...     target_tenant_id="tenant-id",
            ...     resource_group="my-rg"
            ... )
            >>> print(job['pid'])  # Process ID
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

        # Prepare environment
        process_env: Dict[str, str] = dict(os.environ)
        if env:
            process_env.update(env)

        # Setup log file
        log_file = job_dir / "output.log"
        config_file = job_dir / "config.json"
        status_file = job_dir / "status.json"
        pid_file = job_dir / "pid.lock"

        # Save job configuration
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

        # Initialize status
        initial_status: Dict[str, Any] = {
            "job_id": job_id,
            "status": "starting",
            "phase": "init",
            "created_at": config["created_at"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pid": None,
            "exit_code": None,
            "error": None,
        }

        with open(status_file, "w") as f:
            json.dump(initial_status, f, indent=2)

        try:
            # Spawn background process with output redirection
            with open(log_file, "w") as log_handle:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=process_env,
                    cwd=Path.cwd(),
                    start_new_session=True,  # Detach from parent
                )

            pid = process.pid

            # Save PID
            with open(pid_file, "w") as f:
                f.write(str(pid))

            # Update status with PID
            initial_status["pid"] = pid
            initial_status["status"] = "running"
            initial_status["updated_at"] = datetime.now(timezone.utc).isoformat()

            with open(status_file, "w") as f:
                json.dump(initial_status, f, indent=2)

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
            self._logger.exception("Failed to spawn deployment process", job_id=job_id, error=str(e))

            # Update status to failed
            error_status = {
                **initial_status,
                "status": "failed",
                "error": f"Failed to spawn process: {e!s}",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            with open(status_file, "w") as f:
                json.dump(error_status, f, indent=2)

            raise RuntimeError(f"Failed to spawn deployment process: {e}") from e

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the current status of a deployment job.

        Reads status from disk and checks if the process is still running
        by verifying the PID. Updates status to 'completed' or 'failed'
        if the process has terminated.

        Args:
            job_id: Job identifier

        Returns:
            dict: Job status including status, phase, pid, exit_code, etc.

        Raises:
            ValueError: If job_id does not exist

        Example:
            >>> status = manager.get_status("deploy-123")
            >>> print(status['status'])  # "running", "completed", "failed"
            'running'
        """
        job_dir = self.jobs_dir / job_id
        status_file = job_dir / "status.json"

        if not status_file.exists():
            raise ValueError(f"Job {job_id} not found")

        with open(status_file) as f:
            status = json.load(f)

        # Check if process is still running
        pid = status.get("pid")
        if pid and status["status"] == "running":
            is_running = self._check_pid(pid)

            if not is_running:
                # Process has terminated, update status
                self._logger.info(
                    "Process terminated, updating status",
                    job_id=job_id,
                    pid=pid,
                )

                # Try to determine exit code by checking log for errors
                log_file = job_dir / "output.log"
                has_error = False
                if log_file.exists():
                    try:
                        with open(log_file) as f:
                            log_content = f.read()
                            has_error = "error" in log_content.lower() or "failed" in log_content.lower()
                    except Exception:
                        pass

                status["status"] = "failed" if has_error else "completed"
                status["phase"] = "failed" if has_error else "complete"
                status["updated_at"] = datetime.now(timezone.utc).isoformat()
                status["exit_code"] = 1 if has_error else 0

                if has_error:
                    status["error"] = "Deployment failed (check logs for details)"

                # Save updated status
                with open(status_file, "w") as f:
                    json.dump(status, f, indent=2)

        return status

    def list_deployments(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all deployment jobs with optional status filtering.

        Args:
            status_filter: Optional status to filter by (running/completed/failed)

        Returns:
            list[dict]: List of job status dictionaries, sorted by created_at DESC

        Example:
            >>> jobs = manager.list_deployments(status_filter="running")
            >>> for job in jobs:
            ...     print(f"{job['job_id']}: {job['status']}")
            deploy-123: running
            deploy-124: running
        """
        jobs = []

        if not self.jobs_dir.exists():
            return jobs

        for job_dir in self.jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            status_file = job_dir / "status.json"
            if not status_file.exists():
                continue

            try:
                with open(status_file) as f:
                    status = json.load(f)

                # Update status if needed (check PID)
                job_id = job_dir.name
                status = self.get_status(job_id)

                # Apply filter
                if status_filter and status.get("status") != status_filter:
                    continue

                jobs.append(status)

            except Exception as e:
                self._logger.warning(
                    "Failed to read job status",
                    job_id=job_dir.name,
                    error=str(e),
                )

        # Sort by created_at descending
        def sort_key(job: Dict[str, Any]) -> str:
            return str(job.get("created_at", ""))

        jobs.sort(key=sort_key, reverse=True)

        return jobs

    def stream_logs(
        self,
        job_id: str,
        follow: bool = False,
        tail_lines: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Stream log output from a deployment job.

        Args:
            job_id: Job identifier
            follow: If True, continuously stream new log lines (like tail -f)
            tail_lines: If specified, only return last N lines initially

        Yields:
            str: Log lines from the deployment output

        Raises:
            ValueError: If job_id does not exist

        Example:
            >>> for line in manager.stream_logs("deploy-123", follow=True):
            ...     print(line)
            Initializing Terraform...
            Terraform has been successfully initialized!
            ...
        """
        job_dir = self.jobs_dir / job_id
        log_file = job_dir / "output.log"

        if not log_file.exists():
            raise ValueError(f"Log file for job {job_id} not found")

        self._logger.debug("Streaming logs", job_id=job_id, follow=follow, tail_lines=tail_lines)

        # Read existing content
        with open(log_file) as f:
            if tail_lines:
                # Read all lines and return last N
                lines = f.readlines()
                for line in lines[-tail_lines:]:
                    yield line.rstrip("\n")
            else:
                # Read all existing content
                for line in f:
                    yield line.rstrip("\n")

            # If follow mode, keep reading new content
            if follow:
                while True:
                    line = f.readline()
                    if line:
                        yield line.rstrip("\n")
                    else:
                        # Check if process is still running
                        status = self.get_status(job_id)
                        if status["status"] != "running":
                            # Process finished, stop following
                            break

                        # Sleep before checking again
                        time.sleep(0.5)

    def cancel_deployment(self, job_id: str, force: bool = False) -> bool:
        """
        Cancel a running deployment by terminating its process.

        Args:
            job_id: Job identifier
            force: If True, use SIGKILL instead of SIGTERM (Unix only)

        Returns:
            bool: True if cancellation succeeded, False otherwise

        Raises:
            ValueError: If job_id does not exist

        Example:
            >>> success = manager.cancel_deployment("deploy-123")
            >>> print(success)
            True
        """
        job_dir = self.jobs_dir / job_id
        status_file = job_dir / "status.json"
        pid_file = job_dir / "pid.lock"

        if not status_file.exists():
            raise ValueError(f"Job {job_id} not found")

        # Get current status
        status = self.get_status(job_id)

        if status["status"] != "running":
            self._logger.warning(
                "Cannot cancel non-running job",
                job_id=job_id,
                status=status["status"],
            )
            return False

        pid = status.get("pid")
        if not pid:
            self._logger.warning("No PID found for job", job_id=job_id)
            return False

        self._logger.info(
            "Cancelling deployment",
            job_id=job_id,
            pid=pid,
            force=force,
        )

        try:
            # Terminate process
            if sys.platform == "win32":
                # Windows: use taskkill
                import subprocess
                cmd = ["taskkill", "/F" if force else "/T", "/PID", str(pid)]
                result = subprocess.run(cmd, capture_output=True, check=False)
                success = result.returncode == 0
            else:
                # Unix: send signal
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(pid, sig)
                success = True

            if success:
                # Update status
                status["status"] = "cancelled"
                status["phase"] = "cancelled"
                status["updated_at"] = datetime.now(timezone.utc).isoformat()
                status["error"] = "Deployment cancelled by user"

                with open(status_file, "w") as f:
                    json.dump(status, f, indent=2)

                # Remove PID file
                if pid_file.exists():
                    pid_file.unlink()

                self._logger.info("Successfully cancelled deployment", job_id=job_id, pid=pid)

            return success

        except ProcessLookupError:
            # Process already terminated
            self._logger.warning("Process already terminated", job_id=job_id, pid=pid)

            # Update status anyway
            status["status"] = "failed"
            status["phase"] = "failed"
            status["updated_at"] = datetime.now(timezone.utc).isoformat()
            status["error"] = "Process terminated unexpectedly"

            with open(status_file, "w") as f:
                json.dump(status, f, indent=2)

            return False

        except Exception as e:
            self._logger.exception("Failed to cancel deployment", job_id=job_id, error=str(e))
            return False

    def _check_pid(self, pid: int) -> bool:
        """
        Check if a process with the given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            bool: True if process is running, False otherwise
        """
        try:
            if sys.platform == "win32":
                # Windows: use tasklist
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return str(pid) in result.stdout
            else:
                # Unix: send signal 0 (doesn't actually send signal, just checks)
                os.kill(pid, 0)
                return True
        except (ProcessLookupError, PermissionError):
            return False
        except Exception as e:
            self._logger.warning("Error checking PID", pid=pid, error=str(e))
            return False

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        Clean up job directories older than specified days.

        Args:
            days: Remove jobs older than this many days

        Returns:
            int: Number of jobs cleaned up

        Example:
            >>> count = manager.cleanup_old_jobs(days=7)
            >>> print(f"Cleaned up {count} old jobs")
            Cleaned up 3 old jobs
        """
        if not self.jobs_dir.exists():
            return 0

        cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 86400)
        cleaned = 0

        for job_dir in self.jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            status_file = job_dir / "status.json"
            if not status_file.exists():
                continue

            try:
                with open(status_file) as f:
                    status = json.load(f)

                # Parse created_at timestamp
                created_at = datetime.fromisoformat(status.get("created_at", ""))
                if created_at.timestamp() < cutoff_time:
                    # Only cleanup completed/failed jobs
                    if status.get("status") in ("completed", "failed", "cancelled"):
                        import shutil
                        shutil.rmtree(job_dir)
                        cleaned += 1
                        self._logger.info("Cleaned up old job", job_id=job_dir.name)

            except Exception as e:
                self._logger.warning(
                    "Failed to cleanup job",
                    job_id=job_dir.name,
                    error=str(e),
                )

        return cleaned

    def get_job_config(self, job_id: str) -> Dict[str, Any]:
        """
        Get the configuration for a deployment job.

        Args:
            job_id: Job identifier

        Returns:
            dict: Job configuration including command, paths, etc.

        Raises:
            ValueError: If job_id does not exist

        Example:
            >>> config = manager.get_job_config("deploy-123")
            >>> print(config['iac_dir'])
            /path/to/terraform
        """
        job_dir = self.jobs_dir / job_id
        config_file = job_dir / "config.json"

        if not config_file.exists():
            raise ValueError(f"Config for job {job_id} not found")

        with open(config_file) as f:
            return json.load(f)
