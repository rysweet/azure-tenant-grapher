#!/bin/bash
# Deployment Test Script for Issue #570 Fix Verification
# Tests that SCAN_SOURCE_NODE relationships are preserved in layer operations

set -e

echo "🏴‍☠️ Issue #570 Deployment Test Script"
echo "======================================="
echo ""

# Function to query Neo4j
query_neo4j() {
    uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    result = session.run('$1')
    record = result.single()
    if record:
        print(record[0])
    else:
        print('0')

driver.close()
"
}

# Step 1: Verify scan completed
echo "Step 1: Verifying scan data..."
RESOURCE_COUNT=$(query_neo4j "MATCH (r:Resource) RETURN count(r)")
echo "  Resources in Neo4j: $RESOURCE_COUNT"

if [ "$RESOURCE_COUNT" -lt "100" ]; then
    echo "  ❌ Not enough resources. Scan may still be running."
    echo "  Wait for scan to complete and try again."
    exit 1
fi
echo "  ✅ Scan data available"

# Step 2: Verify SCAN_SOURCE_NODE relationships exist in base graph
echo ""
echo "Step 2: Verifying SCAN_SOURCE_NODE in base graph..."
SCAN_SOURCE_COUNT=$(query_neo4j "MATCH ()-[r:SCAN_SOURCE_NODE]->() RETURN count(r)")
echo "  SCAN_SOURCE_NODE relationships: $SCAN_SOURCE_COUNT"

if [ "$SCAN_SOURCE_COUNT" -lt "10" ]; then
    echo "  ❌ Not enough SCAN_SOURCE_NODE relationships"
    exit 1
fi
echo "  ✅ SCAN_SOURCE_NODE relationships created during scan"

# Step 3: Create test layer
echo ""
echo "Step 3: Creating test layer..."
uv run azure-tenant-grapher layer create test-scan-source \
    --name "SCAN_SOURCE_NODE Test Layer" \
    --description "Testing PR #571 fix for Issue #570" \
    --tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
    --yes

echo "  ✅ Test layer created"

# Step 4: Add resources to test layer (manually via Neo4j)
echo ""
echo "Step 4: Adding resources to test layer..."
uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    # Add 50 resources to test layer that have SCAN_SOURCE_NODE
    result = session.run('''
        MATCH (orig:Resource:Original)
        WHERE orig.layer_id IS NULL
        WITH orig LIMIT 50
        MATCH (abs:Resource)-[:SCAN_SOURCE_NODE]->(orig)
        WHERE abs.layer_id IS NULL
        SET abs.layer_id = \"test-scan-source\"
        RETURN count(abs) as added
    ''')
    added = result.single()['added']
    print(f'  Added {added} resources to test-scan-source layer')

    # Verify SCAN_SOURCE_NODE preserved
    result = session.run('''
        MATCH (abs:Resource {layer_id: \"test-scan-source\"})-[:SCAN_SOURCE_NODE]->(orig)
        RETURN count(*) as scan_count
    ''')
    scan_count = result.single()['scan_count']
    print(f'  SCAN_SOURCE_NODE in layer: {scan_count}')

driver.close()
"

echo "  ✅ Resources added to test layer"

# Step 5: Copy layer to test SCAN_SOURCE_NODE preservation (THE FIX!)
echo ""
echo "Step 5: Testing layer copy (PR #571 fix)..."
uv run azure-tenant-grapher layer copy test-scan-source test-copy-result \
    --name "Copy Test Result" \
    --description "Result of PR #571 fix test" \
    --yes

echo "  ✅ Layer copied"

# Step 6: Verify SCAN_SOURCE_NODE preserved in copied layer
echo ""
echo "Step 6: Verifying SCAN_SOURCE_NODE preserved..."
COPIED_SCAN_SOURCE=$(uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    result = session.run('''
        MATCH (abs:Resource {layer_id: \"test-copy-result\"})-[:SCAN_SOURCE_NODE]->(orig)
        RETURN count(*) as copied_scan_count
    ''')
    count = result.single()['copied_scan_count']
    print(count)

driver.close()
")

echo "  SCAN_SOURCE_NODE in copied layer: $COPIED_SCAN_SOURCE"

if [ "$COPIED_SCAN_SOURCE" -eq "0" ]; then
    echo "  ❌ FAIL: SCAN_SOURCE_NODE relationships NOT preserved!"
    echo "  The fix didn't work - relationships should have been copied"
    exit 1
fi

echo "  ✅ SUCCESS: SCAN_SOURCE_NODE relationships PRESERVED!"
echo "  PR #571 fix is WORKING correctly!"

# Step 7: Generate IaC to test smart import
echo ""
echo "Step 7: Generating IaC with smart import..."
mkdir -p ./test-deployment-verification
uv run azure-tenant-grapher generate-iac \
    --format terraform \
    --scan-target \
    --output ./test-deployment-verification \
    --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285

echo "  ✅ IaC generated"

# Step 8: Check classification results
echo ""
echo "Step 8: Checking smart import classification..."
if [ -f "./test-deployment-verification/generation_report.txt" ]; then
    grep -E "NEW|EXACT_MATCH|DRIFTED" ./test-deployment-verification/generation_report.txt | head -10
    echo "  ✅ Classification report available"
else
    echo "  ⚠️ Generation report not found"
fi

echo ""
echo "======================================="
echo "🎉 DEPLOYMENT TEST COMPLETE!"
echo "======================================="
echo ""
echo "Summary:"
echo "  ✅ SCAN_SOURCE_NODE relationships preserved in layer copy"
echo "  ✅ PR #571 fix verified working"
echo "  ✅ Ready for full deployment"
echo ""
echo "Next: Deploy to Azure with:"
echo "  cd ./test-deployment-verification"
echo "  terraform init && terraform apply"
echo ""
