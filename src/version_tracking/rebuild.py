"""Rebuild Service for graph reconstruction.

This module orchestrates the graph rebuild process:
1. Backup existing metadata to JSON file
2. Drop all nodes and relationships from Neo4j
3. Rescan Azure tenant (via discovery service)
4. Update metadata with new version

SECURITY NOTES:
- Backup files created with 0o600 permissions (owner read/write only)
- Path traversal validation prevents malicious backup path manipulation
- drop_all() requires explicit confirm=True to prevent accidental data loss
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class RebuildService:
    """Orchestrates graph rebuild operations.

    Manages the complete rebuild workflow including backup, drop, rescan, and
    metadata update. Ensures safe operations with confirmation requirements and
    proper error handling.
    """

    def __init__(
        self,
        session_manager,
        metadata_service,
        discovery_service,
        backup_dir: Optional[Path] = None,
    ):
        """Initialize rebuild service with dependencies.

        Args:
            session_manager: Neo4jSessionManager instance
            metadata_service: GraphMetadataService instance
            discovery_service: Azure discovery service for rescanning
            backup_dir: Directory for backup files (default: ~/.atg/backups/)
        """
        self.session_manager = session_manager
        self.metadata_service = metadata_service
        self.discovery_service = discovery_service

        # Default backup directory
        if backup_dir is None:
            backup_dir = Path.home() / ".atg" / "backups"

        self.backup_dir = backup_dir

    def backup_metadata(self) -> Optional[Path]:
        """Backup current graph metadata to JSON file.

        Creates timestamped backup file in backup directory. File permissions
        set to 0o600 (owner read/write only) for security.

        Returns:
            Path to backup file or None if no metadata to backup

        Raises:
            Exception: If backup fails
        """
        # Read current metadata
        metadata = self.metadata_service.read_metadata()

        if metadata is None:
            return None

        # Ensure backup directory exists
        self._ensure_backup_directory()

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"metadata_{timestamp}.json"
        backup_path = self.backup_dir / backup_filename

        # SECURITY: Validate path to prevent traversal attacks
        self._validate_backup_path(backup_path)

        # Write backup file
        backup_content = json.dumps(metadata, indent=2)
        backup_path.write_text(backup_content, encoding="utf-8")

        # SECURITY: Set restrictive file permissions (owner read/write only)
        os.chmod(backup_path, 0o600)

        return backup_path

    def drop_all(self, confirm: bool = False) -> None:
        """Drop all nodes and relationships from Neo4j.

        DESTRUCTIVE OPERATION: Deletes everything in the graph database.

        Args:
            confirm: Must be True to execute. Safety check.

        Raises:
            ValueError: If confirm is not True
            Exception: If Neo4j delete fails
        """
        if not confirm:
            raise ValueError("drop_all requires confirm=True to execute")

        query = """
        MATCH (n)
        DETACH DELETE n
        """

        with self.session_manager.session() as session:
            session.run(query)

    def rebuild(self, new_version: str, confirm: bool = False) -> None:
        """Orchestrate complete graph rebuild.

        Workflow:
        1. Backup existing metadata
        2. Drop all nodes/relationships
        3. Rescan Azure tenant
        4. Update metadata with new version

        Args:
            new_version: New graph version to write after rebuild
            confirm: Must be True to execute. Safety check.

        Raises:
            ValueError: If confirm is not True or version format invalid
            Exception: If any step fails (backup, drop, discover, update)
        """
        if not confirm:
            raise ValueError("rebuild requires confirm=True to execute")

        # Validate version format
        from .metadata import GraphMetadataService

        GraphMetadataService._validate_version(new_version)

        # Step 1: Backup metadata
        self.backup_metadata()

        # Step 2: Drop all data
        self.drop_all(confirm=True)

        # Step 3: Rescan Azure tenant
        self.discovery_service.discover_all()

        # Step 4: Update metadata with new version
        timestamp = datetime.now().isoformat()
        self.metadata_service.write_metadata(
            version=new_version, last_scan_at=timestamp
        )

    def restore_backup(self, backup_path: Path) -> None:
        """Restore metadata from backup file.

        Args:
            backup_path: Path to backup JSON file

        Raises:
            FileNotFoundError: If backup file doesn't exist
            Exception: If restore fails
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # SECURITY: Validate path to prevent traversal attacks
        self._validate_backup_path(backup_path)

        # Read backup file
        backup_content = backup_path.read_text(encoding="utf-8")
        metadata = json.loads(backup_content)

        # Write metadata to Neo4j
        self.metadata_service.write_metadata(
            version=metadata["version"], last_scan_at=metadata["last_scan_at"]
        )

    def list_backups(self) -> List[Path]:
        """List all backup files in backup directory.

        Returns:
            List of backup file paths (sorted by name/timestamp)
        """
        if not self.backup_dir.exists():
            return []

        return sorted(self.backup_dir.glob("metadata_*.json"))

    def cleanup_old_backups(self, keep: int = 10) -> None:
        """Remove old backup files, keeping N most recent.

        Args:
            keep: Number of most recent backups to keep
        """
        backups = self.list_backups()

        if len(backups) <= keep:
            return  # Nothing to delete

        # Delete oldest backups
        backups_to_delete = backups[:-keep]
        for backup_path in backups_to_delete:
            backup_path.unlink()

    def _ensure_backup_directory(self) -> None:
        """Create backup directory if it doesn't exist."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _validate_backup_path(self, backup_path: Path) -> None:
        """Validate backup path to prevent directory traversal attacks.

        SECURITY: Ensures backup_path is within backup_dir to prevent
        malicious paths like "../../etc/passwd".

        Args:
            backup_path: Path to validate

        Raises:
            ValueError: If path is outside backup directory
        """
        try:
            # Resolve both paths to absolute paths
            resolved_backup = backup_path.resolve()
            resolved_dir = self.backup_dir.resolve()

            # Check if backup path is within backup directory
            if not str(resolved_backup).startswith(str(resolved_dir)):
                raise ValueError(
                    f"Security: Backup path must be within backup directory. "
                    f"Path: {backup_path}, Directory: {self.backup_dir}"
                )
        except Exception as e:
            raise ValueError(f"Invalid backup path: {e}") from e
