"""Code analysis module for handler property extraction.

Philosophy:
- AST-based static analysis for accurate detection
- Standard library only (ast module)
- Self-contained and regeneratable

Public API:
    HandlerAnalyzer: Main analyzer class
    analyze_handler: Convenience function
"""

from .handler_analyzer import HandlerAnalyzer, analyze_handler

__all__ = ["HandlerAnalyzer", "analyze_handler"]
