// ============================================================================
// Dual-Graph Architecture: Example Cypher Queries
// ============================================================================
// This file contains example queries for working with the dual-graph schema
// where resources exist as both Original (Azure IDs) and Abstracted (hash IDs).
//
// Documentation: See docs/DUAL_GRAPH_SCHEMA.md
// ============================================================================

// ============================================================================
// 1. BASIC QUERIES - Getting Resources
// ============================================================================

// Get all abstracted resources (default for IaC generation)
MATCH (r:Resource:Abstracted)
RETURN r.id, r.name, r.type, r.location
ORDER BY r.type, r.name
LIMIT 100;

// Get all original resources (Azure view)
MATCH (r:Resource:Original)
RETURN r.id, r.name, r.type, r.location
ORDER BY r.type, r.name
LIMIT 100;

// Get all resources (both types)
MATCH (r:Resource)
RETURN labels(r) as labels, r.id, r.name, r.type
ORDER BY r.type, r.name
LIMIT 100;

// Filter out Original nodes from mixed queries (backward compatibility)
MATCH (r:Resource)
WHERE NOT r:Original
RETURN r.id, r.name, r.type
LIMIT 100;

// ============================================================================
// 2. CROSS-REFERENCE QUERIES - Linking Original and Abstracted
// ============================================================================

// Get abstracted resource with its original source (via relationship)
MATCH (abs:Abstracted {id: $abstracted_id})-[rel:SCAN_SOURCE_NODE]->(orig:Original)
RETURN abs, rel, orig;

// Get abstracted resource with its original source (via property - faster)
MATCH (abs:Abstracted {id: $abstracted_id})
MATCH (orig:Original {id: abs.original_id})
RETURN abs, orig;

// Get original resource with all its abstracted versions (usually 1, but handles edge cases)
MATCH (orig:Original {id: $original_id})<-[:SCAN_SOURCE_NODE]-(abs:Abstracted)
RETURN orig, collect(abs) as abstracted_versions;

// Find resources with bidirectional reference
MATCH (abs:Abstracted)
WHERE abs.original_id IS NOT NULL
MATCH (orig:Original {id: abs.original_id})
WHERE orig.abstracted_id = abs.id
RETURN abs.id as abstracted_id,
       orig.id as original_id,
       "Properly linked" as status;

// ============================================================================
// 3. TOPOLOGY QUERIES - Graph Structure
// ============================================================================

// Get full abstracted graph topology for a tenant
MATCH (abs:Abstracted)-[rel]->(target:Abstracted)
WHERE abs.tenant_id = $tenant_id
RETURN abs.id, abs.name, abs.type,
       type(rel) as relationship_type,
       target.id, target.name, target.type
ORDER BY abs.type, abs.name;

// Get full original graph topology for a tenant
MATCH (orig:Original)-[rel]->(target:Original)
WHERE orig.tenant_id = $tenant_id
RETURN orig.id, orig.name, orig.type,
       type(rel) as relationship_type,
       target.id, target.name, target.type
ORDER BY orig.type, orig.name;

// Find all resources of a specific type in abstracted graph
MATCH (r:Abstracted {type: "Microsoft.Compute/virtualMachines"})
WHERE r.tenant_id = $tenant_id
RETURN r.id, r.name, r.location, r.resource_group
ORDER BY r.name;

// Get resource with all its relationships (abstracted view)
MATCH (r:Abstracted {id: $resource_id})
OPTIONAL MATCH (r)-[rel_out]->(target)
OPTIONAL MATCH (source)-[rel_in]->(r)
RETURN r,
       collect(DISTINCT {type: type(rel_out), target: target}) as outgoing,
       collect(DISTINCT {type: type(rel_in), source: source}) as incoming;

// ============================================================================
// 4. COMPARISON QUERIES - Finding Differences Between Graphs
// ============================================================================

