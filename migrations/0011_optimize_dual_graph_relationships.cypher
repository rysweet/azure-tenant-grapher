// Migration 0011 - Optimize Dual-Graph Relationship Creation
// Adds critical indexes to fix N+1 query problem in relationship creation

// INDEX 1: Resource.original_id - enables fast lookup of abstracted nodes from original IDs
// This replaces slow OPTIONAL MATCH traversals with fast index lookups
// Critical for dual-graph relationship creation performance
CREATE INDEX resource_original_id IF NOT EXISTS
FOR (r:Resource)
ON (r.original_id);

// INDEX 2: Composite index for relationship traversal optimization
// Speeds up queries that filter by type and original_id together
CREATE INDEX resource_type_original_id IF NOT EXISTS
FOR (r:Resource)
ON (r.type, r.original_id);

// INDEX 3: Original.id index (should exist, but ensure it's present)
CREATE INDEX original_id IF NOT EXISTS
FOR (r:Original)
ON (r.id);

// INDEX 4: Resource:Original composite label index
// Optimizes MATCH (r:Resource:Original {id: $id}) queries
CREATE INDEX resource_original_composite IF NOT EXISTS
FOR (r:Original)
ON (r.id);
