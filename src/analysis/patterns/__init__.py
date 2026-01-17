"""
Pattern Analysis Module

Modular architecture for architectural pattern analysis.
Replaces the monolithic architectural_pattern_analyzer.py.

Public API:
    ArchitecturalPatternOrchestrator: Main orchestration class

Issue #714: Refactor architectural_pattern_analyzer.py god object
"""

from .orchestrator import ArchitecturalPatternOrchestrator

__all__ = ["ArchitecturalPatternOrchestrator"]
