"""
Scale-Up Service - Backward Compatibility Shim

This module provides backward compatibility for code importing from the old
monolithic scale_up_service.py location. All functionality has been moved
to the modular src.services.scale_up package.

DEPRECATED: Use `from src.services.scale_up import ScaleUpService, ScaleUpResult` instead.

This shim will be maintained for backward compatibility but new code should
import from the new package location.
"""

# Re-export all public APIs from the new modular package
from src.services.scale_up import ScaleUpResult, ScaleUpService

__all__ = ["ScaleUpService", "ScaleUpResult"]