// Compare relationship counts between graphs
MATCH (orig:Original)-[rel_orig]->(target_orig:Original)
WITH count(rel_orig) as original_rel_count
MATCH (abs:Abstracted)-[rel_abs]->(target_abs:Abstracted)
WITH original_rel_count, count(rel_abs) as abstracted_rel_count
RETURN original_rel_count,
       abstracted_rel_count,
       original_rel_count - abstracted_rel_count as difference,
       CASE
         WHEN original_rel_count = abstracted_rel_count
         THEN "Graphs in sync"
         ELSE "Graph mismatch detected"
       END as status;

// Find relationships in original graph missing from abstracted graph
MATCH (orig1:Original)-[rel:CONNECTED_TO]->(orig2:Original)
MATCH (abs1:Abstracted {original_id: orig1.id})
MATCH (abs2:Abstracted {original_id: orig2.id})
WHERE NOT (abs1)-[:CONNECTED_TO]->(abs2)
RETURN orig1.id as source_original,
       orig2.id as target_original,
       abs1.id as source_abstracted,
       abs2.id as target_abstracted,
       "Missing in abstracted graph" as issue;

// Find resources in original graph missing from abstracted graph
MATCH (orig:Original)
WHERE NOT EXISTS {
  MATCH (abs:Abstracted {original_id: orig.id})
}
RETURN orig.id, orig.name, orig.type,
       "No abstracted counterpart" as issue;

// Find resources in abstracted graph missing from original graph
MATCH (abs:Abstracted)
WHERE NOT EXISTS {
  MATCH (orig:Original {id: abs.original_id})
}
RETURN abs.id, abs.name, abs.type,
       "No original counterpart" as issue;

// ============================================================================
// 5. VALIDATION QUERIES - Data Quality and Consistency
// ============================================================================

// Find orphaned abstracted resources (no SCAN_SOURCE_NODE relationship)
MATCH (abs:Abstracted)
WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->(:Original)
RETURN abs.id, abs.name, abs.type, abs.scan_id,
       "Orphaned abstracted node" as issue
ORDER BY abs.type, abs.name;

// Find orphaned original resources (no SCAN_SOURCE_NODE relationship)
MATCH (orig:Original)
WHERE NOT (orig)<-[:SCAN_SOURCE_NODE]-(:Abstracted)
RETURN orig.id, orig.name, orig.type, orig.scan_id,
       "Orphaned original node" as issue
ORDER BY orig.type, orig.name;

// Find resources with mismatched bidirectional references
MATCH (abs:Abstracted)
WHERE abs.original_id IS NOT NULL
MATCH (orig:Original {id: abs.original_id})
WHERE orig.abstracted_id IS NULL OR orig.abstracted_id <> abs.id
RETURN abs.id as abstracted_id,
       abs.original_id as abstracted_original_ref,
       orig.id as original_id,
       orig.abstracted_id as original_abstracted_ref,
       "Mismatched references" as issue;

// Check for hash collisions in abstracted IDs
MATCH (abs:Abstracted)
WITH abs.abstracted_id as hash_id, collect(abs) as resources
WHERE size(resources) > 1
RETURN hash_id,
       [r in resources | r.original_id] as original_ids,
       [r in resources | r.name] as names,
       size(resources) as collision_count
ORDER BY collision_count DESC;

// Verify resource counts by type
MATCH (r:Resource)
RETURN r.type,
       count(CASE WHEN r:Abstracted THEN 1 END) as abstracted_count,
       count(CASE WHEN r:Original THEN 1 END) as original_count,
       count(CASE WHEN NOT r:Abstracted AND NOT r:Original THEN 1 END) as unlabeled_count
ORDER BY r.type;

// Check abstraction seed consistency for a tenant
MATCH (t:Tenant {id: $tenant_id})
MATCH (r:Abstracted {tenant_id: $tenant_id})
RETURN t.abstraction_seed as tenant_seed,
       count(DISTINCT r.abstraction_seed) as unique_seeds,
       count(r) as resource_count,
       CASE
         WHEN count(DISTINCT r.abstraction_seed) = 1
         THEN "Consistent"
         ELSE "Inconsistent"
       END as status;

// ============================================================================
// 6. IAC GENERATION QUERIES - What IaC Traverser Should Use
// ============================================================================

// Get all abstracted resources for IaC generation (starting point)
MATCH (r:Abstracted)
WHERE r.tenant_id = $tenant_id
  AND NOT r:Original  // Defensive filter
