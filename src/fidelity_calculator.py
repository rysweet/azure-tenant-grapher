"""
Fidelity Calculator

Calculates and tracks resource replication fidelity between source and target subscriptions.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from neo4j import GraphDatabase

from src.utils.secure_credentials import Neo4jCredentials, get_neo4j_credentials

logger = logging.getLogger(__name__)


class FidelityMetrics:
    """Container for fidelity calculation results."""

    def __init__(
        self,
        timestamp: str,
        source_subscription_id: str,
        target_subscription_id: str,
        source_resources: int,
        target_resources: int,
        source_relationships: int,
        target_relationships: int,
        source_resource_groups: int,
        target_resource_groups: int,
        source_resource_types: int,
        target_resource_types: int,
        overall_fidelity: float,
        fidelity_by_type: dict[str, float],
        missing_resources: int,
        objective_met: bool = False,
        target_fidelity: float = 95.0,
    ):
        self.timestamp = timestamp
        self.source_subscription_id = source_subscription_id
        self.target_subscription_id = target_subscription_id
        self.source_resources = source_resources
        self.target_resources = target_resources
        self.source_relationships = source_relationships
        self.target_relationships = target_relationships
        self.source_resource_groups = source_resource_groups
        self.target_resource_groups = target_resource_groups
        self.source_resource_types = source_resource_types
        self.target_resource_types = target_resource_types
        self.overall_fidelity = overall_fidelity
        self.fidelity_by_type = fidelity_by_type
        self.missing_resources = missing_resources
        self.objective_met = objective_met
        self.target_fidelity = target_fidelity

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary format."""
        return {
            "timestamp": self.timestamp,
            "source": {
                "subscription_id": self.source_subscription_id,
                "resources": self.source_resources,
                "relationships": self.source_relationships,
                "resource_groups": self.source_resource_groups,
                "resource_types": self.source_resource_types,
            },
            "target": {
                "subscription_id": self.target_subscription_id,
                "resources": self.target_resources,
                "relationships": self.target_relationships,
                "resource_groups": self.target_resource_groups,
                "resource_types": self.target_resource_types,
            },
            "fidelity": {
                "overall": round(self.overall_fidelity, 1),
                "by_type": {k: round(v, 1) for k, v in self.fidelity_by_type.items()},
                "missing_resources": self.missing_resources,
                "objective_met": self.objective_met,
                "target_fidelity": self.target_fidelity,
            },
        }


