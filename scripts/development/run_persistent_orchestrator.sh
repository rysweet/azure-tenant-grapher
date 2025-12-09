#!/bin/bash
#
# Persistent Orchestrator Runner
#
# This script ensures the autonomous orchestrator keeps running until the objective is achieved.
# It will restart the orchestrator if it crashes and send status updates.
#

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_PATH="$REPO_ROOT/scripts/autonomous_replication_orchestrator.py"
STATUS_FILE="$REPO_ROOT/demos/orchestrator_status.json"
LOG_FILE="$REPO_ROOT/logs/orchestrator_runner.log"
IMESSAGE_TOOL="$HOME/.local/bin/imessR"

# Create logs directory
mkdir -p "$REPO_ROOT/logs"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Send iMessage
send_message() {
    if [ -x "$IMESSAGE_TOOL" ]; then
        "$IMESSAGE_TOOL" "$*" || true
    fi
}

log "=================================="
log "PERSISTENT ORCHESTRATOR RUNNER"
log "=================================="
log "Script: $SCRIPT_PATH"
log "Status: $STATUS_FILE"
log "=================================="

send_message "🤖 Starting persistent replication orchestrator"

# Run orchestrator in a loop
attempt=1
max_attempts=100

while [ $attempt -le $max_attempts ]; do
    log "Attempt $attempt/$max_attempts: Starting orchestrator..."

    # Run the orchestrator
    cd "$REPO_ROOT"
    if python3 "$SCRIPT_PATH"; then
        log "Orchestrator completed successfully!"
        send_message "✅ Replication orchestrator completed successfully!"

        # Check if objective was achieved
        if [ -f "$STATUS_FILE" ]; then
            if grep -q '"objective_achieved": true' "$STATUS_FILE" 2>/dev/null; then
                log "🎉 OBJECTIVE ACHIEVED! Exiting."
                send_message "🎉 OBJECTIVE ACHIEVED! Tenant replication complete!"
                exit 0
            fi
        fi

        log "Orchestrator finished but objective not achieved. Restarting in 60 seconds..."
        sleep 60
    else
        exit_code=$?
        log "Orchestrator exited with code $exit_code. Restarting in 30 seconds..."
        send_message "⚠️ Orchestrator crashed (exit $exit_code). Restarting..."
        sleep 30
    fi

    attempt=$((attempt + 1))
done

log "Reached maximum attempts ($max_attempts). Stopping."
send_message "⚠️ Orchestrator stopped after $max_attempts attempts"
