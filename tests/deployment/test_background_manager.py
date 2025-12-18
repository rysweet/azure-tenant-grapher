"""
Tests for Background Deployment Manager

Comprehensive test coverage for the modular background deployment manager,
verifying zero breaking changes from the original monolithic implementation.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.deployment.background import BackgroundDeploymentManager


@pytest.fixture
def temp_jobs_dir(tmp_path):
    """Create a temporary jobs directory for testing."""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


@pytest.fixture
def manager(temp_jobs_dir):
    """Create a BackgroundDeploymentManager instance with temp directory."""
    return BackgroundDeploymentManager(jobs_dir=temp_jobs_dir)


@pytest.fixture
def sample_job_dir(temp_jobs_dir):
    """Create a sample job directory with files."""
    job_id = "test-job-123"
    job_dir = temp_jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create config file
    config = {
        "job_id": job_id,
        "iac_dir": "/path/to/iac",
        "target_tenant_id": "tenant-123",
        "resource_group": "rg-test",
        "location": "eastus",
        "subscription_id": None,
        "iac_format": None,
        "dry_run": False,
        "command": ["python", "-m", "src.cli", "deploy"],
        "created_at": "2024-01-01T00:00:00+00:00",
    }

    with open(job_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Create status file
    status = {
        "job_id": job_id,
        "status": "running",
        "phase": "deploy",
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
        "pid": 12345,
        "exit_code": None,
        "error": None,
    }

    with open(job_dir / "status.json", "w") as f:
        json.dump(status, f, indent=2)

    # Create log file
    with open(job_dir / "output.log", "w") as f:
        f.write("Initializing deployment...\n")
        f.write("Deployment in progress...\n")

    # Create PID file
    with open(job_dir / "pid.lock", "w") as f:
        f.write("12345")

    return job_dir


class TestInitialization:
    """Tests for manager initialization."""

    def test_init_with_default_jobs_dir(self, tmp_path):
        """Test initialization with default jobs directory."""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            manager = BackgroundDeploymentManager()
            expected_dir = tmp_path / ".deployments" / "jobs"
            assert manager.jobs_dir == expected_dir
            assert expected_dir.exists()

    def test_init_with_custom_jobs_dir(self, temp_jobs_dir):
        """Test initialization with custom jobs directory."""
        manager = BackgroundDeploymentManager(jobs_dir=temp_jobs_dir)
        assert manager.jobs_dir == temp_jobs_dir
        assert temp_jobs_dir.exists()

    def test_components_initialized(self, manager):
        """Test that all components are properly initialized."""
        assert manager.state_manager is not None
        assert manager.process_manager is not None
        assert manager.job_tracker is not None
        assert manager.job_spawner is not None
        assert manager.log_streamer is not None


class TestSpawnDeployment:
    """Tests for spawning deployments."""

    @patch("subprocess.Popen")
    def test_spawn_deployment_basic(self, mock_popen, manager, temp_jobs_dir):
        """Test basic deployment spawning."""
        # Setup mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # Spawn deployment
        result = manager.spawn_deployment(
            job_id="test-job",
            iac_dir=Path("/path/to/iac"),
            target_tenant_id="tenant-123",
            resource_group="rg-test",
        )

        # Verify result
        assert result["job_id"] == "test-job"
        assert result["pid"] == 12345
        assert result["status"] == "running"
        assert "log_file" in result
        assert "status_file" in result

        # Verify files created
        job_dir = temp_jobs_dir / "test-job"
        assert job_dir.exists()
        assert (job_dir / "config.json").exists()
        assert (job_dir / "status.json").exists()
        assert (job_dir / "pid.lock").exists()

    @patch("subprocess.Popen")
    def test_spawn_deployment_with_all_params(self, mock_popen, manager):
        """Test deployment spawning with all optional parameters."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = manager.spawn_deployment(
            job_id="test-job-full",
            iac_dir=Path("/path/to/iac"),
            target_tenant_id="tenant-123",
            resource_group="rg-test",
            location="westus",
            subscription_id="sub-456",
            iac_format="terraform",
            dry_run=True,
            env={"TEST_VAR": "value"},
        )

        assert result["job_id"] == "test-job-full"
        assert result["pid"] == 12345

    def test_spawn_deployment_duplicate_job_id(self, manager, sample_job_dir):
        """Test that spawning with duplicate job_id raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            manager.spawn_deployment(
                job_id="test-job-123",
                iac_dir=Path("/path/to/iac"),
                target_tenant_id="tenant-123",
                resource_group="rg-test",
            )

    @patch("subprocess.Popen", side_effect=Exception("Process spawn failed"))
    def test_spawn_deployment_failure(self, mock_popen, manager):
        """Test handling of process spawn failure."""
        with pytest.raises(RuntimeError, match="Failed to spawn deployment process"):
            manager.spawn_deployment(
                job_id="test-job-fail",
                iac_dir=Path("/path/to/iac"),
                target_tenant_id="tenant-123",
                resource_group="rg-test",
            )


class TestGetStatus:
    """Tests for getting job status."""

    def test_get_status_running_job(self, manager, sample_job_dir):
        """Test getting status of a running job."""
        with patch.object(manager.process_manager, "check_pid", return_value=True):
            status = manager.get_status("test-job-123")

            assert status["job_id"] == "test-job-123"
            assert status["status"] == "running"
            assert status["pid"] == 12345

    def test_get_status_completed_job(self, manager, sample_job_dir):
        """Test status update when job completes."""
        with patch.object(manager.process_manager, "check_pid", return_value=False):
            status = manager.get_status("test-job-123")

            assert status["status"] == "completed"
            assert status["phase"] == "complete"
            assert status["exit_code"] == 0

    def test_get_status_failed_job(self, manager, sample_job_dir):
        """Test status update when job fails."""
        # Add error to log
        log_file = sample_job_dir / "output.log"
        with open(log_file, "a") as f:
            f.write("ERROR: Deployment failed\n")

        with patch.object(manager.process_manager, "check_pid", return_value=False):
            status = manager.get_status("test-job-123")

            assert status["status"] == "failed"
            assert status["phase"] == "failed"
            assert status["exit_code"] == 1
            assert "error" in status

    def test_get_status_nonexistent_job(self, manager):
        """Test getting status of non-existent job raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            manager.get_status("nonexistent-job")


