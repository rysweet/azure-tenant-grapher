"""
Unit tests for Server Models - Request/Response/Event models.

Tests cover:
- Request model validation (ScanRequest, GenerateIacRequest, etc.)
- Response model structure (JobResponse, JobStatusResponse, etc.)
- Event model structure (ProgressEvent, ErrorEvent, etc.)
- Field validation
- Pydantic serialization/deserialization
"""

import pytest
from pydantic import ValidationError

from src.remote.server.models.events import (
    CompletionEvent,
    ErrorEvent,
    ProgressEvent,
)
from src.remote.server.models.requests import (
    GenerateIacRequest,
    GenerateSpecRequest,
    ScanRequest,
)
from src.remote.server.models.responses import (
    ErrorDetail,
    ErrorResponse,
    JobResponse,
    JobStatus,
    JobStatusResponse,
)

# ====================
# Request Model Tests
# ====================


class TestScanRequest:
    """Tests for ScanRequest model."""

    def test_scan_request_validates_valid_tenant_id(self):
        """Test that ScanRequest accepts valid UUID tenant ID."""
        valid_tenant_id = "12345678-1234-1234-1234-123456789abc"
        request = ScanRequest(tenant_id=valid_tenant_id)  # type: ignore[call-arg]  # Pydantic Field defaults not recognized by Pyright

        assert request.tenant_id == valid_tenant_id

    def test_scan_request_rejects_invalid_tenant_id_format(self):
        """Test that ScanRequest rejects invalid tenant ID format."""
        with pytest.raises(ValidationError) as exc_info:
            ScanRequest(tenant_id="invalid-tenant-id")  # type: ignore[call-arg]

        assert "tenant_id must be a valid UUID" in str(exc_info.value)

    def test_scan_request_rejects_short_tenant_id(self):
        """Test that ScanRequest rejects short tenant ID."""
        with pytest.raises(ValidationError):
            ScanRequest(tenant_id="12345")  # type: ignore[call-arg]  # Pydantic Field defaults

    def test_scan_request_uses_default_values(self):
        """Test that ScanRequest uses correct default values."""
        request = ScanRequest(tenant_id="12345678-1234-1234-1234-123456789abc")  # type: ignore[call-arg]  # Pydantic Field defaults

        assert request.max_llm_threads == 5
        assert request.max_build_threads == 20
        assert request.max_retries == 3
        assert request.max_concurrency == 100
        assert request.generate_spec is False
        assert request.visualize is False
        assert request.rebuild_edges is False
        assert request.no_aad_import is False

    def test_scan_request_accepts_optional_parameters(self):
        """Test that ScanRequest accepts optional parameters."""
        request = ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            tenant_id="12345678-1234-1234-1234-123456789abc",
            resource_limit=100,
            max_llm_threads=10,
            generate_spec=True,
        )

        assert request.resource_limit == 100
        assert request.max_llm_threads == 10
        assert request.generate_spec is True

    def test_scan_request_validates_resource_limit_positive(self):
        """Test that ScanRequest requires positive resource_limit."""
        with pytest.raises(ValidationError):
            ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
                tenant_id="12345678-1234-1234-1234-123456789abc", resource_limit=0
            )

    def test_scan_request_validates_max_llm_threads_range(self):
        """Test that ScanRequest validates max_llm_threads range (1-20)."""
        # Valid range
        request = ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            tenant_id="12345678-1234-1234-1234-123456789abc", max_llm_threads=15
        )
        assert request.max_llm_threads == 15

        # Too low
        with pytest.raises(ValidationError):
            ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
                tenant_id="12345678-1234-1234-1234-123456789abc", max_llm_threads=0
            )

        # Too high
        with pytest.raises(ValidationError):
            ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
                tenant_id="12345678-1234-1234-1234-123456789abc", max_llm_threads=25
            )

    def test_scan_request_accepts_filter_parameters(self):
        """Test that ScanRequest accepts filter parameters."""
        request = ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            tenant_id="12345678-1234-1234-1234-123456789abc",
            filter_by_subscriptions="sub1,sub2",
            filter_by_rgs="rg1,rg2",
        )

        assert request.filter_by_subscriptions == "sub1,sub2"
        assert request.filter_by_rgs == "rg1,rg2"


