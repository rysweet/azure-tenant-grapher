"""
Tests for deployment state manager.

Tests state persistence, job configuration storage/retrieval, status management,
log file access, and cleanup operations.

Philosophy:
- Test state persistence reliability
- Boundary conditions for file I/O
- Error handling for missing/corrupted files
- Cleanup logic validation
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.deployment.background.state_manager import StateManager


@pytest.fixture
def jobs_dir(tmp_path: Path) -> Path:
    """Create temporary jobs directory for tests."""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


@pytest.fixture
def state_manager(jobs_dir: Path) -> StateManager:
    """Create state manager with temporary directory."""
    return StateManager(jobs_dir)


@pytest.fixture
def sample_job_dir(jobs_dir: Path) -> Path:
    """Create sample job directory with files."""
    job_dir = jobs_dir / "test-job-123"
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create config file
    config = {
        "job_id": "test-job-123",
        "iac_dir": "/path/to/iac",
        "target_tenant_id": "tenant-123",
        "resource_group": "test-rg",
        "location": "eastus",
        "subscription_id": "sub-123",
        "iac_format": "terraform",
        "dry_run": False,
        "command": ["python", "-m", "src.cli", "deploy"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (job_dir / "config.json").write_text(json.dumps(config, indent=2))

    # Create status file
    status = {
        "job_id": "test-job-123",
        "status": "running",
        "phase": "deploy",
        "created_at": config["created_at"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pid": 12345,
        "exit_code": None,
        "error": None,
    }
    (job_dir / "status.json").write_text(json.dumps(status, indent=2))

    # Create log file
    (job_dir / "output.log").write_text("Sample log output\n")

    # Create PID file
    (job_dir / "pid.lock").write_text("12345")

    return job_dir


class TestStateManagerInit:
    """Test state manager initialization."""

    def test_init_sets_jobs_dir(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Jobs directory is stored correctly."""
        assert state_manager.jobs_dir == jobs_dir


class TestConfigRetrieval:
    """Test job configuration retrieval."""

    def test_get_job_config_returns_config(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Job configuration is retrieved successfully."""
        config = state_manager.get_job_config("test-job-123")

        assert config["job_id"] == "test-job-123"
        assert config["iac_dir"] == "/path/to/iac"
        assert config["target_tenant_id"] == "tenant-123"
        assert config["resource_group"] == "test-rg"
        assert config["location"] == "eastus"
        assert config["iac_format"] == "terraform"

    def test_get_job_config_raises_when_not_exists(
        self, state_manager: StateManager
    ) -> None:
        """ValueError raised when job config does not exist."""
        with pytest.raises(ValueError, match="Config for job nonexistent not found"):
            state_manager.get_job_config("nonexistent")

    def test_get_job_config_handles_corrupted_json(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Corrupted JSON config raises appropriate error."""
        job_dir = jobs_dir / "corrupted-job"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "config.json").write_text("invalid json {{{")

        with pytest.raises(json.JSONDecodeError):
            state_manager.get_job_config("corrupted-job")