class TestListDeployments:
    """Tests for listing deployments."""

    def test_list_deployments_empty(self, manager):
        """Test listing deployments when none exist."""
        jobs = manager.list_deployments()
        assert jobs == []

    def test_list_deployments_with_jobs(self, manager, sample_job_dir):
        """Test listing all deployments."""
        with patch.object(manager.process_manager, "check_pid", return_value=True):
            jobs = manager.list_deployments()

            assert len(jobs) == 1
            assert jobs[0]["job_id"] == "test-job-123"
            assert jobs[0]["status"] == "running"

    def test_list_deployments_with_filter(self, manager, sample_job_dir):
        """Test listing deployments with status filter."""
        with patch.object(manager.process_manager, "check_pid", return_value=False):
            # Should find completed job
            completed_jobs = manager.list_deployments(status_filter="completed")
            assert len(completed_jobs) == 1

            # Should not find running jobs
            running_jobs = manager.list_deployments(status_filter="running")
            assert len(running_jobs) == 0


class TestStreamLogs:
    """Tests for streaming logs."""

    def test_stream_logs_basic(self, manager, sample_job_dir):
        """Test basic log streaming."""
        lines = list(manager.stream_logs("test-job-123"))

        assert len(lines) == 2
        assert "Initializing deployment..." in lines[0]
        assert "Deployment in progress..." in lines[1]

    def test_stream_logs_with_tail(self, manager, sample_job_dir):
        """Test log streaming with tail_lines parameter."""
        lines = list(manager.stream_logs("test-job-123", tail_lines=1))

        assert len(lines) == 1
        assert "Deployment in progress..." in lines[0]

    def test_stream_logs_nonexistent_job(self, manager):
        """Test streaming logs for non-existent job raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            list(manager.stream_logs("nonexistent-job"))


class TestCancelDeployment:
    """Tests for canceling deployments."""

    def test_cancel_deployment_success(self, manager, sample_job_dir):
        """Test successful deployment cancellation."""
        # Mock both check_pid and terminate_process
        with patch.object(
            manager.process_manager, "check_pid", return_value=True
        ), patch.object(
            manager.process_manager, "terminate_process", return_value=True
        ):
            success = manager.cancel_deployment("test-job-123")

            assert success is True

            # Verify status updated
            status = manager.get_status("test-job-123")
            assert status["status"] == "cancelled"
            assert "cancelled by user" in status["error"]

    def test_cancel_non_running_job(self, manager, sample_job_dir):
        """Test canceling a non-running job returns False."""
        # Mark job as completed
        status_file = sample_job_dir / "status.json"
        with open(status_file) as f:
            status = json.load(f)
        status["status"] = "completed"
        with open(status_file, "w") as f:
            json.dump(status, f)

        success = manager.cancel_deployment("test-job-123")
        assert success is False

    def test_cancel_deployment_process_not_found(self, manager, sample_job_dir):
        """Test canceling when process already terminated."""
        # Mock check_pid to return True so cancel is attempted
        with patch.object(
            manager.process_manager, "check_pid", return_value=True
        ), patch.object(
            manager.process_manager,
            "terminate_process",
            side_effect=ProcessLookupError(),
        ):
            success = manager.cancel_deployment("test-job-123")

            assert success is False

            # Verify status marked as failed
            status = manager.get_status("test-job-123")
            assert status["status"] == "failed"


class TestCleanupOldJobs:
    """Tests for cleaning up old jobs."""

    def test_cleanup_old_jobs(self, manager, sample_job_dir):
        """Test cleaning up old completed jobs."""
        # Mark job as old and completed
        status_file = sample_job_dir / "status.json"
        with open(status_file) as f:
            status = json.load(f)
        status["status"] = "completed"
        status["created_at"] = "2020-01-01T00:00:00+00:00"  # Very old
        with open(status_file, "w") as f:
            json.dump(status, f)

        # Cleanup jobs older than 30 days
        count = manager.cleanup_old_jobs(days=30)

        assert count == 1
        assert not sample_job_dir.exists()

    def test_cleanup_preserves_running_jobs(self, manager, sample_job_dir):
        """Test that running jobs are not cleaned up."""
        # Mark job as old but still running
        status_file = sample_job_dir / "status.json"
        with open(status_file) as f:
            status = json.load(f)
        status["created_at"] = "2020-01-01T00:00:00+00:00"  # Very old
        status["status"] = "running"  # Still running
        with open(status_file, "w") as f:
            json.dump(status, f)

        # Try to cleanup
        count = manager.cleanup_old_jobs(days=30)

        assert count == 0
        assert sample_job_dir.exists()


class TestGetJobConfig:
    """Tests for getting job configuration."""

    def test_get_job_config(self, manager, sample_job_dir):
        """Test getting job configuration."""
        config = manager.get_job_config("test-job-123")

        assert config["job_id"] == "test-job-123"
        assert config["iac_dir"] == "/path/to/iac"
        assert config["target_tenant_id"] == "tenant-123"
        assert config["resource_group"] == "rg-test"

    def test_get_job_config_nonexistent(self, manager):
        """Test getting config for non-existent job raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            manager.get_job_config("nonexistent-job")
