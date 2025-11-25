#!/bin/bash
#
# Persistent Master Replication Engine Runner
#
# This script ensures the master engine keeps running continuously.
# It will restart on crashes and only stop when objective is achieved.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE_SCRIPT="$REPO_ROOT/scripts/master_replication_engine.py"
STATE_FILE="$REPO_ROOT/demos/engine_state.json"
LOG_FILE="$REPO_ROOT/logs/engine_runner.log"
IMESSAGE_TOOL="$HOME/.local/bin/imessR"

# Create logs directory
mkdir -p "$REPO_ROOT/logs"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Send iMessage
send_msg() {
    if [ -x "$IMESSAGE_TOOL" ]; then
        "$IMESSAGE_TOOL" "$*" 2>/dev/null || true
    fi
}

# Check if objective is achieved
check_objective() {
    if [ -f "$STATE_FILE" ]; then
        if grep -q '"objective_achieved": true' "$STATE_FILE" 2>/dev/null; then
            return 0  # Achieved
        fi
    fi
    return 1  # Not achieved
}

log "=========================================="
log "PERSISTENT REPLICATION ENGINE RUNNER"
log "=========================================="
log "Engine: $ENGINE_SCRIPT"
log "State: $STATE_FILE"
log "=========================================="

send_msg "🤖 Starting persistent replication engine"

# Main loop
attempt=1
max_attempts=200

while [ $attempt -le $max_attempts ]; do
    log "Attempt $attempt/$max_attempts: Launching master engine..."

    # Check if objective already achieved
    if check_objective; then
        log "🎉 OBJECTIVE ALREADY ACHIEVED! Exiting."
        send_msg "🎉 Objective already achieved!"
        exit 0
    fi

    # Run the engine
    cd "$REPO_ROOT"

    # Load environment
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi

    # Run engine
    if python3 "$ENGINE_SCRIPT"; then
        log "Engine completed normally"

        # Check if objective was achieved
        if check_objective; then
            log "🎉 OBJECTIVE ACHIEVED! Exiting successfully."
            send_msg "🎉 OBJECTIVE ACHIEVED! Tenant replication complete!"
            exit 0
        fi

        log "Engine finished but objective not achieved. Restarting in 30 seconds..."
        send_msg "🔄 Engine finished cycle $attempt. Restarting..."
        sleep 30
    else
        exit_code=$?
        log "Engine exited with code $exit_code"

        if [ $exit_code -eq 130 ]; then
            log "Engine interrupted by user (SIGINT). Exiting."
            send_msg "⏸️ Engine stopped by user"
            exit 130
        fi

        log "Restarting engine in 30 seconds..."
        send_msg "⚠️ Engine crashed (exit $exit_code). Restarting..."
        sleep 30
    fi

    attempt=$((attempt + 1))
done

log "Reached maximum attempts ($max_attempts). Stopping."
send_msg "⚠️ Engine stopped after $max_attempts attempts"
exit 1
