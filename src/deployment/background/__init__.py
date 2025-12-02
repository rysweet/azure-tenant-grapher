"""
Background Deployment Manager

Orchestrates background deployment processes with modular components
for job spawning, status tracking, log streaming, and process management.

Philosophy:
- Orchestrator delegates to specialized components
- Each component is a self-contained brick
- Clear public API via __all__

Public API:
    BackgroundDeploymentManager: Main orchestrator class
"""

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import structlog

from .job_spawner import JobSpawner
from .job_tracker import JobTracker
from .log_streamer import LogStreamer
from .process_manager import ProcessManager
from .state_manager import StateManager

logger = structlog.get_logger(__name__)

__all__ = ["BackgroundDeploymentManager"]


class BackgroundDeploymentManager:
    """
    Manages background deployment processes with state tracking and monitoring.

    Orchestrates specialized components for spawning deployments, tracking status,
    streaming logs, and managing process lifecycle. All job state is persisted
    to disk for reliability across restarts.

    This is a thin orchestration layer that delegates to specialized components:
    - JobSpawner: Creates background processes
    - JobTracker: Monitors job status
    - LogStreamer: Streams log output
    - ProcessManager: Manages process lifecycle
    - StateManager: Handles state persistence
    """

    def __init__(self, jobs_dir: Optional[Path] = None) -> None:
        """
        Initialize the background deployment manager.

        Args:
            jobs_dir: Directory for job state storage (default: .deployments/jobs/)
        """
        self.jobs_dir = jobs_dir or Path.cwd() / ".deployments" / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.state_manager = StateManager(self.jobs_dir)
        self.process_manager = ProcessManager()
        self.job_tracker = JobTracker(self.state_manager, self.process_manager)
        self.job_spawner = JobSpawner(self.jobs_dir)
        self.log_streamer = LogStreamer(
            check_job_running=self.job_tracker.is_job_running
        )

        self._logger = logger.bind(component="BackgroundDeploymentManager")
        self._logger.info(
            "Initialized background deployment manager", jobs_dir=str(self.jobs_dir)
        )

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
            >>> print(job['pid'])
            12345
        """
        return self.job_spawner.spawn_deployment(
            job_id=job_id,
            iac_dir=iac_dir,
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=iac_format,
            dry_run=dry_run,
            env=env,
        )

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
            >>> print(status['status'])
            'running'
        """
        return self.job_tracker.get_status(job_id)

    def list_deployments(
        self, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
        return self.job_tracker.list_deployments(status_filter)

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
        log_file = self.state_manager.get_log_file(job_id)
        yield from self.log_streamer.stream_logs(
            job_id=job_id,
            log_file=log_file,
            follow=follow,
            tail_lines=tail_lines,
        )

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
        # Get current status
        status = self.job_tracker.get_status(job_id)

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
            success = self.process_manager.terminate_process(pid, force)

            if success:
                # Update status
                status["status"] = "cancelled"
                status["phase"] = "cancelled"
                status["updated_at"] = datetime.now(timezone.utc).isoformat()
                status["error"] = "Deployment cancelled by user"

                self.state_manager.write_status(job_id, status)

                # Remove PID file
                pid_file = self.state_manager.get_pid_file(job_id)
                if pid_file.exists():
                    pid_file.unlink()

                self._logger.info(
                    "Successfully cancelled deployment", job_id=job_id, pid=pid
                )

            return success

        except ProcessLookupError:
            # Process already terminated
            self._logger.warning("Process already terminated", job_id=job_id, pid=pid)

            # Update status anyway
            status["status"] = "failed"
            status["phase"] = "failed"
            status["updated_at"] = datetime.now(timezone.utc).isoformat()
            status["error"] = "Process terminated unexpectedly"

            self.state_manager.write_status(job_id, status)

            return False

        except Exception as e:
            self._logger.exception(
                "Failed to cancel deployment", job_id=job_id, error=str(e)
            )
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
        return self.state_manager.cleanup_old_jobs(days)

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
        return self.state_manager.get_job_config(job_id)


# Import datetime for cancel_deployment
from datetime import datetime, timezone
