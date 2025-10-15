#!/bin/bash
###############################################################################
# Master Orchestrator for Azure Tenant Grapher Autonomous Replication
#
# This script runs continuously until the objective in demos/OBJECTIVE.md is achieved.
# It coordinates parallel workstreams, monitors progress, and spawns agents as needed.
###############################################################################

set -euo pipefail

PROJECT_ROOT="/Users/ryan/src/msec/atg-0723/azure-tenant-grapher"
IMESS_TOOL="$HOME/.local/bin/imessR"
STATE_DIR="$PROJECT_ROOT/.claude/runtime/orchestrator"
ITERATION_DIR="$PROJECT_ROOT/demos"
AGENT_LOG_DIR="$STATE_DIR/agent_logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create state directories
mkdir -p "$STATE_DIR" "$AGENT_LOG_DIR"

# Send iMessage update
send_imessage() {
    local message="$1"
    if [ -x "$IMESS_TOOL" ]; then
        "$IMESS_TOOL" "$message" 2>/dev/null || true
    fi
}

# Log with timestamp
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo -e "${timestamp} [${level}] ${message}"
}

# Get Neo4j resource counts
get_resource_counts() {
    cd "$PROJECT_ROOT"
    source .env
    
    python3 <<PYTHON
from py2neo import Graph
import os

graph = Graph('bolt://localhost:7688', auth=('neo4j', os.environ.get('NEO4J_PASSWORD', 'password')))

# Count source tenant resources
source_count = graph.run('''
MATCH (r:Resource)
WHERE r.subscription_id = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
RETURN count(r) as count
''').evaluate()

# Count target tenant resources
target_count = graph.run('''
MATCH (r:Resource)
WHERE r.subscription_id = "c190c55a-9ab2-4b1e-92c4-cc8b1a032285"
RETURN count(r) as count
''').evaluate()

fidelity = (target_count / source_count * 100) if source_count > 0 else 0

print(f"{source_count},{target_count},{fidelity:.1f}")
PYTHON
}

# Get latest iteration number
get_latest_iteration() {
    local max_iter=0
    for dir in "$ITERATION_DIR"/iteration*; do
        if [ -d "$dir" ]; then
            local num=$(basename "$dir" | grep -oE '[0-9]+' || echo "0")
            if [ "$num" -gt "$max_iter" ]; then
                max_iter=$num
            fi
        fi
    done
    echo "$max_iter"
}

# Check if iteration is complete
check_iteration_complete() {
    local iter_num="$1"
    local iter_dir="$ITERATION_DIR/iteration${iter_num}"
    
    if [ ! -d "$iter_dir" ]; then
        echo "not_found"
        return
    fi
    
    if [ -f "$iter_dir/terraform.tfstate" ]; then
        echo "complete"
    elif [ -f "$iter_dir/tfplan" ]; then
        echo "applying"
    elif [ -d "$iter_dir/.terraform" ]; then
        echo "planning"
    elif [ -f "$iter_dir/main.tf.json" ]; then
        echo "generated"
    else
        echo "empty"
    fi
}

# Spawn a copilot subagent in background
spawn_agent() {
    local agent_name="$1"
    local prompt="$2"
    local log_file="$AGENT_LOG_DIR/${agent_name}_$(date +%s).log"
    
    log "INFO" "${BLUE}Spawning agent: ${agent_name}${NC}"
    
    # Run copilot in background
    (
        cd "$PROJECT_ROOT"
        copilot --allow-all-tools -p "$prompt" > "$log_file" 2>&1
        local exit_code=$?
        log "INFO" "${GREEN}Agent ${agent_name} completed with exit code ${exit_code}${NC}"
        echo "$exit_code" > "${log_file}.exitcode"
    ) &
    
    local agent_pid=$!
    echo "$agent_pid" > "$STATE_DIR/${agent_name}.pid"
    
    log "INFO" "Agent ${agent_name} started with PID ${agent_pid}"
    send_imessage "🤖 Started agent: ${agent_name}"
    
    echo "$agent_pid"
}

# Check if agent is still running
check_agent() {
    local agent_name="$1"
    local pid_file="$STATE_DIR/${agent_name}.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo "not_running"
        return
    fi
    
    local pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo "running"
    else
        echo "complete"
    fi
}

# Evaluate objective achievement
evaluate_objective() {
    log "INFO" "${BLUE}Evaluating objective...${NC}"
    
    # Get resource counts
    local counts=$(get_resource_counts)
    local source_count=$(echo "$counts" | cut -d',' -f1)
    local target_count=$(echo "$counts" | cut -d',' -f2)
    local fidelity=$(echo "$counts" | cut -d',' -f3)
    
    # Get latest iteration
    local latest_iter=$(get_latest_iteration)
    
    # Check if fidelity >= 95%
    local fidelity_achieved=false
    if (( $(echo "$fidelity >= 95.0" | bc -l) )); then
        fidelity_achieved=true
    fi
    
    # Check last 3 iterations for completion
    local consecutive_passes=0
    for i in $(seq "$latest_iter" -1 $(($latest_iter - 2))); do
        if [ "$i" -le 0 ]; then
            break
        fi
        local status=$(check_iteration_complete "$i")
        if [ "$status" = "complete" ]; then
            ((consecutive_passes++))
        else
            break
        fi
    done
    
    # Objective is achieved if fidelity >= 95% AND 3 consecutive passes
    local objective_achieved=false
    if [ "$fidelity_achieved" = true ] && [ "$consecutive_passes" -ge 3 ]; then
        objective_achieved=true
    fi
    
    log "INFO" "Source Resources: $source_count"
    log "INFO" "Target Resources: $target_count"
    log "INFO" "Fidelity: $fidelity%"
    log "INFO" "Latest Iteration: $latest_iter"
    log "INFO" "Consecutive Passes: $consecutive_passes"
    log "INFO" "Objective Achieved: $objective_achieved"
    
    if [ "$objective_achieved" = true ]; then
        echo "achieved"
    else
        echo "in_progress"
    fi
}

