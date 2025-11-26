"""Web handlers for Terraform emission."""

from .app_service import AppServiceHandler
from .service_plan import ServicePlanHandler
from .static_web_app import StaticWebAppHandler

__all__ = [
    "AppServiceHandler",
    "ServicePlanHandler",
    "StaticWebAppHandler",
]
