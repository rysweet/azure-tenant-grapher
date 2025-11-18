"""
Scale-Up Service Module

This module provides scale-up functionality for the Azure Tenant Grapher,
organized into focused components following the Single Responsibility Principle.

Components:
- ProjectionSetup: Setup and configuration management
- ResourceProjection: Resource and relationship projection
- ValidationService: Operation validation and rollback
- ScaleUpOrchestrator: Main coordinator (primary entry point)

Public API:
- ScaleUpOrchestrator: Main service class (use this)
- ScaleUpResult: Operation result dataclass
"""

from src.services.scale_up.orchestrator import ScaleUpOrchestrator, ScaleUpResult
from src.services.scale_up.projection_setup import ProjectionSetup
from src.services.scale_up.resource_projection import ResourceProjection
from src.services.scale_up.validation import ValidationService

__all__ = [
    "ScaleUpOrchestrator",
    "ScaleUpResult",
    "ProjectionSetup",
    "ResourceProjection",
    "ValidationService",
]
