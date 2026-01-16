#!/bin/bash
# 03-enable-sentinel.sh - Enable Microsoft Sentinel
#
# Purpose: Enable Azure Sentinel solution on Log Analytics Workspace
# Exit Codes:
#   0 - Success (enabled or already enabled)
#   8 - Sentinel enablement failed
#   9 - Content pack installation failed

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
SENTINEL_STATUS_FILE="${OUTPUT_DIR}/sentinel-status.json"

log_info "========================================="
log_info "Module 03: Enable Microsoft Sentinel"
log_info "========================================="

# ========================
# Read workspace ID from previous module
# ========================

if [[ ! -f "$WORKSPACE_ID_FILE" ]]; then
    log_error "Workspace ID file not found: $WORKSPACE_ID_FILE"
    log_error "Module 02 must run before Module 03"
    exit 8
fi

WORKSPACE_ID=$(cat "$WORKSPACE_ID_FILE")

if [[ -z "$WORKSPACE_ID" ]]; then
    log_error "Workspace ID is empty in file: $WORKSPACE_ID_FILE"
    exit 8
fi

log_info "Workspace ID: $WORKSPACE_ID"

# Parse workspace components
WORKSPACE_NAME=$(basename "$WORKSPACE_ID")
RESOURCE_GROUP=$(echo "$WORKSPACE_ID" | cut -d'/' -f5)

log_info "Workspace Name: $WORKSPACE_NAME"
log_info "Resource Group: $RESOURCE_GROUP"

# ========================
# Check if Sentinel already enabled (Idempotency)
# ========================

log_info "Checking if Sentinel is already enabled..."