RETURN r
ORDER BY r.type, r.name;

// Get abstracted resources by subscription
MATCH (s:Subscription {id: $subscription_id})<-[:CONTAINS]-(r:Abstracted)
WHERE NOT r:Original
RETURN r
ORDER BY r.type, r.name;

// Get abstracted resources by resource group
MATCH (rg:ResourceGroup {id: $resource_group_id})<-[:CONTAINS]-(r:Abstracted)
WHERE NOT r:Original
RETURN r
ORDER BY r.type, r.name;

// Get abstracted resource with all dependencies (for IaC ordering)
MATCH (r:Abstracted {id: $resource_id})
OPTIONAL MATCH (r)-[:DEPENDS_ON*]->(dep:Abstracted)
WHERE NOT dep:Original
RETURN r, collect(DISTINCT dep) as dependencies;

// Get all abstracted VMs with their network dependencies
MATCH (vm:Abstracted {type: "Microsoft.Compute/virtualMachines"})
WHERE vm.tenant_id = $tenant_id AND NOT vm:Original
OPTIONAL MATCH (vm)-[:USES_SUBNET]->(subnet:Abstracted)
OPTIONAL MATCH (subnet)-[:SECURED_BY]->(nsg:Abstracted)
RETURN vm.id, vm.name,
       subnet.id as subnet_id,
       nsg.id as nsg_id;

// ============================================================================
// 7. SCAN AND AUDIT QUERIES - Tracking Changes
// ============================================================================

// Find all resources created in a specific scan
MATCH (r:Resource {scan_id: $scan_id})
RETURN labels(r) as node_labels,
       r.id, r.name, r.type,
       exists((r)-[:SCAN_SOURCE_NODE]->()) as is_abstracted,
       exists((r)<-[:SCAN_SOURCE_NODE]-()) as is_original;

// Get scan summary
MATCH (r:Resource {scan_id: $scan_id})
RETURN count(CASE WHEN r:Abstracted THEN 1 END) as abstracted_count,
       count(CASE WHEN r:Original THEN 1 END) as original_count,
       count(DISTINCT r.type) as unique_resource_types,
       min(r.created_at) as scan_start,
       max(r.updated_at) as scan_end;

// Find resources updated in the last hour
MATCH (r:Resource)
WHERE r.updated_at > datetime() - duration('PT1H')
RETURN labels(r) as labels, r.id, r.name, r.type, r.updated_at
ORDER BY r.updated_at DESC;

// Compare two scans to find changes
MATCH (r1:Resource {scan_id: $scan_id_1})
MATCH (r2:Resource {scan_id: $scan_id_2})
WHERE r1.abstracted_id = r2.abstracted_id
  AND r1:Abstracted AND r2:Abstracted
  AND r1.properties <> r2.properties
RETURN r1.id, r1.name, r1.type,
       "Properties changed" as change_type;

// ============================================================================
// 8. DEBUGGING QUERIES - Troubleshooting Issues
// ============================================================================

// Check if a specific Azure resource ID exists in the database
MATCH (r:Resource)
WHERE r.id = $azure_resource_id OR r.original_id = $azure_resource_id
RETURN labels(r) as labels, r.id, r.abstracted_id, r.original_id;

// Find resources without required properties
MATCH (r:Abstracted)
WHERE r.abstracted_id IS NULL
   OR r.abstraction_seed IS NULL
   OR r.original_id IS NULL
RETURN r.id, r.name, r.type,
       CASE
         WHEN r.abstracted_id IS NULL THEN "Missing abstracted_id"
         WHEN r.abstraction_seed IS NULL THEN "Missing abstraction_seed"
         WHEN r.original_id IS NULL THEN "Missing original_id"
       END as issue;

// Get detailed node information
MATCH (r:Resource {id: $resource_id})
RETURN labels(r) as labels,
       properties(r) as properties,
       size([(r)-->() | 1]) as outgoing_relationships,
       size([(r)<--() | 1]) as incoming_relationships;

