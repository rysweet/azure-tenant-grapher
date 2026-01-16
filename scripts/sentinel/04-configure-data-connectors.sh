#!/bin/bash
# 04-configure-data-connectors.sh - Configure Sentinel Data Connectors
#
# Purpose: Configure Azure data connectors for Sentinel
# Exit Codes:
#   0 - Success (all connectors configured)
#   10 - Data connector configuration failed

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
CONNECTORS_STATUS_FILE="${OUTPUT_DIR}/data-connectors-status.json"

log_info "========================================="
log_info "Module 04: Configure Data Connectors"
log_info "========================================="

# ========================
# Read workspace ID from previous module
# ========================

if [[ ! -f "$WORKSPACE_ID_FILE" ]]; then
    log_error "Workspace ID file not found: $WORKSPACE_ID_FILE"
    log_error "Module 02 must run before Module 04"
    exit 10
fi

WORKSPACE_ID=$(cat "$WORKSPACE_ID_FILE")

if [[ -z "$WORKSPACE_ID" ]]; then
    log_error "Workspace ID is empty in file: $WORKSPACE_ID_FILE"
    exit 10
fi

log_info "Workspace ID: $WORKSPACE_ID"

# Parse workspace components
WORKSPACE_NAME=$(basename "$WORKSPACE_ID")
RESOURCE_GROUP=$(echo "$WORKSPACE_ID" | cut -d'/' -f5)
SUBSCRIPTION_ID=$(echo "$WORKSPACE_ID" | cut -d'/' -f3)

log_info "Workspace Name: $WORKSPACE_NAME"
log_info "Resource Group: $RESOURCE_GROUP"
log_info "Subscription ID: $SUBSCRIPTION_ID"

# ========================
# Parse enabled data connectors
# ========================

DATA_CONNECTORS="${DATA_CONNECTORS:-[\"AzureActivity\"]}"

CONNECTOR_COUNT=$(echo "$DATA_CONNECTORS" | jq '. | length' 2>/dev/null || echo "0")

if [[ "$CONNECTOR_COUNT" -eq 0 ]]; then
    log_info "No data connectors specified (DATA_CONNECTORS empty)"
    log_success "Module 04 completed (no connectors to configure)"

    # Write empty status file
    cat > "$CONNECTORS_STATUS_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "connectors": [],
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    exit 0
fi

log_info "Data connectors to configure: $CONNECTOR_COUNT"

# ========================
# Configure Azure Activity Data Connector
# ========================

