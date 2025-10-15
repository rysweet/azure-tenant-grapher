#!/bin/bash
#
# Persistent Monitor - Keeps running and checking status
# This script monitors iterations and triggers actions but does NOT exit
#

REPO_ROOT="/Users/ryan/src/msec/atg-0723/azure-tenant-grapher"
cd "$REPO_ROOT" || exit 1

IMESS_R="$HOME/.local/bin/imessR"

# Function to send iMessage
send_message() {
    if [ -x "$IMESS_R" ]; then
        "$IMESS_R" "$1" 2>/dev/null || true
    fi
}

# Function to get latest iteration
get_latest_iteration() {
    find demos -maxdepth 1 -type d -name "iteration*" | \
        sed 's/.*iteration//' | \
        sort -n | \
        tail -1
}

# Function to check if terraform is running
check_terraform_running() {
    pgrep -f "terraform apply" > /dev/null
}

# Function to check iteration validation status
check_validation() {
    local iter_dir="$1"
    if [ ! -d "$iter_dir" ]; then
        echo "NOT_EXIST"
        return
    fi
    
    cd "$iter_dir" || return
    
    # Run terraform validate
    if ! terraform init -backend=false > /dev/null 2>&1; then
        echo "INIT_FAILED"
        return
    fi
    
    if terraform validate -json 2>/dev/null | jq -r '.valid' 2>/dev/null | grep -q "true"; then
        echo "PASS"
    else
        echo "FAIL"
    fi
    
    cd "$REPO_ROOT" || return
}

send_message "🔄 Persistent monitor started. Will check status every 2 minutes and report."

iteration_count=0
while true; do
    iteration_count=$((iteration_count + 1))
    
    # Get latest iteration
    latest=$(get_latest_iteration)
    iter_dir="demos/iteration${latest}"
    
    # Check validation status
    validation=$(check_validation "$iter_dir")
    
    # Check if terraform is running
    if check_terraform_running; then
        terraform_status="RUNNING"
    else
        terraform_status="IDLE"
    fi
    
    # Get Neo4j stats
    source_count=$(uv run python -c "
import os
from neo4j import GraphDatabase
uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
password = os.getenv('NEO4J_PASSWORD', '')
if not password:
    with open('.env') as f:
        for line in f:
            if 'NEO4J_PASSWORD=' in line:
                password = line.split('=', 1)[1].strip().strip('\"')
                break
driver = GraphDatabase.driver(uri, auth=('neo4j', password))
with driver.session() as session:
    result = session.run('MATCH (r:Resource) WHERE r.subscription_id = \$sub RETURN count(r) as count', sub='9b00bc5e-9abc-45de-9958-02a9d9277b16')
    print(result.single()['count'])
driver.close()
" 2>/dev/null || echo "0")
    
    target_count=$(uv run python -c "
import os
from neo4j import GraphDatabase
uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
password = os.getenv('NEO4J_PASSWORD', '')
if not password:
    with open('.env') as f:
        for line in f:
            if 'NEO4J_PASSWORD=' in line:
                password = line.split('=', 1)[1].strip().strip('\"')
                break
driver = GraphDatabase.driver(uri, auth=('neo4j', password))
with driver.session() as session:
    result = session.run('MATCH (r:Resource) WHERE r.subscription_id = \$sub RETURN count(r) as count', sub='c190c55a-9ab2-4b1e-92c4-cc8b1a032285')
    print(result.single()['count'])
driver.close()
" 2>/dev/null || echo "0")
    
    # Calculate fidelity
    if [ "$source_count" -gt 0 ]; then
        fidelity=$(echo "scale=1; ($target_count * 100) / $source_count" | bc)
    else
        fidelity="0.0"
    fi
    
    # Log status
    timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    echo "[$timestamp] Check #$iteration_count: Iteration $latest, Validation: $validation, Terraform: $terraform_status, Fidelity: ${fidelity}% ($target_count/$source_count)"
    
    # Send periodic updates (every 10 checks = ~20 minutes)
    if [ $((iteration_count % 10)) -eq 0 ]; then
        send_message "Status check #$iteration_count: Latest iteration $latest, Validation: $validation, Terraform: $terraform_status, Fidelity: ${fidelity}% ($target_count/$source_count resources)"
    fi
    
    # Check if objective achieved
    if [ "$validation" = "PASS" ] && [ "$(echo "$fidelity > 95" | bc)" -eq 1 ]; then
        send_message "🎉 OBJECTIVE ACHIEVED! Validation: PASS, Fidelity: ${fidelity}%. Monitor stopping."
        echo "OBJECTIVE ACHIEVED!"
        break
    fi
    
    # Sleep for 2 minutes
    sleep 120
done

send_message "✓ Persistent monitor completed successfully."
