#!/bin/bash
# Monitor Source Tenant Scan Progress
# Created: 2025-10-20 (Autonomous Demo)

set -euo pipefail

source .env

echo "=== Source Tenant Scan Monitor ==="
echo "Timestamp: $(date -Iseconds)"
echo ""

# Check if scan process is running
SCAN_PID=$(ps aux | grep "[a]tg scan" | awk '{print $2}' | head -1)
if [ -n "$SCAN_PID" ]; then
    echo "✅ Scan Process: RUNNING (PID: $SCAN_PID)"
else
    echo "❌ Scan Process: NOT RUNNING"
fi
echo ""

# Check log file size
if [ -f "demos/iteration_autonomous_001/logs/source_scan.log" ]; then
    LOG_LINES=$(wc -l < demos/iteration_autonomous_001/logs/source_scan.log)
    LOG_SIZE=$(du -h demos/iteration_autonomous_001/logs/source_scan.log | cut -f1)
    echo "📄 Log File: $LOG_LINES lines ($LOG_SIZE)"
    echo ""
    echo "Last 5 log lines:"
    tail -5 demos/iteration_autonomous_001/logs/source_scan.log | sed 's/^/  /'
else
    echo "❌ Log file not found"
fi
echo ""

# Check Neo4j node count
echo "=== Neo4j Database Status ==="
NEO4J_COUNT=$(docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
    "MATCH (n) RETURN count(n) as total;" 2>/dev/null | tail -1 || echo "0")
echo "📊 Total Nodes: $NEO4J_COUNT"

# Check if spec file generated
echo ""
echo "=== Spec File Status ==="
LATEST_SPEC=$(ls -t specs/*.yaml 2>/dev/null | head -1)
if [ -n "$LATEST_SPEC" ]; then
    echo "✅ Spec File: $LATEST_SPEC"
    echo "   Size: $(du -h "$LATEST_SPEC" | cut -f1)"
    echo "   Modified: $(stat -c %y "$LATEST_SPEC" | cut -d'.' -f1)"
else
    echo "⏳ Spec File: Not generated yet"
fi

echo ""
echo "=== Estimated Progress ==="
# Assuming 1632 resources discovered, estimate progress
EXPECTED_RESOURCES=1632
if [ "$NEO4J_COUNT" -gt 0 ] && [ "$NEO4J_COUNT" -lt "$EXPECTED_RESOURCES" ]; then
    PROGRESS=$((NEO4J_COUNT * 100 / EXPECTED_RESOURCES))
    echo "Progress: ~${PROGRESS}% ($NEO4J_COUNT / $EXPECTED_RESOURCES nodes)"
elif [ "$NEO4J_COUNT" -ge "$EXPECTED_RESOURCES" ]; then
    echo "Progress: 100% (Complete!)"
else
    echo "Progress: Calculating..."
fi
