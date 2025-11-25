"""
Scale Stats Service for Azure Tenant Grapher

This service provides comprehensive statistics and reporting for scale operations.
It helps track synthetic vs original data, analyze resource distributions, and
compare tenants.

Key Features:
- Show original vs synthetic resource counts
- Resource type breakdown and distribution
- Session history and details
- Tenant comparison and analysis
- Multiple export formats (table, JSON, markdown)

All operations respect the dual-graph architecture.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.services.base_scale_service import BaseScaleService
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class ScaleStatsService(BaseScaleService):
    """
    Service for generating statistics and reports for scale operations.

    This service provides comprehensive analytics on synthetic data,
    including resource counts, type distributions, session histories,
    and tenant comparisons.

    All operations:
    - Analyze both original and synthetic data
    - Provide detailed breakdowns by type and session
    - Support multiple output formats
    - Enable tenant comparisons
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the scale stats service.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        super().__init__(session_manager)

    async def get_tenant_stats(
        self, tenant_id: str, detailed: bool = False
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a tenant.

        This method provides a complete overview of a tenant's resources,
        including both original (scanned) and synthetic (scale-generated) data.

        Args:
            tenant_id: Azure tenant ID
            detailed: If True, include detailed breakdowns (default: False)

        Returns:
            Dict[str, Any]: Statistics including:
                - tenant_id: Azure tenant ID
                - timestamp: When stats were generated
                - total_resources: Total resource count (original + synthetic)
                - original_resources: Count of original (scanned) resources
                - synthetic_resources: Count of synthetic (generated) resources
                - synthetic_percentage: Percentage of synthetic resources
                - resource_type_breakdown: Dict of type -> counts
                - session_count: Number of scale operation sessions
                - sessions: List of session summaries (if detailed=True)
                - relationship_count: Total relationship count
                - original_relationships: Count of original relationships
                - synthetic_relationships: Count of synthetic relationships

        Raises:
            ValueError: If tenant doesn't exist
            Exception: If query fails

        Example:
            >>> stats = await service.get_tenant_stats("abc123", detailed=True)
            >>> print(f"Total: {stats['total_resources']} resources")
            >>> print(f"Synthetic: {stats['synthetic_percentage']:.1f}%")
            >>> for rtype, count in stats['resource_type_breakdown'].items():
            ...     print(f"  {rtype}: {count}")
        """
        self.logger.info(f"Getting tenant stats for {tenant_id} (detailed={detailed})")

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # Query 1: Basic resource counts
        resource_count_query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
        WITH r,
             CASE WHEN r.synthetic = true THEN 'synthetic' ELSE 'original' END as category
        RETURN category, count(r) as count
        """

        # Query 2: Resource type breakdown
        type_breakdown_query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
        WITH r.type as resource_type,
             CASE WHEN r.synthetic = true THEN 'synthetic' ELSE 'original' END as category,
             count(r) as count
        RETURN resource_type, category, count
        ORDER BY count DESC
        """

        # Query 3: Session summary
        session_summary_query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND r.synthetic = true
          AND r.scale_operation_id IS NOT NULL
        WITH r.scale_operation_id as session_id,
             count(r) as resource_count,
             collect(DISTINCT r.generation_strategy)[0] as strategy,
             collect(DISTINCT r.generation_timestamp)[0] as timestamp
        RETURN session_id, resource_count, strategy, timestamp
        ORDER BY timestamp DESC
        """

        # Query 4: Relationship counts
        relationship_count_query = """
        MATCH (r1:Resource)-[rel]->(r2:Resource)
        WHERE NOT r1:Original AND NOT r2:Original
          AND (r1.tenant_id = $tenant_id OR r2.tenant_id = $tenant_id)
        WITH rel,
             CASE WHEN r1.synthetic = true OR r2.synthetic = true
                  THEN 'synthetic' ELSE 'original' END as category
        RETURN category, count(rel) as count
        """

        try:
            stats: Dict[str, Any] = {
                "tenant_id": tenant_id,
                "timestamp": datetime.now().isoformat(),
                "total_resources": 0,
                "original_resources": 0,
                "synthetic_resources": 0,
                "synthetic_percentage": 0.0,
                "resource_type_breakdown": {},
                "session_count": 0,
                "relationship_count": 0,
                "original_relationships": 0,
                "synthetic_relationships": 0,
            }

            with self.session_manager.session() as session:
                # Execute query 1: Resource counts
                result1 = session.run(resource_count_query, {"tenant_id": tenant_id})
                for record in result1:
                    category = record["category"]
                    count = record["count"]
                    stats["total_resources"] += count

                    if category == "original":
                        stats["original_resources"] = count
                    elif category == "synthetic":
                        stats["synthetic_resources"] = count

                # Calculate synthetic percentage
                if stats["total_resources"] > 0:
                    stats["synthetic_percentage"] = (
                        stats["synthetic_resources"] / stats["total_resources"]
                    ) * 100

                # Execute query 2: Type breakdown
                result2 = session.run(type_breakdown_query, {"tenant_id": tenant_id})
                type_breakdown: Dict[str, Dict[str, int]] = defaultdict(
                    lambda: {"original": 0, "synthetic": 0, "total": 0}
                )

                for record in result2:
                    resource_type = record["resource_type"]
                    category = record["category"]
                    count = record["count"]

                    type_breakdown[resource_type][category] = count
                    type_breakdown[resource_type]["total"] += count

                stats["resource_type_breakdown"] = dict(type_breakdown)

                # Execute query 3: Session summary
                result3 = session.run(session_summary_query, {"tenant_id": tenant_id})
                sessions = []
                for record in result3:
                    sessions.append(
                        {
                            "session_id": record["session_id"],
                            "resource_count": record["resource_count"],
                            "strategy": record["strategy"],
                            "timestamp": record["timestamp"],
                        }
                    )

                stats["session_count"] = len(sessions)
                if detailed:
                    stats["sessions"] = sessions

                # Execute query 4: Relationship counts
                result4 = session.run(
                    relationship_count_query, {"tenant_id": tenant_id}
                )
                for record in result4:
                    category = record["category"]
                    count = record["count"]
                    stats["relationship_count"] += count

                    if category == "original":
                        stats["original_relationships"] = count
                    elif category == "synthetic":
                        stats["synthetic_relationships"] = count

            self.logger.info(
                f"Stats generated: {stats['total_resources']} total resources "
                f"({stats['synthetic_percentage']:.1f}% synthetic)"
            )

            return stats

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to get tenant stats: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error getting tenant stats: {e}")
            raise

    async def compare_tenants(
        self, tenant_ids: List[str], detailed: bool = False
    ) -> Dict[str, Any]:
        """
        Compare statistics across multiple tenants.

        This method generates comparative statistics for multiple tenants,
        enabling analysis of scale operation effectiveness and data distribution.

        Args:
            tenant_ids: List of Azure tenant IDs to compare
            detailed: If True, include detailed per-tenant breakdowns (default: False)

        Returns:
            Dict[str, Any]: Comparison results including:
                - tenant_count: Number of tenants compared
                - timestamp: When comparison was generated
                - tenants: Dict mapping tenant_id -> stats
                - summary: Aggregated statistics across all tenants
                - comparison_metrics: Comparative metrics (min/max/avg)

        Raises:
            ValueError: If tenant_ids is empty or invalid
            Exception: If comparison fails

        Example:
            >>> comparison = await service.compare_tenants(
            ...     ["tenant1", "tenant2", "tenant3"],
            ...     detailed=True
            ... )
            >>> print(f"Comparing {comparison['tenant_count']} tenants")
            >>> summary = comparison['summary']
            >>> print(f"Total synthetic: {summary['total_synthetic_resources']}")
        """
        self.logger.info(f"Comparing {len(tenant_ids)} tenants")

        if not tenant_ids:
            raise ValueError("tenant_ids cannot be empty")

        if len(tenant_ids) > 100:
            raise ValueError("Cannot compare more than 100 tenants at once")

        # Validate all tenants exist
        for tenant_id in tenant_ids:
            if not await self.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found in database")

        try:
            # Get stats for each tenant
            tenant_stats: Dict[str, Dict[str, Any]] = {}
            for tenant_id in tenant_ids:
                tenant_stats[tenant_id] = await self.get_tenant_stats(
                    tenant_id, detailed=detailed
                )

            # Calculate summary statistics
            summary = {
                "total_resources": sum(
                    t["total_resources"] for t in tenant_stats.values()
                ),
                "total_original_resources": sum(
                    t["original_resources"] for t in tenant_stats.values()
                ),
                "total_synthetic_resources": sum(
                    t["synthetic_resources"] for t in tenant_stats.values()
                ),
                "total_relationships": sum(
                    t["relationship_count"] for t in tenant_stats.values()
                ),
                "total_sessions": sum(
                    t["session_count"] for t in tenant_stats.values()
                ),
            }

            # Calculate comparison metrics
            synthetic_percentages = [
                t["synthetic_percentage"] for t in tenant_stats.values()
            ]
            resource_counts = [t["total_resources"] for t in tenant_stats.values()]

            comparison_metrics = {
                "synthetic_percentage": {
                    "min": min(synthetic_percentages) if synthetic_percentages else 0,
                    "max": max(synthetic_percentages) if synthetic_percentages else 0,
                    "avg": (
                        sum(synthetic_percentages) / len(synthetic_percentages)
                        if synthetic_percentages
                        else 0
                    ),
                },
                "resource_count": {
                    "min": min(resource_counts) if resource_counts else 0,
                    "max": max(resource_counts) if resource_counts else 0,
                    "avg": (
                        sum(resource_counts) / len(resource_counts)
                        if resource_counts
                        else 0
                    ),
                },
            }

            result = {
                "tenant_count": len(tenant_ids),
                "timestamp": datetime.now().isoformat(),
                "tenants": tenant_stats if detailed else list(tenant_stats.keys()),
                "summary": summary,
                "comparison_metrics": comparison_metrics,
            }

            self.logger.info(
                f"Comparison complete: {len(tenant_ids)} tenants, "
                f"{summary['total_resources']} total resources"
            )

            return result

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to compare tenants: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error comparing tenants: {e}")
            raise

    async def get_session_history(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get detailed history of all scale operation sessions for a tenant.

        This method provides a chronological list of all scale operations
        performed on a tenant, with detailed information about each session.

        Args:
            tenant_id: Azure tenant ID

        Returns:
            List[Dict[str, Any]]: List of session details, each including:
                - session_id: Scale operation ID
                - strategy: Generation strategy (template/scenario/random)
                - timestamp: ISO 8601 timestamp of creation
                - resource_count: Number of resources created
                - relationship_count: Number of relationships created
                - resource_types: List of resource types created
                - duration_estimate: Estimated operation duration (if available)

        Raises:
            ValueError: If tenant doesn't exist
            Exception: If query fails

        Example:
            >>> history = await service.get_session_history("abc123")
            >>> print(f"Found {len(history)} scale operations")
            >>> for session in history:
            ...     print(f"{session['timestamp']}: {session['strategy']} - "
            ...           f"{session['resource_count']} resources")
        """
        self.logger.info(f"Getting session history for tenant {tenant_id}")

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # Query for session details
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND r.synthetic = true
          AND r.scale_operation_id IS NOT NULL
        WITH r.scale_operation_id as session_id,
             count(r) as resource_count,
             collect(DISTINCT r.type) as resource_types,
             collect(DISTINCT r.generation_strategy)[0] as strategy,
             collect(DISTINCT r.generation_timestamp)[0] as timestamp
        OPTIONAL MATCH (r2:Resource)-[rel]->()
        WHERE NOT r2:Original
          AND r2.tenant_id = $tenant_id
          AND r2.scale_operation_id = session_id
        WITH session_id, resource_count, resource_types, strategy, timestamp,
             count(DISTINCT rel) as relationship_count
        RETURN session_id, strategy, timestamp, resource_count,
               relationship_count, resource_types
        ORDER BY timestamp DESC
        """

        try:
            history: List[Dict[str, Any]] = []

            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})

                for record in result:
                    history.append(
                        {
                            "session_id": record["session_id"],
                            "strategy": record["strategy"] or "unknown",
                            "timestamp": record["timestamp"] or "unknown",
                            "resource_count": record["resource_count"],
                            "relationship_count": record["relationship_count"],
                            "resource_types": list(record["resource_types"]),
                        }
                    )

            self.logger.info(f"Found {len(history)} scale operation sessions")

            return history

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to get session history: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error getting session history: {e}")
            raise

    async def export_stats(
        self,
        tenant_id: str,
        format: str = "json",
        output_path: Optional[str] = None,
        detailed: bool = False,
    ) -> str:
        """
        Export tenant statistics in specified format.

        This method generates a formatted export of tenant statistics
        suitable for reporting, documentation, or further analysis.

        Args:
            tenant_id: Azure tenant ID
            format: Export format (json, markdown, table) (default: json)
            output_path: Optional file path to write output
            detailed: If True, include detailed breakdowns (default: False)

        Returns:
            str: Formatted statistics string

        Raises:
            ValueError: If tenant doesn't exist or format is invalid
            Exception: If export fails

        Example:
            >>> # Export to file
            >>> output = await service.export_stats(
            ...     "abc123",
            ...     format="markdown",
            ...     output_path="/tmp/stats.md",
            ...     detailed=True
            ... )
            >>> print(f"Exported to /tmp/stats.md")
            >>>
            >>> # Get as string
            >>> json_output = await service.export_stats(
            ...     "abc123",
            ...     format="json"
            ... )
            >>> print(json_output)
        """
        self.logger.info(f"Exporting stats for tenant {tenant_id} in {format} format")

        valid_formats = ["json", "markdown", "table"]
        if format not in valid_formats:
            raise ValueError(
                f"Invalid format: {format}. Must be one of: {valid_formats}"
            )

        # Get stats
        stats = await self.get_tenant_stats(tenant_id, detailed=detailed)

        # Format output based on requested format
        if format == "json":
            output = json.dumps(stats, indent=2)
        elif format == "markdown":
            output = self._format_markdown(stats)
        elif format == "table":
            output = self._format_table(stats)
        else:
            raise ValueError(f"Unsupported format: {format}")

        # Write to file if path provided
        if output_path:
            with open(output_path, "w") as f:
                f.write(output)
            self.logger.info(f"Stats exported to {output_path}")

        return output

    # =========================================================================
    # Private Formatting Methods
    # =========================================================================

    def _format_markdown(self, stats: Dict[str, Any]) -> str:
        """Format statistics as Markdown."""
        lines = [
            f"# Tenant Statistics: {stats['tenant_id']}",
            "",
            f"**Generated:** {stats['timestamp']}",
            "",
            "## Resource Summary",
            "",
            f"- **Total Resources:** {stats['total_resources']}",
            f"- **Original Resources:** {stats['original_resources']}",
            f"- **Synthetic Resources:** {stats['synthetic_resources']}",
            f"- **Synthetic Percentage:** {stats['synthetic_percentage']:.1f}%",
            "",
            "## Relationship Summary",
            "",
            f"- **Total Relationships:** {stats['relationship_count']}",
            f"- **Original Relationships:** {stats['original_relationships']}",
            f"- **Synthetic Relationships:** {stats['synthetic_relationships']}",
            "",
            "## Scale Operations",
            "",
            f"- **Session Count:** {stats['session_count']}",
            "",
        ]

        # Add resource type breakdown
        if stats["resource_type_breakdown"]:
            lines.extend(
                [
                    "## Resource Type Breakdown",
                    "",
                    "| Resource Type | Original | Synthetic | Total |",
                    "|--------------|----------|-----------|-------|",
                ]
            )

            for resource_type, counts in sorted(
                stats["resource_type_breakdown"].items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            ):
                original = counts.get("original", 0)
                synthetic = counts.get("synthetic", 0)
                total = counts.get("total", 0)
                lines.append(
                    f"| {resource_type} | {original} | {synthetic} | {total} |"
                )

            lines.append("")

        # Add session details if available
        if stats.get("sessions"):
            lines.extend(
                [
                    "## Scale Operation Sessions",
                    "",
                    "| Session ID | Strategy | Resources | Timestamp |",
                    "|------------|----------|-----------|-----------|",
                ]
            )

            for session in stats["sessions"]:
                lines.append(
                    f"| {session['session_id']} | {session['strategy']} | "
                    f"{session['resource_count']} | {session['timestamp']} |"
                )

            lines.append("")

        return "\n".join(lines)

    def _format_table(self, stats: Dict[str, Any]) -> str:
        """Format statistics as ASCII table."""
        lines = [
            "=" * 80,
            f"Tenant Statistics: {stats['tenant_id']}",
            f"Generated: {stats['timestamp']}",
            "=" * 80,
            "",
            "Resource Summary:",
            "-" * 80,
            f"  Total Resources:       {stats['total_resources']:>10}",
            f"  Original Resources:    {stats['original_resources']:>10}",
            f"  Synthetic Resources:   {stats['synthetic_resources']:>10}",
            f"  Synthetic Percentage:  {stats['synthetic_percentage']:>9.1f}%",
            "",
            "Relationship Summary:",
            "-" * 80,
            f"  Total Relationships:   {stats['relationship_count']:>10}",
            f"  Original Relationships:{stats['original_relationships']:>10}",
            f"  Synthetic Relationships:{stats['synthetic_relationships']:>9}",
            "",
            "Scale Operations:",
            "-" * 80,
            f"  Session Count:         {stats['session_count']:>10}",
            "",
        ]

        # Add resource type breakdown
        if stats["resource_type_breakdown"]:
            lines.extend(
                [
                    "Resource Type Breakdown:",
                    "-" * 80,
                    f"{'Resource Type':<50} {'Original':>10} {'Synthetic':>10} {'Total':>8}",
                    "-" * 80,
                ]
            )

            for resource_type, counts in sorted(
                stats["resource_type_breakdown"].items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )[:20]:  # Limit to top 20
                original = counts.get("original", 0)
                synthetic = counts.get("synthetic", 0)
                total = counts.get("total", 0)
                # Truncate long resource type names
                rtype_display = (
                    resource_type[:47] + "..."
                    if len(resource_type) > 50
                    else resource_type
                )
                lines.append(
                    f"{rtype_display:<50} {original:>10} {synthetic:>10} {total:>8}"
                )

            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)
