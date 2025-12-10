"""
Process Manager Module

Handles process lifecycle management including PID checking and termination.

Philosophy:
- Single responsibility: Process management only
- Self-contained and regeneratable
- Cross-platform support (Windows/Unix)

Public API:
    ProcessManager: Manages process lifecycle and termination
"""

import os
import signal
import subprocess
import sys

import structlog

logger = structlog.get_logger(__name__)

__all__ = ["ProcessManager"]


class ProcessManager:
    """
    Manages process lifecycle and termination.

    Provides cross-platform process checking and termination,
    with proper status updates and cleanup.
    """

    def __init__(self) -> None:
        """Initialize the process manager."""
        self._logger = logger.bind(component="ProcessManager")

    def check_pid(self, pid: int) -> bool:
        """
        Check if a process with the given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            bool: True if process is running, False otherwise

        Example:
            >>> manager = ProcessManager()
            >>> is_running = manager.check_pid(12345)
            >>> print(is_running)
            True
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

    def terminate_process(self, pid: int, force: bool = False) -> bool:
        """
        Terminate a process by PID.

        Args:
            pid: Process ID to terminate
            force: If True, use SIGKILL instead of SIGTERM (Unix only)

        Returns:
            bool: True if termination succeeded, False otherwise

        Raises:
            ProcessLookupError: If process doesn't exist

        Example:
            >>> manager = ProcessManager()
            >>> success = manager.terminate_process(12345)
            >>> print(success)
            True
        """
        self._logger.info(
            "Terminating process",
            pid=pid,
            force=force,
        )

        try:
            if sys.platform == "win32":
                # Windows: use taskkill
                cmd = ["taskkill", "/F" if force else "/T", "/PID", str(pid)]
                result = subprocess.run(cmd, capture_output=True, check=False)
                success = result.returncode == 0
            else:
                # Unix: send signal
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(pid, sig)
                success = True

            if success:
                self._logger.info("Successfully terminated process", pid=pid)

            return success

        except ProcessLookupError:
            # Process already terminated
            self._logger.warning("Process already terminated", pid=pid)
            raise

        except Exception as e:
            self._logger.exception("Failed to terminate process", pid=pid, error=str(e))
            return False
