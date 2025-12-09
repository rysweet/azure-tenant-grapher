#!/bin/bash
# Auto-Complete Deployment Script
# Monitors scan completion and automatically regenerates/deploys with full dataset

set -e

echo "🏴‍☠️ Auto-Complete Deployment Monitor"
echo "======================================"
echo ""
echo "This script will:"
echo "1. Monitor Azure scan completion"
echo "2. Regenerate IaC with complete SCAN_SOURCE_NODE data"
echo "3. Deploy with improved coverage"
echo ""

# Configuration
TARGET_RESOURCES=1500  # Expected final resource count
CHECK_INTERVAL=60      # Check every 60 seconds
MAX_WAIT=7200         # Max 2 hours

# Function to check Neo4j
check_neo4j() {
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
    result = session.run('MATCH (r:Resource) RETURN count(r) as total')
    total = result.single()['total']

    result = session.run('MATCH ()-[r:SCAN_SOURCE_NODE]->() RETURN count(r) as scan')
    scan = result.single()['scan']

    print(f'{total},{scan}')

driver.close()
" 2>&1 | tail -1
}

# Monitor scan progress
elapsed=0
last_count=0
stable_count=0

while [ $elapsed -lt $MAX_WAIT ]; do
    # Get current counts
    counts=$(check_neo4j)
    current_resources=$(echo $counts | cut -d',' -f1)
    current_scan=$(echo $counts | cut -d',' -f2)

    coverage=$(echo "scale=1; $current_scan * 100 / $current_resources" | bc)

    echo "[$(date +%H:%M:%S)] Resources: $current_resources | SCAN_SOURCE_NODE: $current_scan | Coverage: ${coverage}%"

    # Check if count is stable (scan might be complete)
    if [ "$current_resources" -eq "$last_count" ]; then
        stable_count=$((stable_count + 1))
        echo "  Stable for ${stable_count} checks"

        if [ $stable_count -ge 3 ]; then
            echo ""
            echo "✅ Scan appears complete (stable for 3 checks)"
            break
        fi
    else
        stable_count=0
    fi

    last_count=$current_resources

    # Check if target reached
    if [ "$current_resources" -ge "$TARGET_RESOURCES" ]; then
        echo ""
        echo "✅ Target resource count reached ($TARGET_RESOURCES)"
        break
    fi

    sleep $CHECK_INTERVAL
    elapsed=$((elapsed + CHECK_INTERVAL))
done

echo ""
echo "======================================"
echo "Scan Status Summary"
echo "======================================"
echo "Resources: $current_resources"
echo "SCAN_SOURCE_NODE: $current_scan"
echo "Coverage: ${coverage}%"
echo ""

if [ "$current_resources" -lt 1000 ]; then
    echo "⚠️  Scan still in progress (< 1000 resources)"
    echo "Recommend waiting for completion before regenerating"
    exit 1
fi

echo "✅ Sufficient data for improved deployment"
echo ""
echo "======================================"
echo "Step 2: Regenerating IaC"
echo "======================================"

# Regenerate with full dataset
cd /home/azureuser/src/azure-tenant-grapher
mkdir -p ./outputs/deployment-improved

uv run azure-tenant-grapher generate-iac \
  --format terraform \
  --output ./outputs/deployment-improved \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --naming-suffix v2 \
  --skip-conflict-check

echo ""
echo "======================================"
echo "Generation Complete"
echo "======================================"

# Check results
if [ -f "./outputs/deployment-improved/generation_report.txt" ]; then
    echo "📊 Generation Report:"
    cat ./outputs/deployment-improved/generation_report.txt

    echo ""
    echo "✅ IaC regenerated with improved SCAN_SOURCE_NODE coverage"
    echo ""
    echo "To deploy:"
    echo "  cd ./outputs/deployment-improved"
    echo "  terraform init"
    echo "  terraform plan"
    echo "  terraform apply"
else
    echo "❌ Generation failed - check logs"
    exit 1
fi

echo ""
echo "🏴‍☠️ Auto-deployment preparation complete!"
