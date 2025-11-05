// Migration 0010 - Dual-Graph Architecture Schema
// Constraints and indexes for dual-graph architecture (Original + Abstracted nodes)

CREATE CONSTRAINT original_resource_id_unique IF NOT EXISTS
FOR (r:Original)
REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT abstracted_resource_id_unique IF NOT EXISTS
FOR (r:Abstracted)
REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS
FOR (t:Tenant)
REQUIRE t.id IS UNIQUE;

CREATE INDEX abstracted_by_original_id IF NOT EXISTS
FOR (r:Abstracted)
ON (r.original_id);

CREATE INDEX original_by_abstracted_id IF NOT EXISTS
FOR (r:Original)
ON (r.abstracted_id);

CREATE INDEX resource_scan_id IF NOT EXISTS
FOR (r:Resource)
ON (r.scan_id);

CREATE INDEX abstracted_type IF NOT EXISTS
FOR (r:Abstracted)
ON (r.type);

CREATE INDEX abstracted_tenant_type IF NOT EXISTS
FOR (r:Abstracted)
ON (r.tenant_id, r.type);

CREATE INDEX resource_abstracted_id IF NOT EXISTS
FOR (r:Resource)
ON (r.abstracted_id);

CREATE INDEX abstracted_seed IF NOT EXISTS
FOR (r:Abstracted)
ON (r.abstraction_seed);

// Add seed_algorithm property to Tenant nodes (actual seed values set during first scan)
MATCH (t:Tenant)
WHERE t.abstraction_seed IS NULL
SET t.seed_algorithm = "sha256-truncated"
RETURN count(t) as tenants_prepared;