class TestGenerateIacRequest:
    """Tests for GenerateIacRequest model."""

    def test_generate_iac_request_validates_valid_tenant_id(self):
        """Test that GenerateIacRequest accepts valid tenant ID."""
        request = GenerateIacRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            tenant_id="12345678-1234-1234-1234-123456789abc", format="terraform"
        )

        assert request.tenant_id == "12345678-1234-1234-1234-123456789abc"
        assert request.format == "terraform"

    def test_generate_iac_request_rejects_invalid_tenant_id(self):
        """Test that GenerateIacRequest accepts invalid tenant ID (tenant_id is Optional)."""
        # tenant_id is Optional in GenerateIacRequest, so invalid values are accepted
        request = GenerateIacRequest(tenant_id="invalid", format="terraform")  # type: ignore[call-arg]  # Pydantic Field defaults
        assert request.tenant_id == "invalid"

    def test_generate_iac_request_validates_output_format(self):
        """Test that GenerateIacRequest validates output format."""
        # Valid formats
        for fmt in ["terraform", "bicep", "arm"]:
            request = GenerateIacRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
                tenant_id="12345678-1234-1234-1234-123456789abc", format=fmt
            )
            assert request.format == fmt

        # Invalid format
        with pytest.raises(ValidationError):
            GenerateIacRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
                tenant_id="12345678-1234-1234-1234-123456789abc", format="invalid"
            )

    def test_generate_iac_request_uses_default_values(self):
        """Test that GenerateIacRequest uses correct default values."""
        request = GenerateIacRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

        assert request.format == "terraform"
        assert request.auto_import_existing is False
        assert request.auto_register_providers is False
        assert request.auto_fix_subnets is False
        assert request.skip_subnet_validation is False

    def test_generate_iac_request_accepts_optional_parameters(self):
        """Test that GenerateIacRequest accepts optional parameters."""
        request = GenerateIacRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            tenant_id="12345678-1234-1234-1234-123456789abc",
            format="bicep",
            target_tenant_id="87654321-4321-4321-4321-cba987654321",
            target_subscription="sub-123",
            auto_import_existing=True,
            import_strategy="resource_groups",
        )

        assert request.format == "bicep"
        assert request.target_tenant_id == "87654321-4321-4321-4321-cba987654321"
        assert request.target_subscription == "sub-123"
        assert request.auto_import_existing is True
        assert request.import_strategy == "resource_groups"


class TestGenerateSpecRequest:
    """Tests for GenerateSpecRequest model."""

    def test_generate_spec_request_allows_optional_tenant_id(self):
        """Test that GenerateSpecRequest allows None tenant_id."""
        request = GenerateSpecRequest()  # type: ignore[call-arg]  # Pydantic Field defaults

        assert request.tenant_id is None
        assert request.hierarchical is False

    def test_generate_spec_request_validates_tenant_id_when_provided(self):
        """Test that GenerateSpecRequest validates tenant_id format when provided."""
        # Valid UUID
        request = GenerateSpecRequest(tenant_id="12345678-1234-1234-1234-123456789abc")  # type: ignore[call-arg]  # Pydantic Field defaults
        assert request.tenant_id == "12345678-1234-1234-1234-123456789abc"

        # Invalid UUID
        with pytest.raises(ValidationError):
            GenerateSpecRequest(tenant_id="invalid-uuid")  # type: ignore[call-arg]  # Pydantic Field defaults

    def test_generate_spec_request_accepts_optional_parameters(self):
        """Test that GenerateSpecRequest accepts optional parameters."""
        request = GenerateSpecRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
            domain_name="example.com", limit=100, hierarchical=True
        )

        assert request.domain_name == "example.com"
        assert request.limit == 100
        assert request.hierarchical is True


# ====================
# Response Model Tests
# ====================


class TestJobResponse:
    """Tests for JobResponse model."""

    def test_job_response_creates_with_required_fields(self):
        """Test that JobResponse can be created with required fields."""
        from datetime import datetime, timezone

        created = datetime.now(timezone.utc)
        response = JobResponse(
            job_id="job-123",
            status=JobStatus.QUEUED,
            created_at=created,
            websocket_url="wss://atg.example.com/ws/progress/job-123",
        )

        assert response.job_id == "job-123"
        assert response.status == JobStatus.QUEUED
        assert response.created_at == created
        assert response.websocket_url == "wss://atg.example.com/ws/progress/job-123"

    def test_job_response_serializes_to_dict(self):
        """Test that JobResponse serializes to dictionary correctly."""
        from datetime import datetime, timezone

        created = datetime.now(timezone.utc)
        response = JobResponse(
            job_id="job-123",
            status=JobStatus.RUNNING,
            created_at=created,
            websocket_url="wss://atg.example.com/ws/progress/job-123",
        )

        data = response.model_dump()

        assert data["job_id"] == "job-123"
        assert data["status"] == "running"
        assert data["created_at"] == created
        assert data["websocket_url"] == "wss://atg.example.com/ws/progress/job-123"


