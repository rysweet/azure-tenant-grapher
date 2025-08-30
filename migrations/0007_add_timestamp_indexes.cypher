// Migration 0007 - Add indexes for timestamp fields for performance optimization
// This migration adds indexes on updated_at and created_at fields to improve query performance

// Create index on updated_at field for Resource nodes
CREATE INDEX updated_at_index IF NOT EXISTS FOR (r:Resource) ON (r.updated_at);

// Create index on created_at field for Resource nodes
CREATE INDEX created_at_index IF NOT EXISTS FOR (r:Resource) ON (r.created_at);

// Create index on LastSyncedTimestamp field for Subscription nodes
CREATE INDEX last_synced_timestamp_index IF NOT EXISTS FOR (s:Subscription) ON (s.LastSyncedTimestamp);

// Create composite index for better filtering on Resource nodes with timestamps
CREATE INDEX resource_timestamp_index IF NOT EXISTS FOR (r:Resource) ON (r.updated_at, r.created_at);