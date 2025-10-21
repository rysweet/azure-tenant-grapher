#!/bin/bash
#
# Autonomous Tenant Replication Loop
# Runs continuously until 100% fidelity achieved
#

set -euo pipefail

PROJECT_ROOT="/Users/ryan/src/msec/atg-0723/azure-tenant-grapher"
cd "$PROJECT_ROOT"

# Configuration
SOURCE_SUB="9b00bc5e-9abc-45de-9958-02a9d9277b16"  # DefenderATEVET17
TARGET_SUB="c190c55a-9ab2-4b1e-92c4-cc8b1a032285"  # DefenderATEVET12
DEMOS_DIR="$PROJECT_ROOT/demos"
LOG_DIR="$PROJECT_ROOT/logs"
IMESSAGE_CMD="$HOME/.local/bin/imessR"

# Find latest iteration
find_latest_iteration() {
    ls -d "$DEMOS_DIR"/iteration* 2>/dev/null | \
        sed 's/.*iteration//' | \
        sort -n | \
        tail -1 || echo "99"
}

# Send iMessage
send_message() {
    if [ -x "$IMESSAGE_CMD" ]; then
        $IMESSAGE_CMD "$1" 2>/dev/null || true
    fi
}

# Get Neo4j counts
get_neo4j_counts() {
    local sub_id=$1
    local count=$(docker exec azure-tenant-grapher-neo4j-1 \
        cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-neo4j}" \
        "MATCH (r:Resource) WHERE r.subscription_id = '$sub_id' RETURN count(r) as count" 2>/dev/null | \
        grep -E '^\d+' | head -1 || echo "0")
    echo "${count:-0}"
}

# Calculate fidelity
calculate_fidelity() {
    local source=$1
    local target=$2
    if [ "$source" -gt 0 ]; then
        echo "scale=2; $target * 100 / $source" | bc
    else
        echo "0"
    fi
}

