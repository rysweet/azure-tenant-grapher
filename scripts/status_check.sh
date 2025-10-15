#!/usr/bin/env bash
#
# Quick status check script for Azure Tenant Grapher
# Shows: git status, iteration count, running processes, recent docs
#

set -euo pipefail

PROJECT_ROOT="/Users/ryan/src/msec/atg-0723/azure-tenant-grapher"
cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════════════════════"
echo "  AZURE TENANT GRAPHER - STATUS CHECK"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Git status
echo "📦 GIT STATUS:"
echo "  Branch: $(git branch --show-current)"
echo "  Last commit: $(git log -1 --oneline)"
echo "  Commits today: $(git log --oneline --since='1 day ago' | wc -l | tr -d ' ')"
echo ""

# Iterations
echo "🔄 ITERATIONS:"
ITERATION_COUNT=$(ls -1d demos/iteration* 2>/dev/null | wc -l | tr -d ' ')
LATEST_ITERATION=$(ls -1d demos/iteration* 2>/dev/null | tail -1 | xargs basename 2>/dev/null || echo "none")
echo "  Total iterations: $ITERATION_COUNT"
echo "  Latest: $LATEST_ITERATION"
if [ -f "demos/continuous_iteration_status.json" ]; then
    VALIDATION_PASSES=$(python3 -c "import json; print(json.load(open('demos/continuous_iteration_status.json'))['validation_passes'])" 2>/dev/null || echo "0")
    echo "  Validation passes: $VALIDATION_PASSES"
fi
echo ""

# Running processes
echo "🏃 RUNNING PROCESSES:"
SCAN_COUNT=$(ps aux | grep "[u]v run atg scan" | wc -l | tr -d ' ')
MONITOR_COUNT=$(ps aux | grep "[c]ontinuous_iteration_monitor" | wc -l | tr -d ' ')
WORKSTREAM_COUNT=$(ps aux | grep "[p]arallel_workstreams" | wc -l | tr -d ' ')
echo "  Scan processes: $SCAN_COUNT"
echo "  Monitor processes: $MONITOR_COUNT"
echo "  Workstream processes: $WORKSTREAM_COUNT"
echo ""

# Neo4j
echo "🗄️  NEO4J:"
if docker ps | grep -q "azure-tenant-grapher-neo4j"; then
    NEO4J_STATUS=$(docker ps --filter "name=azure-tenant-grapher-neo4j" --format "{{.Status}}" | head -1)
    echo "  Status: $NEO4J_STATUS"
else
    echo "  Status: Not running"
fi
echo ""

# Documentation
echo "📚 DOCUMENTATION:"
DOC_COUNT=$(ls -1 demos/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "  Total docs: $DOC_COUNT"
echo "  Recent docs:"
ls -1t demos/*.md 2>/dev/null | head -5 | while read doc; do
    echo "    - $(basename "$doc")"
done
echo ""

# Status files
echo "📊 STATUS FILES:"
if [ -f "demos/continuous_iteration_status.json" ]; then
    echo "  ✅ continuous_iteration_status.json"
fi
if [ -f "demos/workstream_status.json" ]; then
    echo "  ✅ workstream_status.json"
fi
if [ -f "/tmp/scan_output.log" ]; then
    SCAN_SIZE=$(wc -l < /tmp/scan_output.log | tr -d ' ')
    echo "  ✅ scan_output.log ($SCAN_SIZE lines)"
fi
echo ""

# Quick recommendations
echo "💡 QUICK ACTIONS:"
if [ "$SCAN_COUNT" -gt 0 ]; then
    echo "  📝 Scan running - check: tail -f /tmp/scan_output.log"
fi
if [ -f "demos/SESSION_HANDOFF_2025-10-15.md" ]; then
    echo "  📖 Read handoff: cat demos/SESSION_HANDOFF_2025-10-15.md | less"
fi
if [ "$LATEST_ITERATION" != "none" ]; then
    echo "  🔍 Check latest: cd demos/$LATEST_ITERATION && terraform validate"
fi
echo "  🚀 Generate next: uv run atg generate-iac --help"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  For full status: cat demos/CONTINUOUS_OPERATION_STATUS_FINAL.md"
echo "════════════════════════════════════════════════════════════════"
