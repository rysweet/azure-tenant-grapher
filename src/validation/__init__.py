"""Validation module for deployment comparison and reporting.

This module provides functionality to compare source and target deployments
by analyzing their Neo4j graph representations and generating detailed reports.

Public API:
    - compare_graphs: Compare two resource lists
    - compare_filtered_graphs: Compare with optional filtering
    - generate_markdown_report: Create markdown validation report
    - generate_json_report: Create JSON validation report
    - ComparisonResult: Dataclass containing comparison results
"""

from .comparator import ComparisonResult, compare_filtered_graphs, compare_graphs
from .report import generate_json_report, generate_markdown_report

__all__ = [
    "ComparisonResult",
    "compare_graphs",
    "compare_filtered_graphs",
    "generate_markdown_report",
    "generate_json_report",
]
