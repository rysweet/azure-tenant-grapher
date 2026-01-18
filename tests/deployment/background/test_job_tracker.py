"""
Tests for deployment job tracker.

Tests job status tracking, listing with filtering, process health checks,
and integration with StateManager and ProcessManager.

Philosophy:
- Test job tracking accuracy
- Verify process state detection
- Test status filtering logic
- Integration with component managers
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from src.deployment.background.job_tracker import JobTracker
from src.deployment.background.process_manager import ProcessManager
from src.deployment.background.state_manager import StateManager


@pytest.fixture
def jobs_dir(tmp_path: Path) -> Path:
    """Create temporary jobs directory for tests."""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


@pytest.fixture
def state_manager(jobs_dir: Path) -> StateManager:
    """Create state manager for tests."""
    return StateManager(jobs_dir)


@pytest.fixture
def process_manager() -> ProcessManager:
    """Create process manager for tests."""
    return ProcessManager()


@pytest.fixture
def job_tracker(
    state_manager: StateManager, process_manager: ProcessManager
) -> JobTracker:
    """Create job tracker for tests."""
    return JobTracker(state_manager, process_manager)


@pytest.fixture
def sample_running_job(jobs_dir: Path) -> Dict[str, Any]:
    """Create sample running job."""
    job_id = "job-running-123"
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    import json
    import os

    status = {
        "job_id": job_id,
        "status": "running",
        "phase": "deploy",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),  # Use current process PID (alive)
        "exit_code": None,
        "error": None,
    }
    (job_dir / "status.json").write_text(json.dumps(status, indent=2))
    (job_dir / "output.log").write_text("Deployment in progress...\n")

    return status


@pytest.fixture
def sample_completed_job(jobs_dir: Path) -> Dict[str, Any]:
    """Create sample completed job."""
    job_id = "job-completed-456"
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    import json

    status = {
        "job_id": job_id,
        "status": "completed",
        "phase": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pid": 12345,
        "exit_code": 0,
        "error": None,
    }
    (job_dir / "status.json").write_text(json.dumps(status, indent=2))
    (job_dir / "output.log").write_text("Deployment completed successfully.\n")

    return status


@pytest.fixture
def sample_failed_job(jobs_dir: Path) -> Dict[str, Any]:
    """Create sample failed job."""
    job_id = "job-failed-789"
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    import json

    status = {
        "job_id": job_id,
        "status": "failed",
        "phase": "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pid": 99999,
        "exit_code": 1,
        "error": "Deployment failed (check logs for details)",
    }
    (job_dir / "status.json").write_text(json.dumps(status, indent=2))
    (job_dir / "output.log").write_text("Error: Terraform apply failed\n")

    return status


class TestJobTrackerInit:
    """Test job tracker initialization."""

    def test_init_sets_managers(
        self,
        job_tracker: JobTracker,
        state_manager: StateManager,
        process_manager: ProcessManager,
    ) -> None:
        """StateManager and ProcessManager are stored correctly."""
        assert job_tracker.state_manager == state_manager
        assert job_tracker.process_manager == process_manager


class TestGetStatus:
    """Test job status retrieval."""

    def test_get_status_returns_status_for_running_job(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
    ) -> None:
        """Status for running job is retrieved correctly."""
        status = job_tracker.get_status("job-running-123")

        assert status["job_id"] == "job-running-123"
        assert status["status"] == "running"
        assert status["phase"] == "deploy"
        assert status["pid"] is not None

    def test_get_status_returns_status_for_completed_job(
        self,
        job_tracker: JobTracker,
        sample_completed_job: Dict[str, Any],
    ) -> None:
        """Status for completed job is retrieved correctly."""
        status = job_tracker.get_status("job-completed-456")

        assert status["job_id"] == "job-completed-456"
        assert status["status"] == "completed"
        assert status["phase"] == "complete"
        assert status["exit_code"] == 0

    def test_get_status_raises_when_job_not_exists(
        self, job_tracker: JobTracker
    ) -> None:
        """ValueError raised when job does not exist."""
        with pytest.raises(ValueError, match="Job nonexistent not found"):
            job_tracker.get_status("nonexistent")

    def test_get_status_updates_terminated_process_to_completed(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Terminated process without errors is marked as completed."""
        import json

        # Create job with dead PID
        job_id = "job-terminated-clean"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {
            "job_id": job_id,
            "status": "running",
            "phase": "deploy",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pid": 99999999,  # Dead PID
            "exit_code": None,
            "error": None,
        }
        (job_dir / "status.json").write_text(json.dumps(status, indent=2))
        (job_dir / "output.log").write_text("Deployment completed.\n")

        # Get status (should detect process terminated)
        updated_status = job_tracker.get_status(job_id)

        assert updated_status["status"] == "completed"
        assert updated_status["phase"] == "complete"
        assert updated_status["exit_code"] == 0

    def test_get_status_updates_terminated_process_to_failed_on_error(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Terminated process with errors in log is marked as failed."""
        import json

        # Create job with dead PID and error in log
        job_id = "job-terminated-error"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {
            "job_id": job_id,
            "status": "running",
            "phase": "deploy",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pid": 99999999,  # Dead PID
            "exit_code": None,
            "error": None,
        }
        (job_dir / "status.json").write_text(json.dumps(status, indent=2))
        (job_dir / "output.log").write_text("Error: Terraform apply failed\n")

        # Get status (should detect process terminated with error)
        updated_status = job_tracker.get_status(job_id)

        assert updated_status["status"] == "failed"
        assert updated_status["phase"] == "failed"
        assert updated_status["exit_code"] == 1
        assert "Deployment failed" in updated_status["error"]


class TestListDeployments:
    """Test deployment listing with filtering."""

    def test_list_deployments_returns_all_jobs_without_filter(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
        sample_completed_job: Dict[str, Any],
        sample_failed_job: Dict[str, Any],
    ) -> None:
        """All jobs are listed when no filter is applied."""
        jobs = job_tracker.list_deployments()

        assert len(jobs) == 3
        job_ids = {job["job_id"] for job in jobs}
        assert "job-running-123" in job_ids
        assert "job-completed-456" in job_ids
        assert "job-failed-789" in job_ids

    def test_list_deployments_filters_by_running_status(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
        sample_completed_job: Dict[str, Any],
        sample_failed_job: Dict[str, Any],
    ) -> None:
        """Only running jobs are listed when filtered."""
        jobs = job_tracker.list_deployments(status_filter="running")

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-running-123"
        assert jobs[0]["status"] == "running"

    def test_list_deployments_filters_by_completed_status(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
        sample_completed_job: Dict[str, Any],
        sample_failed_job: Dict[str, Any],
    ) -> None:
        """Only completed jobs are listed when filtered."""
        jobs = job_tracker.list_deployments(status_filter="completed")

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-completed-456"
        assert jobs[0]["status"] == "completed"

    def test_list_deployments_filters_by_failed_status(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
        sample_completed_job: Dict[str, Any],
        sample_failed_job: Dict[str, Any],
    ) -> None:
        """Only failed jobs are listed when filtered."""
        jobs = job_tracker.list_deployments(status_filter="failed")

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-failed-789"
        assert jobs[0]["status"] == "failed"

    def test_list_deployments_returns_empty_for_nonexistent_status(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
    ) -> None:
        """Empty list returned when filtering by nonexistent status."""
        jobs = job_tracker.list_deployments(status_filter="cancelled")

        assert len(jobs) == 0

    def test_list_deployments_sorts_by_created_at_descending(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Jobs are sorted by created_at in descending order."""
        import json
        import time

        # Create jobs with different timestamps
        for i in range(3):
            job_id = f"job-{i}"
            job_dir = jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            # Different timestamps (i=0 is oldest, i=2 is newest)
            timestamp = datetime.now(timezone.utc)
            if i == 0:
                timestamp = timestamp.replace(year=2024, month=1)
            elif i == 1:
                timestamp = timestamp.replace(year=2024, month=6)
            # i=2 uses current timestamp

            status = {
                "job_id": job_id,
                "status": "completed",
                "created_at": timestamp.isoformat(),
            }
            (job_dir / "status.json").write_text(json.dumps(status, indent=2))

            time.sleep(0.01)  # Small delay to ensure different timestamps

        jobs = job_tracker.list_deployments()

        # Should be sorted newest first
        assert jobs[0]["job_id"] == "job-2"
        assert jobs[1]["job_id"] == "job-1"
        assert jobs[2]["job_id"] == "job-0"

    def test_list_deployments_handles_missing_status_file(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Jobs without status files are skipped."""
        # Create job directory without status file
        job_dir = jobs_dir / "job-no-status"
        job_dir.mkdir(parents=True, exist_ok=True)

        jobs = job_tracker.list_deployments()

        # Should return empty list (job skipped)
        assert len(jobs) == 0

    def test_list_deployments_handles_corrupted_status_file(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
        sample_running_job: Dict[str, Any],
    ) -> None:
        """Jobs with corrupted status files are skipped gracefully."""
        # Create job with corrupted status
        job_dir = jobs_dir / "job-corrupted"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "status.json").write_text("invalid json")

        # Should not raise, should skip corrupted job
        jobs = job_tracker.list_deployments()

        # Should only return the valid job
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-running-123"


class TestIsJobRunning:
    """Test job running status check."""

    def test_is_job_running_returns_true_for_running_job(
        self,
        job_tracker: JobTracker,
        sample_running_job: Dict[str, Any],
    ) -> None:
        """Returns True for running job."""
        is_running = job_tracker.is_job_running("job-running-123")

        assert is_running is True

    def test_is_job_running_returns_false_for_completed_job(
        self,
        job_tracker: JobTracker,
        sample_completed_job: Dict[str, Any],
    ) -> None:
        """Returns False for completed job."""
        is_running = job_tracker.is_job_running("job-completed-456")

        assert is_running is False

    def test_is_job_running_returns_false_for_failed_job(
        self,
        job_tracker: JobTracker,
        sample_failed_job: Dict[str, Any],
    ) -> None:
        """Returns False for failed job."""
        is_running = job_tracker.is_job_running("job-failed-789")

        assert is_running is False

    def test_is_job_running_returns_false_for_nonexistent_job(
        self, job_tracker: JobTracker
    ) -> None:
        """Returns False for nonexistent job."""
        is_running = job_tracker.is_job_running("nonexistent")

        assert is_running is False


class TestCheckLogForErrors:
    """Test error detection in logs."""

    def test_check_log_for_errors_detects_error_keyword(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Error keyword in log is detected."""
        import json

        job_id = "job-with-error"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {"job_id": job_id, "status": "running"}
        (job_dir / "status.json").write_text(json.dumps(status))
        (job_dir / "output.log").write_text("Error: Something went wrong\n")

        has_error = job_tracker._check_log_for_errors(job_id)

        assert has_error is True

    def test_check_log_for_errors_detects_failed_keyword(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Failed keyword in log is detected."""
        import json

        job_id = "job-failed-keyword"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {"job_id": job_id, "status": "running"}
        (job_dir / "status.json").write_text(json.dumps(status))
        (job_dir / "output.log").write_text("Deployment failed\n")

        has_error = job_tracker._check_log_for_errors(job_id)

        assert has_error is True

    def test_check_log_for_errors_returns_false_for_clean_log(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Clean log without errors returns False."""
        import json

        job_id = "job-clean-log"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {"job_id": job_id, "status": "running"}
        (job_dir / "status.json").write_text(json.dumps(status))
        (job_dir / "output.log").write_text("Deployment in progress...\n")

        has_error = job_tracker._check_log_for_errors(job_id)

        assert has_error is False

    def test_check_log_for_errors_handles_missing_log_file(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Missing log file returns False (no error detected)."""
        import json

        job_id = "job-no-log"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {"job_id": job_id, "status": "running"}
        (job_dir / "status.json").write_text(json.dumps(status))
        # No log file created

        has_error = job_tracker._check_log_for_errors(job_id)

        assert has_error is False

    def test_check_log_for_errors_is_case_insensitive(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Error detection is case-insensitive."""
        import json

        job_id = "job-uppercase-error"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {"job_id": job_id, "status": "running"}
        (job_dir / "status.json").write_text(json.dumps(status))
        (job_dir / "output.log").write_text("ERROR: Something went wrong\n")

        has_error = job_tracker._check_log_for_errors(job_id)

        assert has_error is True


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_list_deployments_with_empty_jobs_directory(
        self, job_tracker: JobTracker
    ) -> None:
        """Empty list returned when no jobs exist."""
        jobs = job_tracker.list_deployments()

        assert jobs == []

    def test_get_status_updates_status_only_once(
        self,
        job_tracker: JobTracker,
        jobs_dir: Path,
    ) -> None:
        """Status is updated only once when process terminates."""
        import json

        job_id = "job-terminated"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        status = {
            "job_id": job_id,
            "status": "running",
            "pid": 99999999,  # Dead PID
        }
        (job_dir / "status.json").write_text(json.dumps(status, indent=2))
        (job_dir / "output.log").write_text("Completed.\n")

        # First call updates status
        status1 = job_tracker.get_status(job_id)
        assert status1["status"] == "completed"

        # Second call should return updated status (not re-update)
        status2 = job_tracker.get_status(job_id)
        assert status2["status"] == "completed"
        assert status1["updated_at"] == status2["updated_at"]
