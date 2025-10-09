#!/bin/bash
# Helper script to extract all node IDs for a resource group from Neo4j
# Usage: ./get_rg_node_ids.sh <resource_group_name>

set -e

RG_NAME=${1:-SimuLand}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-azure-grapher-2024}

echo "📊 Extracting node IDs for resource group: $RG_NAME"
echo ""

# Query Neo4j for all resources in the resource group
docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  "MATCH (rg:ResourceGroup {name: '$RG_NAME'})-[:CONTAINS]->(r:Resource)
   RETURN r.id as id" --format plain | \
  grep -v "^id$" | \
  grep -v "^$" | \
  tr '\n' ' '

echo ""
echo ""
echo "✅ Node IDs extracted"
