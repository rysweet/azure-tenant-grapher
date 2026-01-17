"""Property Validation System for IaC Generation.

This module provides comprehensive property validation for Infrastructure-as-Code
generation, ensuring all required properties are present and correctly classified.

Philosophy:
- Modular brick design (Schema Loader, Validation Engine, Reporter)
- Clear separation of concerns
- Self-contained and regeneratable
- Standard library focus

Public API:
    Models: Criticality, PropertyDefinition, PropertyGap, CoverageMetrics
    Validation: CoverageCalculator, GapFinder, CriticalClassifier
"""

from .models import (
    Criticality,
    CoverageMetrics,
    PropertyDefinition,
    PropertyGap,
)
from .validation import (
    CoverageCalculator,
    CriticalClassifier,
    GapFinder,
)

__all__ = [
    # Models
    "Criticality",
    "CoverageMetrics",
    "PropertyDefinition",
    "PropertyGap",
    # Validation
    "CoverageCalculator",
    "CriticalClassifier",
    "GapFinder",
]