class FidelityCalculator:
    """Calculate resource replication fidelity between subscriptions."""

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        credentials: Optional[Neo4jCredentials] = None,
    ):
        """
        Initialize FidelityCalculator with Neo4j connection.

        Args:
            neo4j_uri: Neo4j connection URI (deprecated - use credentials parameter)
            neo4j_user: Neo4j username (deprecated - use credentials parameter)
            neo4j_password: Neo4j password (deprecated - use credentials parameter)
            credentials: Neo4jCredentials object (preferred method)

        Note:
            If credentials parameter is None, will attempt to load from legacy
            parameters or use get_neo4j_credentials() for secure loading.
        """
        # Use provided credentials or load securely
        if credentials:
            creds = credentials
        elif neo4j_uri and neo4j_user and neo4j_password:
            # Legacy path - create credentials from parameters
            logger.warning(
                "Passing credentials as individual parameters is deprecated. "
                "Use credentials parameter or get_neo4j_credentials() instead."
            )
            creds = Neo4jCredentials(
                uri=neo4j_uri, username=neo4j_user, password=neo4j_password
            )
        else:
            # Secure path - load from Key Vault or environment
            creds = get_neo4j_credentials()

        # Store credentials securely and connect
        self._credentials = creds
        self.driver = GraphDatabase.driver(
            creds.uri, auth=(creds.username, creds.password)
        )

    def __repr__(self) -> str:
        """Return string representation without exposing credentials."""
        return f"FidelityCalculator(uri='{self._credentials.uri}')"

    def close(self) -> None:
        """Close Neo4j driver connection."""
        if self.driver is not None:
            self.driver.close()

    def calculate_fidelity(
        self,
        source_subscription_id: str,
        target_subscription_id: str,
        target_fidelity: float = 95.0,
    ) -> FidelityMetrics:
        """
        Calculate fidelity between source and target subscriptions.

        Args:
            source_subscription_id: Source subscription ID to compare from
            target_subscription_id: Target subscription ID to compare to
            target_fidelity: Target fidelity percentage for objective checking

        Returns:
            FidelityMetrics object with calculated metrics

        Raises:
            ValueError: If subscription IDs are invalid or not found
        """
        with self.driver.session() as session:
            # Get source metrics
            source_metrics = self._get_subscription_metrics(
                session, source_subscription_id
            )
            if not source_metrics:
                raise ValueError(
                    f"Source subscription not found: {source_subscription_id}"
                )

            # Get target metrics
            target_metrics = self._get_subscription_metrics(
                session, target_subscription_id
            )
            if not target_metrics:
                raise ValueError(
                    f"Target subscription not found: {target_subscription_id}"
                )

            # Calculate overall fidelity
            overall_fidelity = self._calculate_overall_fidelity(
                source_metrics, target_metrics
            )

            # Calculate fidelity by resource type
            fidelity_by_type = self._calculate_fidelity_by_type(
                session, source_subscription_id, target_subscription_id
            )

            # Calculate missing resources
            missing_resources = (
                source_metrics["resources"] - target_metrics["resources"]
            )

            # Check if objective is met
            objective_met = overall_fidelity >= target_fidelity

            # Create timestamp
            timestamp = datetime.now(tz=timezone.utc).isoformat()

            return FidelityMetrics(
                timestamp=timestamp,
                source_subscription_id=source_subscription_id,
                target_subscription_id=target_subscription_id,
                source_resources=source_metrics["resources"],
                target_resources=target_metrics["resources"],
                source_relationships=source_metrics["relationships"],
                target_relationships=target_metrics["relationships"],
                source_resource_groups=source_metrics["resource_groups"],
                target_resource_groups=target_metrics["resource_groups"],
                source_resource_types=source_metrics["resource_types"],
                target_resource_types=target_metrics["resource_types"],
                overall_fidelity=overall_fidelity,
                fidelity_by_type=fidelity_by_type,
                missing_resources=missing_resources,
                objective_met=objective_met,
                target_fidelity=target_fidelity,
            )

    def _get_subscription_metrics(
        self, session: Any, subscription_id: str
    ) -> Optional[dict[str, int]]:
        """
        Get metrics for a specific subscription.

        Args:
            session: Neo4j session
            subscription_id: Subscription ID to query

        Returns:
            Dictionary with resource counts or None if not found
        """
        # Check if subscription exists
        check_query = """
        MATCH (r:Resource)
        WHERE r.subscription_id = $sub_id
        RETURN count(r) as count
        """
        result = session.run(check_query, {"sub_id": subscription_id})  # type: ignore[arg-type]
        record = result.single()
        if not record or record["count"] == 0:
            return None

        metrics = {}

        # Count resources
        resource_query = """
        MATCH (r:Resource)
        WHERE r.subscription_id = $sub_id
        RETURN count(r) as count
        """
        result = session.run(resource_query, {"sub_id": subscription_id})  # type: ignore[arg-type]
        metrics["resources"] = result.single()["count"]

        # Count relationships
        relationship_query = """
        MATCH (r:Resource)-[rel]-()
        WHERE r.subscription_id = $sub_id
        RETURN count(DISTINCT rel) as count
        """
        result = session.run(relationship_query, {"sub_id": subscription_id})  # type: ignore[arg-type]
        metrics["relationships"] = result.single()["count"]

        # Count resource groups
        rg_query = """
        MATCH (r:Resource)
        WHERE r.subscription_id = $sub_id
        AND r.resourceGroup IS NOT NULL
        RETURN count(DISTINCT r.resourceGroup) as count
        """
        result = session.run(rg_query, {"sub_id": subscription_id})  # type: ignore[arg-type]
        metrics["resource_groups"] = result.single()["count"]

        # Count resource types
        type_query = """
        MATCH (r:Resource)
        WHERE r.subscription_id = $sub_id
        RETURN count(DISTINCT r.type) as count
        """
        result = session.run(type_query, {"sub_id": subscription_id})  # type: ignore[arg-type]
        metrics["resource_types"] = result.single()["count"]

        return metrics

    def _calculate_overall_fidelity(
        self, source_metrics: dict[str, int], target_metrics: dict[str, int]
    ) -> float:
        """
        Calculate overall fidelity percentage.

        Args:
            source_metrics: Source subscription metrics
            target_metrics: Target subscription metrics

        Returns:
            Fidelity percentage (0-100)
        """
        if source_metrics["resources"] == 0:
            return 0.0

        return (target_metrics["resources"] / source_metrics["resources"]) * 100.0

    def _calculate_fidelity_by_type(
        self,
        session: Any,
        source_subscription_id: str,
        target_subscription_id: str,
    ) -> dict[str, float]:
        """
        Calculate fidelity by resource type.

        Args:
            session: Neo4j session
            source_subscription_id: Source subscription ID
            target_subscription_id: Target subscription ID

        Returns:
            Dictionary mapping resource type to fidelity percentage
        """
        # Get all resource types from source
        source_types_query = """
        MATCH (r:Resource)
        WHERE r.subscription_id = $sub_id
        RETURN r.type as type, count(r) as count
        """
        source_result = session.run(
            source_types_query, {"sub_id": source_subscription_id}
        )
        source_types = {record["type"]: record["count"] for record in source_result}

        # Get all resource types from target
        target_result = session.run(
            source_types_query, {"sub_id": target_subscription_id}
        )
        target_types = {record["type"]: record["count"] for record in target_result}

        # Calculate fidelity for each type
        fidelity_by_type = {}
        for resource_type, source_count in source_types.items():
            target_count = target_types.get(resource_type, 0)
            if source_count > 0:
                fidelity_by_type[resource_type] = (target_count / source_count) * 100.0
            else:
                fidelity_by_type[resource_type] = 0.0

        return fidelity_by_type

    def export_to_json(self, metrics: FidelityMetrics, output_path: str) -> None:
        """
        Export fidelity metrics to JSON file.

        Args:
            metrics: FidelityMetrics to export
            output_path: Output file path

        Raises:
            IOError: If file cannot be written
        """
        try:
            with open(output_path, "w") as f:
                json.dump(metrics.to_dict(), f, indent=2)
            logger.info(str(f"Fidelity metrics exported to {output_path}"))
        except OSError as e:
            logger.error(str(f"Failed to export metrics to {output_path}: {e}"))
            raise

    def track_fidelity(
        self,
        metrics: FidelityMetrics,
        tracking_file: str = "demos/fidelity_history.jsonl",
    ) -> None:
        """
        Append fidelity metrics to time-series tracking file.

        Args:
            metrics: FidelityMetrics to track
            tracking_file: Path to JSONL tracking file

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(tracking_file), exist_ok=True)

            # Append to JSONL file
            with open(tracking_file, "a") as f:
                f.write(json.dumps(metrics.to_dict()) + "\n")
            logger.info(str(f"Fidelity metrics tracked to {tracking_file}"))
        except OSError as e:
            logger.error(str(f"Failed to track metrics to {tracking_file}: {e}"))
            raise

    def check_objective(
        self, objective_file: str, current_fidelity: float
    ) -> tuple[bool, float]:
        """
        Check if fidelity meets objective defined in OBJECTIVE.md.

        Args:
            objective_file: Path to OBJECTIVE.md file
            current_fidelity: Current overall fidelity percentage

        Returns:
            Tuple of (objective_met, target_fidelity)

        Raises:
            IOError: If objective file cannot be read
        """
        try:
            with open(objective_file) as f:
                content = f.read()

            # Parse target fidelity from OBJECTIVE.md
            # Look for patterns like "95% fidelity" or "fidelity: 95%"
            import re

            patterns = [
                r"(\d+)%\s*fidelity",
                r"fidelity[:\s]*(\d+)%",
                r"target[:\s]*(\d+)%",
            ]

            target_fidelity = 95.0  # Default
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    target_fidelity = float(match.group(1))
                    break

            objective_met = current_fidelity >= target_fidelity
            logger.info(
                f"Objective check: current={current_fidelity:.1f}%, "
                f"target={target_fidelity}%, met={objective_met}"
            )

            return objective_met, target_fidelity

        except OSError as e:
            logger.error(str(f"Failed to read objective file {objective_file}: {e}"))
            raise
