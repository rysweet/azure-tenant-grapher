#!/usr/bin/env bash
#
# Architecture-Based Tenant Replication - Helper Script
#
# This script helps you run the complete architecture-based replication workflow.
# It will:
# 1. Verify Neo4j connection and find available subscriptions
# 2. Run the replication orchestrator with appropriate parameters
# 3. Generate comprehensive reports with fidelity validation
#
# Usage:
#   ./scripts/run_architecture_replication.sh
#
# Or with custom parameters:
#   ./scripts/run_architecture_replication.sh \
#       --source-subscription SOURCE_ID \
#       --target-subscription TARGET_ID \
#       --target-instance-count 10

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}Architecture-Based Tenant Replication${NC}"
echo -e "${BLUE}======================================================${NC}"
echo

# Check if Neo4j is running
echo -e "${YELLOW}[1/5] Checking Neo4j connection...${NC}"
if docker ps --filter "name=neo4j" --format "{{.Names}}" 2>/dev/null | grep -q neo4j; then
    echo -e "${GREEN}✓ Neo4j container is running${NC}"
else
    echo -e "${RED}✗ Neo4j container is not running${NC}"
    echo "Please start Neo4j first"
    exit 1
fi

# Check Neo4j credentials
echo -e "\n${YELLOW}[2/5] Verifying Neo4j credentials...${NC}"

# Load from .env file if it exists
if [ -f .env ]; then
    echo "Loading credentials from .env file..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Use environment variables or defaults
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-}"

# If still not found, try to extract from Docker container
if [ -z "$NEO4J_PASSWORD" ]; then
    echo "Attempting to extract password from Neo4j container..."
    NEO4J_AUTH=$(docker exec atg-neo4j env 2>/dev/null | grep "^NEO4J_AUTH=" | cut -d'=' -f2)
    if [ -n "$NEO4J_AUTH" ]; then
        NEO4J_PASSWORD=$(echo "$NEO4J_AUTH" | cut -d'/' -f2)
        echo -e "${GREEN}✓ Password extracted from container${NC}"
    fi
fi

# Final fallback: prompt user
if [ -z "$NEO4J_PASSWORD" ]; then
    echo -e "${YELLOW}Neo4j password not found in .env or container${NC}"
    echo -n "Enter Neo4j password: "
    read -s NEO4J_PASSWORD
    echo
fi

export NEO4J_PASSWORD

# Test connection and query subscriptions
echo -e "\n${YELLOW}[3/5] Querying available subscriptions...${NC}"
python3 << PYEOF
import sys
from neo4j import GraphDatabase

try:
    driver = GraphDatabase.driver(
        "${NEO4J_URI}",
        auth=("${NEO4J_USER}", "${NEO4J_PASSWORD}")
    )

    with driver.session() as session:
        result = session.run("""
            MATCH (r:Resource:Original)
            RETURN DISTINCT r.subscription_id as subscription_id, count(*) as resource_count
            ORDER BY resource_count DESC
            LIMIT 10
        """)

        print("\\nAvailable subscriptions in Neo4j:")
        print("-" * 80)
        subscriptions = []
        for record in result:
            sub_id = record['subscription_id']
            count = record['resource_count']
            subscriptions.append((sub_id, count))
            print(f"  {len(subscriptions)}. {sub_id} ({count} resources)")

        if not subscriptions:
            print("  No subscriptions found in Neo4j!")
            print("  Please scan a source tenant first.")
            sys.exit(1)

        print("-" * 80)

        # Export for shell use
        with open('/tmp/atg_subscriptions.txt', 'w') as f:
            for sub_id, count in subscriptions:
                f.write(f"{sub_id}|{count}\\n")

    driver.close()
    print("\\n✓ Neo4j connection successful")

except Exception as e:
    print(f"\\n✗ Error connecting to Neo4j: {e}", file=sys.stderr)
    print("\\nPlease check your Neo4j credentials and try again.")
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    exit 1
fi

# Get source subscription (from args or interactive)
echo -e "\n${YELLOW}[4/5] Configuring replication parameters...${NC}"

SOURCE_SUBSCRIPTION="$1"
TARGET_SUBSCRIPTION="$2"
INSTANCE_COUNT="${3:-10}"

if [ -z "$SOURCE_SUBSCRIPTION" ]; then
    echo -n "Enter source subscription ID (or number from list above): "
    read SOURCE_INPUT

    # Check if it's a number
    if [[ "$SOURCE_INPUT" =~ ^[0-9]+$ ]]; then
        SOURCE_SUBSCRIPTION=$(awk -F'|' "NR==$SOURCE_INPUT {print \$1}" /tmp/atg_subscriptions.txt)
    else
        SOURCE_SUBSCRIPTION="$SOURCE_INPUT"
    fi
fi

if [ -z "$TARGET_SUBSCRIPTION" ]; then
    # Get current Azure subscription
    CURRENT_SUB=$(az account show --query 'id' -o tsv 2>/dev/null || echo "")

    if [ -n "$CURRENT_SUB" ]; then
        echo -e "${GREEN}✓ Found current Azure subscription: $CURRENT_SUB${NC}"
        echo -n "Use this as target subscription? (Y/n): "
        read USE_CURRENT
        if [ -z "$USE_CURRENT" ] || [ "$USE_CURRENT" = "Y" ] || [ "$USE_CURRENT" = "y" ]; then
            TARGET_SUBSCRIPTION="$CURRENT_SUB"
        fi
    fi

    if [ -z "$TARGET_SUBSCRIPTION" ]; then
        echo -n "Enter target subscription ID: "
        read TARGET_SUBSCRIPTION
    fi
fi

echo
echo "Configuration:"
echo "  Source Subscription: $SOURCE_SUBSCRIPTION"
echo "  Target Subscription: $TARGET_SUBSCRIPTION"
echo "  Instance Count: $INSTANCE_COUNT"
echo

# Create output directory with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="./output/replication_${TIMESTAMP}"

echo -e "${YELLOW}[5/5] Running replication orchestrator...${NC}"
echo "Output directory: $OUTPUT_DIR"
echo

# Run the orchestrator
python3 scripts/architecture_replication_with_fidelity.py \
    --source-subscription "$SOURCE_SUBSCRIPTION" \
    --target-subscription "$TARGET_SUBSCRIPTION" \
    --target-instance-count "$INSTANCE_COUNT" \
    --output-dir "$OUTPUT_DIR" \
    --neo4j-uri "$NEO4J_URI" \
    --neo4j-user "$NEO4J_USER" \
    --neo4j-password "$NEO4J_PASSWORD"

if [ $? -eq 0 ]; then
    echo
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}✓ Replication workflow completed successfully!${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo
    echo "Results saved to: $OUTPUT_DIR"
    echo
    echo "Generated files:"
    ls -1 "$OUTPUT_DIR"
    echo
    echo "View comprehensive report:"
    echo "  cat $OUTPUT_DIR/00_COMPREHENSIVE_REPORT.md"
else
    echo
    echo -e "${RED}======================================================${NC}"
    echo -e "${RED}✗ Replication workflow failed${NC}"
    echo -e "${RED}======================================================${NC}"
    echo
    echo "Check the logs above for error details."
    exit 1
fi
