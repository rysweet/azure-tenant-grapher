#!/bin/bash
# Quick progress checker for source scan

LOG_FILE="demos/iteration_autonomous_001/logs/source_scan.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found!"
    exit 1
fi

echo "📊 Scan Progress Report"
echo "======================="
echo ""
echo "📝 Log lines: $(wc -l < $LOG_FILE)"
echo ""
echo "🔍 Latest activity:"
tail -5 "$LOG_FILE"
echo ""
echo "✅ Completed resources:"
grep -c "Successfully processed resource" "$LOG_FILE" 2>/dev/null || echo "0"
echo ""
echo "❌ Failed resources:"
grep -c "Failed to process resource" "$LOG_FILE" 2>/dev/null || echo "0"
