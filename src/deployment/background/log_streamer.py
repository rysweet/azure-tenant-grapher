"""
Log Streamer Module

Handles streaming log output from deployment jobs.

Philosophy:
- Single responsibility: Log streaming only
- Self-contained and regeneratable
- Generator-based for memory efficiency

Public API:
    LogStreamer: Streams log output from job files
"""

import time
from pathlib import Path
from typing import Callable, Generator, Optional

import structlog

logger = structlog.get_logger(__name__)

__all__ = ["LogStreamer"]


class LogStreamer:
    """
    Streams log output from deployment jobs.

    Provides both static and follow-mode log streaming with
    optional tail functionality for viewing recent lines only.
    """

    def __init__(self, check_job_running: Callable[[str], bool]) -> None:
        """
        Initialize the log streamer.

        Args:
            check_job_running: Callback to check if a job is still running
        """
        self._check_job_running = check_job_running
        self._logger = logger.bind(component="LogStreamer")

    def stream_logs(
        self,
        job_id: str,
        log_file: Path,
        follow: bool = False,
        tail_lines: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Stream log output from a deployment job.

        Args:
            job_id: Job identifier (for status checking)
            log_file: Path to the log file
            follow: If True, continuously stream new log lines (like tail -f)
            tail_lines: If specified, only return last N lines initially

        Yields:
            str: Log lines from the deployment output

        Example:
            >>> streamer = LogStreamer(check_running_fn)
            >>> for line in streamer.stream_logs("deploy-123", log_path, follow=True):
            ...     print(line)
            Initializing Terraform...
            Terraform has been successfully initialized!
            ...
        """
        self._logger.debug(
            "Streaming logs", job_id=job_id, follow=follow, tail_lines=tail_lines
        )

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
                yield from self._follow_logs(f, job_id)

    def _follow_logs(self, file_handle, job_id: str) -> Generator[str, None, None]:
        """
        Follow log file for new content (like tail -f).

        Args:
            file_handle: Open file handle positioned at end of existing content
            job_id: Job identifier for status checking

        Yields:
            str: New log lines as they appear
        """
        while True:
            line = file_handle.readline()
            if line:
                yield line.rstrip("\n")
            else:
                # Check if process is still running
                if not self._check_job_running(job_id):
                    # Process finished, stop following
                    break

                # Sleep before checking again
                time.sleep(0.5)
