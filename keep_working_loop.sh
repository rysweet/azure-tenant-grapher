#!/bin/bash
# This script keeps checking and working - NEVER STOPS

echo "�� Keep Working Loop Starting..."
COUNTER=0

while true; do
    COUNTER=$((COUNTER + 1))
    echo "=== Check #$COUNTER @ $(date +%H:%M:%S) ==="

    # Check if monitoring loop is still running
    if ! pgrep -f "monitor_and_fix_loop.py" > /dev/null; then
        echo "⚠️ Monitoring loop died! Restarting..."
        ~/.local/bin/imessR "⚠️ Monitoring loop stopped - restarting it now"
        nohup python3 monitor_and_fix_loop.py >> logs/continuous_monitoring.log 2>&1 &
    else
        echo "✅ Monitoring loop is running (PID: $(pgrep -f monitor_and_fix_loop.py))"
    fi

    # Check latest iteration status
    LATEST_ITER=$(ls -d demos/iteration* 2>/dev/null | sed 's/demos\/iteration//' | sort -n | tail -1)
    if [ ! -z "$LATEST_ITER" ]; then
        echo "📊 Latest iteration: $LATEST_ITER"

        if [ -f "demos/iteration${LATEST_ITER}/main.tf.json" ]; then
            SIZE=$(wc -l < "demos/iteration${LATEST_ITER}/main.tf.json")
            echo "   File exists: $SIZE lines"
        else
            echo "   File not yet created"
        fi
    fi

    # Check logs
    if [ -f "logs/continuous_monitoring.log" ]; then
        LAST_LINE=$(tail -1 logs/continuous_monitoring.log)
        echo "   Last log: $LAST_LINE"
    fi

    # Sleep and continue
    sleep 15
done
