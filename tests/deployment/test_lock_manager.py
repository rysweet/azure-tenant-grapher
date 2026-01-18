"""
Tests for deployment lock manager.

Tests lock acquisition/release, stale lock detection, concurrent access prevention,
and error handling for file-based deployment locking.

Philosophy:
- Test critical path for lock operations
- Comprehensive boundary condition coverage
- Error handling for concurrent access
- Platform-specific behavior (Unix/Windows)
"""

import json
import os
import time
from pathlib import Path

import pytest

from src.deployment.lock_manager import (
    DeploymentLockManager,
    LockError,
    LockTimeout,
)


@pytest.fixture
def temp_lock_dir(tmp_path: Path) -> Path:
    """Create temporary lock directory for tests."""
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir


@pytest.fixture
def lock_manager(
    tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> DeploymentLockManager:
    """Create lock manager with temporary directory."""
    # Patch LOCK_DIR to use temp directory
    monkeypatch.setattr(
        "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
        temp_lock_dir,
    )
    iac_dir = tmp_path / "iac"
    iac_dir.mkdir(parents=True, exist_ok=True)
    return DeploymentLockManager(iac_dir, job_id="test-job-123")


class TestDeploymentLockManagerInit:
    """Test lock manager initialization."""

    def test_init_creates_lock_directory(
        self, tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock directory is created during initialization."""
        # Remove lock dir if it exists
        if temp_lock_dir.exists():
            import shutil

            shutil.rmtree(temp_lock_dir)

        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir(parents=True, exist_ok=True)

        # Initialize lock manager (creates directory)
        DeploymentLockManager(iac_dir, job_id="test-job")

        assert temp_lock_dir.exists()
        assert temp_lock_dir.is_dir()

    def test_init_sets_job_id(self, lock_manager: DeploymentLockManager) -> None:
        """Job ID is stored correctly."""
        assert lock_manager.job_id == "test-job-123"

    def test_init_resolves_iac_dir_path(
        self, tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IaC directory path is resolved to absolute path."""
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        iac_dir = tmp_path / "iac" / ".." / "iac"  # Relative path with ..
        iac_dir.mkdir(parents=True, exist_ok=True)

        lock_mgr = DeploymentLockManager(iac_dir, job_id="test-job")

        assert lock_mgr.iac_dir.is_absolute()
        assert ".." not in str(lock_mgr.iac_dir)


class TestLockAcquisition:
    """Test lock acquisition logic."""

    def test_acquire_lock_succeeds_when_no_lock_exists(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Lock acquisition succeeds when no existing lock."""
        success = lock_manager.acquire()

        assert success is True
        assert lock_manager._lock_acquired is True
        assert lock_manager.lock_file.exists()

    def test_acquire_lock_writes_metadata(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Lock metadata is written to lock file."""
        lock_manager.acquire()

        metadata = lock_manager._read_lock_metadata()
        assert metadata is not None
        assert metadata["job_id"] == "test-job-123"
        assert metadata["pid"] == os.getpid()
        assert "timestamp" in metadata
        assert "hostname" in metadata
        assert "iac_dir" in metadata

    def test_acquire_lock_fails_when_lock_exists(
        self,
        lock_manager: DeploymentLockManager,
        tmp_path: Path,
        temp_lock_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Lock acquisition fails when lock already exists."""
        # First manager acquires lock
        lock_manager.acquire()

        # Second manager tries to acquire same lock (short timeout)
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        lock_manager2 = DeploymentLockManager(
            lock_manager.iac_dir, job_id="test-job-456"
        )

        success = lock_manager2.acquire(timeout=0.5)

        assert success is False
        assert lock_manager2._lock_acquired is False

    def test_acquire_lock_with_timeout_raises_exception(
        self,
        lock_manager: DeploymentLockManager,
        tmp_path: Path,
        temp_lock_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Lock acquisition raises LockTimeout when timeout > 0."""
        # First manager acquires lock
        lock_manager.acquire()

        # Second manager tries with timeout
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        lock_manager2 = DeploymentLockManager(
            lock_manager.iac_dir, job_id="test-job-456"
        )

        with pytest.raises(LockTimeout, match="Failed to acquire lock"):
            lock_manager2.acquire(timeout=1.0)

    def test_acquire_lock_detects_stale_lock_dead_process(
        self, lock_manager: DeploymentLockManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stale lock (dead process) is detected and removed."""
        # Create stale lock with dead PID
        stale_metadata = {
            "job_id": "old-job",
            "pid": 99999999,  # Non-existent PID
            "timestamp": time.time(),
            "hostname": "localhost",
            "iac_dir": str(lock_manager.iac_dir),
        }

        lock_manager.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_manager.lock_file, "w") as f:
            json.dump(stale_metadata, f)

        # Should acquire successfully by removing stale lock
        success = lock_manager.acquire()

        assert success is True
        assert lock_manager._lock_acquired is True

        # Verify new metadata
        metadata = lock_manager._read_lock_metadata()
        assert metadata is not None
        assert metadata["job_id"] == "test-job-123"
        assert metadata["pid"] == os.getpid()

    def test_acquire_lock_detects_stale_lock_old_timestamp(
        self, lock_manager: DeploymentLockManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stale lock (old timestamp) is detected and removed."""
        # Create stale lock with old timestamp (> 1 hour)
        old_timestamp = time.time() - (DeploymentLockManager.STALE_LOCK_THRESHOLD + 100)
        stale_metadata = {
            "job_id": "old-job",
            "pid": os.getpid(),  # Same PID but old timestamp
            "timestamp": old_timestamp,
            "hostname": "localhost",
            "iac_dir": str(lock_manager.iac_dir),
        }

        lock_manager.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_manager.lock_file, "w") as f:
            json.dump(stale_metadata, f)

        # Should acquire successfully by removing stale lock
        success = lock_manager.acquire()

        assert success is True
        assert lock_manager._lock_acquired is True

    def test_acquire_lock_already_acquired_returns_true(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Acquiring already-acquired lock returns True."""
        lock_manager.acquire()

        # Try to acquire again
        success = lock_manager.acquire()

        assert success is True


class TestLockRelease:
    """Test lock release logic."""

    def test_release_lock_removes_lock_file(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Lock file is removed on release."""
        lock_manager.acquire()
        assert lock_manager.lock_file.exists()

        lock_manager.release()

        assert not lock_manager.lock_file.exists()
        assert lock_manager._lock_acquired is False

    def test_release_lock_closes_file_descriptor(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """File descriptor is closed on release."""
        lock_manager.acquire()
        fd = lock_manager._lock_fd
        assert fd is not None

        lock_manager.release()

        assert lock_manager._lock_fd is None

        # Verify FD is closed (os.close on closed FD raises OSError)
        with pytest.raises(OSError):
            os.close(fd)  # type: ignore[arg-type]

    def test_release_lock_not_acquired_is_safe(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Releasing non-acquired lock is safe (no-op)."""
        # Don't acquire, just release
        lock_manager.release()

        # Should not raise any errors
        assert lock_manager._lock_acquired is False

    def test_release_lock_multiple_times_is_safe(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Multiple releases are safe (idempotent)."""
        lock_manager.acquire()

        lock_manager.release()
        lock_manager.release()  # Second release

        assert lock_manager._lock_acquired is False


class TestLockStatus:
    """Test lock status checking."""

    def test_is_locked_returns_false_when_no_lock(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """is_locked returns False when no lock file exists."""
        assert lock_manager.is_locked() is False

    def test_is_locked_returns_true_when_lock_exists(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """is_locked returns True when valid lock exists."""
        lock_manager.acquire()

        assert lock_manager.is_locked() is True

    def test_is_locked_returns_false_for_stale_lock(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """is_locked returns False for stale lock."""
        # Create stale lock
        stale_metadata = {
            "job_id": "old-job",
            "pid": 99999999,  # Dead PID
            "timestamp": time.time(),
            "hostname": "localhost",
            "iac_dir": str(lock_manager.iac_dir),
        }

        lock_manager.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_manager.lock_file, "w") as f:
            json.dump(stale_metadata, f)

        assert lock_manager.is_locked() is False


class TestStaleLockCleaning:
    """Test stale lock cleanup functionality."""

    def test_clean_stale_locks_removes_stale_locks(
        self, lock_manager: DeploymentLockManager, temp_lock_dir: Path
    ) -> None:
        """Stale locks are removed during cleanup."""
        # Create multiple stale lock files
        for i in range(3):
            stale_lock = temp_lock_dir / f"stale-lock-{i}.lock"
            stale_metadata = {
                "job_id": f"old-job-{i}",
                "pid": 99999999 + i,  # Dead PIDs
                "timestamp": time.time(),
                "hostname": "localhost",
                "iac_dir": str(lock_manager.iac_dir),
            }
            with open(stale_lock, "w") as f:
                json.dump(stale_metadata, f)

        # Create one valid lock
        lock_manager.acquire()

        # Clean stale locks
        removed_count = lock_manager.clean_stale_locks()

        assert removed_count == 3
        # Valid lock should still exist
        assert lock_manager.lock_file.exists()

    def test_clean_stale_locks_preserves_valid_locks(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Valid locks are not removed during cleanup."""
        lock_manager.acquire()

        removed_count = lock_manager.clean_stale_locks()

        assert removed_count == 0
        assert lock_manager.lock_file.exists()

    def test_clean_stale_locks_returns_zero_when_no_locks(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Cleanup returns 0 when no locks exist."""
        removed_count = lock_manager.clean_stale_locks()

        assert removed_count == 0


class TestContextManager:
    """Test context manager protocol."""

    def test_context_manager_acquires_and_releases_lock(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Context manager acquires on enter, releases on exit."""
        with lock_manager:
            assert lock_manager._lock_acquired is True
            assert lock_manager.lock_file.exists()

        assert lock_manager._lock_acquired is False
        assert not lock_manager.lock_file.exists()

    def test_context_manager_releases_lock_on_exception(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Context manager releases lock even when exception occurs."""
        try:
            with lock_manager:
                assert lock_manager._lock_acquired is True
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock should be released despite exception
        assert lock_manager._lock_acquired is False
        assert not lock_manager.lock_file.exists()


class TestDestructor:
    """Test destructor cleanup."""

    def test_destructor_releases_lock_if_not_released(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Destructor releases lock if not explicitly released."""
        lock_manager.acquire()
        lock_file = lock_manager.lock_file

        # Delete manager without releasing
        lock_manager.__del__()

        # Lock should be released
        assert not lock_file.exists()


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_lock_with_very_long_iac_path(
        self, tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock works with very long IaC directory paths."""
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        # Create deeply nested path
        long_path = tmp_path
        for i in range(20):
            long_path = long_path / f"dir{i}"
        long_path.mkdir(parents=True, exist_ok=True)

        lock_mgr = DeploymentLockManager(long_path, job_id="test-job")

        success = lock_mgr.acquire()
        assert success is True
        lock_mgr.release()

    def test_lock_with_special_characters_in_path(
        self, tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock works with special characters in IaC directory path."""
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        # Path with spaces and special chars
        special_path = tmp_path / "path with spaces" / "special-chars_123"
        special_path.mkdir(parents=True, exist_ok=True)

        lock_mgr = DeploymentLockManager(special_path, job_id="test-job")

        success = lock_mgr.acquire()
        assert success is True
        lock_mgr.release()

    def test_lock_with_unicode_in_path(
        self, tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock works with Unicode characters in IaC directory path."""
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        unicode_path = tmp_path / "iac_测试_🚀"
        unicode_path.mkdir(parents=True, exist_ok=True)

        lock_mgr = DeploymentLockManager(unicode_path, job_id="test-job")

        success = lock_mgr.acquire()
        assert success is True
        lock_mgr.release()

    def test_lock_timeout_zero_returns_false_immediately(
        self,
        lock_manager: DeploymentLockManager,
        tmp_path: Path,
        temp_lock_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Lock acquisition with timeout=0 returns False immediately."""
        lock_manager.acquire()

        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        lock_manager2 = DeploymentLockManager(lock_manager.iac_dir, job_id="test-job-2")

        success = lock_manager2.acquire(timeout=0)

        assert success is False


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_acquire_lock_handles_permission_error(
        self, lock_manager: DeploymentLockManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock acquisition handles permission errors gracefully."""

        def mock_open(*args, **kwargs):
            raise PermissionError("No permission")

        monkeypatch.setattr("os.open", mock_open)

        with pytest.raises(LockError, match="Failed to acquire file lock"):
            lock_manager.acquire()

    def test_read_lock_metadata_handles_corrupted_json(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Reading corrupted lock metadata returns None."""
        # Create lock file with invalid JSON
        lock_manager.lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_manager.lock_file.write_text("invalid json {{{")

        metadata = lock_manager._read_lock_metadata()

        assert metadata is None

    def test_read_lock_metadata_handles_missing_file(
        self, lock_manager: DeploymentLockManager
    ) -> None:
        """Reading non-existent lock metadata returns None."""
        metadata = lock_manager._read_lock_metadata()

        assert metadata is None

    def test_is_process_alive_handles_permission_error(
        self, lock_manager: DeploymentLockManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Process liveness check handles permission errors."""

        def mock_kill(pid, sig):
            raise PermissionError("No permission")

        monkeypatch.setattr("os.kill", mock_kill)

        # Should return False and not raise
        result = lock_manager._is_process_alive(os.getpid())

        assert result is False


class TestConcurrentAccess:
    """Test concurrent access scenarios."""

    def test_concurrent_lock_attempts_only_one_succeeds(
        self, tmp_path: Path, temp_lock_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only one of concurrent lock attempts succeeds."""
        monkeypatch.setattr(
            "src.deployment.lock_manager.DeploymentLockManager.LOCK_DIR",
            temp_lock_dir,
        )
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir(parents=True, exist_ok=True)

        lock_mgr1 = DeploymentLockManager(iac_dir, job_id="job-1")
        lock_mgr2 = DeploymentLockManager(iac_dir, job_id="job-2")

        # First acquires successfully
        success1 = lock_mgr1.acquire()

        # Second fails (short timeout)
        success2 = lock_mgr2.acquire(timeout=0.5)

        assert success1 is True
        assert success2 is False

        # After first releases, second can acquire
        lock_mgr1.release()
        success2_retry = lock_mgr2.acquire()
        assert success2_retry is True
        lock_mgr2.release()
