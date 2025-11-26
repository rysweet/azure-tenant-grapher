"""Machine Learning handlers for Terraform emission."""

from .cognitive_services import CognitiveServicesHandler
from .ml_workspace import MLWorkspaceHandler

__all__ = [
    "CognitiveServicesHandler",
    "MLWorkspaceHandler",
]
