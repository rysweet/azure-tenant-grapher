"""
Scale-Down Service Backward Compatibility Facade

This file maintains backward compatibility for code that imports ScaleDownService.
The actual implementation has been refactored into modular components in the
src/services/scale_down/ package.

Migration Path:
- OLD: from src.services.scale_down_service import ScaleDownService
- NEW: from src.services.scale_down import ScaleDownOrchestrator

All existing imports will continue to work via the alias below.
"""

from src.services.scale_down import ScaleDownOrchestrator
from src.services.scale_down.quality_metrics import QualityMetrics

# Backward compatibility alias
ScaleDownService = ScaleDownOrchestrator

__all__ = ["QualityMetrics", "ScaleDownOrchestrator", "ScaleDownService"]