configure_azure_activity_connector() {
    log_info "Configuring Azure Activity data connector..."

    # Check if already configured (idempotency)
    EXISTING_CONNECTOR=$(az rest \
        --method GET \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/dataConnectors?api-version=2024-03-01" \
        2>/dev/null || echo "{}")

    if echo "$EXISTING_CONNECTOR" | jq -e '.value[] | select(.kind=="AzureActivity")' > /dev/null 2>&1; then
        log_success "Azure Activity connector already configured"
        return 0
    fi

    if is_dry_run; then
        dry_run_message "Would configure Azure Activity data connector"
        return 0
    fi

    # Configure using Azure Policy (recommended approach)
    log_info "Configuring Azure Activity connector via diagnostic settings..."

    # The actual connection happens through diagnostic settings (Module 05)
    # This creates the data connector definition in Sentinel

    CONNECTOR_ID="$(uuidgen)"
    CONNECTOR_BODY=$(cat <<EOF
{
  "kind": "AzureActivity",
  "properties": {
    "subscriptionId": "$SUBSCRIPTION_ID"
  }
}
EOF
)

    CONNECTOR_RESULT=$(az rest \
        --method PUT \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/dataConnectors/${CONNECTOR_ID}?api-version=2024-03-01" \
        --body "$CONNECTOR_BODY" \
        2>&1) || {
        log_warn "Failed to configure Azure Activity connector"
        log_debug "Error: $CONNECTOR_RESULT"
        return 1
    }

    log_success "Azure Activity data connector configured"
    return 0
}

# ========================
# Configure Azure Active Directory Connector
# ========================

configure_azure_ad_connector() {
    log_info "Configuring Azure Active Directory data connector..."

    # Check if already configured
    EXISTING_CONNECTOR=$(az rest \
        --method GET \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/dataConnectors?api-version=2024-03-01" \
        2>/dev/null || echo "{}")

    if echo "$EXISTING_CONNECTOR" | jq -e '.value[] | select(.kind=="AzureActiveDirectory")' > /dev/null 2>&1; then
        log_success "Azure AD connector already configured"
        return 0
    fi

    if is_dry_run; then
        dry_run_message "Would configure Azure AD data connector"
        return 0
    fi

    CONNECTOR_ID="$(uuidgen)"
    CONNECTOR_BODY=$(cat <<EOF
{
  "kind": "AzureActiveDirectory",
  "properties": {
    "tenantId": "$AZURE_TENANT_ID"
  }
}
EOF
)

    CONNECTOR_RESULT=$(az rest \
        --method PUT \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/dataConnectors/${CONNECTOR_ID}?api-version=2024-03-01" \
        --body "$CONNECTOR_BODY" \
        2>&1) || {
        log_warn "Failed to configure Azure AD connector"
        log_debug "Error: $CONNECTOR_RESULT"
        return 1
    }

    log_success "Azure AD data connector configured"
    return 0
}

# ========================
# Configure Microsoft Defender Connector
# ========================

configure_defender_connector() {
    log_info "Configuring Microsoft Defender data connector..."

    # Check if already configured
    EXISTING_CONNECTOR=$(az rest \
        --method GET \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/dataConnectors?api-version=2024-03-01" \
        2>/dev/null || echo "{}")

    if echo "$EXISTING_CONNECTOR" | jq -e '.value[] | select(.kind=="MicrosoftDefenderAdvancedThreatProtection")' > /dev/null 2>&1; then
        log_success "Microsoft Defender connector already configured"
        return 0
    fi

    if is_dry_run; then
        dry_run_message "Would configure Microsoft Defender data connector"
        return 0
    fi

    CONNECTOR_ID="$(uuidgen)"
    CONNECTOR_BODY=$(cat <<EOF
{
  "kind": "MicrosoftDefenderAdvancedThreatProtection",
  "properties": {
    "tenantId": "$AZURE_TENANT_ID"
  }
}
EOF
)

    CONNECTOR_RESULT=$(az rest \
        --method PUT \
        --url "https://management.azure.com${WORKSPACE_ID}/providers/Microsoft.SecurityInsights/dataConnectors/${CONNECTOR_ID}?api-version=2024-03-01" \
        --body "$CONNECTOR_BODY" \
        2>&1) || {
        log_warn "Failed to configure Microsoft Defender connector"
        log_debug "Error: $CONNECTOR_RESULT"
        return 1
    }

    log_success "Microsoft Defender data connector configured"
    return 0
}

# ========================
# Configure all enabled connectors
# ========================

CONNECTOR_RESULTS="["
FIRST_CONNECTOR=true

for i in $(seq 0 $((CONNECTOR_COUNT - 1))); do
    CONNECTOR_NAME=$(echo "$DATA_CONNECTORS" | jq -r ".[$i]")
    log_info "Processing connector: $CONNECTOR_NAME"

    CONNECTOR_SUCCESS=false

    case "$CONNECTOR_NAME" in
        "AzureActivity")
            if configure_azure_activity_connector; then
                CONNECTOR_SUCCESS=true
            fi
            ;;
        "AzureActiveDirectory"|"AzureAD")
            if configure_azure_ad_connector; then
                CONNECTOR_SUCCESS=true
            fi
            ;;
        "Defender"|"MicrosoftDefender")
            if configure_defender_connector; then
                CONNECTOR_SUCCESS=true
            fi
            ;;
        *)
            log_warn "Unknown connector type: $CONNECTOR_NAME"
            log_warn "Skipping unsupported connector"
            ;;
    esac

    # Build JSON result
    if [[ "$FIRST_CONNECTOR" == false ]]; then
        CONNECTOR_RESULTS+=","
    fi
    FIRST_CONNECTOR=false

    CONNECTOR_RESULTS+=$(cat <<EOF
{
  "name": "$CONNECTOR_NAME",
  "configured": $CONNECTOR_SUCCESS,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
done

CONNECTOR_RESULTS+="]"

# ========================
# Write status file
# ========================

cat > "$CONNECTORS_STATUS_FILE" <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "workspace_name": "$WORKSPACE_NAME",
  "connectors": $CONNECTOR_RESULTS,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

log_success "Data connectors status written to: $CONNECTORS_STATUS_FILE"

# ========================
# Summary
# ========================

CONFIGURED_COUNT=$(echo "$CONNECTOR_RESULTS" | jq '[.[] | select(.configured==true)] | length')

log_success "========================================="
log_success "Module 04 Completed"
log_success "========================================="
log_success "Connectors configured: $CONFIGURED_COUNT/$CONNECTOR_COUNT"
log_success "Status file: $CONNECTORS_STATUS_FILE"

if [[ "$CONFIGURED_COUNT" -lt "$CONNECTOR_COUNT" ]]; then
    log_warn "Some connectors failed to configure"
    log_warn "Check $CONNECTORS_STATUS_FILE for details"
fi

exit 0
