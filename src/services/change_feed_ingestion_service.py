"""
ChangeFeedIngestionService

This service is responsible for ingesting resource change events from Azure Resource Graph's resourcechanges table
and ARM Activity Logs, maintaining a LastSyncedTimestamp per subscription, and upserting or marking resources as deleted
in the Neo4j graph. It is designed for efficient delta ingestion and minimal API usage.

Implements the requirements of Issue #54 and docs/ARCHITECTURE_IMPROVEMENTS.md section 1.

Future: May be extended to support Event Grid for near-real-time updates.
"""

import logging
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient

try:
    from azure.mgmt.monitor.v2015_04_01 import MonitorClient
except ImportError:
    MonitorClient = None

logger = logging.getLogger(__name__)


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
            subscription_id: Azure subscription ID.
            since_timestamp: ISO8601 timestamp string; if None, will use stored LastSyncedTimestamp.

        Returns:
            List of upserted or marked resources.
        """
        import datetime

        logger.info(
            f"Starting delta ingestion for subscription {subscription_id} since {since_timestamp}"
        )

        # 1. Determine since_timestamp
        if since_timestamp is None:
            since_timestamp = self.get_last_synced_timestamp(subscription_id)
        if since_timestamp is None:
            # Default to 7 days ago if never synced
            since_timestamp = (
                datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=7)
            ).isoformat()

        # 2. Query Azure Resource Graph for resourcechanges
        credential = DefaultAzureCredential()
        resourcegraph_client = ResourceGraphClient(credential)
        query = f"""
        ResourceChanges
        | where subscriptionId == '{subscription_id}'
        | where changeTime > datetime('{since_timestamp}')
        | project id, changeType, changeTime, after, before
        """
        try:
            response = resourcegraph_client.resources(
                query=query,
                subscriptions=[subscription_id],
                result_format="objectArray",
            )
            changes = response.data if hasattr(response, "data") else []
        except Exception as e:
            logger.error(f"Failed to query Resource Graph: {e}")
            changes = []

        # 3. Query ARM Activity Logs for deletions
        deleted_ids = set()
        if MonitorClient is not None:
            monitor_client = MonitorClient(credential, subscription_id)
            try:
                activity_logs = monitor_client.activity_logs.list(
                    filter=f"eventTimestamp ge '{since_timestamp}' and (operationName/value eq 'Microsoft.Resources/subscriptions/resourceGroups/delete' or operationName/value eq 'Microsoft.Resources/delete')"
                )
                for event in activity_logs:
                    if hasattr(event, "resourceId"):
                        deleted_ids.add(event.resourceId)
            except Exception as e:
                logger.error(f"Failed to query Activity Logs: {e}")
        else:
            logger.warning(
                "MonitorClient is not available; skipping activity log deletion detection."
            )

        # 4. Upsert changed resources
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
                import nest_asyncio

                nest_asyncio.apply()
                asyncio.get_event_loop().create_task(
                    self.resource_processing_service.process_resources(upsert_resources)
                )

        # 5. Mark deleted resources as state="deleted"
        with self.neo4j_session_manager.session() as session:
            for resource_id in deleted_ids:
                session.run(
                    "MATCH (r:Resource {id: $id}) SET r.state = 'deleted', r.updated_at = datetime()",
                    {"id": resource_id},
                )

        # 6. Update LastSyncedTimestamp
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
        # TODO: Implement orchestration across all subscriptions.
        logger.info("Stub: ingest_all()")
        return {}
