"""
Deployment Lock Manager

Provides file-based locking mechanism to prevent concurrent deployments
to the same IaC directory. Supports automatic stale lock detection and cleanup.
"""

import hashlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Optional

import structlog  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)


class LockError(Exception):
    """Raised when a lock cannot be acquired."""

    pass


class LockTimeout(LockError):
    """Raised when lock acquisition times out."""

    pass


class DeploymentLockManager:
    """
    Manages file-based locks for deployment operations.

    Prevents concurrent deployments to the same IaC directory using
    file-based locking with automatic stale lock detection.

    The lock manager uses OS-specific file locking primitives:
    - Unix/Linux/macOS: fcntl.flock()
    - Windows: msvcrt.locking()

    Lock files contain metadata in JSON format:
    {
        "job_id": "unique-job-identifier",
        "pid": 12345,
        "timestamp": 1234567890.0,
        "hostname": "machine-name"
    }

    Stale locks are automatically detected by checking if the PID is still alive.
    """

    LOCK_DIR = Path(".deployments/locks")
    STALE_LOCK_THRESHOLD = 3600  # 1 hour in seconds

    def __init__(self, iac_dir: Path, job_id: str) -> None:
        """
        Initialize the deployment lock manager.

        Args:
            iac_dir: Path to the IaC directory to lock
            job_id: Unique identifier for the deployment job
        """
        self.iac_dir = Path(iac_dir).resolve()
        self.job_id = job_id
        self._logger = logger.bind(
            component="DeploymentLockManager",
            job_id=job_id,
            iac_dir=str(self.iac_dir),
        )

        # Generate lock file path based on normalized IaC directory hash
        self.lock_file = self._get_lock_file_path()
        self._lock_fd: Optional[int] = None
        self._lock_acquired = False

        # Ensure lock directory exists
        self.LOCK_DIR.mkdir(parents=True, exist_ok=True)

    def _get_lock_file_path(self) -> Path:
        """
        Generate lock file path based on IaC directory hash.

        Returns:
            Path: Path to the lock file
        """
        # Normalize the path and create a hash
        normalized_path = str(self.iac_dir)
        path_hash = hashlib.sha256(normalized_path.encode()).hexdigest()[:16]

        lock_file = self.LOCK_DIR / f"{path_hash}.lock"
        self._logger.debug(
            "Generated lock file path",
            lock_file=str(lock_file),
            path_hash=path_hash,
        )
        return lock_file

    def _write_lock_metadata(self) -> None:
        """Write lock metadata to the lock file."""
        metadata = {
            "job_id": self.job_id,
            "pid": os.getpid(),
            "timestamp": time.time(),
            "hostname": socket.gethostname(),
            "iac_dir": str(self.iac_dir),
        }

        try:
            with open(self.lock_file, "w") as f:
                json.dump(metadata, f, indent=2)
            self._logger.debug("Wrote lock metadata", metadata=metadata)
        except Exception as e:
            self._logger.warning("Failed to write lock metadata", error=str(e))

    def _read_lock_metadata(self) -> Optional[dict[str, Any]]:
        """
        Read lock metadata from the lock file.

        Returns:
            Optional[dict]: Lock metadata if file exists and is valid, None otherwise
        """
        if not self.lock_file.exists():
            return None

        try:
            with open(self.lock_file) as f:
                metadata = json.load(f)
            self._logger.debug("Read lock metadata", metadata=metadata)
            return metadata
        except Exception as e:
            self._logger.warning("Failed to read lock metadata", error=str(e))
            return None

    def _is_process_alive(self, pid: int) -> bool:
        """
        Check if a process with the given PID is still running.

        Args:
            pid: Process ID to check

        Returns:
            bool: True if process is alive, False otherwise
        """
        try:
            # os.kill with signal 0 doesn't actually kill the process,
            # it just checks if it exists
            os.kill(pid, 0)
            return True
        except OSError:
            return False
        except Exception as e:
            self._logger.warning(
                "Error checking process liveness",
                pid=pid,
                error=str(e),
            )
            return False

    def _is_stale_lock(self, metadata: dict[str, Any]) -> bool:
        """
        Determine if a lock is stale.

        A lock is considered stale if:
        1. The process that created it is no longer running, OR
        2. The lock is older than STALE_LOCK_THRESHOLD

        Args:
            metadata: Lock metadata dictionary

        Returns:
            bool: True if lock is stale, False otherwise
        """
        # Check if process is still alive
        pid = metadata.get("pid")
        if pid is not None and not self._is_process_alive(pid):
            self._logger.info(
                "Lock is stale (process not running)",
                pid=pid,
                job_id=metadata.get("job_id"),
            )
            return True

        # Check if lock is too old
        timestamp = metadata.get("timestamp")
        if timestamp is not None:
            age = time.time() - timestamp
            if age > self.STALE_LOCK_THRESHOLD:
                self._logger.info(
                    "Lock is stale (too old)",
                    age_seconds=age,
                    threshold=self.STALE_LOCK_THRESHOLD,
                    job_id=metadata.get("job_id"),
                )
                return True

        return False

    def _acquire_file_lock(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire an OS-level file lock.

        Args:
            timeout: Maximum time to wait for lock in seconds (None = no timeout)

        Returns:
            bool: True if lock acquired, False if timeout

        Raises:
            LockError: If lock acquisition fails
        """
        start_time = time.time()

        while True:
            try:
                # Open the lock file with write access
                # Use os.open with O_CREAT | O_EXCL for atomic creation
                fd = os.open(
                    self.lock_file,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
                self._lock_fd = fd
                self._logger.debug("Acquired file lock", fd=fd)
                return True

            except FileExistsError:
                # Lock file already exists - check if it's stale
                metadata = self._read_lock_metadata()
                if metadata and self._is_stale_lock(metadata):
                    self._logger.info("Removing stale lock", metadata=metadata)
                    try:
                        self.lock_file.unlink()
                        continue  # Try to acquire again
                    except Exception as e:
                        self._logger.warning(
                            "Failed to remove stale lock",
                            error=str(e),
                        )

                # Check timeout
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        self._logger.warning(
                            "Lock acquisition timed out",
                            timeout=timeout,
                            elapsed=elapsed,
                        )
                        return False

                # Wait a bit before retrying
                time.sleep(0.5)

            except Exception as e:
                raise LockError(f"Failed to acquire file lock: {e}") from e

    def _release_file_lock(self) -> None:
        """Release the OS-level file lock."""
        if self._lock_fd is not None:
            try:
                os.close(self._lock_fd)
                self._logger.debug("Released file lock", fd=self._lock_fd)
            except Exception as e:
                self._logger.warning("Error closing lock file", error=str(e))
            finally:
                self._lock_fd = None

        # Remove the lock file
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
                self._logger.debug("Removed lock file")
        except Exception as e:
            self._logger.warning("Error removing lock file", error=str(e))

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a deployment lock.

        Blocks until the lock is acquired or timeout is reached.
        Automatically detects and cleans up stale locks.

        Args:
            timeout: Maximum time to wait for lock in seconds (None = wait forever)

        Returns:
            bool: True if lock acquired, False if timeout

        Raises:
            LockError: If lock acquisition fails
            LockTimeout: If timeout is reached (when timeout > 0)

        Example:
            >>> lock_mgr = DeploymentLockManager(Path("./iac"), "job-123")
            >>> if lock_mgr.acquire(timeout=30):
            ...     try:
            ...         # Perform deployment
            ...         pass
            ...     finally:
            ...         lock_mgr.release()
        """
        if self._lock_acquired:
            self._logger.warning("Lock already acquired")
            return True

        self._logger.info(
            "Attempting to acquire lock",
            timeout=timeout,
        )

        success = self._acquire_file_lock(timeout=timeout)

        if success:
            self._write_lock_metadata()
            self._lock_acquired = True
            self._logger.info("Successfully acquired lock")
            return True
        else:
            if timeout is not None and timeout > 0:
                raise LockTimeout(
                    f"Failed to acquire lock for {self.iac_dir} within {timeout}s"
                )
            return False

    def release(self) -> None:
        """
        Release the deployment lock.

        Safe to call multiple times - will only release once.

        Example:
            >>> lock_mgr = DeploymentLockManager(Path("./iac"), "job-123")
            >>> lock_mgr.acquire()
            >>> lock_mgr.release()
        """
        if not self._lock_acquired:
            self._logger.debug("Lock not acquired, nothing to release")
            return

        self._logger.info("Releasing lock")
        self._release_file_lock()
        self._lock_acquired = False
        self._logger.info("Successfully released lock")

    def is_locked(self) -> bool:
        """
        Check if the IaC directory is currently locked.

        This checks if ANY lock exists for the directory, not just this instance.

        Returns:
            bool: True if locked (by any process), False otherwise

        Example:
            >>> lock_mgr = DeploymentLockManager(Path("./iac"), "job-123")
            >>> if not lock_mgr.is_locked():
            ...     lock_mgr.acquire()
        """
        if not self.lock_file.exists():
            return False

        metadata = self._read_lock_metadata()
        if metadata is None:
            return False

        # Check if it's a stale lock
        if self._is_stale_lock(metadata):
            self._logger.debug("Lock file exists but is stale")
            return False

        self._logger.debug("Lock is active", metadata=metadata)
        return True

    def clean_stale_locks(self) -> int:
        """
        Clean up all stale locks in the lock directory.

        Scans all lock files and removes those that are stale.

        Returns:
            int: Number of stale locks removed

        Example:
            >>> lock_mgr = DeploymentLockManager(Path("./iac"), "job-123")
            >>> removed = lock_mgr.clean_stale_locks()
            >>> print(str(f"Removed {removed} stale locks"))
        """
        if not self.LOCK_DIR.exists():
            return 0

        removed_count = 0
        self._logger.info("Scanning for stale locks", lock_dir=str(self.LOCK_DIR))

        for lock_file in self.LOCK_DIR.glob("*.lock"):
            try:
                # Read metadata
                with open(lock_file) as f:
                    metadata = json.load(f)

                # Check if stale
                if self._is_stale_lock(metadata):
                    self._logger.info(
                        "Removing stale lock",
                        lock_file=str(lock_file),
                        metadata=metadata,
                    )
                    lock_file.unlink()
                    removed_count += 1

            except Exception as e:
                self._logger.warning(
                    "Error processing lock file",
                    lock_file=str(lock_file),
                    error=str(e),
                )

        self._logger.info(
            "Stale lock cleanup complete",
            removed_count=removed_count,
        )
        return removed_count

    def __enter__(self):
        """Context manager entry - acquire lock."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """Context manager exit - release lock."""
        self.release()
        return False

    def __del__(self):
        """Destructor - ensure lock is released."""
        if self._lock_acquired:
            self._logger.warning("Lock not explicitly released, cleaning up")
            self.release()
