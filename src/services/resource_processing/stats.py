"""
Processing Statistics Module

This module provides the ProcessingStats dataclass for tracking
resource processing operations statistics.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ProcessingStats:
    """Statistics for resource processing operations."""

    total_resources: int = 0
    processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    llm_generated: int = 0
    llm_skipped: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        return (self.successful / max(self.processed, 1)) * 100

    @property
    def progress_percentage(self) -> float:
        """Calculate overall progress as a percentage."""
        return (self.processed / max(self.total_resources, 1)) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_resources": self.total_resources,
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "llm_generated": self.llm_generated,
            "llm_skipped": self.llm_skipped,
            "success_rate": round(self.success_rate, 2),
            "progress_percentage": round(self.progress_percentage, 2),
        }
