"""
IaC Generation Router for ATG Remote API.

Philosophy:
- Long HTTP support for generation operations
- WebSocket progress streaming
- Wrap existing ATG generation functionality

Endpoints:
    POST /api/v1/generate-iac - Generate IaC templates
    GET /api/v1/generate-iac/{job_id} - Get generation status
    POST /api/v1/generate-spec - Generate tenant spec
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
from ..models.requests import GenerateIacRequest, GenerateSpecRequest
from ..models.responses import JobResponse, JobStatus, JobStatusResponse
from ..services import BackgroundExecutor, JobStorage

router = APIRouter()


@router.post(
    "/generate-iac", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED
)
@require_api_key
async def submit_generate_iac_job(
    request: Request,
    generate_request: GenerateIacRequest,
    background_tasks: BackgroundTasks,
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    config: ATGServerConfig = Depends(get_config),
    executor: BackgroundExecutor = Depends(get_background_executor),
) -> JobResponse:
    """
    Submit an IaC generation operation.

    Requires authentication. Generates Infrastructure-as-Code templates
    (Terraform, ARM, or Bicep) from scanned tenant graph.

    Args:
        request: FastAPI request object (contains auth context)
        generate_request: Generation parameters
        background_tasks: FastAPI background tasks
        connection_manager: Neo4j connection manager
        config: Server configuration
        executor: Background executor service

    Returns:
        JobResponse with job_id and websocket_url

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 400: Invalid parameters
        HTTPException 404: Tenant graph not found
        HTTPException 503: Service unavailable
    """
    # Check Neo4j connectivity
    try:
        is_healthy = await connection_manager.health_check()
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
    job_id = f"iac-{uuid.uuid4().hex[:12]}"

    # Submit IaC generation to background executor (Phase 4)
    await executor.submit_generate_iac(
        background_tasks=background_tasks,
        job_id=job_id,
        tenant_id=generate_request.tenant_id,
        output_format=generate_request.output_format,
        output_path=generate_request.output_path,
        target_tenant_id=generate_request.target_tenant_id,
        auto_import=generate_request.auto_import,
        user_id=getattr(request.state, "user_id", None),
    )

    websocket_url = f"ws://{config.host}:{config.port}/ws/progress/{job_id}"

    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        websocket_url=websocket_url,
    )


@router.get("/generate-iac/{job_id}", response_model=JobStatusResponse)
@require_api_key
async def get_generate_iac_status(
    request: Request,
    job_id: str,
    job_storage: JobStorage = Depends(get_job_storage),
) -> JobStatusResponse:
    """
    Get status of an IaC generation operation.

    Requires authentication.

    Args:
        request: FastAPI request object
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
    return JobStatusResponse(
        job_id=job["id"],
        operation_type=job["operation_type"],
        status=JobStatus(job["status"]),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        error=job.get("error"),
        result=job.get("result"),
    )


@router.post(
    "/generate-spec", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED
)
@require_api_key
async def submit_generate_spec_job(
    request: Request,
    spec_request: GenerateSpecRequest,
    background_tasks: BackgroundTasks,
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    config: ATGServerConfig = Depends(get_config),
    executor: BackgroundExecutor = Depends(get_background_executor),
) -> JobResponse:
    """
    Submit a tenant specification generation operation.

    Requires authentication. Generates markdown specification from tenant graph.

    Args:
        request: FastAPI request object
        spec_request: Specification generation parameters
        connection_manager: Neo4j connection manager
        config: Server configuration

    Returns:
        JobResponse with job_id and websocket_url

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 503: Service unavailable
    """
    # Check Neo4j connectivity
    try:
        is_healthy = await connection_manager.health_check()
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
    job_id = f"spec-{uuid.uuid4().hex[:12]}"

    # Submit spec generation to background executor
    await executor.submit_generate_spec(
        background_tasks=background_tasks,
        job_id=job_id,
        tenant_id=spec_request.tenant_id,
        output_path=spec_request.output_path,
        user_id=getattr(request.state, "user_id", None),
    )

    websocket_url = f"ws://{config.host}:{config.port}/ws/progress/{job_id}"

    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        websocket_url=websocket_url,
    )


__all__ = ["router"]
