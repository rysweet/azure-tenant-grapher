"""Validation Engine for property coverage analysis.

This module provides the core validation logic for analyzing property coverage
in generated Infrastructure-as-Code.

Philosophy:
- Self-contained validation brick
- Clear public API via __all__
- No external service dependencies
- Standard library only (except for local imports)

Public API (the "studs"):
    CoverageCalculator: Calculate coverage metrics
    GapFinder: Identify missing properties
    CriticalClassifier: Classify property criticality
"""

from .coverage_calculator import CoverageCalculator
from .critical_classifier import CriticalClassifier
from .gap_finder import GapFinder

__all__ = [
    "CoverageCalculator",
    "CriticalClassifier",
    "GapFinder",
]