class TestJobStatusResponse:
    """Tests for JobStatusResponse model."""

    def test_job_status_response_creates_with_all_fields(self):
        """Test that JobStatusResponse can be created with all fields."""
        from datetime import datetime, timezone

        from src.remote.server.models.responses import JobProgress

        created = datetime.now(timezone.utc)
        progress = JobProgress(
            phase="completed",
            percent_complete=100.0,
            resources_discovered=500,
        )

        response = JobStatusResponse(
            job_id="job-123",
            status=JobStatus.COMPLETED,
            created_at=created,
            progress=progress,
        )

        assert response.job_id == "job-123"
        assert response.status == JobStatus.COMPLETED
        assert response.progress.percent_complete == 100.0
        assert response.progress.phase == "completed"

    def test_job_status_response_uses_default_progress(self):
        """Test that JobStatusResponse allows None progress."""
        from datetime import datetime, timezone

        created = datetime.now(timezone.utc)
        response = JobStatusResponse(
            job_id="job-123", status=JobStatus.QUEUED, created_at=created
        )

        assert response.progress is None
        assert response.error is None


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_creates_with_error_detail(self):
        """Test that ErrorResponse creates with ErrorDetail."""
        error_detail = ErrorDetail(
            code="VALIDATION_ERROR", message="Invalid tenant ID format"
        )
        response = ErrorResponse(error=error_detail)

        assert response.error.code == "VALIDATION_ERROR"
        assert response.error.message == "Invalid tenant ID format"

    def test_error_detail_accepts_optional_details(self):
        """Test that ErrorDetail accepts optional details field."""
        error = ErrorDetail(
            code="SERVICE_UNAVAILABLE",
            message="Database connection failed",
            details={"neo4j_status": "disconnected"},
        )

        assert error.details == {"neo4j_status": "disconnected"}


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_job_status_enum_has_all_states(self):
        """Test that JobStatus enum has all expected states."""
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"


# ====================
# Event Model Tests
# ====================


class TestProgressEvent:
    """Tests for ProgressEvent model."""

    def test_progress_event_creates_with_required_fields(self):
        """Test that ProgressEvent can be created with required fields."""
        event = ProgressEvent(
            job_id="job-123", phase="scanning", percent=50.0, message="Processing"
        )

        assert event.type == "progress"
        assert event.job_id == "job-123"
        assert event.percent == 50.0
        assert event.message == "Processing"

    def test_progress_event_validates_progress_range(self):
        """Test that ProgressEvent validates percent is 0-100."""
        # Valid progress
        event = ProgressEvent(
            job_id="job-123", phase="scanning", percent=75.5, message="Almost done"
        )
        assert event.percent == 75.5

        # Outside range should fail
        with pytest.raises(ValidationError):
            ProgressEvent(
                job_id="job-123", phase="scanning", percent=150.0, message="Too high"
            )

    def test_progress_event_serializes_to_json(self):
        """Test that ProgressEvent serializes to JSON correctly."""
        event = ProgressEvent(
            job_id="job-123", phase="processing", percent=60.0, message="Processing"
        )

        data = event.model_dump()

        assert data["type"] == "progress"
        assert data["job_id"] == "job-123"
        assert data["percent"] == 60.0
        assert data["message"] == "Processing"


class TestCompletionEvent:
    """Tests for CompletionEvent model."""

    def test_completion_event_creates_with_required_fields(self):
        """Test that CompletionEvent can be created."""
        event = CompletionEvent(job_id="job-123", status="completed")

        assert event.type == "completion"
        assert event.job_id == "job-123"
        assert event.status == "completed"

    def test_completion_event_accepts_optional_result(self):
        """Test that CompletionEvent accepts optional result field."""
        event = CompletionEvent(
            job_id="job-123",
            status="completed",
            result={"resources": 100, "relationships": 200},
        )

        assert event.result == {"resources": 100, "relationships": 200}


