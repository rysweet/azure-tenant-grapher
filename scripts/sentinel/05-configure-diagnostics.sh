#!/bin/bash
# 05-configure-diagnostics.sh - Configure Diagnostic Settings
#
# Purpose: Configure diagnostic settings for Azure resources
# Exit Codes:
#   0 - Success (all or partial success)
#   11 - Diagnostic configuration failed

set -euo pipefail

# Get script directory and load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# ========================
# Configuration
# ========================

load_config_env

# Output paths
OUTPUT_DIR="${OUTPUT_DIR:-./output}"
WORKSPACE_ID_FILE="${OUTPUT_DIR}/workspace-id.txt"
RESOURCES_FILE="${OUTPUT_DIR}/resources-list.json"
DIAGNOSTICS_REPORT_FILE="${OUTPUT_DIR}/diagnostics-report.json"

log_info "========================================="
log_info "Module 05: Configure Diagnostic Settings"
log_info "========================================="

# ========================
# Read workspace ID from previous module
# ========================

if [[ ! -f "$WORKSPACE_ID_FILE" ]]; then
    log_error "Workspace ID file not found: $WORKSPACE_ID_FILE"
    log_error "Module 02 must run before Module 05"
    exit 11
fi

WORKSPACE_ID=$(cat "$WORKSPACE_ID_FILE")

if [[ -z "$WORKSPACE_ID" ]]; then
    log_error "Workspace ID is empty in file: $WORKSPACE_ID_FILE"
    exit 11
fi

log_info "Workspace ID: $WORKSPACE_ID"

# ========================
# Read resources list
# ========================

if [[ ! -f "$RESOURCES_FILE" ]]; then
    log_warn "Resources list file not found: $RESOURCES_FILE"
    log_warn "No resources to configure diagnostic settings for"

    # Write empty report
    cat > "$DIAGNOSTICS_REPORT_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "resources_processed": 0,
  "resources_configured": 0,
  "resources_skipped": 0,
  "resources_failed": 0,
  "resources": [],
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    log_success "Module 05 completed (no resources to process)"
    exit 0
fi

# Parse resources JSON
RESOURCE_COUNT=$(jq '. | length' "$RESOURCES_FILE" 2>/dev/null || echo "0")

if [[ "$RESOURCE_COUNT" -eq 0 ]]; then
    log_info "No resources in list file"

    cat > "$DIAGNOSTICS_REPORT_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "resources_processed": 0,
  "resources_configured": 0,
  "resources_skipped": 0,
  "resources_failed": 0,
  "resources": [],
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    log_success "Module 05 completed (no resources to process)"
    exit 0
fi

log_info "Resources to process: $RESOURCE_COUNT"

# ========================
# Configuration options
# ========================

DIAGNOSTIC_SETTING_NAME="${DIAGNOSTIC_SETTING_NAME:-diagnostic-to-sentinel}"
DIAGNOSTIC_LOG_CATEGORIES="${DIAGNOSTIC_LOG_CATEGORIES:-[\"AllLogs\"]}"

# Rate limiting configuration (Fix #8)
BATCH_SIZE=10
BATCH_DELAY=5  # seconds between batches

log_info "Diagnostic setting name: $DIAGNOSTIC_SETTING_NAME"
log_info "Log categories: $DIAGNOSTIC_LOG_CATEGORIES"
log_info "Rate limiting: process $BATCH_SIZE resources, pause ${BATCH_DELAY}s"

# ========================
# Configure diagnostic settings for each resource
# ========================

RESOURCES_CONFIGURED=0
RESOURCES_SKIPPED=0
RESOURCES_FAILED=0

RESOURCE_RESULTS="["
FIRST_RESOURCE=true

