"""
Scale-Up Service - Backward Compatibility Facade

This module provides backward compatibility for existing code that imports
from scale_up_service.py. All functionality has been refactored into modular
components under src/services/scale_up/.

DEPRECATED: Use ScaleUpOrchestrator from src.services.scale_up directly.

Migration Guide:
    Old: from src.services.scale_up_service import ScaleUpService, ScaleUpResult
    New: from src.services.scale_up import ScaleUpOrchestrator as ScaleUpService, ScaleUpResult

The refactoring splits the monolithic 1,722-line service into focused modules:
- projection_setup.py: Setup and validation
- resource_projection.py: Node/edge projection
- validation.py: Pre/post validation
- orchestrator.py: Main coordinator

For new code, import directly from src.services.scale_up.
"""

from src.services.scale_up.orchestrator import ScaleUpOrchestrator, ScaleUpResult

# Backward compatibility alias
ScaleUpService = ScaleUpOrchestrator

__all__ = ["ScaleUpService", "ScaleUpOrchestrator", "ScaleUpResult"]
