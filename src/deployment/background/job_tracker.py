"""
Job Tracker Module

Handles job status tracking, listing, and state updates.

Philosophy:
- Single responsibility: Job status tracking only
- Self-contained and regeneratable
- Uses composition (StateManager, ProcessManager)

Public API:
    JobTracker: Tracks and reports job status
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from .process_manager import ProcessManager
from .state_manager import StateManager

logger = structlog.get_logger(__name__)

__all__ = ["JobTracker"]


class JobTracker:
    """
    Tracks and reports job status.

    Monitors job state, checks process health, and provides
    job listing with filtering capabilities.
    """

    def __init__(
        self,
        state_manager: StateManager,
        process_manager: ProcessManager,
    ) -> None:
        """
        Initialize the job tracker.

        Args:
            state_manager: State persistence manager
            process_manager: Process lifecycle manager
        """
        self.state_manager = state_manager
        self.process_manager = process_manager
        self._logger = logger.bind(component="JobTracker")

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
            >>> tracker = JobTracker(state_mgr, process_mgr)
            >>> status = tracker.get_status("deploy-123")
            >>> print(status['status'])
            'running'
        """
        status = self.state_manager.read_status(job_id)

        # Check if process is still running
        pid = status.get("pid")
        if pid and status["status"] == "running":
            is_running = self.process_manager.check_pid(pid)

            if not is_running:
                # Process has terminated, update status
                self._logger.info(
                    "Process terminated, updating status",
                    job_id=job_id,
                    pid=pid,
                )

                # Try to determine exit code by checking log for errors
                has_error = self._check_log_for_errors(job_id)

                status["status"] = "failed" if has_error else "completed"
                status["phase"] = "failed" if has_error else "complete"
                status["updated_at"] = datetime.now(timezone.utc).isoformat()
                status["exit_code"] = 1 if has_error else 0

                if has_error:
                    status["error"] = "Deployment failed (check logs for details)"

                # Save updated status
                self.state_manager.write_status(job_id, status)

        return status

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
            >>> tracker = JobTracker(state_mgr, process_mgr)
            >>> jobs = tracker.list_deployments(status_filter="running")
            >>> for job in jobs:
            ...     print(f"{job['job_id']}: {job['status']}")
            deploy-123: running
            deploy-124: running
        """
        jobs = []

        for job_dir in self.state_manager.list_job_dirs():
            status_file = job_dir / "status.json"
            if not status_file.exists():
                continue

            try:
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

    def is_job_running(self, job_id: str) -> bool:
        """
        Check if a job is currently running.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if job is running, False otherwise

        Example:
            >>> tracker = JobTracker(state_mgr, process_mgr)
            >>> is_running = tracker.is_job_running("deploy-123")
            >>> print(is_running)
            True
        """
        try:
            status = self.get_status(job_id)
            return status["status"] == "running"
        except ValueError:
            return False

    def _check_log_for_errors(self, job_id: str) -> bool:
        """
        Check if job log contains error indicators.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if errors detected, False otherwise
        """
        try:
            log_file = self.state_manager.get_log_file(job_id)
            with open(log_file) as f:
                log_content = f.read()
                return (
                    "error" in log_content.lower()
                    or "failed" in log_content.lower()
                )
        except Exception:
            return False
