// Migration 0005 – Add LastSyncedTimestamp property to Subscription nodes
// This property will be used to track the last time delta ingestion was performed per subscription.

MATCH (s:Subscription)
WHERE NOT exists(s.LastSyncedTimestamp)
SET s.LastSyncedTimestamp = null;

// No-op for nodes that already have the property.
