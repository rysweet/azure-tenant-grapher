"""Version Detector for graph version mismatch detection.

This module detects version mismatches between the semaphore file (.atg_graph_version)
and the Neo4j metadata node. Completes in < 100ms for fast startup checks.
"""

from pathlib import Path
from typing import Any, Dict, Optional


class VersionDetector:
    """Detects version mismatches between semaphore file and Neo4j metadata.

    Reads the semaphore file (.atg_graph_version) and compares it to the version
    stored in the Neo4j GraphMetadata node. Returns mismatch details if versions differ.

    Performance: Completes in < 100ms.
    """

    def __init__(self, semaphore_path: Optional[Path] = None):
        """Initialize detector with semaphore file path.

        Args:
            semaphore_path: Path to .atg_graph_version file. If None, uses default
                          path (package root / .atg_graph_version).
        """
        if semaphore_path is None:
            # Default to package root / .atg_graph_version
            package_root = Path(__file__).parent.parent.parent
            self.semaphore_path = package_root / ".atg_graph_version"
        else:
            self.semaphore_path = semaphore_path

    def read_semaphore_version(self) -> Optional[str]:
        """Read version string from semaphore file.

        Returns:
            Version string (stripped of whitespace) or None if file missing/unreadable.
        """
        try:
            if not self.semaphore_path.exists():
                return None

            content = self.semaphore_path.read_text(encoding="utf-8")
            version = content.strip()

            # Return None for empty content
            if not version:
                return None

            return version

        except (OSError, UnicodeDecodeError):
            # Handle read errors and encoding errors
            return None

    def compare_versions(
        self, semaphore_version: Optional[str], metadata_version: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Compare semaphore and metadata versions.

        Args:
            semaphore_version: Version from semaphore file (or None)
            metadata_version: Version from Neo4j metadata (or None)

        Returns:
            None if versions match (or both None)
            Dict with mismatch details if versions differ:
                {
                    "semaphore_version": str | None,
                    "metadata_version": str | None,
                    "reason": str
                }
        """
        # Both None = no versions to compare = no mismatch
        if semaphore_version is None and metadata_version is None:
            return None

        # Versions match = no mismatch
        if semaphore_version == metadata_version:
            return None

        # Versions differ = mismatch
        reason = self._get_mismatch_reason(semaphore_version, metadata_version)

        return {
            "semaphore_version": semaphore_version,
            "metadata_version": metadata_version,
            "reason": reason,
        }

    def _get_mismatch_reason(
        self, semaphore_version: Optional[str], metadata_version: Optional[str]
    ) -> str:
        """Generate human-readable reason for mismatch."""
        if semaphore_version is None:
            return "Semaphore file missing or unreadable"
        if metadata_version is None:
            return "Metadata node missing in Neo4j"
        return "Version mismatch detected"

    def detect_mismatch(self, metadata_service) -> Optional[Dict[str, Any]]:
        """Detect version mismatch between semaphore and metadata.

        This is the main entry point that orchestrates the complete mismatch check.

        Args:
            metadata_service: GraphMetadataService instance for reading metadata

        Returns:
            None if versions match
            Dict with mismatch details if versions differ

        Raises:
            Exception: If metadata service fails (re-raises exception)
        """
        # Read semaphore version
        semaphore_version = self.read_semaphore_version()

        # Read metadata version (may raise exception)
        metadata = metadata_service.read_metadata()
        metadata_version = metadata.get("version") if metadata else None

        # Compare versions
        return self.compare_versions(semaphore_version, metadata_version)
