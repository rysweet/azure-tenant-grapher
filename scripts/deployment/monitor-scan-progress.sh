#!/bin/bash
# Monitor Azure Tenant Scan Progress

echo "🏴‍☠️ Monitoring Azure Tenant Scan Progress"
echo "=========================================="

while true; do
    clear
    echo "🏴‍☠️ Azure Tenant Scan Progress"
    echo "==============================="
    echo "Time: $(date '+%H:%M:%S')"
    echo ""

    # Check Neo4j resource count
    COUNT=$(uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

try:
    with driver.session() as session:
        result = session.run('MATCH (r:Resource) RETURN count(r) as total')
        print(result.single()['total'])
except:
    print('0')
finally:
    driver.close()
" 2>&1 | tail -1)

    echo "Resources in Neo4j: $COUNT"

    # Check SCAN_SOURCE_NODE count
    SCAN_COUNT=$(uv run python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

try:
    with driver.session() as session:
        result = session.run('MATCH ()-[r:SCAN_SOURCE_NODE]->() RETURN count(r) as total')
        print(result.single()['total'])
except:
    print('0')
finally:
    driver.close()
" 2>&1 | tail -1)

    echo "SCAN_SOURCE_NODE: $SCAN_COUNT"

    # Check scan log
    echo ""
    echo "Recent scan activity:"
    tail -5 azure-scan.log | grep -E "Processing|resources|Discovered" || echo "  (waiting for updates...)"

    echo ""
    echo "Press Ctrl+C to stop monitoring"
    echo "Scan running in background (PID: $(pgrep -f 'azure-tenant-grapher scan' || echo 'N/A'))"

    sleep 10
done
