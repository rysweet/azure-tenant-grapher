// Migration 0010 – Dual-Graph Architecture Schema
// This migration adds support for dual-graph architecture where every resource
// exists as both an Original node (with Azure IDs) and an Abstracted node (with hash IDs).
//
// Design: (Abstracted)-[:SCAN_SOURCE_NODE]->(Original)
//
// Labels:
//   - Abstracted nodes: :Resource:Abstracted
//   - Original nodes: :Resource:Original
//
// This migration is additive and backward-compatible when used with feature flag.

// ============================================================================
// STEP 1: Add constraints for new node types
// ============================================================================

// Constraint for Original resources (Azure IDs)
CREATE CONSTRAINT original_resource_id_unique IF NOT EXISTS
FOR (r:Original)
REQUIRE r.id IS UNIQUE;

// Constraint for Abstracted resources (hash IDs)
CREATE CONSTRAINT abstracted_resource_id_unique IF NOT EXISTS
FOR (r:Abstracted)
REQUIRE r.id IS UNIQUE;

// Constraint for Tenant (should already exist, but defensive)
CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS
FOR (t:Tenant)
REQUIRE t.id IS UNIQUE;

// ============================================================================
// STEP 2: Add indexes for dual-graph queries
// ============================================================================

// Fast lookup of abstracted resources by their original Azure ID
CREATE INDEX abstracted_by_original_id IF NOT EXISTS
FOR (r:Abstracted)
ON (r.original_id);

// Fast lookup of original resources by their abstracted hash ID
CREATE INDEX original_by_abstracted_id IF NOT EXISTS
FOR (r:Original)
ON (r.abstracted_id);

// Scan-based queries (useful for audit and incremental updates)
CREATE INDEX resource_scan_id IF NOT EXISTS
FOR (r:Resource)
ON (r.scan_id);

// Type-based queries on abstracted resources (common in IaC generation)
CREATE INDEX abstracted_type IF NOT EXISTS
FOR (r:Abstracted)
ON (r.type);

// Composite index for abstracted resources by tenant and type
CREATE INDEX abstracted_tenant_type IF NOT EXISTS
FOR (r:Abstracted)
ON (r.tenant_id, r.type);

// Index on abstracted_id property for quick lookups
CREATE INDEX resource_abstracted_id IF NOT EXISTS
FOR (r:Resource)
ON (r.abstracted_id);

// Index on abstraction_seed property
CREATE INDEX abstracted_seed IF NOT EXISTS
FOR (r:Abstracted)
ON (r.abstraction_seed);

// ============================================================================
// STEP 3: Migration of existing resources (OPTIONAL - only if not rescanning)
// ============================================================================

// NOTE: This step is COMMENTED OUT by default. Operators should:
//   Option A: Rescan tenants with dual-graph mode enabled (RECOMMENDED)
//   Option B: Uncomment and run this migration to convert existing data
//
// If you choose Option B, uncomment the following block:

/*
// Mark all existing Resource nodes as Abstracted (they have abstracted-style IDs)
MATCH (r:Resource)
WHERE NOT r:Original AND NOT r:Abstracted
SET r:Abstracted
SET r.abstracted_id = r.id
SET r.migration_note = "Migrated from single-graph in migration 0010"
RETURN count(r) as resources_marked_abstracted;
*/

// ============================================================================
// STEP 4: Add abstraction metadata to Tenant nodes
// ============================================================================

// This step adds properties to Tenant nodes to store abstraction seeds.
// Actual seed values will be set by the application during first scan.
// We just ensure the properties exist.

MATCH (t:Tenant)
WHERE t.abstraction_seed IS NULL
SET t.seed_algorithm = "sha256-truncated"
RETURN count(t) as tenants_prepared;

// ============================================================================
// VERIFICATION QUERIES (for operators to run manually)
// ============================================================================

// These are provided as examples and should be run separately to verify migration:
//
// 1. Check constraint status:
//    SHOW CONSTRAINTS;
//
// 2. Check index status:
//    SHOW INDEXES;
//
// 3. Count node types:
//    MATCH (r:Resource)
//    RETURN
//      count(CASE WHEN r:Abstracted THEN 1 END) as abstracted_count,
//      count(CASE WHEN r:Original THEN 1 END) as original_count,
//      count(CASE WHEN NOT r:Abstracted AND NOT r:Original THEN 1 END) as unlabeled_count;
//
// 4. Check for orphaned nodes:
//    MATCH (abs:Abstracted)
//    WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->(:Original)
//    RETURN count(abs) as orphaned_abstracted_nodes;
//
// 5. Verify relationship parity:
//    MATCH (orig:Original)-[rel_orig]->(target_orig:Original)
//    WITH count(rel_orig) as original_rel_count
//    MATCH (abs:Abstracted)-[rel_abs]->(target_abs:Abstracted)
//    WITH original_rel_count, count(rel_abs) as abstracted_rel_count
//    RETURN original_rel_count, abstracted_rel_count,
//           original_rel_count - abstracted_rel_count as difference;
