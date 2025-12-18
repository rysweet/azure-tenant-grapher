"""
Response Models for ATG Remote API.

Philosophy:
- Consistent response structure
- Match OpenAPI spec exactly
- Clear typing for API consumers

All response models use Pydantic for automatic serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobResponse(BaseModel):
    """
    Response after submitting a job.

    Used for 202 Accepted responses.
    """

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    websocket_url: Optional[str] = Field(
        None, description="WebSocket URL for progress streaming"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "scan-a1b2c3d4",
                "status": "queued",
                "created_at": "2025-12-09T10:30:00Z",
                "websocket_url": "wss://atg-dev.example.com/ws/progress/scan-a1b2c3d4",
            }
        }


class JobProgress(BaseModel):
    """Job progress information."""

    phase: str = Field(..., description="Current execution phase")
    current_subscription: Optional[int] = Field(
        None, description="Current subscription being processed"
    )
    total_subscriptions: Optional[int] = Field(
        None, description="Total subscriptions to process"
    )
    resources_discovered: Optional[int] = Field(
        None, description="Number of resources discovered"
    )
    percent_complete: Optional[float] = Field(
        None, description="Progress percentage (0-100)", ge=0, le=100
    )


class JobStatusResponse(BaseModel):
    """
    Response for job status queries.

    Used for GET /api/v1/scan/{job_id} and similar endpoints.
    """

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    tenant_id: Optional[str] = Field(None, description="Tenant ID being processed")
    progress: Optional[JobProgress] = Field(None, description="Progress information")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(
        None, description="Job completion timestamp"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "scan-a1b2c3d4",
                "status": "running",
                "tenant_id": "12345678-1234-1234-1234-123456789abc",
                "progress": {
                    "phase": "scanning",
                    "current_subscription": 2,
                    "total_subscriptions": 5,
                    "resources_discovered": 487,
                    "percent_complete": 40.0,
                },
                "created_at": "2025-12-09T10:30:00Z",
                "started_at": "2025-12-09T10:30:05Z",
                "completed_at": None,
                "error": None,
            }
        }


class GeneratedFile(BaseModel):
    """Information about a generated file."""

    file_id: str = Field(..., description="File ID for download endpoint")
    filename: str = Field(..., description="Filename")
    mime_type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes", ge=0)
    download_url: Optional[str] = Field(None, description="Direct download URL")


class JobResultResponse(BaseModel):
    """
    Response for completed job results.

    Used for GET /api/v1/generate-iac/{job_id} and similar endpoints.
    """

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Job status")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")
    format: Optional[str] = Field(None, description="IaC format (for generate-iac)")
    result: Dict[str, Any] = Field(..., description="Operation-specific results")
    files: List[GeneratedFile] = Field(
        default_factory=list, description="Generated files available for download"
    )
    created_at: datetime = Field(..., description="Job creation timestamp")
    completed_at: datetime = Field(..., description="Job completion timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "iac-g7h8i9j0",
                "status": "completed",
                "tenant_id": "12345678-1234-1234-1234-123456789abc",
                "format": "terraform",
                "result": {
                    "files_generated": 127,
                    "resources_included": 845,
                    "output_size_bytes": 524288,
                },
                "files": [
                    {
                        "file_id": "file-001",
                        "filename": "main.tf",
                        "mime_type": "text/plain",
                        "size": 12345,
                        "download_url": "/api/v1/operations/iac-g7h8i9j0/download",
                    }
                ],
                "created_at": "2025-12-09T10:45:00Z",
                "completed_at": "2025-12-09T10:52:30Z",
            }
        }


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class ErrorResponse(BaseModel):
    """
    Standard error response format.

    Used for all error responses (400, 401, 404, 500, etc.).
    """

    error: ErrorDetail = Field(..., description="Error information")

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "INVALID_TENANT_ID",
                    "message": "Invalid tenant_id format. Must be a valid UUID.",
                    "details": {"tenant_id": "invalid-id"},
                }
            }
        }


__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "GeneratedFile",
    "JobProgress",
    "JobResponse",
    "JobResultResponse",
    "JobStatus",
    "JobStatusResponse",
]
