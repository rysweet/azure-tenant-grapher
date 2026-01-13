"""
Operations Management Router for ATG Remote API.

Philosophy:
- Cross-cutting operation management
- Job listing, cancellation, results
- File downloads

Endpoints:
    GET /api/v1/operations - List all operations
    DELETE /api/v1/operations/{job_id} - Cancel operation
    GET /api/v1/operations/{job_id}/download - Download results
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from ...auth.middleware import require_api_key
from ..dependencies import get_file_generator, get_job_storage
from ..models.responses import JobStatus, JobStatusResponse
from ..services import FileGenerator, JobStorage

router = APIRouter()


@router.get("/operations", response_model=List[JobStatusResponse])
@require_api_key
async def list_operations(
    request: Request,
    status_filter: Optional[str] = None,
    operation_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    job_storage: JobStorage = Depends(get_job_storage),
) -> List[JobStatusResponse]:
    """
    List all operations for the current user.

    Requires authentication. Returns list of operations with pagination.

    Args:
        request: FastAPI request object
        status_filter: Filter by status (queued, running, completed, failed, cancelled)
        operation_type: Filter by type (scan, generate-iac, etc.)
        limit: Maximum results to return (default: 50)
        offset: Pagination offset (default: 0)
        job_storage: Job storage service

    Returns:
        List of JobStatusResponse

    Raises:
        HTTPException 401: Invalid API key
    """
    # Get user ID from auth context
    user_id = getattr(request.state, "user_id", None)

    # List jobs from storage (Phase 4)
    jobs = await job_storage.list_jobs(
        status_filter=status_filter,
        operation_type=operation_type,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    # Map to response models
    return [
        JobStatusResponse(
            job_id=job["id"],
            operation_type=job["operation_type"],
            status=JobStatus(job["status"]),
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            error=job.get("error"),
            result=job.get("result"),
        )
        for job in jobs
    ]


@router.delete("/operations/{job_id}")
@require_api_key
async def cancel_operation(
    request: Request,
    job_id: str,
    job_storage: JobStorage = Depends(get_job_storage),
) -> dict:
    """
    Cancel a running operation.

    Requires authentication. Cancels the operation if it's still running.

    Args:
        request: FastAPI request object
        job_id: Job identifier
        job_storage: Job storage service

    Returns:
        Dictionary with job_id and status

    Raises:
        HTTPException 404: Job not found
        HTTPException 409: Job already completed
        HTTPException 401: Invalid API key
    """
    # Get job (Phase 4)
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

    # Check if cancellable
    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "JOB_NOT_CANCELLABLE",
                    "message": f"Job {job_id} cannot be cancelled (status: {job['status']})",
                }
            },
        )

    # Update to cancelled
    # Note: This doesn't actually kill the background task,
    # but marks it as cancelled. The task should check this status.
    await job_storage.update_status(job_id, "cancelled")

    return {
        "job_id": job_id,
        "status": "cancelled",
    }


@router.get("/operations/{job_id}/download")
@require_api_key
async def download_operation_results(
    request: Request,
    job_id: str,
    job_storage: JobStorage = Depends(get_job_storage),
    file_generator: FileGenerator = Depends(get_file_generator),
):
    """
    Download operation results as ZIP file.

    Requires authentication. Returns generated files as a ZIP archive.

    Args:
        request: FastAPI request object
        job_id: Job identifier
        job_storage: Job storage service
        file_generator: File generator service

    Returns:
        FileResponse with ZIP archive

    Raises:
        HTTPException 404: Results not found
        HTTPException 410: Results expired/deleted
        HTTPException 401: Invalid API key
    """
    # Verify job exists (Phase 4)
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

    # Check if job has completed
    if job["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "JOB_NOT_COMPLETED",
                    "message": f"Job {job_id} has not completed (status: {job['status']})",
                }
            },
        )

    # Try to create/get ZIP archive
    try:
        zip_path = file_generator.create_zip_archive(job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "RESULTS_NOT_FOUND",
                    "message": str(e),
                }
            },
        ) from e

    # Return ZIP file
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{job_id}.zip",
    )


__all__ = ["router"]
