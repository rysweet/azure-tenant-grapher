"""
State Manager Module

Handles persistence and retrieval of job state and configuration.

Philosophy:
- Single responsibility: State persistence only
- Self-contained and regeneratable
- Uses standard library file I/O

Public API:
    StateManager: Manages job state and configuration persistence
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import structlog  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)

__all__ = ["StateManager"]


class StateManager:
    """
    Manages job state and configuration persistence.

    Handles reading/writing job state files, configuration files,
    and cleanup of old job directories.
    """

    def __init__(self, jobs_dir: Path) -> None:
        """
        Initialize the state manager.

        Args:
            jobs_dir: Directory for job state storage
        """
        self.jobs_dir = jobs_dir
        self._logger = logger.bind(component="StateManager")

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
            >>> manager = StateManager(Path(".deployments/jobs"))
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

    def read_status(self, job_id: str) -> Dict[str, Any]:
        """
        Read the status file for a job.

        Args:
            job_id: Job identifier

        Returns:
            dict: Job status data

        Raises:
            ValueError: If job_id does not exist
        """
        job_dir = self.jobs_dir / job_id
        status_file = job_dir / "status.json"

        if not status_file.exists():
            raise ValueError(f"Job {job_id} not found")

        with open(status_file) as f:
            return json.load(f)

    def write_status(self, job_id: str, status: Dict[str, Any]) -> None:
        """
        Write the status file for a job.

        Args:
            job_id: Job identifier
            status: Status data to write

        Raises:
            ValueError: If job_id does not exist
        """
        job_dir = self.jobs_dir / job_id
        status_file = job_dir / "status.json"

        if not job_dir.exists():
            raise ValueError(f"Job {job_id} not found")

        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)

    def get_log_file(self, job_id: str) -> Path:
        """
        Get the log file path for a job.

        Args:
            job_id: Job identifier

        Returns:
            Path: Log file path

        Raises:
            ValueError: If log file does not exist
        """
        job_dir = self.jobs_dir / job_id
        log_file = job_dir / "output.log"

        if not log_file.exists():
            raise ValueError(f"Log file for job {job_id} not found")

        return log_file

    def get_pid_file(self, job_id: str) -> Path:
        """
        Get the PID file path for a job.

        Args:
            job_id: Job identifier

        Returns:
            Path: PID file path
        """
        job_dir = self.jobs_dir / job_id
        return job_dir / "pid.lock"

    def list_job_dirs(self) -> list[Path]:
        """
        List all job directories.

        Returns:
            list[Path]: List of job directory paths
        """
        if not self.jobs_dir.exists():
            return []

        return [job_dir for job_dir in self.jobs_dir.iterdir() if job_dir.is_dir()]

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        Clean up job directories older than specified days.

        Args:
            days: Remove jobs older than this many days

        Returns:
            int: Number of jobs cleaned up

        Example:
            >>> manager = StateManager(Path(".deployments/jobs"))
            >>> count = manager.cleanup_old_jobs(days=7)
            >>> print(str(f"Cleaned up {count} old jobs"))
            Cleaned up 3 old jobs
        """
        if not self.jobs_dir.exists():
            return 0

        cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 86400)
        cleaned = 0

        for job_dir in self.list_job_dirs():
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