# Main orchestration loop
main() {
    log "INFO" "${GREEN}🚀 Master Orchestrator Started${NC}"
    send_imessage "🚀 Master Orchestrator started - working until objective achieved"
    
    local iteration_count=0
    local last_status_update=0
    
    while true; do
        ((iteration_count++))
        log "INFO" "${YELLOW}========== Orchestration Cycle $iteration_count ==========${NC}"
        
        # 1. Evaluate objective
        local objective_status=$(evaluate_objective)
        
        if [ "$objective_status" = "achieved" ]; then
            log "INFO" "${GREEN}🎉 OBJECTIVE ACHIEVED!${NC}"
            send_imessage "🎉 OBJECTIVE ACHIEVED! Tenant replication complete."
            exit 0
        fi
        
        # 2. Get current state
        local latest_iter=$(get_latest_iteration)
        local iter_status=$(check_iteration_complete "$latest_iter")
        
        log "INFO" "Latest iteration: $latest_iter (status: $iter_status)"
        
        # 3. Check active agents
        for pid_file in "$STATE_DIR"/*.pid; do
            if [ -f "$pid_file" ]; then
                local agent_name=$(basename "$pid_file" .pid)
                local agent_status=$(check_agent "$agent_name")
                
                if [ "$agent_status" = "complete" ]; then
                    log "INFO" "${GREEN}✅ Agent ${agent_name} completed${NC}"
                    rm -f "$pid_file"
                    send_imessage "✅ Agent ${agent_name} completed"
                fi
            fi
        done
        
        # 4. Progress current iteration if needed
        case "$iter_status" in
            "complete")
                log "INFO" "${GREEN}Iteration $latest_iter complete, generating next...${NC}"
                
                # Generate next iteration
                local next_iter=$((latest_iter + 1))
                log "INFO" "Generating iteration $next_iter..."
                
                cd "$PROJECT_ROOT"
                if uv run atg generate-iac \
                    --resource-filters "resourceGroup=~'(?i).*(simuland|SimuLand).*'" \
                    --resource-group-prefix "ITERATION${next_iter}_" \
                    --skip-name-validation \
                    --output "demos/iteration${next_iter}" 2>&1 | tee "$STATE_DIR/generate_${next_iter}.log"; then
                    
                    log "INFO" "${GREEN}✅ Generated iteration $next_iter${NC}"
                    send_imessage "✅ Generated iteration $next_iter"
                else
                    log "ERROR" "${RED}❌ Failed to generate iteration $next_iter${NC}"
                    send_imessage "❌ Failed to generate iteration $next_iter"
                fi
                ;;
                
            "generated")
                log "INFO" "Iteration $latest_iter generated, initializing terraform..."
                
                cd "$ITERATION_DIR/iteration${latest_iter}"
                terraform init > "$STATE_DIR/init_${latest_iter}.log" 2>&1
                ;;
                
            "planning")
                log "INFO" "Iteration $latest_iter initialized, creating plan..."
                
                cd "$ITERATION_DIR/iteration${latest_iter}"
                terraform plan -out=tfplan > "$STATE_DIR/plan_${latest_iter}.log" 2>&1
                ;;
                
            "applying")
                log "INFO" "Iteration $latest_iter planned, applying..."
                
                cd "$ITERATION_DIR/iteration${latest_iter}"
                terraform apply tfplan > "$STATE_DIR/apply_${latest_iter}.log" 2>&1 &
                local apply_pid=$!
                echo "$apply_pid" > "$STATE_DIR/terraform_apply_${latest_iter}.pid"
                
                log "INFO" "Terraform apply started with PID $apply_pid"
                send_imessage "🔄 Deploying iteration $latest_iter..."
                ;;
        esac
        
        # 5. Send periodic status updates
        local current_time=$(date +%s)
        if [ $((current_time - last_status_update)) -ge 600 ]; then  # Every 10 minutes
            local counts=$(get_resource_counts)
            local fidelity=$(echo "$counts" | cut -d',' -f3)
            
            send_imessage "🔄 Cycle $iteration_count | Fidelity: ${fidelity}% | Iteration: $latest_iter"
            last_status_update=$current_time
        fi
        
        # 6. Sleep before next cycle
        sleep 30  # Check every 30 seconds
    done
}

# Trap signals for clean shutdown
trap 'log "INFO" "⏸️  Interrupted by user"; send_imessage "⏸️  Orchestrator stopped"; exit 1' INT TERM

# Run main loop
main
