"""
Pattern Analysis Module

Modular architecture for architectural pattern analysis.
Replaces the monolithic architectural_pattern_analyzer.py.

Public API:
    Core modules: ResourceTypeHandler, GraphBuilder
    Detectors: PatternDetector, OrphanDetector

Issue #714: Refactor architectural_pattern_analyzer.py god object
Issue #729: Remove unused scaffolding modules (Zero-BS compliance)
"""

__all__ = []  # Re-export from submodules as needed
