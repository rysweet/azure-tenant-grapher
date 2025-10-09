#!/bin/bash
# Step 1: Generate IaC from Source Tenant (DefenderATEVET17)
#
# This script demonstrates using the ATG CLI to generate Infrastructure-as-Code
# for a specific resource group by querying Neo4j and passing node IDs.

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SOURCE_TENANT_ID="3cd87a41-1f61-4aef-a212-cefdecd9a2d1"
RESOURCE_GROUP="SimuLand"
IAC_FORMAT="terraform"
OUTPUT_DIR="./output/iac"
NEO4J_PASSWORD=${NEO4J_PASSWORD:-azure-grapher-2024}

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Step 1: Generate IaC from Source Tenant                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}📋 Demo Configuration:${NC}"
echo "  Source Tenant: DefenderATEVET17"
echo "  Tenant ID: $SOURCE_TENANT_ID"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  IaC Format: $IAC_FORMAT"
echo "  Output Directory: $OUTPUT_DIR"
echo ""

# Step 1.1: Query Neo4j for resource count
echo -e "${GREEN}→ Querying Neo4j for $RESOURCE_GROUP resources...${NC}"
RESOURCE_COUNT=$(docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  "MATCH (rg:ResourceGroup {name: '$RESOURCE_GROUP'})-[:CONTAINS]->(r:Resource)
   RETURN count(r) as count" --format plain | grep -v "^count$" | grep -v "^$" | head -1)

echo "  Found: $RESOURCE_COUNT resources in $RESOURCE_GROUP"
echo ""

# Step 1.2: Get sample of resource types
echo -e "${GREEN}→ Sample resource types in $RESOURCE_GROUP:${NC}"
docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  "MATCH (rg:ResourceGroup {name: '$RESOURCE_GROUP'})-[:CONTAINS]->(r:Resource)
   RETURN DISTINCT r.type as Type, count(*) as Count
   ORDER BY Count DESC
   LIMIT 10" --format plain
echo ""

# Step 1.3: Extract node IDs
echo -e "${GREEN}→ Extracting resource IDs from Neo4j...${NC}"
NODE_IDS=$(docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  "MATCH (rg:ResourceGroup {name: '$RESOURCE_GROUP'})-[:CONTAINS]->(r:Resource)
   RETURN r.id as id" --format plain | \
  grep -v "^id$" | \
  grep -v "^$" | \
  head -10)  # Start with just 10 resources for testing

echo "  Extracted $(echo "$NODE_IDS" | wc -l | tr -d ' ') node IDs (limited to 10 for demo)"
echo ""

#Step 1.4: Build the generate-iac command
echo -e "${GREEN}→ Building ATG CLI command...${NC}"
echo ""
echo -e "${BLUE}Command:${NC}"
echo "uv run atg generate-iac \\"
echo "  --tenant-id $SOURCE_TENANT_ID \\"
echo "  --format $IAC_FORMAT \\"
echo "  --output $OUTPUT_DIR \\"

# Build node-id arguments
NODE_ID_ARGS=""
while IFS= read -r node_id; do
  NODE_ID_ARGS="$NODE_ID_ARGS --node-id \"$node_id\""
done <<< "$NODE_IDS"

echo "$NODE_ID_ARGS" | head -3  # Show first 3 for brevity
echo "  ... (and $(echo "$NODE_IDS" | wc -l | tr -d ' ') total --node-id arguments)"
echo ""

# Step 1.5: Create output directory
mkdir -p "$OUTPUT_DIR"

# Step 1.6: Execute IaC generation
echo -e "${GREEN}→ Generating IaC templates...${NC}"
echo ""

# Build the full command
CMD="uv run atg generate-iac --tenant-id $SOURCE_TENANT_ID --format $IAC_FORMAT --output $OUTPUT_DIR"
while IFS= read -r node_id; do
  CMD="$CMD --node-id \"$node_id\""
done <<< "$NODE_IDS"

# Execute
eval $CMD

echo ""
echo -e "${GREEN}✅ IaC Generation Complete!${NC}"
echo ""

# Step 1.7: Show generated files
echo -e "${YELLOW}📁 Generated Files:${NC}"
ls -lh "$OUTPUT_DIR" || echo "  No files generated (check for errors above)"
echo ""

echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Next Step: ./02_deploy.sh                                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
