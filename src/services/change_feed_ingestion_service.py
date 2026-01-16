"""
ChangeFeedIngestionService

This service is responsible for ingesting resource change events from Azure Resource Graph's resourcechanges table
and ARM Activity Logs, maintaining a LastSyncedTimestamp per subscription, and upserting or marking resources as deleted
in the Neo4j graph. It is designed for efficient delta ingestion and minimal API usage.

Implements the requirements of Issue #54 and docs/ARCHITECTURE_IMPROVEMENTS.md section 1.

Future: May be extended to support Event Grid for near-real-time updates.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
from azure.mgmt.resourcegraph import ResourceGraphClient  # type: ignore[import-untyped]
from azure.mgmt.resourcegraph.models import (  # type: ignore[import-untyped]
    QueryRequest,
    QueryRequestOptions,
)

try:
    from azure.mgmt.monitor import (
        MonitorManagementClient,  # type: ignore[import-untyped]
    )

    MonitorClient = MonitorManagementClient  # type: ignore[misc]
except ImportError:
    MonitorClient = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def validate_subscription_id(subscription_id: str) -> None:
    """
    Validate Azure subscription ID format to prevent KQL injection.

    Args:
        subscription_id: Azure subscription ID to validate

    Raises:
        ValueError: If subscription_id is not a valid GUID format
    """
    if not subscription_id:
        raise ValueError("Subscription ID cannot be empty")

    # Azure subscription IDs are GUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    guid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )

    if not guid_pattern.match(subscription_id):
        raise ValueError(
            f"Invalid subscription ID format: {subscription_id}. Must be a valid GUID (e.g., 12345678-1234-1234-1234-123456789012)"
        )


def validate_iso8601_timestamp(timestamp: str) -> None:
    """
    Validate ISO8601 timestamp format to prevent KQL injection.

    Args:
        timestamp: ISO8601 timestamp string to validate

    Raises:
        ValueError: If timestamp is not valid ISO8601 format
    """
    if not timestamp:
        raise ValueError("Timestamp cannot be empty")

    # ISO8601 format requires 'T' separator between date and time
    # Formats: 2024-01-01T00:00:00Z or 2024-01-01T00:00:00.000000+00:00
    if "T" not in timestamp:
        raise ValueError(
            f"Invalid timestamp format: {timestamp}. Must be valid ISO8601 format (e.g., 2024-01-01T00:00:00Z)"
        )

    # Try parsing with datetime to validate ISO8601 format
    try:
        # Try fromisoformat (Python 3.7+)
        if timestamp.endswith("Z"):
            # Replace Z with +00:00 for fromisoformat compatibility
            timestamp_normalized = timestamp[:-1] + "+00:00"
            datetime.fromisoformat(timestamp_normalized)
        else:
            datetime.fromisoformat(timestamp)
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Invalid timestamp format: {timestamp}. Must be valid ISO8601 format (e.g., 2024-01-01T00:00:00Z)"
        ) from e


class ChangeFeedIngestionService:
    """
    Service for ingesting resource change events and synchronizing the graph.

    Responsibilities:
    - Query Azure Resource Graph's resourcechanges and ARM Activity Logs for each subscription.
    - Maintain a LastSyncedTimestamp per subscription.
    - Upsert changed resources; mark deleted resources as state="deleted" (or optionally remove).
    - Designed for extension to support Event Grid in the future.
    """

    def __init__(
        self,
        config: Any,
        neo4j_session_manager: Any,
        resource_processing_service: Any = None,
    ):
        """
        Initialize the ChangeFeedIngestionService.

        Args:
            config: Configuration object with Azure and processing settings.
            neo4j_session_manager: Neo4j session manager for database operations.
            resource_processing_service: ResourceProcessingService for upserting resources.
        """
        self.config = config
        self.neo4j_session_manager = neo4j_session_manager
        self.resource_processing_service = resource_processing_service

    async def ingest_changes_for_subscription(
        self, subscription_id: str, since_timestamp: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Ingest resource changes for a given subscription since the provided timestamp.

        Args:
            subscription_id: Azure subscription ID (must be valid GUID format).
            since_timestamp: ISO8601 timestamp string; if None, will use stored LastSyncedTimestamp.

        Returns:
            List of upserted or marked resources.

        Raises:
            ValueError: If subscription_id or since_timestamp have invalid formats
        """
        import datetime

        logger.info(
            f"Starting delta ingestion for subscription {subscription_id} since {since_timestamp}"
        )

        # 1. Validate subscription_id to prevent KQL injection
        validate_subscription_id(subscription_id)

        # 2. Determine since_timestamp
        if since_timestamp is None:
            since_timestamp = self.get_last_synced_timestamp(subscription_id)
        if since_timestamp is None:
            # Default to 7 days ago if never synced
            since_timestamp = (
                datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=7)
            ).isoformat()

        # 3. Validate timestamp to prevent KQL injection
        validate_iso8601_timestamp(since_timestamp)

        # 4. Query Azure Resource Graph for resourcechanges
        # Note: After validation, these values are safe to use in query construction
        credential = DefaultAzureCredential()
        resourcegraph_client = ResourceGraphClient(credential)
        query = f"""
        ResourceChanges
        | where subscriptionId == '{subscription_id}'
        | where changeTime > datetime('{since_timestamp}')
        | project id, changeType, changeTime, after, before
        """
        try:
            query_options = QueryRequestOptions(result_format="objectArray")
            query_request = QueryRequest(
                query=query, subscriptions=[subscription_id], options=query_options
            )
            response = resourcegraph_client.resources(query=query_request)
            changes = response.data if hasattr(response, "data") else []
        except Exception as e:
            logger.error(str(f"Failed to query Resource Graph: {e}"))
            changes = []

        # 5. Query ARM Activity Logs for deletions
        deleted_ids = set()
        if MonitorClient is not None:
            monitor_client = MonitorClient(credential, subscription_id)
            try:
                activity_logs = monitor_client.activity_logs.list(
                    filter=f"eventTimestamp ge '{since_timestamp}' and (operationName/value eq 'Microsoft.Resources/subscriptions/resourceGroups/delete' or operationName/value eq 'Microsoft.Resources/delete')"
                )
                for event in activity_logs:
                    resource_id = getattr(event, "resourceId", None)
                    if resource_id:
                        deleted_ids.add(resource_id)
            except Exception as e:
                logger.error(str(f"Failed to query Activity Logs: {e}"))
        else:
            logger.warning(
                "MonitorClient is not available; skipping activity log deletion detection."
            )

        # 6. Upsert changed resources
        upsert_resources = []
        for change in changes:
            if change.get("changeType") == "Delete":
                deleted_ids.add(change.get("id"))
            else:
                # Use 'after' state if present, else 'before'
                resource_data = change.get("after") or change.get("before") or {}
                resource_data["id"] = change.get("id")
                upsert_resources.append(resource_data)

        # Use ResourceProcessingService to upsert
        if self.resource_processing_service and upsert_resources:
            import asyncio

            asyncio.get_event_loop()
            try:
                asyncio.run(
                    self.resource_processing_service.process_resources(upsert_resources)
                )
            except RuntimeError:
                # Already in event loop (e.g., in test), use create_task
                import nest_asyncio  # type: ignore[import-untyped]

                nest_asyncio.apply()
                asyncio.get_event_loop().create_task(
                    self.resource_processing_service.process_resources(upsert_resources)
                )

        # 7. Mark deleted resources as state="deleted"
        with self.neo4j_session_manager.session() as session:
            for resource_id in deleted_ids:
                session.run(
                    "MATCH (r:Resource {id: $id}) SET r.state = 'deleted', r.updated_at = datetime()",
                    {"id": resource_id},
                )

        # 8. Update LastSyncedTimestamp
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.set_last_synced_timestamp(subscription_id, now_iso)

        logger.info(
            f"Delta ingestion complete for subscription {subscription_id}. Upserted: {len(upsert_resources)}, Deleted: {len(deleted_ids)}"
        )
        return upsert_resources

    def get_last_synced_timestamp(self, subscription_id: str) -> Optional[str]:
        """
        Retrieve the LastSyncedTimestamp for a subscription from Neo4j.

        Args:
            subscription_id: Azure subscription ID.

        Returns:
            ISO8601 timestamp string or None if not set.
        """
        with self.neo4j_session_manager.session() as session:
            result = session.run(
                "MATCH (s:Subscription {id: $sub_id}) RETURN s.LastSyncedTimestamp AS ts",
                {"sub_id": subscription_id},
            )
            record = result.single()
            return record["ts"] if record and "ts" in record else None

    def set_last_synced_timestamp(self, subscription_id: str, timestamp: str) -> None:
        """
        Set the LastSyncedTimestamp for a subscription in Neo4j.

        Args:
            subscription_id: Azure subscription ID.
            timestamp: ISO8601 timestamp string to set.
        """
        with self.neo4j_session_manager.session() as session:
            session.run(
                "MATCH (s:Subscription {id: $sub_id}) SET s.LastSyncedTimestamp = $ts",
                {"sub_id": subscription_id, "ts": timestamp},
            )

    async def ingest_all(self):
        """
        Ingest changes for all configured subscriptions.

        Returns:
            Dict mapping subscription_id to list of upserted/marked resources.
        """
        logger.info("Starting change feed ingestion for all subscriptions")

        # Get all subscriptions from the database
        with self.neo4j_session_manager.driver.session() as session:
            result = session.run(
                "MATCH (s:Subscription) RETURN s.subscription_id as id"
            )
            subscription_ids = [record["id"] for record in result]

        if not subscription_ids:
            logger.warning("No subscriptions found in database")
            return {}

        logger.info(str(f"Found {len(subscription_ids)} subscriptions to process"))

        # Process each subscription concurrently
        tasks = []
        for subscription_id in subscription_ids:
            task = self.ingest_changes_for_subscription(subscription_id)
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        all_results = {}
        for subscription_id, result in zip(subscription_ids, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error processing subscription {subscription_id}: {result}"
                )
                all_results[subscription_id] = {"error": str(result)}
            else:
                all_results[subscription_id] = result

        logger.info(
            f"Completed change feed ingestion for {len(all_results)} subscriptions"
        )
        return all_results
