"""
WebSocket Protocol for ATG Remote Service.

Philosophy:
- Simple JSON message protocol
- Fast serialization/deserialization
- Clear message types

Message Types:
    progress: Progress updates during execution
    error: Error notifications
    completion: Job completion notifications
    log: Log message streaming
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProtocolError(Exception):
    """Raised when protocol validation fails."""

    pass


class BaseMessage(BaseModel):
    """Base class for all WebSocket messages."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="Message type")
    job_id: str = Field(..., description="Job identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message timestamp",
    )

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, v: str) -> str:
        """Validate job_id format."""
        if not v or len(v) < 3:
            raise ProtocolError("job_id must be at least 3 characters")
        if "/" in v or " " in v:
            raise ProtocolError("job_id cannot contain spaces or slashes")
        return v

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return self.model_dump_json(by_alias=True)

    def validate_size(self) -> None:
        """Validate message size."""
        json_str = self.to_json()
        if len(json_str) > 1024 * 1024:  # 1MB limit
            raise ProtocolError("Message size exceeds 1MB limit")


class ProgressMessage(BaseMessage):
    """
    Progress update message.

    Sent periodically during job execution.
    """

    type: Literal["progress"] = "progress"
    progress: float = Field(
        ..., description="Progress percentage (0-100)", ge=0, le=100
    )
    message: str = Field(..., description="Human-readable progress message")


class ErrorMessage(BaseMessage):
    """
    Error message.

    Sent when a job encounters an error.
    """

    type: Literal["error"] = "error"
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class CompletionMessage(BaseMessage):
    """
    Job completion message.

    Sent when a job completes (successfully or with failure).
    """

    type: Literal["completion"] = "completion"
    status: str = Field(..., description="Final status (completed/failed)")
    result: Optional[Dict[str, Any]] = Field(None, description="Result summary")


class LogMessage(BaseMessage):
    """
    Log message.

    Sent to stream log messages to the client.
    """

    type: Literal["log"] = "log"
    level: str = Field(..., description="Log level (INFO, WARNING, ERROR)")
    message: str = Field(..., description="Log message")


# Type alias for all message types
Message = Union[ProgressMessage, ErrorMessage, CompletionMessage, LogMessage]


def from_json(json_str: str) -> Message:
    """
    Deserialize message from JSON string.

    Args:
        json_str: JSON string

    Returns:
        Message instance

    Raises:
        ProtocolError: If deserialization fails
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON: {e}") from e

    msg_type = data.get("type")

    if msg_type == "progress":
        return ProgressMessage(**data)
    elif msg_type == "error":
        return ErrorMessage(**data)
    elif msg_type == "completion":
        return CompletionMessage(**data)
    elif msg_type == "log":
        return LogMessage(**data)
    else:
        raise ProtocolError(f"Unknown message type: {msg_type}")


__all__ = [
    "BaseMessage",
    "CompletionMessage",
    "ErrorMessage",
    "LogMessage",
    "Message",
    "ProgressMessage",
    "ProtocolError",
    "from_json",
]
