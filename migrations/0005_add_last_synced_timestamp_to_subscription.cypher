// Migration 0005 – Add LastSyncedTimestamp property to Subscription nodes
// This property will be used to track the last time delta ingestion was performed per subscription.

MATCH (s:Subscription)
WHERE s.LastSyncedTimestamp IS NULL
SET s.LastSyncedTimestamp = null;
