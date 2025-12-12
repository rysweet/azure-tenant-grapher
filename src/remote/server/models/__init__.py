"""
Request and Response Models for ATG Remote API.

Philosophy:
- Pydantic models for request/response validation
- Clear field descriptions and examples
- Strict validation matching OpenAPI spec

Public API:
    Request models: ScanRequest, GenerateIacRequest, GenerateSpecRequest
    Response models: JobResponse, JobStatusResponse, JobResultResponse
"""

from .events import (
    CompletionEvent,
    ErrorEvent,
    ProgressEvent,
)
from .requests import (
    AgentModeRequest,
    CreateTenantRequest,
    GenerateIacRequest,
    GenerateSpecRequest,
    ScanRequest,
    ThreatModelRequest,
    VisualizeRequest,
)
from .responses import (
    ErrorResponse,
    JobResponse,
    JobResultResponse,
    JobStatusResponse,
)

__all__ = [
    "AgentModeRequest",
    "CompletionEvent",
    "CreateTenantRequest",
    "ErrorEvent",
    "ErrorResponse",
    "GenerateIacRequest",
    "GenerateSpecRequest",
    # Responses
    "JobResponse",
    "JobResultResponse",
    "JobStatusResponse",
    # Events
    "ProgressEvent",
    # Requests
    "ScanRequest",
    "ThreatModelRequest",
    "VisualizeRequest",
]
