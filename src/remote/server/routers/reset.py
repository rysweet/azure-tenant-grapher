"""Reset Operations Router for ATG Remote API.

Philosophy:
- Safety-first: Multiple confirmation layers
- Clear error messages for safety violations
- Comprehensive audit logging

Endpoints:
    GET /api/v1/reset/tenant/preview - Preview tenant reset
    POST /api/v1/reset/tenant - Execute tenant reset
    GET /api/v1/reset/subscription/{subscription_id}/preview - Preview subscription reset
    POST /api/v1/reset/subscription/{subscription_id} - Execute subscription reset
    GET /api/v1/reset/resource-group/{subscription_id}/{rg_name}/preview - Preview RG reset
    POST /api/v1/reset/resource-group/{subscription_id}/{rg_name} - Execute RG reset
    GET /api/v1/reset/resource/preview - Preview resource reset
    POST /api/v1/reset/resource - Execute resource reset

Issue #627: Tenant Reset Feature with Granular Scopes
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...auth.middleware import require_api_key
from ..logging.audit import log_audit_event
from ....services.tenant_reset_service import (
    InvalidConfirmationTokenError,
    TenantResetService,
)

router = APIRouter()


# ========================================================================
# Request/Response Models
# ========================================================================


class ResetExecutionRequest(BaseModel):
    """Request body for executing a reset operation."""

    confirmation_token: str = Field(
        ...,
        description='Confirmation token - must be exactly "DELETE" (case-sensitive)',
        examples=["DELETE"],
    )
    dry_run: bool = Field(False, description="If true, preview only (no actual deletion)")


class ResetPreviewResponse(BaseModel):
    """Response for reset preview endpoints."""

    scope: Dict
    azure_resources_count: int
    entra_users_count: int = 0
    entra_groups_count: int = 0
    entra_service_principals_count: int = 0
    graph_nodes_count: int = 0
    estimated_duration_seconds: int = 0
    warnings: list[str] = []


class ResetResultResponse(BaseModel):
    """Response for reset execution endpoints."""

    scope: Dict
    status: str
    success: bool
    deleted_azure_resources: int = 0
    deleted_entra_users: int = 0
    deleted_entra_groups: int = 0
    deleted_entra_service_principals: int = 0
    deleted_graph_nodes: int = 0
    deleted_graph_relationships: int = 0
    errors: list[str] = []
    duration_seconds: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None


# ========================================================================
# Dependency Injection
# ========================================================================


def get_tenant_reset_service(request: Request) -> TenantResetService:
    """Get tenant reset service from request state.

    Returns:
        TenantResetService instance
    """
    # TODO: Inject proper dependencies (Azure credential, Graph client, Neo4j driver)
    # For now, use default initialization
    return TenantResetService()


# ========================================================================
# Tenant-Level Reset Endpoints
# ========================================================================


@router.get("/reset/tenant/preview", response_model=ResetPreviewResponse)
@require_api_key
async def preview_tenant_reset(
    request: Request,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetPreviewResponse:
    """Preview tenant-level reset without executing.

    Shows counts of resources that would be deleted across the entire tenant.

    Requires authentication.

    Returns:
        ResetPreviewResponse with counts and warnings

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 500: Internal server error
    """
    try:
        # Audit log: Preview request
        await log_audit_event(
            request=request,
            action="reset_tenant_preview",
            resource="tenant",
            details={},
        )

        preview = await service.preview_tenant_reset()
        return ResetPreviewResponse(**preview.to_dict())

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview tenant reset: {str(e)}",
        )


@router.post("/reset/tenant", response_model=ResetResultResponse)
@require_api_key
async def execute_tenant_reset(
    request: Request,
    body: ResetExecutionRequest,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetResultResponse:
    """Execute tenant-level reset after confirmation.

    CRITICAL: This DELETES ALL Azure resources and Entra ID objects (except ATG SP).

    Requires:
    - Authentication
    - confirmation_token must be exactly "DELETE"

    Args:
        request: FastAPI request
        body: Reset execution request with confirmation token
        service: Tenant reset service

    Returns:
        ResetResultResponse with deletion details

    Raises:
        HTTPException 400: Invalid confirmation token
        HTTPException 401: Invalid API key
        HTTPException 500: Internal server error
    """
    try:
        # Audit log: Execution attempt
        await log_audit_event(
            request=request,
            action="reset_tenant_execute",
            resource="tenant",
            details={
                "confirmation_token": body.confirmation_token,
                "dry_run": body.dry_run,
            },
        )

        # Override service dry_run if requested
        if body.dry_run:
            service.dry_run = True

        result = await service.execute_tenant_reset(confirmation_token=body.confirmation_token)

        # Audit log: Execution result
        await log_audit_event(
            request=request,
            action="reset_tenant_completed",
            resource="tenant",
            details={
                "status": result.status.value,
                "deleted_resources": result.deleted_azure_resources,
                "deleted_entra_objects": (
                    result.deleted_entra_users
                    + result.deleted_entra_groups
                    + result.deleted_entra_service_principals
                ),
                "duration_seconds": result.duration_seconds,
            },
        )

        return ResetResultResponse(**result.to_dict())

    except InvalidConfirmationTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute tenant reset: {str(e)}",
        )


# ========================================================================
# Subscription-Level Reset Endpoints
# ========================================================================


@router.get(
    "/reset/subscription/{subscription_id}/preview", response_model=ResetPreviewResponse
)
@require_api_key
async def preview_subscription_reset(
    request: Request,
    subscription_id: str,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetPreviewResponse:
    """Preview subscription-level reset without executing.

    Args:
        request: FastAPI request
        subscription_id: Azure subscription ID
        service: Tenant reset service

    Returns:
        ResetPreviewResponse with counts and warnings
    """
    try:
        await log_audit_event(
            request=request,
            action="reset_subscription_preview",
            resource=f"subscription:{subscription_id}",
            details={"subscription_id": subscription_id},
        )

        preview = await service.preview_subscription_reset(subscription_id=subscription_id)
        return ResetPreviewResponse(**preview.to_dict())

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview subscription reset: {str(e)}",
        )


@router.post("/reset/subscription/{subscription_id}", response_model=ResetResultResponse)
@require_api_key
async def execute_subscription_reset(
    request: Request,
    subscription_id: str,
    body: ResetExecutionRequest,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetResultResponse:
    """Execute subscription-level reset after confirmation.

    Args:
        request: FastAPI request
        subscription_id: Azure subscription ID
        body: Reset execution request
        service: Tenant reset service

    Returns:
        ResetResultResponse with deletion details
    """
    try:
        await log_audit_event(
            request=request,
            action="reset_subscription_execute",
            resource=f"subscription:{subscription_id}",
            details={
                "subscription_id": subscription_id,
                "confirmation_token": body.confirmation_token,
                "dry_run": body.dry_run,
            },
        )

        if body.dry_run:
            service.dry_run = True

        result = await service.execute_subscription_reset(
            subscription_id=subscription_id, confirmation_token=body.confirmation_token
        )

        await log_audit_event(
            request=request,
            action="reset_subscription_completed",
            resource=f"subscription:{subscription_id}",
            details={
                "status": result.status.value,
                "deleted_resources": result.deleted_azure_resources,
                "duration_seconds": result.duration_seconds,
            },
        )

        return ResetResultResponse(**result.to_dict())

    except InvalidConfirmationTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute subscription reset: {str(e)}",
        )


# ========================================================================
# Resource Group Reset Endpoints
# ========================================================================


@router.get(
    "/reset/resource-group/{subscription_id}/{rg_name}/preview",
    response_model=ResetPreviewResponse,
)
@require_api_key
async def preview_resource_group_reset(
    request: Request,
    subscription_id: str,
    rg_name: str,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetPreviewResponse:
    """Preview resource group reset without executing.

    Args:
        request: FastAPI request
        subscription_id: Azure subscription ID
        rg_name: Resource group name
        service: Tenant reset service

    Returns:
        ResetPreviewResponse with counts and warnings
    """
    try:
        await log_audit_event(
            request=request,
            action="reset_resource_group_preview",
            resource=f"rg:{subscription_id}/{rg_name}",
            details={"subscription_id": subscription_id, "resource_group_name": rg_name},
        )

        preview = await service.preview_resource_group_reset(
            subscription_id=subscription_id, rg_name=rg_name
        )
        return ResetPreviewResponse(**preview.to_dict())

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview resource group reset: {str(e)}",
        )


@router.post(
    "/reset/resource-group/{subscription_id}/{rg_name}", response_model=ResetResultResponse
)
@require_api_key
async def execute_resource_group_reset(
    request: Request,
    subscription_id: str,
    rg_name: str,
    body: ResetExecutionRequest,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetResultResponse:
    """Execute resource group reset after confirmation.

    Args:
        request: FastAPI request
        subscription_id: Azure subscription ID
        rg_name: Resource group name
        body: Reset execution request
        service: Tenant reset service

    Returns:
        ResetResultResponse with deletion details
    """
    try:
        await log_audit_event(
            request=request,
            action="reset_resource_group_execute",
            resource=f"rg:{subscription_id}/{rg_name}",
            details={
                "subscription_id": subscription_id,
                "resource_group_name": rg_name,
                "confirmation_token": body.confirmation_token,
                "dry_run": body.dry_run,
            },
        )

        if body.dry_run:
            service.dry_run = True

        result = await service.execute_resource_group_reset(
            subscription_id=subscription_id, rg_name=rg_name, confirmation_token=body.confirmation_token
        )

        await log_audit_event(
            request=request,
            action="reset_resource_group_completed",
            resource=f"rg:{subscription_id}/{rg_name}",
            details={
                "status": result.status.value,
                "deleted_resources": result.deleted_azure_resources,
                "duration_seconds": result.duration_seconds,
            },
        )

        return ResetResultResponse(**result.to_dict())

    except InvalidConfirmationTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute resource group reset: {str(e)}",
        )


# ========================================================================
# Resource-Level Reset Endpoints
# ========================================================================


@router.get("/reset/resource/preview", response_model=ResetPreviewResponse)
@require_api_key
async def preview_resource_reset(
    request: Request,
    resource_id: str,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetPreviewResponse:
    """Preview individual resource reset without executing.

    Args:
        request: FastAPI request
        resource_id: Full Azure resource ID (query parameter)
        service: Tenant reset service

    Returns:
        ResetPreviewResponse with counts and warnings
    """
    try:
        await log_audit_event(
            request=request,
            action="reset_resource_preview",
            resource=f"resource:{resource_id}",
            details={"resource_id": resource_id},
        )

        preview = await service.preview_resource_reset(resource_id=resource_id)
        return ResetPreviewResponse(**preview.to_dict())

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview resource reset: {str(e)}",
        )


@router.post("/reset/resource", response_model=ResetResultResponse)
@require_api_key
async def execute_resource_reset(
    request: Request,
    resource_id: str,
    body: ResetExecutionRequest,
    service: TenantResetService = Depends(get_tenant_reset_service),
) -> ResetResultResponse:
    """Execute individual resource reset after confirmation.

    Args:
        request: FastAPI request
        resource_id: Full Azure resource ID (query parameter)
        body: Reset execution request
        service: Tenant reset service

    Returns:
        ResetResultResponse with deletion details
    """
    try:
        await log_audit_event(
            request=request,
            action="reset_resource_execute",
            resource=f"resource:{resource_id}",
            details={
                "resource_id": resource_id,
                "confirmation_token": body.confirmation_token,
                "dry_run": body.dry_run,
            },
        )

        if body.dry_run:
            service.dry_run = True

        result = await service.execute_resource_reset(
            resource_id=resource_id, confirmation_token=body.confirmation_token
        )

        await log_audit_event(
            request=request,
            action="reset_resource_completed",
            resource=f"resource:{resource_id}",
            details={
                "status": result.status.value,
                "deleted_resources": result.deleted_azure_resources,
                "duration_seconds": result.duration_seconds,
            },
        )

        return ResetResultResponse(**result.to_dict())

    except InvalidConfirmationTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute resource reset: {str(e)}",
        )
