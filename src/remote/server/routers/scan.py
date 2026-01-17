"""
Scan Operation Router for ATG Remote API.

Philosophy:
- Long HTTP support (60 min timeout)
- WebSocket progress streaming
- Wrap existing ATG scan functionality

Endpoints:
    POST /api/v1/scan - Start scan operation
    GET /api/v1/scan/{job_id} - Get scan status
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from ...auth.middleware import require_api_key
from ...db.connection_manager import ConnectionManager
from ..config import ATGServerConfig
from ..dependencies import (
    get_background_executor,
    get_config,
    get_connection_manager,
    get_job_storage,
)
from ..models.requests import ScanRequest
from ..models.responses import JobResponse, JobStatus, JobStatusResponse
from ..services import BackgroundExecutor, JobStorage

router = APIRouter()


@router.post("/scan", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
@require_api_key
async def submit_scan_job(
    request: Request,
    scan_request: ScanRequest,
    background_tasks: BackgroundTasks,
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    config: ATGServerConfig = Depends(get_config),
    executor: BackgroundExecutor = Depends(get_background_executor),
) -> JobResponse:
    """
    Submit a tenant scan operation.

    Requires authentication. Returns immediately with job ID and WebSocket URL
    for progress tracking. The scan operation runs in the background.

    Args:
        request: FastAPI request object (contains auth context)
        scan_request: Scan parameters
        background_tasks: FastAPI background tasks
        connection_manager: Neo4j connection manager
        config: Server configuration
        executor: Background executor service

    Returns:
        JobResponse with job_id and websocket_url

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 400: Invalid parameters
        HTTPException 503: Service unavailable (Neo4j down)
    """
    # Check Neo4j connectivity
    try:
        is_healthy = await connection_manager.health_check()  # type: ignore[misc]
        if not is_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Database connection unavailable",
                    }
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Database connection unavailable",
                }
            },
        ) from e

    # Generate job ID
    job_id = f"scan-{uuid.uuid4().hex[:12]}"

    # Submit scan operation to background executor (Phase 4)
    await executor.submit_scan(
        background_tasks=background_tasks,
        job_id=job_id,
        tenant_id=scan_request.tenant_id,
        subscription_id=scan_request.subscription_id,  # type: ignore[attr-defined]
        resource_limit=scan_request.resource_limit,
        user_id=getattr(request.state, "user_id", None),
    )

    websocket_url = f"ws://{config.host}:{config.port}/ws/progress/{job_id}"

    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        websocket_url=websocket_url,
    )


@router.get("/scan/{job_id}", response_model=JobStatusResponse)
@require_api_key
async def get_scan_status(
    request: Request,
    job_id: str,
    job_storage: JobStorage = Depends(get_job_storage),
) -> JobStatusResponse:
    """
    Get status of a scan operation.

    Requires authentication. Returns current job status and progress information.

    Args:
        request: FastAPI request object (contains auth context)
        job_id: Job identifier
        job_storage: Job storage service

    Returns:
        JobStatusResponse with status and progress

    Raises:
        HTTPException 404: Job not found
        HTTPException 401: Invalid API key
    """
    # Get job from storage (Phase 4)
    job = await job_storage.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job {job_id} not found",
                }
            },
        )

    # Map to response model
    return JobStatusResponse(  # type: ignore[misc]
        job_id=job["id"],
        operation_type=job["operation_type"],  # type: ignore[misc]
        status=JobStatus(job["status"]),
        created_at=job["created_at"],
        updated_at=job["updated_at"],  # type: ignore[misc]
        error=job.get("error"),
        result=job.get("result"),  # type: ignore[misc]
    )


__all__ = ["router"]