// Find resources with duplicate names (potential naming conflicts)
MATCH (r:Abstracted)
WHERE r.tenant_id = $tenant_id
WITH r.name as name, r.type as type, collect(r) as resources
WHERE size(resources) > 1
RETURN name, type, size(resources) as count,
       [res in resources | res.id] as ids
ORDER BY count DESC;

// Check database statistics
CALL db.stats.retrieve("GRAPH COUNTS")
YIELD data
RETURN data;

// ============================================================================
// 9. ADMINISTRATIVE QUERIES - Maintenance and Cleanup
// ============================================================================

// Count all nodes by label
MATCH (n)
RETURN labels(n) as labels, count(n) as count
ORDER BY count DESC;

// Count all relationships by type
MATCH ()-[r]->()
RETURN type(r) as relationship_type, count(r) as count
ORDER BY count DESC;

// Find unused indexes
CALL db.indexes()
YIELD name, state, populationPercent, type
WHERE state <> "ONLINE" OR populationPercent < 100
RETURN name, state, populationPercent, type;

// Delete resources from a specific scan (CAUTION: destructive)
// MATCH (r:Resource {scan_id: $scan_id})
// DETACH DELETE r;

// Remove orphaned abstracted nodes (CAUTION: verify first)
// MATCH (abs:Abstracted)
// WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->(:Original)
// DETACH DELETE abs;

// ============================================================================
// 10. PERFORMANCE TESTING QUERIES
// ============================================================================

// Profile abstracted query performance
PROFILE MATCH (r:Abstracted)
WHERE r.tenant_id = $tenant_id
RETURN count(r);

// Profile query with label filter
PROFILE MATCH (r:Resource)
WHERE NOT r:Original AND r.tenant_id = $tenant_id
RETURN count(r);

// Profile query with property filter
PROFILE MATCH (r:Resource)
WHERE r.abstracted_id IS NOT NULL AND r.tenant_id = $tenant_id
RETURN count(r);

// Profile relationship traversal in abstracted graph
PROFILE MATCH (r:Abstracted)-[rel*1..3]->(target:Abstracted)
WHERE r.tenant_id = $tenant_id
RETURN count(DISTINCT r);

// Profile bidirectional lookup
PROFILE MATCH (abs:Abstracted {id: $abstracted_id})
MATCH (orig:Original {id: abs.original_id})
RETURN abs, orig;

// ============================================================================
// 11. ADVANCED QUERIES - Complex Analysis
// ============================================================================

// Find isolated resources (no relationships)
MATCH (r:Abstracted)
WHERE r.tenant_id = $tenant_id
  AND NOT (r)--()
RETURN r.id, r.name, r.type,
       "Isolated resource" as note;

// Find resources with the most dependencies
MATCH (r:Abstracted)
WHERE r.tenant_id = $tenant_id
OPTIONAL MATCH (r)-[:DEPENDS_ON]->(dep)
WITH r, count(dep) as dep_count
WHERE dep_count > 0
RETURN r.id, r.name, r.type, dep_count
ORDER BY dep_count DESC
LIMIT 20;

// Find circular dependencies
MATCH path = (r:Abstracted)-[:DEPENDS_ON*]->(r)
WHERE r.tenant_id = $tenant_id
RETURN [node in nodes(path) | node.id] as circular_dependency_chain,
       length(path) as chain_length
ORDER BY chain_length;

// Find resources that would be affected if a specific resource is deleted
MATCH (r:Abstracted {id: $resource_id})
OPTIONAL MATCH (dependent)-[:DEPENDS_ON*]->(r)
WHERE dependent:Abstracted
RETURN r.id, r.name,
       collect(DISTINCT dependent.id) as dependent_resources,
       size(collect(DISTINCT dependent)) as dependent_count;

// Get network topology (all connected resources)
MATCH path = (start:Abstracted)-[:CONNECTED_TO|USES_SUBNET|SECURED_BY*1..5]->(end:Abstracted)
WHERE start.id = $resource_id
  AND NOT start:Original
  AND NOT end:Original
RETURN DISTINCT end.id, end.name, end.type,
       [rel in relationships(path) | type(rel)] as connection_path
LIMIT 50;

// ============================================================================
// End of queries
// ============================================================================
