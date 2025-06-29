// Migration 0004 – Ensure index on Resource {id} for fast upsert
// This migration is defensive: 0002 already adds a uniqueness constraint on Resource.id,
// but we explicitly ensure an index exists for upsert performance and future compatibility.

CREATE INDEX resource_id_index IF NOT EXISTS
  FOR (r:Resource)
  ON (r.id);

// No-op if uniqueness constraint from 0002 is present.