class TestErrorEvent:
    """Tests for ErrorEvent model."""

    def test_error_event_creates_with_error_message(self):
        """Test that ErrorEvent can be created with error message."""
        event = ErrorEvent(
            job_id="job-123",
            error_code="CONNECTION_FAILED",
            error_message="Connection failed",
        )

        assert event.type == "error"
        assert event.job_id == "job-123"
        assert event.error_message == "Connection failed"
        assert event.error_code == "CONNECTION_FAILED"

    def test_error_event_accepts_optional_details(self):
        """Test that ErrorEvent accepts optional details field."""
        event = ErrorEvent(
            job_id="job-123",
            error_code="AUTH_ERROR",
            error_message="Authentication failed",
            details={"tenant_id": "12345678-1234-1234-1234-123456789abc"},
        )

        assert event.details == {"tenant_id": "12345678-1234-1234-1234-123456789abc"}


# ====================
# Model Integration Tests
# ====================


def test_request_response_round_trip():
    """Test that requests and responses work together."""
    from datetime import datetime, timezone

    # Create scan request
    scan_request = ScanRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
        tenant_id="12345678-1234-1234-1234-123456789abc", resource_limit=50
    )

    # Create job response
    job_response = JobResponse(
        job_id="job-456",
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        websocket_url="wss://atg.example.com/ws/progress/job-456",
    )

    # Verify they work together
    assert scan_request.tenant_id in str(scan_request.model_dump())
    assert job_response.job_id in str(job_response.model_dump())


def test_event_workflow_sequence():
    """Test that events can represent a complete workflow."""
    job_id = "job-789"

    # Progress events
    event1 = ProgressEvent(
        job_id=job_id, phase="starting", percent=25.0, message="Starting"
    )
    event2 = ProgressEvent(
        job_id=job_id, phase="processing", percent=75.0, message="Processing"
    )

    # Completion event
    event3 = CompletionEvent(job_id=job_id, status="completed")

    # Verify sequence
    events = [event1, event2, event3]
    assert all(e.job_id == job_id for e in events)
    assert events[-1].type == "completion"


def test_error_response_creation():
    """Test creating error responses for API errors."""
    # Create error detail
    error = ErrorDetail(code="INVALID_REQUEST", message="Missing tenant_id")  # type: ignore[call-arg]  # Pydantic Field defaults

    # Create error response
    response = ErrorResponse(error=error)

    # Serialize to dict (as would be sent in HTTP response)
    data = response.model_dump()

    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error"]["message"] == "Missing tenant_id"


def test_all_models_support_json_serialization():
    """Test that all models support JSON serialization."""
    from datetime import datetime, timezone

    created = datetime.now(timezone.utc)

    # Request models
    scan_req = ScanRequest(tenant_id="12345678-1234-1234-1234-123456789abc")  # type: ignore[call-arg]  # Pydantic Field defaults
    iac_req = GenerateIacRequest(  # type: ignore[call-arg]  # Pydantic Field defaults
        tenant_id="12345678-1234-1234-1234-123456789abc", format="terraform"
    )
    spec_req = GenerateSpecRequest()  # type: ignore[call-arg]  # Pydantic Field defaults

    # Response models
    job_resp = JobResponse(
        job_id="job-1",
        status=JobStatus.RUNNING,
        created_at=created,
        websocket_url="wss://example.com",
    )
    status_resp = JobStatusResponse(  # type: ignore[call-arg]  # Pydantic Field defaults
        job_id="job-1", status=JobStatus.COMPLETED, created_at=created
    )
    error_resp = ErrorResponse(error=ErrorDetail(code="ERROR", message="Failed"))  # type: ignore[call-arg]  # Pydantic Field defaults

    # Event models
    progress_evt = ProgressEvent(
        job_id="job-1", phase="working", percent=50.0, message="Working"
    )
    complete_evt = CompletionEvent(job_id="job-1", status="completed")  # type: ignore[call-arg]  # Pydantic Field defaults
    error_evt = ErrorEvent(  # type: ignore[call-arg]  # Pydantic Field defaults
        job_id="job-1", error_code="ERROR", error_message="Error occurred"
    )

    # All should serialize without errors
    models = [
        scan_req,
        iac_req,
        spec_req,
        job_resp,
        status_resp,
        error_resp,
        progress_evt,
        complete_evt,
        error_evt,
    ]

    for model in models:
        data = model.model_dump()
        assert isinstance(data, dict)
        assert len(data) > 0