class TestStatusReadWrite:
    """Test status file read/write operations."""

    def test_read_status_returns_status(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Job status is read successfully."""
        status = state_manager.read_status("test-job-123")

        assert status["job_id"] == "test-job-123"
        assert status["status"] == "running"
        assert status["phase"] == "deploy"
        assert status["pid"] == 12345
        assert status["exit_code"] is None

    def test_read_status_raises_when_not_exists(
        self, state_manager: StateManager
    ) -> None:
        """ValueError raised when job status does not exist."""
        with pytest.raises(ValueError, match="Job nonexistent not found"):
            state_manager.read_status("nonexistent")

    def test_write_status_creates_status_file(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Status file is written successfully."""
        new_status = {
            "job_id": "test-job-123",
            "status": "completed",
            "phase": "complete",
            "exit_code": 0,
        }

        state_manager.write_status("test-job-123", new_status)

        # Verify written data
        status_file = sample_job_dir / "status.json"
        written_status = json.loads(status_file.read_text())
        assert written_status["status"] == "completed"
        assert written_status["phase"] == "complete"
        assert written_status["exit_code"] == 0

    def test_write_status_raises_when_job_not_exists(
        self, state_manager: StateManager
    ) -> None:
        """ValueError raised when writing status for non-existent job."""
        with pytest.raises(ValueError, match="Job nonexistent not found"):
            state_manager.write_status("nonexistent", {"status": "running"})

    def test_write_status_preserves_formatting(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Status file is written with proper JSON formatting."""
        status = {"job_id": "test-job-123", "status": "failed"}

        state_manager.write_status("test-job-123", status)

        status_file = sample_job_dir / "status.json"
        content = status_file.read_text()

        # Verify indentation (2 spaces)
        assert "  " in content
        # Verify it's valid JSON
        parsed = json.loads(content)
        assert parsed["status"] == "failed"


class TestLogFileAccess:
    """Test log file path retrieval."""

    def test_get_log_file_returns_path(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Log file path is returned correctly."""
        log_file = state_manager.get_log_file("test-job-123")

        assert log_file == sample_job_dir / "output.log"
        assert log_file.exists()

    def test_get_log_file_raises_when_not_exists(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """ValueError raised when log file does not exist."""
        # Create job dir without log file
        job_dir = jobs_dir / "no-log-job"
        job_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ValueError, match="Log file for job no-log-job not found"):
            state_manager.get_log_file("no-log-job")


class TestPIDFileAccess:
    """Test PID file path retrieval."""

    def test_get_pid_file_returns_path(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """PID file path is returned correctly."""
        pid_file = state_manager.get_pid_file("test-job-123")

        assert pid_file == sample_job_dir / "pid.lock"


class TestJobListing:
    """Test job directory listing."""

    def test_list_job_dirs_returns_all_job_directories(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """All job directories are listed."""
        # Create multiple job directories
        for i in range(3):
            (jobs_dir / f"job-{i}").mkdir(parents=True, exist_ok=True)

        job_dirs = state_manager.list_job_dirs()

        assert len(job_dirs) == 3
        job_names = {d.name for d in job_dirs}
        assert "job-0" in job_names
        assert "job-1" in job_names
        assert "job-2" in job_names

    def test_list_job_dirs_ignores_files(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Non-directory files are ignored."""
        # Create job directory and a file
        (jobs_dir / "job-1").mkdir(parents=True, exist_ok=True)
        (jobs_dir / "not-a-dir.txt").write_text("test")

        job_dirs = state_manager.list_job_dirs()

        assert len(job_dirs) == 1
        assert job_dirs[0].name == "job-1"

    def test_list_job_dirs_returns_empty_when_no_jobs(
        self, state_manager: StateManager
    ) -> None:
        """Empty list returned when no job directories exist."""
        job_dirs = state_manager.list_job_dirs()

        assert job_dirs == []

    def test_list_job_dirs_returns_empty_when_dir_not_exists(
        self, tmp_path: Path
    ) -> None:
        """Empty list returned when jobs directory doesn't exist."""
        non_existent_dir = tmp_path / "nonexistent"
        manager = StateManager(non_existent_dir)

        job_dirs = manager.list_job_dirs()

        assert job_dirs == []


class TestJobCleanup:
    """Test old job cleanup functionality."""

    def test_cleanup_old_jobs_removes_old_completed_jobs(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Old completed jobs are removed."""
        # Create old completed job
        old_job_dir = jobs_dir / "old-job"
        old_job_dir.mkdir(parents=True, exist_ok=True)

        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        old_status = {
            "job_id": "old-job",
            "status": "completed",
            "created_at": old_timestamp.isoformat(),
        }
        (old_job_dir / "status.json").write_text(json.dumps(old_status))

        # Create recent job
        recent_job_dir = jobs_dir / "recent-job"
        recent_job_dir.mkdir(parents=True, exist_ok=True)

        recent_status = {
            "job_id": "recent-job",
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (recent_job_dir / "status.json").write_text(json.dumps(recent_status))

        # Cleanup jobs older than 30 days
        removed_count = state_manager.cleanup_old_jobs(days=30)

        assert removed_count == 1
        assert not old_job_dir.exists()
        assert recent_job_dir.exists()

    def test_cleanup_old_jobs_preserves_running_jobs(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Running jobs are not removed even if old."""
        # Create old running job
        old_running_dir = jobs_dir / "old-running"
        old_running_dir.mkdir(parents=True, exist_ok=True)

        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        old_status = {
            "job_id": "old-running",
            "status": "running",
            "created_at": old_timestamp.isoformat(),
        }
        (old_running_dir / "status.json").write_text(json.dumps(old_status))

        # Cleanup
        removed_count = state_manager.cleanup_old_jobs(days=30)

        assert removed_count == 0
        assert old_running_dir.exists()

    def test_cleanup_old_jobs_removes_failed_jobs(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Old failed jobs are removed."""
        # Create old failed job
        old_failed_dir = jobs_dir / "old-failed"
        old_failed_dir.mkdir(parents=True, exist_ok=True)

        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        old_status = {
            "job_id": "old-failed",
            "status": "failed",
            "created_at": old_timestamp.isoformat(),
        }
        (old_failed_dir / "status.json").write_text(json.dumps(old_status))

        # Cleanup
        removed_count = state_manager.cleanup_old_jobs(days=30)

        assert removed_count == 1
        assert not old_failed_dir.exists()

    def test_cleanup_old_jobs_removes_cancelled_jobs(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Old cancelled jobs are removed."""
        # Create old cancelled job
        old_cancelled_dir = jobs_dir / "old-cancelled"
        old_cancelled_dir.mkdir(parents=True, exist_ok=True)

        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        old_status = {
            "job_id": "old-cancelled",
            "status": "cancelled",
            "created_at": old_timestamp.isoformat(),
        }
        (old_cancelled_dir / "status.json").write_text(json.dumps(old_status))

        # Cleanup
        removed_count = state_manager.cleanup_old_jobs(days=30)

        assert removed_count == 1
        assert not old_cancelled_dir.exists()

    def test_cleanup_old_jobs_handles_corrupted_status(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Cleanup handles jobs with corrupted status gracefully."""
        # Create job with corrupted status
        corrupted_dir = jobs_dir / "corrupted"
        corrupted_dir.mkdir(parents=True, exist_ok=True)
        (corrupted_dir / "status.json").write_text("invalid json")

        # Cleanup should not raise, should skip corrupted job
        removed_count = state_manager.cleanup_old_jobs(days=30)

        assert removed_count == 0
        assert corrupted_dir.exists()

    def test_cleanup_old_jobs_returns_zero_when_no_jobs(
        self, state_manager: StateManager
    ) -> None:
        """Cleanup returns 0 when no jobs exist."""
        removed_count = state_manager.cleanup_old_jobs(days=30)

        assert removed_count == 0

    def test_cleanup_old_jobs_returns_zero_when_dir_not_exists(
        self, tmp_path: Path
    ) -> None:
        """Cleanup returns 0 when jobs directory doesn't exist."""
        non_existent_dir = tmp_path / "nonexistent"
        manager = StateManager(non_existent_dir)

        removed_count = manager.cleanup_old_jobs(days=30)

        assert removed_count == 0


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_read_status_with_minimal_status_file(
        self, state_manager: StateManager, jobs_dir: Path
    ) -> None:
        """Minimal status file (just job_id) can be read."""
        job_dir = jobs_dir / "minimal-job"
        job_dir.mkdir(parents=True, exist_ok=True)

        minimal_status = {"job_id": "minimal-job"}
        (job_dir / "status.json").write_text(json.dumps(minimal_status))

        status = state_manager.read_status("minimal-job")

        assert status["job_id"] == "minimal-job"

    def test_write_status_with_unicode_content(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Status with Unicode content is written correctly."""
        unicode_status = {
            "job_id": "test-job-123",
            "status": "failed",
            "error": "错误: Deployment failed 🚫",
        }

        state_manager.write_status("test-job-123", unicode_status)

        # Verify written data
        written_status = state_manager.read_status("test-job-123")
        assert written_status["error"] == "错误: Deployment failed 🚫"

    def test_cleanup_with_very_large_days_value(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Cleanup with very large days value works correctly."""
        # Cleanup jobs older than 10 years
        removed_count = state_manager.cleanup_old_jobs(days=3650)

        # No jobs should be removed (recent job)
        assert removed_count == 0
        assert sample_job_dir.exists()

    def test_cleanup_with_zero_days(
        self, state_manager: StateManager, sample_job_dir: Path
    ) -> None:
        """Cleanup with days=0 removes all completed jobs."""
        # Mark job as completed
        status = state_manager.read_status("test-job-123")
        status["status"] = "completed"
        state_manager.write_status("test-job-123", status)

        # Cleanup with 0 days
        removed_count = state_manager.cleanup_old_jobs(days=0)

        # Job should be removed
        assert removed_count == 1
        assert not sample_job_dir.exists()


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_read_status_handles_permission_error(
        self,
        state_manager: StateManager,
        sample_job_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Permission error when reading status is propagated."""

        def mock_open(*args, **kwargs):
            raise PermissionError("No permission")

        monkeypatch.setattr("builtins.open", mock_open)

        with pytest.raises(PermissionError):
            state_manager.read_status("test-job-123")

    def test_write_status_handles_disk_full(
        self,
        state_manager: StateManager,
        sample_job_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Disk full error when writing status is propagated."""

        def mock_open(*args, **kwargs):
            from io import StringIO

            mock_file = StringIO()
            mock_file.write = lambda x: (_ for _ in ()).throw(
                OSError("No space left on device")
            )
            mock_file.__enter__ = lambda self: self
            mock_file.__exit__ = lambda self, *args: None
            return mock_file

        monkeypatch.setattr("builtins.open", mock_open)

        with pytest.raises(OSError, match="No space left on device"):
            state_manager.write_status("test-job-123", {"status": "running"})

    def test_cleanup_handles_permission_error_when_removing(
        self,
        state_manager: StateManager,
        jobs_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Permission error during cleanup is logged and handled gracefully."""
        # Create old completed job
        old_job_dir = jobs_dir / "old-job"
        old_job_dir.mkdir(parents=True, exist_ok=True)

        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        old_status = {
            "job_id": "old-job",
            "status": "completed",
            "created_at": old_timestamp.isoformat(),
        }
        (old_job_dir / "status.json").write_text(json.dumps(old_status))

        def mock_rmtree(path):
            raise PermissionError("No permission")

        monkeypatch.setattr("shutil.rmtree", mock_rmtree)

        # Cleanup should not raise, should handle error gracefully
        removed_count = state_manager.cleanup_old_jobs(days=30)

        # Count should be 0 since removal failed
        assert removed_count == 0
        assert old_job_dir.exists()