for i in $(seq 0 $((RESOURCE_COUNT - 1))); do
    RESOURCE_ID=$(jq -r ".[$i].id" "$RESOURCES_FILE")
    RESOURCE_TYPE=$(jq -r ".[$i].type" "$RESOURCES_FILE")

    if [[ -z "$RESOURCE_ID" ]] || [[ "$RESOURCE_ID" == "null" ]]; then
        log_warn "Invalid resource at index $i (empty ID)"
        RESOURCES_FAILED=$((RESOURCES_FAILED + 1))
        continue
    fi

    log_info "[$((i + 1))/$RESOURCE_COUNT] Processing: $RESOURCE_ID"
    log_debug "  Type: $RESOURCE_TYPE"

    RESOURCE_STATUS="unknown"
    RESOURCE_ERROR=""

    # Check if diagnostic settings already exist (idempotency)
    if diagnostic_setting_exists "$RESOURCE_ID" "$DIAGNOSTIC_SETTING_NAME"; then
        log_info "  Diagnostic settings already exist (skipping)"
        RESOURCES_SKIPPED=$((RESOURCES_SKIPPED + 1))
        RESOURCE_STATUS="skipped"
    else
        if is_dry_run; then
            dry_run_message "  Would configure diagnostic settings for: $RESOURCE_ID"
            RESOURCE_STATUS="dry_run"
            RESOURCES_CONFIGURED=$((RESOURCES_CONFIGURED + 1))
        else
            # Get available log categories for this resource type
            AVAILABLE_CATEGORIES=$(az monitor diagnostic-settings categories list \
                --resource "$RESOURCE_ID" \
                --query "[?categoryType=='Logs'].name" \
                -o json 2>/dev/null || echo "[]")

            if [[ "$AVAILABLE_CATEGORIES" == "[]" ]] || [[ -z "$AVAILABLE_CATEGORIES" ]]; then
                log_warn "  No log categories available for this resource type"
                RESOURCES_SKIPPED=$((RESOURCES_SKIPPED + 1))
                RESOURCE_STATUS="no_categories"
            else
                # Build logs configuration
                if [[ "$DIAGNOSTIC_LOG_CATEGORIES" == *"AllLogs"* ]]; then
                    # Enable all available categories
                    LOGS_CONFIG=$(echo "$AVAILABLE_CATEGORIES" | jq '[.[] | {category: ., enabled: true}]')
                else
                    # Enable only specified categories
                    LOGS_CONFIG="$DIAGNOSTIC_LOG_CATEGORIES"
                fi

                # Create diagnostic setting
                CREATE_RESULT=$(az monitor diagnostic-settings create \
                    --name "$DIAGNOSTIC_SETTING_NAME" \
                    --resource "$RESOURCE_ID" \
                    --workspace "$WORKSPACE_ID" \
                    --logs "$LOGS_CONFIG" \
                    --metrics '[{"category":"AllMetrics","enabled":true}]' \
                    2>&1) || {
                    log_warn "  Failed to create diagnostic settings"
                    log_debug "  Error: $CREATE_RESULT"
                    RESOURCES_FAILED=$((RESOURCES_FAILED + 1))
                    RESOURCE_STATUS="failed"
                    RESOURCE_ERROR=$(echo "$CREATE_RESULT" | head -n 1)
                    # Continue to next resource (non-fatal)
                }

                if [[ "$RESOURCE_STATUS" != "failed" ]]; then
                    log_success "  Diagnostic settings configured"
                    RESOURCES_CONFIGURED=$((RESOURCES_CONFIGURED + 1))
                    RESOURCE_STATUS="configured"
                fi
            fi
        fi
    fi

    # Build JSON result
    if [[ "$FIRST_RESOURCE" == false ]]; then
        RESOURCE_RESULTS+=","
    fi
    FIRST_RESOURCE=false

    RESOURCE_RESULTS+=$(cat <<EOF
{
  "resource_id": "$RESOURCE_ID",
  "resource_type": "$RESOURCE_TYPE",
  "status": "$RESOURCE_STATUS",
  "error": "$RESOURCE_ERROR",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)

    # Rate limit: pause every N resources (Fix #8)
    if [[ $(((i + 1) % BATCH_SIZE)) -eq 0 ]] && [[ $((i + 1)) -lt $RESOURCE_COUNT ]]; then
        log_info "Processed $((i + 1))/$RESOURCE_COUNT resources, pausing ${BATCH_DELAY}s to avoid rate limiting..."
        sleep $BATCH_DELAY
    fi
done

RESOURCE_RESULTS+="]"

# ========================
# Write diagnostics report
# ========================

cat > "$DIAGNOSTICS_REPORT_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "diagnostic_setting_name": "$DIAGNOSTIC_SETTING_NAME",
  "resources_processed": $RESOURCE_COUNT,
  "resources_configured": $RESOURCES_CONFIGURED,
  "resources_skipped": $RESOURCES_SKIPPED,
  "resources_failed": $RESOURCES_FAILED,
  "resources": $RESOURCE_RESULTS,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

log_success "Diagnostics report written to: $DIAGNOSTICS_REPORT_FILE"

# ========================
# Summary
# ========================

log_success "========================================="
log_success "Module 05 Completed"
log_success "========================================="
log_success "Resources processed: $RESOURCE_COUNT"
log_success "  Configured: $RESOURCES_CONFIGURED"
log_success "  Skipped (already exist): $RESOURCES_SKIPPED"
log_success "  Failed: $RESOURCES_FAILED"
log_success "Report file: $DIAGNOSTICS_REPORT_FILE"

if [[ "$RESOURCES_FAILED" -gt 0 ]]; then
    log_warn "Some resources failed diagnostic configuration"
    log_warn "This is common for resource types that don't support diagnostics"
    log_warn "Check $DIAGNOSTICS_REPORT_FILE for details"
fi

# Exit 0 even if some resources failed (partial success is acceptable)
exit 0
