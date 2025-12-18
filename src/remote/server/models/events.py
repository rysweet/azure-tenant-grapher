"""
WebSocket Event Models for ATG Remote API.

Philosophy:
- Clear event types for WebSocket communication
- Consistent JSON serialization
- Fast serialization/deserialization

Events are sent from server to client over WebSocket connections.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base class for all WebSocket events."""

    type: str = Field(..., description="Event type")
    job_id: str = Field(..., description="Job identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp",
    )


class ProgressEvent(BaseEvent):
    """
    Progress update event.

    Sent periodically during job execution to report progress.
    """

    type: Literal["progress"] = "progress"
    phase: str = Field(..., description="Current execution phase")
    message: str = Field(..., description="Human-readable progress message")
    percent: float = Field(..., description="Progress percentage (0-100)", ge=0, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "type": "progress",
                "job_id": "scan-a1b2c3d4",
                "phase": "scanning",
                "message": "Scanning subscription 2/5: Development",
                "percent": 40.0,
                "timestamp": "2025-12-09T10:36:42Z",
            }
        }


class ErrorEvent(BaseEvent):
    """
    Error event.

    Sent when a job encounters an error.
    """

    type: Literal["error"] = "error"
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "error",
                "job_id": "scan-a1b2c3d4",
                "error_code": "AZURE_AUTH_FAILED",
                "error_message": "Failed to authenticate with Azure",
                "details": {"tenant_id": "12345678-..."},
                "timestamp": "2025-12-09T10:35:30Z",
            }
        }


class CompletionEvent(BaseEvent):
    """
    Job completion event.

    Sent when a job completes successfully or fails.
    """

    type: Literal["completion"] = "completion"
    status: str = Field(..., description="Final job status (completed/failed)")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result summary")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "completion",
                "job_id": "scan-a1b2c3d4",
                "status": "completed",
                "result": {
                    "resources_discovered": 1247,
                    "relationships_created": 3892,
                    "duration_seconds": 735,
                },
                "timestamp": "2025-12-09T10:42:15Z",
            }
        }


class LogEvent(BaseEvent):
    """
    Log message event.

    Sent to stream log messages to the client.
    """

    type: Literal["log"] = "log"
    level: str = Field(..., description="Log level (INFO, WARNING, ERROR)")
    message: str = Field(..., description="Log message")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "log",
                "job_id": "scan-a1b2c3d4",
                "level": "INFO",
                "message": "Discovered 125 resources in subscription",
                "timestamp": "2025-12-09T10:37:08Z",
            }
        }


__all__ = [
    "BaseEvent",
    "CompletionEvent",
    "ErrorEvent",
    "LogEvent",
    "ProgressEvent",
]