# Main loop
main() {
    echo "=================================================================================================="
    echo "AUTONOMOUS TENANT REPLICATION LOOP - STARTING"
    echo "=================================================================================================="
    echo "Source: DefenderATEVET17 ($SOURCE_SUB)"
    echo "Target: DefenderATEVET12 ($TARGET_SUB)"
    echo "Time: $(date)"
    echo "=================================================================================================="

    send_message "🚀 Autonomous replication loop starting"

    CONSECUTIVE_PASSES=0
    LOOP_COUNT=0

    while true; do
        LOOP_COUNT=$((LOOP_COUNT + 1))
        CURRENT_ITER=$(find_latest_iteration)
        NEXT_ITER=$((CURRENT_ITER + 1))

        echo ""
        echo "=================================================================================="
        echo "LOOP $LOOP_COUNT - Iteration $NEXT_ITER"
        echo "Time: $(date)"
        echo "=================================================================================="

        # Get Neo4j metrics
        echo "Querying Neo4j for resource counts..."
        SOURCE_COUNT=$(get_neo4j_counts "$SOURCE_SUB")
        TARGET_COUNT=$(get_neo4j_counts "$TARGET_SUB")
        FIDELITY=$(calculate_fidelity "$SOURCE_COUNT" "$TARGET_COUNT")

        echo "Source resources: $SOURCE_COUNT"
        echo "Target resources: $TARGET_COUNT"
        echo "Fidelity: $FIDELITY%"
        echo "Consecutive passes: $CONSECUTIVE_PASSES"

        # Check if objective achieved
        if (( $(echo "$FIDELITY >= 95" | bc -l) )) && [ "$CONSECUTIVE_PASSES" -ge 3 ]; then
            echo ""
            echo "🎉🎉🎉 OBJECTIVE ACHIEVED! 🎉🎉🎉"
            echo "Fidelity: $FIDELITY%"
            echo "Consecutive passes: $CONSECUTIVE_PASSES"
            send_message "✅ OBJECTIVE ACHIEVED! Fidelity: $FIDELITY%, Consecutive passes: $CONSECUTIVE_PASSES"
            break
        fi

        # Generate iteration
        echo ""
        echo "Generating iteration $NEXT_ITER..."
        ITER_DIR="$DEMOS_DIR/iteration$NEXT_ITER"

        if uv run atg generate-iac \
            --resource-filters "resourceGroup=~'(?i).*(simuland|SimuLand).*'" \
            --resource-group-prefix "ITERATION${NEXT_ITER}_" \
            --target-subscription "$TARGET_SUB" \
            --skip-name-validation \
            --skip-conflict-check \
            --output "$ITER_DIR" 2>&1 | tee "$LOG_DIR/iteration${NEXT_ITER}_generate.log"; then
            echo "✅ Generation succeeded"
        else
            echo "❌ Generation failed"
            send_message "❌ Iteration $NEXT_ITER generation failed"
            echo "Waiting 60s before retry..."
            sleep 60
            continue
        fi

        # Validate
        echo ""
        echo "Validating iteration $NEXT_ITER..."
        cd "$ITER_DIR"

        # Set terraform environment variables for target subscription
        export ARM_SUBSCRIPTION_ID="$TARGET_SUB"

        terraform init > "$LOG_DIR/iteration${NEXT_ITER}_init.log" 2>&1

        if terraform validate -json > "$LOG_DIR/iteration${NEXT_ITER}_validate.json" 2>&1; then
            VALID=$(jq -r '.valid' "$LOG_DIR/iteration${NEXT_ITER}_validate.json")
            if [ "$VALID" = "true" ]; then
                echo "✅ Validation passed"
                CONSECUTIVE_PASSES=$((CONSECUTIVE_PASSES + 1))

                # Deploy
                echo ""
                echo "Deploying iteration $NEXT_ITER..."
                send_message "🚀 Deploying iteration $NEXT_ITER (Fidelity: $FIDELITY%)"

                if terraform plan -out=tfplan > "$LOG_DIR/iteration${NEXT_ITER}_plan.log" 2>&1; then
                    echo "✅ Plan succeeded"

                    if terraform apply -auto-approve tfplan > "$LOG_DIR/iteration${NEXT_ITER}_apply.log" 2>&1; then
                        echo "✅ Apply succeeded"
                        send_message "✅ Iteration $NEXT_ITER deployed successfully! Fidelity: $FIDELITY%"
                    else
                        echo "❌ Apply failed"
                        send_message "❌ Iteration $NEXT_ITER apply failed"

                        # Extract errors for analysis
                        grep -i "error" "$LOG_DIR/iteration${NEXT_ITER}_apply.log" | head -10 > "$LOG_DIR/iteration${NEXT_ITER}_errors.txt"

                        echo "Waiting 5 minutes before next iteration..."
                        sleep 300
                    fi
                else
                    echo "❌ Plan failed"
                    send_message "❌ Iteration $NEXT_ITER plan failed"
                    sleep 300
                fi
            else
                echo "❌ Validation failed"
                CONSECUTIVE_PASSES=0

                # Extract validation errors
                jq -r '.diagnostics[]? | "\(.severity): \(.summary)"' "$LOG_DIR/iteration${NEXT_ITER}_validate.json" \
                    > "$LOG_DIR/iteration${NEXT_ITER}_validation_errors.txt"

                ERROR_COUNT=$(wc -l < "$LOG_DIR/iteration${NEXT_ITER}_validation_errors.txt")
                send_message "⚠️ Iteration $NEXT_ITER validation failed: $ERROR_COUNT errors"

                echo "Waiting 5 minutes before next iteration..."
                sleep 300
            fi
        else
            echo "❌ Validation command failed"
            CONSECUTIVE_PASSES=0
            sleep 300
        fi

        cd "$PROJECT_ROOT"

        # Brief pause between iterations
        sleep 30
    done

    echo ""
    echo "=================================================================================================="
    echo "AUTONOMOUS LOOP COMPLETE"
    echo "=================================================================================================="
}

# Run main loop
main "$@"
