"""Graph Metadata Service for Neo4j version tracking.

This module manages the :GraphMetadata node in Neo4j that stores:
- Graph construction version
- Last scan timestamp

SECURITY NOTE: The :GraphMetadata label is system-internal and should never
be exposed to external queries. Access should be restricted to version tracking
services only to prevent unauthorized version manipulation.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional


class GraphMetadataService:
    """Manages graph metadata in Neo4j.

    Provides CRUD operations for the singleton :GraphMetadata node that tracks
    the graph construction version and last scan timestamp.

    Thread Safety: Neo4j session manager handles concurrent access.
    """

    def __init__(self, session_manager):
        """Initialize service with Neo4j session manager.

        Args:
            session_manager: Neo4jSessionManager instance

        Raises:
            TypeError: If session_manager is invalid
        """
        if session_manager is None:
            raise TypeError("session_manager cannot be None")

        # Basic type check (duck typing - if it has session, it's valid)
        if not hasattr(session_manager, "session"):
            raise TypeError("session_manager must have session method")

        self.session_manager = session_manager

    def read_metadata(self) -> Optional[Dict[str, Any]]:
        """Read graph metadata from Neo4j.

        Returns:
            Dict with metadata fields (version, last_scan_at) or None if not exists

        Raises:
            Exception: If Neo4j query fails
        """
        query = """
        MATCH (m:GraphMetadata)
        RETURN m.version AS version, m.last_scan_at AS last_scan_at
        LIMIT 1
        """

        with self.session_manager.session() as session:
            result = session.run(query)
            record = result.single()

            if record is None:
                return None

            return {
                "version": record["version"],
                "last_scan_at": record["last_scan_at"],
            }

    def write_metadata(self, version: str, last_scan_at: str) -> None:
        """Write or update graph metadata in Neo4j.

        Creates a new :GraphMetadata node or updates existing one (MERGE behavior).
        Only one :GraphMetadata node exists in the graph.

        Args:
            version: Semantic version string (e.g., "1.0.0")
            last_scan_at: ISO8601 timestamp string

        Raises:
            ValueError: If version or timestamp format invalid
            Exception: If Neo4j write fails
        """
        # Validate inputs
        self._validate_version(version)
        self._validate_timestamp(last_scan_at)

        query = """
        MERGE (m:GraphMetadata)
        SET m.version = $version,
            m.last_scan_at = $last_scan_at
        RETURN m.version AS version
        """

        params = {"version": version, "last_scan_at": last_scan_at}

        with self.session_manager.session() as session:
            session.run(query, params)

    def update_last_scan(self, timestamp: Optional[str] = None) -> None:
        """Update last scan timestamp without changing version.

        Args:
            timestamp: ISO8601 timestamp string. If None, uses current time.

        Raises:
            ValueError: If GraphMetadata node doesn't exist or timestamp invalid
            Exception: If Neo4j update fails
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        else:
            self._validate_timestamp(timestamp)

        query = """
        MATCH (m:GraphMetadata)
        SET m.last_scan_at = $last_scan_at
        RETURN m.last_scan_at AS last_scan_at
        """

        params = {"last_scan_at": timestamp}

        with self.session_manager.session() as session:
            result = session.run(query, params)
            record = result.single()

            if record is None:
                raise ValueError("GraphMetadata node not found")

    def delete_metadata(self) -> None:
        """Delete graph metadata node from Neo4j.

        Succeeds even if node doesn't exist (idempotent).

        Raises:
            Exception: If Neo4j delete fails
        """
        query = """
        MATCH (m:GraphMetadata)
        DELETE m
        """

        with self.session_manager.session() as session:
            session.run(query)

    @staticmethod
    def _validate_version(version: str) -> None:
        """Validate semantic version format.

        Args:
            version: Version string to validate

        Raises:
            ValueError: If version format invalid
        """
        if not version:
            raise ValueError("Version cannot be empty")

        # Basic semver validation (X.Y.Z where X, Y, Z are integers)
        semver_pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(semver_pattern, version):
            raise ValueError(
                f"Invalid version format: {version}. Expected semver (e.g., '1.0.0')"
            )

    @staticmethod
    def _validate_timestamp(timestamp: str) -> None:
        """Validate ISO8601 timestamp format.

        Args:
            timestamp: Timestamp string to validate

        Raises:
            ValueError: If timestamp format invalid
        """
        if not timestamp:
            raise ValueError("Timestamp cannot be empty")

        # Try parsing as ISO8601
        try:
            # Accept various ISO8601 formats
            if "T" not in timestamp:
                raise ValueError("Timestamp must include time component")

            # Basic validation - must be parseable
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception as e:
            raise ValueError(
                f"Invalid timestamp format: {timestamp}. Expected ISO8601 (e.g., '2025-01-15T10:00:00')"
            ) from e
