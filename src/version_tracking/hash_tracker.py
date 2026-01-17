"""Hash-based tracking of graph construction files.

This module calculates and validates hashes of files that affect graph construction.
When any tracked file changes, the hash changes, indicating a version bump is needed.

Philosophy:
- Fast performance (< 50ms for hash calculation)
- Standard library only (hashlib, pathlib)
- Self-contained and regeneratable
- Clear error messages

Public API:
    HashTracker: Main class for hash calculation and validation
    calculate_construction_hash: Calculate hash of all tracked files
    validate_hash: Compare stored hash against current hash
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class HashValidationResult:
    """Result of hash validation check.

    Attributes:
        matches: True if current hash matches stored hash
        stored_hash: Hash value from version file (or None)
        current_hash: Hash calculated from current files
        changed_files: List of files that changed (empty if matches)
    """

    matches: bool
    stored_hash: Optional[str]
    current_hash: str
    changed_files: List[str]


class HashTracker:
    """Calculate and validate hashes of graph construction files.

    Tracks specific files and directories that affect how the graph is built.
    Changes to these files should trigger a version bump.

    Performance: < 50ms for hash calculation
    """

    # Files and directories that affect graph construction
    TRACKED_PATHS = [
        "src/relationship_rules/",
        "src/services/azure_discovery_service.py",
        "src/resource_processor.py",
        "src/azure_tenant_grapher.py",
    ]

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize hash tracker.

        Args:
            project_root: Root directory of the project. If None, uses package root.
        """
        if project_root is None:
            # Default to package root (3 levels up from this file)
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)

    def _get_tracked_files(self) -> List[Path]:
        """Get list of all files to track.

        Expands directory paths to individual files, excludes __pycache__
        and .pyc files, and sorts for consistent ordering.

        Returns:
            Sorted list of Path objects for all tracked files
        """
        files = []

        for path_str in self.TRACKED_PATHS:
            path = self.project_root / path_str

            if not path.exists():
                # Skip missing files/directories
                continue

            if path.is_file():
                files.append(path)
            elif path.is_dir():
                # Walk directory and collect Python files
                for py_file in path.rglob("*.py"):
                    # Skip __pycache__ and compiled files
                    if "__pycache__" in py_file.parts or py_file.suffix == ".pyc":
                        continue
                    files.append(py_file)

        # Sort for consistent ordering
        return sorted(files)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a single file.

        Args:
            file_path: Path to file to hash

        Returns:
            Hex string of file hash

        Raises:
            OSError: If file cannot be read
        """
        sha256 = hashlib.sha256()

        # Read in chunks for memory efficiency
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest()

    def calculate_construction_hash(self) -> str:
        """Calculate SHA256 hash of all construction files.

        Combines hashes of all tracked files into a single hash representing
        the current state of graph construction code.

        Returns:
            Hex string of combined hash

        Raises:
            OSError: If any file cannot be read
        """
        files = self._get_tracked_files()

        # Combine all file hashes
        combined = hashlib.sha256()

        for file_path in files:
            # Include relative path in hash (so renames trigger change)
            rel_path = file_path.relative_to(self.project_root)
            combined.update(str(rel_path).encode("utf-8"))

            # Include file content hash
            file_hash = self._calculate_file_hash(file_path)
            combined.update(file_hash.encode("utf-8"))

        return combined.hexdigest()

    def _detect_changed_files(
        self, stored_files: List[str], current_hash: str
    ) -> List[str]:
        """Detect which tracked files have changed.

        Compares stored list of files to current files and identifies changes.

        Args:
            stored_files: List of tracked file paths from version file
            current_hash: Current hash (for comparison only)

        Returns:
            List of changed file paths (relative to project root)
        """
        current_files = self._get_tracked_files()
        current_paths = {str(f.relative_to(self.project_root)) for f in current_files}
        stored_paths = set(stored_files) if stored_files else set()

        # Find added or removed files
        added = current_paths - stored_paths
        removed = stored_paths - current_paths

        changed = []
        if added:
            changed.extend(f"+{path}" for path in sorted(added))
        if removed:
            changed.extend(f"-{path}" for path in sorted(removed))

        # If no file changes but hash differs, it's content changes
        if not changed:
            # Report all current files as potentially modified
            changed = [str(p.relative_to(self.project_root)) for p in current_files]

        return changed

    def validate_hash(
        self, stored_hash: Optional[str], stored_files: Optional[List[str]] = None
    ) -> HashValidationResult:
        """Validate current hash matches stored hash.

        Args:
            stored_hash: Hash from version file (or None if no version file)
            stored_files: List of tracked files from version file (optional)

        Returns:
            HashValidationResult with validation details and changed files
        """
        try:
            current_hash = self.calculate_construction_hash()
        except OSError as e:
            # If we can't calculate current hash, validation fails
            return HashValidationResult(
                matches=False,
                stored_hash=stored_hash,
                current_hash="",
                changed_files=[f"Error calculating hash: {e}"],
            )

        # No stored hash = first time setup = no mismatch
        if stored_hash is None:
            return HashValidationResult(
                matches=True,
                stored_hash=None,
                current_hash=current_hash,
                changed_files=[],
            )

        # Compare hashes
        matches = stored_hash == current_hash

        changed_files = []
        if not matches:
            changed_files = self._detect_changed_files(stored_files or [], current_hash)

        return HashValidationResult(
            matches=matches,
            stored_hash=stored_hash,
            current_hash=current_hash,
            changed_files=changed_files,
        )


def calculate_construction_hash(project_root: Optional[Path] = None) -> str:
    """Calculate hash of all graph construction files.

    Convenience function for one-off hash calculation.

    Args:
        project_root: Root directory of the project (optional)

    Returns:
        Hex string of construction hash
    """
    tracker = HashTracker(project_root)
    return tracker.calculate_construction_hash()


def validate_hash(
    stored_hash: Optional[str],
    stored_files: Optional[List[str]] = None,
    project_root: Optional[Path] = None,
) -> HashValidationResult:
    """Validate stored hash against current files.

    Convenience function for one-off validation.

    Args:
        stored_hash: Hash from version file
        stored_files: List of tracked files from version file (optional)
        project_root: Root directory of the project (optional)

    Returns:
        HashValidationResult with validation details
    """
    tracker = HashTracker(project_root)
    return tracker.validate_hash(stored_hash, stored_files)


__all__ = [
    "HashTracker",
    "HashValidationResult",
    "calculate_construction_hash",
    "validate_hash",
]