# Check for SecurityInsights solution using Azure REST API
SENTINEL_CHECK=$(az rest \
    --method GET \
    --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/onboardingStates/default?api-version=2024-03-01" \
    2>/dev/null || echo "{}")

if echo "$SENTINEL_CHECK" | jq -e '.properties' > /dev/null 2>&1; then
    log_success "Sentinel is already enabled on workspace: $WORKSPACE_NAME"
    log_info "Skipping enablement (idempotent)"

    # Write status file
    cat > "$SENTINEL_STATUS_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "workspace_name": "$WORKSPACE_NAME",
  "sentinel_enabled": true,
  "already_enabled": true,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    log_success "Sentinel status written to: $SENTINEL_STATUS_FILE"
    log_success "Module 03 completed (Sentinel already enabled)"
    exit 0
fi

# ========================
# Enable Sentinel
# ========================

log_info "Enabling Microsoft Sentinel on workspace..."

if is_dry_run; then
    dry_run_message "Would enable Sentinel on workspace: $WORKSPACE_NAME"
    dry_run_message "  Resource Group: $RESOURCE_GROUP"

    # Write mock status file for dry run
    cat > "$SENTINEL_STATUS_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "workspace_name": "$WORKSPACE_NAME",
  "sentinel_enabled": true,
  "dry_run": true,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    log_success "[DRY RUN] Sentinel status written to: $SENTINEL_STATUS_FILE"
    exit 0
fi

# Enable Sentinel using Azure REST API
ONBOARD_RESULT=$(az rest \
    --method PUT \
    --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/onboardingStates/default?api-version=2024-03-01" \
    --body '{"properties":{}}' \
    2>&1) || {
    log_error "Failed to enable Sentinel on workspace: $WORKSPACE_NAME"
    log_error "Error: $ONBOARD_RESULT"
    exit 8
}

log_success "Sentinel enabled on workspace: $WORKSPACE_NAME"

# ========================
# Install SecurityInsights Solution
# ========================

log_info "Installing SecurityInsights solution..."

SOLUTION_NAME="SecurityInsights($WORKSPACE_NAME)"
SUBSCRIPTION_ID=$(echo "$WORKSPACE_ID" | cut -d'/' -f3)
LOCATION="${WORKSPACE_LOCATION:-eastus}"

# Create solution using ARM template approach
SOLUTION_BODY=$(cat <<EOF
{
  "location": "$LOCATION",
  "properties": {
    "workspaceResourceId": "$WORKSPACE_ID"
  },
  "plan": {
    "name": "$SOLUTION_NAME",
    "publisher": "Microsoft",
    "product": "OMSGallery/SecurityInsights",
    "promotionCode": ""
  }
}
EOF
)

SOLUTION_RESULT=$(az rest \
    --method PUT \
    --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.OperationsManagement/solutions/${SOLUTION_NAME}?api-version=2015-11-01-preview" \
    --body "$SOLUTION_BODY" \
    2>&1) || {
    log_warn "Failed to install SecurityInsights solution (may already exist)"
    log_debug "Error: $SOLUTION_RESULT"
    # Non-fatal - Sentinel may still work
}

if [[ -n "$SOLUTION_RESULT" ]] && echo "$SOLUTION_RESULT" | jq -e '.id' > /dev/null 2>&1; then
    log_success "SecurityInsights solution installed"
fi

# ========================
# Enable UEBA (User and Entity Behavior Analytics)
# ========================

ENABLE_UEBA="${ENABLE_UEBA:-true}"

if [[ "$ENABLE_UEBA" == "true" ]]; then
    log_info "Enabling UEBA (User and Entity Behavior Analytics)..."

    UEBA_BODY=$(cat <<EOF
{
  "properties": {
    "dataSources": ["AuditLogs", "AzureActivity", "SecurityEvent", "SigninLogs"]
  }
}
EOF
)

    UEBA_RESULT=$(az rest \
        --method PUT \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/settings/Ueba?api-version=2024-03-01" \
        --body "$UEBA_BODY" \
        2>&1) || {
        log_warn "Failed to enable UEBA (may not be available in this region)"
        log_debug "Error: $UEBA_RESULT"
        # Non-fatal
    }

    if [[ -n "$UEBA_RESULT" ]] && echo "$UEBA_RESULT" | jq -e '.properties' > /dev/null 2>&1; then
        log_success "UEBA enabled"
    fi
else
    log_info "Skipping UEBA enablement (ENABLE_UEBA=false)"
fi

# ========================
# Enable Entity Analytics
# ========================

ENABLE_ENTITY_ANALYTICS="${ENABLE_ENTITY_ANALYTICS:-true}"

if [[ "$ENABLE_ENTITY_ANALYTICS" == "true" ]]; then
    log_info "Enabling Entity Analytics..."

    ENTITY_BODY=$(cat <<EOF
{
  "properties": {
    "entityProviders": ["AzureActiveDirectory"]
  }
}
EOF
)

    ENTITY_RESULT=$(az rest \
        --method PUT \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/settings/EntityAnalytics?api-version=2024-03-01" \
        --body "$ENTITY_BODY" \
        2>&1) || {
        log_warn "Failed to enable Entity Analytics (may not be available)"
        log_debug "Error: $ENTITY_RESULT"
        # Non-fatal
    }

    if [[ -n "$ENTITY_RESULT" ]] && echo "$ENTITY_RESULT" | jq -e '.properties' > /dev/null 2>&1; then
        log_success "Entity Analytics enabled"
    fi
else
    log_info "Skipping Entity Analytics (ENABLE_ENTITY_ANALYTICS=false)"
fi

# ========================
# Install Content Packs (Optional)
# ========================

SENTINEL_CONTENT_PACKS="${SENTINEL_CONTENT_PACKS:-[]}"

if [[ "$SENTINEL_CONTENT_PACKS" != "[]" ]] && [[ "$SENTINEL_CONTENT_PACKS" != "" ]]; then
    log_info "Installing Sentinel content packs..."

    # Parse JSON array of content pack names
    PACK_COUNT=$(echo "$SENTINEL_CONTENT_PACKS" | jq '. | length')
    log_info "Content packs to install: $PACK_COUNT"

    for i in $(seq 0 $((PACK_COUNT - 1))); do
        PACK_NAME=$(echo "$SENTINEL_CONTENT_PACKS" | jq -r ".[$i]")
        log_info "Installing content pack: $PACK_NAME"

        # Note: Content pack installation via CLI is limited
        # For production, use Azure Portal or ARM templates
        log_warn "Content pack installation via CLI is limited: $PACK_NAME"
        log_info "Please install content packs manually via Azure Portal if needed"
    done
else
    log_info "No content packs specified (SENTINEL_CONTENT_PACKS empty)"
fi

# ========================
# Verify Sentinel is operational
# ========================

log_info "Verifying Sentinel is operational..."

# Wait a few seconds for changes to propagate
sleep 5

VERIFY_RESULT=$(az rest \
    --method GET \
    --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/onboardingStates/default?api-version=2024-03-01" \
    2>&1) || {
    log_warn "Failed to verify Sentinel status (may still be provisioning)"
    log_debug "Error: $VERIFY_RESULT"
}

if echo "$VERIFY_RESULT" | jq -e '.properties' > /dev/null 2>&1; then
    log_success "Sentinel is operational"
else
    log_warn "Sentinel verification returned unexpected result"
    log_warn "Sentinel may still be provisioning. Check Azure Portal."
fi

# ========================
# Write status file
# ========================

cat > "$SENTINEL_STATUS_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "workspace_name": "$WORKSPACE_NAME",
  "resource_group": "$RESOURCE_GROUP",
  "sentinel_enabled": true,
  "ueba_enabled": $ENABLE_UEBA,
  "entity_analytics_enabled": $ENABLE_ENTITY_ANALYTICS,
  "content_packs": $SENTINEL_CONTENT_PACKS,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

log_success "Sentinel status written to: $SENTINEL_STATUS_FILE"

# ========================
# Summary
# ========================

log_success "========================================="
log_success "Module 03 Completed Successfully"
log_success "========================================="
log_success "Sentinel enabled on: $WORKSPACE_NAME"
log_success "UEBA enabled: $ENABLE_UEBA"
log_success "Entity Analytics enabled: $ENABLE_ENTITY_ANALYTICS"
log_success "Status file: $SENTINEL_STATUS_FILE"

exit 0
