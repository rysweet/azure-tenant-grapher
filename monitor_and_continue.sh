#!/bin/bash
# Continuous monitoring script - polls tenant scan and continues execution

SCAN_PID=$(pgrep -f "atg scan")
LOG_FILE="logs/autonomous_execution_$(date +%Y%m%d_%H%M%S).log"

echo "Starting continuous monitoring loop..." | tee -a "$LOG_FILE"
echo "Scan PID: $SCAN_PID" | tee -a "$LOG_FILE"
echo "Start time: $(date)" | tee -a "$LOG_FILE"

# Monitor loop
while true; do
    if [ -z "$SCAN_PID" ] || ! kill -0 "$SCAN_PID" 2>/dev/null; then
        echo "Scan process completed at $(date)" | tee -a "$LOG_FILE"
        
        # Check if Neo4j has data
        RESOURCE_COUNT=$(uv run python -c "
import sys
sys.path.insert(0, 'src')
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI', 'bolt://localhost:7688'),
    auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', ''))
)

with driver.session() as session:
    result = session.run('MATCH (r:Resource) RETURN count(r) as count')
    count = result.single()['count']
    print(count)
    
driver.close()
" 2>/dev/null)
        
        echo "Resources discovered: $RESOURCE_COUNT" | tee -a "$LOG_FILE"
        
        if [ "$RESOURCE_COUNT" -gt 0 ]; then
            echo "✅ Scan successful! Proceeding to next phase..." | tee -a "$LOG_FILE"
            ~/.local/bin/imessR "✅ Tenant scan COMPLETE! Discovered $RESOURCE_COUNT resources. Proceeding immediately to parallel agent execution."
            exit 0
        else
            echo "⚠️ Scan completed but no resources found" | tee -a "$LOG_FILE"
            ~/.local/bin/imessR "⚠️ Scan completed but Neo4j is still empty. Investigating..."
            exit 1
        fi
    fi
    
    # Check every 2 minutes
    sleep 120
    echo "Still scanning... $(date)" | tee -a "$LOG_FILE"
done
