"""
Pattern Detectors Module

Pattern detection and analysis logic.

Public API:
    PatternDetector: Detects architectural patterns in the graph
    OrphanDetector: Identifies orphaned nodes
"""

from .orphan_detector import OrphanDetector
from .pattern_detector import PatternDetector

__all__ = [
    "OrphanDetector",
    "PatternDetector",
]
