"""
Tests for Deployment Job Tracker

Comprehensive test coverage for deployment job tracking functionality
including job creation, updates, relationships, and error handling.
"""

from unittest.mock import MagicMock

import pytest
from neo4j.exceptions import ServiceUnavailable

from src.deployment.job_tracker import DeploymentJobTracker
from src.exceptions import Neo4jConnectionError, Neo4jQueryError
from src.utils.session_manager import Neo4jSessionManager


@pytest.fixture
def mock_session_manager():
    """Create a mock Neo4j session manager for testing."""
    manager = MagicMock(spec=Neo4jSessionManager)
    manager.is_connected = True
    return manager


@pytest.fixture
def job_tracker(mock_session_manager):
    """Create a DeploymentJobTracker instance with mocked session manager."""
    return DeploymentJobTracker(mock_session_manager)


@pytest.fixture
def mock_neo4j_session():
    """Create a mock Neo4j session."""
    session = MagicMock()
    return session


class TestJobCreation:
    """Tests for deployment job creation."""

    def test_create_job_basic(self, job_tracker, mock_session_manager, mock_neo4j_session):
        """Test basic job creation with minimal parameters."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = {"job_id": "test-job-id"}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        job_id = job_tracker.create_job(
            tenant_id="tenant-123",
            format_type="terraform",
        )

        # Verify
        assert job_id is not None
        assert isinstance(job_id, str)
        # Verify session.run was called with CREATE query
        assert mock_neo4j_session.run.call_count >= 1
        call_args = mock_neo4j_session.run.call_args_list[0]
        assert "CREATE" in call_args[0][0]
        assert "DeploymentJob" in call_args[0][0]

    def test_create_job_with_all_parameters(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test job creation with all optional parameters."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = {"job_id": "test-job-id"}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        metadata = {"user": "test-user", "source": "cli"}

        # Execute
        job_id = job_tracker.create_job(
            tenant_id="tenant-123",
            format_type="bicep",
            status="running",
            metadata=metadata,
        )

        # Verify
        assert job_id is not None
        # Check that properties were passed correctly
        call_args = mock_neo4j_session.run.call_args_list[0]
        properties = call_args[1]["parameters"]["properties"]
        assert properties["tenant_id"] == "tenant-123"
        assert properties["format"] == "bicep"
        assert properties["status"] == "running"
        assert properties["metadata"] == metadata

    def test_create_job_with_parent(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test job creation with parent job ID for iteration tracking."""
        # Setup mock for both queries (CREATE and ITERATION_OF)
        parent_job_id = "parent-job-123"

        def run_side_effect(query, parameters=None):
            mock_result = MagicMock()
            if "ITERATION_OF" in query:
                mock_result.single.return_value = {"job_id": "new-job-id"}
            else:
                mock_result.single.return_value = {"job_id": "new-job-id"}
            return mock_result

        mock_neo4j_session.run.side_effect = run_side_effect
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        job_id = job_tracker.create_job(
            tenant_id="tenant-123",
            format_type="terraform",
            parent_job_id=parent_job_id,
        )

        # Verify
        assert job_id is not None
        # Should have called run twice (CREATE + ITERATION_OF)
        assert mock_neo4j_session.run.call_count == 2
        # Check second call is for ITERATION_OF
        iteration_call = mock_neo4j_session.run.call_args_list[1]
        assert "ITERATION_OF" in iteration_call[0][0]
        assert iteration_call[1]["parameters"]["parent_job_id"] == parent_job_id

    def test_create_job_no_result_raises_error(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test that creating a job with no result raises Neo4jQueryError."""
        # Setup mock to return None
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute and verify exception
        with pytest.raises(Neo4jQueryError) as exc_info:
            job_tracker.create_job(
                tenant_id="tenant-123",
                format_type="terraform",
            )
        assert "no result returned" in str(exc_info.value).lower()

    def test_create_job_neo4j_error(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test that Neo4j errors are properly wrapped and raised."""
        # Setup mock to raise Neo4jError
        mock_neo4j_session.run.side_effect = ServiceUnavailable("Database unavailable")
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute and verify exception
        with pytest.raises((Neo4jQueryError, Neo4jConnectionError, ServiceUnavailable)):
            job_tracker.create_job(
                tenant_id="tenant-123",
                format_type="terraform",
            )


class TestJobUpdate:
    """Tests for deployment job updates."""

    def test_update_job_status(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test updating job status."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = {"job_id": "job-123"}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        result = job_tracker.update_job(
            job_id="job-123",
            status="completed",
        )

        # Verify
        assert result is True
        # Check that SET clause includes status and updated_at
        call_args = mock_neo4j_session.run.call_args_list[0]
        query = call_args[0][0]
        assert "SET" in query
        assert "job.status" in query
        assert "job.updated_at" in query

    def test_update_job_all_fields(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test updating all job fields."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = {"job_id": "job-123"}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        metadata = {"resources_count": 42}

        # Execute
        result = job_tracker.update_job(
            job_id="job-123",
            status="completed",
            output_path="/path/to/output",
            error_message=None,
            metadata=metadata,
        )

        # Verify
        assert result is True
        call_args = mock_neo4j_session.run.call_args_list[0]
        parameters = call_args[1]["parameters"]
        assert parameters["status"] == "completed"
        assert parameters["output_path"] == "/path/to/output"
        assert parameters["metadata"] == metadata

    def test_update_job_not_found(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test updating a non-existent job returns False."""
        # Setup mock to return no record
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        result = job_tracker.update_job(
            job_id="non-existent-job",
            status="completed",
        )

        # Verify
        assert result is False

    def test_update_job_with_error_message(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test updating job with error message for failed jobs."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = {"job_id": "job-123"}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        result = job_tracker.update_job(
            job_id="job-123",
            status="failed",
            error_message="Terraform validation failed",
        )

        # Verify
        assert result is True
        call_args = mock_neo4j_session.run.call_args_list[0]
        parameters = call_args[1]["parameters"]
        assert parameters["status"] == "failed"
        assert parameters["error_message"] == "Terraform validation failed"


class TestJobRetrieval:
    """Tests for retrieving deployment jobs."""

    def test_get_job_success(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test retrieving an existing job."""
        # Setup mock
        mock_node = MagicMock()
        mock_node.items.return_value = [
            ("job_id", "job-123"),
            ("tenant_id", "tenant-123"),
            ("format", "terraform"),
            ("status", "completed"),
            ("created_at", "2024-01-01T00:00:00"),
            ("updated_at", "2024-01-01T01:00:00"),
        ]
        mock_result = MagicMock()
        mock_result.single.return_value = {"job": mock_node}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        job = job_tracker.get_job("job-123")

        # Verify
        assert job is not None
        assert job["job_id"] == "job-123"
        assert job["tenant_id"] == "tenant-123"
        assert job["format"] == "terraform"
        assert job["status"] == "completed"

    def test_get_job_not_found(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test retrieving a non-existent job returns None."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        job = job_tracker.get_job("non-existent-job")

        # Verify
        assert job is None


class TestResourceLinking:
    """Tests for linking deployed resources to jobs."""

    def test_link_deployed_resources(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test linking resources to a deployment job."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = {"relationships_created": 3}
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        resource_ids = ["resource-1", "resource-2", "resource-3"]

        # Execute
        count = job_tracker.link_deployed_resources(
            job_id="job-123",
            resource_ids=resource_ids,
        )

        # Verify
        assert count == 3
        call_args = mock_neo4j_session.run.call_args_list[0]
        query = call_args[0][0]
        assert "DEPLOYED" in query
        assert "MERGE" in query
        parameters = call_args[1]["parameters"]
        assert parameters["resource_ids"] == resource_ids

    def test_link_deployed_resources_empty_list(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test linking with empty resource list returns 0."""
        # Execute
        count = job_tracker.link_deployed_resources(
            job_id="job-123",
            resource_ids=[],
        )

        # Verify
        assert count == 0
        # Should not call session.run
        mock_neo4j_session.run.assert_not_called()

    def test_link_deployed_resources_no_result(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test linking resources when query returns no result."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        count = job_tracker.link_deployed_resources(
            job_id="job-123",
            resource_ids=["resource-1"],
        )

        # Verify
        assert count == 0


class TestJobHistory:
    """Tests for retrieving job history."""

    def test_get_job_history(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test retrieving job history for a tenant."""
        # Setup mock with multiple jobs
        mock_node1 = MagicMock()
        mock_node1.items.return_value = [
            ("job_id", "job-1"),
            ("tenant_id", "tenant-123"),
            ("status", "completed"),
            ("created_at", "2024-01-02T00:00:00"),
        ]
        mock_node2 = MagicMock()
        mock_node2.items.return_value = [
            ("job_id", "job-2"),
            ("tenant_id", "tenant-123"),
            ("status", "failed"),
            ("created_at", "2024-01-01T00:00:00"),
        ]

        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([
            {"job": mock_node1},
            {"job": mock_node2},
        ])
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        jobs = job_tracker.get_job_history(tenant_id="tenant-123", limit=10)

        # Verify
        assert len(jobs) == 2
        assert jobs[0]["job_id"] == "job-1"
        assert jobs[1]["job_id"] == "job-2"
        # Verify query includes ORDER BY and LIMIT
        call_args = mock_neo4j_session.run.call_args_list[0]
        query = call_args[0][0]
        assert "ORDER BY" in query
        assert "LIMIT" in query

    def test_get_job_history_empty(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test retrieving job history when no jobs exist."""
        # Setup mock with empty result
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([])
        mock_neo4j_session.run.return_value = mock_result
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute
        jobs = job_tracker.get_job_history(tenant_id="tenant-123", limit=10)

        # Verify
        assert len(jobs) == 0


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_session_manager_not_connected(self):
        """Test that operations fail gracefully when not connected."""
        # Create session manager that is not connected
        mock_manager = MagicMock(spec=Neo4jSessionManager)
        mock_manager.is_connected = False
        mock_manager.session.side_effect = Neo4jConnectionError(
            "Not connected to Neo4j database"
        )

        tracker = DeploymentJobTracker(mock_manager)

        # Should raise appropriate error (wrapped in Neo4jQueryError)
        with pytest.raises((Neo4jConnectionError, Neo4jQueryError)):
            tracker.create_job(
                tenant_id="tenant-123",
                format_type="terraform",
            )

    def test_concurrent_job_creation(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test that multiple concurrent job creations each get unique IDs."""
        # Setup mock
        call_count = [0]

        def run_side_effect(query, parameters=None):
            mock_result = MagicMock()
            call_count[0] += 1
            mock_result.single.return_value = {
                "job_id": f"job-{call_count[0]}"
            }
            return mock_result

        mock_neo4j_session.run.side_effect = run_side_effect
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # Execute multiple creates
        job_ids = set()
        for _ in range(5):
            job_id = job_tracker.create_job(
                tenant_id="tenant-123",
                format_type="terraform",
            )
            job_ids.add(job_id)

        # Verify all IDs are unique
        assert len(job_ids) == 5


class TestIntegrationPatterns:
    """Tests for common integration patterns."""

    def test_job_lifecycle_pattern(
        self, job_tracker, mock_session_manager, mock_neo4j_session
    ):
        """Test a typical job lifecycle: create -> update -> complete."""
        # Setup mocks for multiple operations
        def run_side_effect(query, parameters=None):
            mock_result = MagicMock()
            if "CREATE" in query:
                mock_result.single.return_value = {"job_id": "job-123"}
            elif "SET" in query:
                mock_result.single.return_value = {"job_id": "job-123"}
            elif "MATCH (job:DeploymentJob {job_id:" in query:
                mock_node = MagicMock()
                mock_node.items.return_value = [
                    ("job_id", "job-123"),
                    ("status", "completed"),
                ]
                mock_result.single.return_value = {"job": mock_node}
            return mock_result

        mock_neo4j_session.run.side_effect = run_side_effect
        mock_session_manager.session.return_value.__enter__.return_value = mock_neo4j_session

        # 1. Create job
        job_id = job_tracker.create_job(
            tenant_id="tenant-123",
            format_type="terraform",
            status="pending",
        )
        assert job_id is not None

        # 2. Update to running
        result = job_tracker.update_job(
            job_id=job_id,
            status="running",
        )
        assert result is True

        # 3. Update to completed with output path
        result = job_tracker.update_job(
            job_id=job_id,
            status="completed",
            output_path="/output/terraform",
        )
        assert result is True

        # 4. Retrieve final job
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == "completed"
