#!/bin/bash

# Monitor script for parallel tenant scans

echo "=== SCAN MONITORING DASHBOARD ==="
echo "Generated: $(date)"
echo

echo "📊 SOURCE SCAN (DefenderATEVET17)"
echo "  Log file: demos/iteration_autonomous_001/logs/source_scan_v2.log"
echo "  Lines: $(wc -l < demos/iteration_autonomous_001/logs/source_scan_v2.log 2>/dev/null || echo '0')"
echo "  Last update: $(stat -c %y demos/iteration_autonomous_001/logs/source_scan_v2.log 2>/dev/null | cut -d'.' -f1 || echo 'N/A')"
echo

echo "📊 TARGET SCAN (DefenderATEVET12)"
echo "  Log file: demos/iteration_autonomous_001/logs/target_scan_baseline.log"
echo "  Lines: $(wc -l < demos/iteration_autonomous_001/logs/target_scan_baseline.log 2>/dev/null || echo '0')"
echo "  Last update: $(stat -c %y demos/iteration_autonomous_001/logs/target_scan_baseline.log 2>/dev/null | cut -d'.' -f1 || echo 'N/A')"
echo

echo "🔍 NEO4J DATABASE STATUS"
source .env
NODES=$(docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "MATCH (n) RETURN count(n) as count" 2>/dev/null | grep -E '^[0-9]+$' | head -1 || echo "0")
echo "  Total nodes: $NODES"
echo

echo "📝 RECENT ERRORS"
echo "  Source scan:"
grep -i "error\|failed\|exception" demos/iteration_autonomous_001/logs/source_scan_v2.log 2>/dev/null | tail -3 | sed 's/^/    /' || echo "    No recent errors"
echo "  Target scan:"
grep -i "error\|failed\|exception" demos/iteration_autonomous_001/logs/target_scan_baseline.log 2>/dev/null | tail -3 | sed 's/^/    /' || echo "    No recent errors"
echo

echo "✅ Monitor complete!"
