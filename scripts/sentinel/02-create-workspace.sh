#!/bin/bash
# 02-create-workspace.sh - Create Log Analytics Workspace
#
# Purpose: Create or validate Log Analytics Workspace for Sentinel
# Exit Codes:
#   0 - Success (created or already exists)
#   6 - Workspace creation failed
#   7 - Workspace provisioning timeout

set -euo pipefail

# Get script directory and load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# ========================
# Configuration
# ========================

load_config_env

# Required configuration variables
REQUIRED_VARS=(
    "WORKSPACE_NAME"
    "WORKSPACE_RESOURCE_GROUP"
    "WORKSPACE_LOCATION"
    "AZURE_SUBSCRIPTION_ID"
)

# Validate required configuration
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        log_error "Required configuration variable not set: $var"
        exit 1
    fi
done

# Optional configuration with defaults
WORKSPACE_SKU="${WORKSPACE_SKU:-PerGB2018}"
WORKSPACE_RETENTION_DAYS="${WORKSPACE_RETENTION_DAYS:-90}"
WORKSPACE_DAILY_CAP_GB="${WORKSPACE_DAILY_CAP_GB:-1}"

# Output paths
OUTPUT_DIR="${OUTPUT_DIR:-./output}"
WORKSPACE_ID_FILE="${OUTPUT_DIR}/workspace-id.txt"
WORKSPACE_KEY_FILE="${OUTPUT_DIR}/workspace-key.txt"

log_info "========================================="
log_info "Module 02: Create Log Analytics Workspace"
log_info "========================================="
log_info "Workspace Name: $WORKSPACE_NAME"
log_info "Resource Group: $WORKSPACE_RESOURCE_GROUP"
log_info "Location: $WORKSPACE_LOCATION"
log_info "SKU: $WORKSPACE_SKU"
log_info "Retention: $WORKSPACE_RETENTION_DAYS days"

# ========================
# Check if workspace already exists (Idempotency)
# ========================

log_info "Checking if workspace already exists..."

if workspace_exists "$WORKSPACE_NAME" "$WORKSPACE_RESOURCE_GROUP"; then
    log_success "Workspace already exists: $WORKSPACE_NAME"
    log_info "Skipping creation (idempotent)"

    # Get existing workspace ID
    WORKSPACE_ID=$(safe_az_cli monitor log-analytics workspace show \
        --workspace-name "$WORKSPACE_NAME" \
        --resource-group "$WORKSPACE_RESOURCE_GROUP" \
        --query id \
        -o tsv)

    if [[ -z "$WORKSPACE_ID" ]]; then
        log_error "Failed to retrieve workspace ID"
        exit 6
    fi

    log_info "Workspace ID: $WORKSPACE_ID"

    # Write workspace ID to file for next modules
    echo "$WORKSPACE_ID" > "$WORKSPACE_ID_FILE"
    log_success "Workspace ID written to: $WORKSPACE_ID_FILE"

    # Get workspace key
    WORKSPACE_KEY=$(safe_az_cli monitor log-analytics workspace get-shared-keys \
        --workspace-name "$WORKSPACE_NAME" \
        --resource-group "$WORKSPACE_RESOURCE_GROUP" \
        --query primarySharedKey \
        -o tsv 2>/dev/null || echo "")

    if [[ -n "$WORKSPACE_KEY" ]]; then
        echo "$WORKSPACE_KEY" > "$WORKSPACE_KEY_FILE"
        chmod 600 "$WORKSPACE_KEY_FILE"
        log_success "Workspace key written to: $WORKSPACE_KEY_FILE (permissions: 0600)"
    fi

    log_success "Module 02 completed (workspace already exists)"
    exit 0
fi

# ========================
# Ensure resource group exists
# ========================

log_info "Ensuring resource group exists: $WORKSPACE_RESOURCE_GROUP"

if ! resource_group_exists "$WORKSPACE_RESOURCE_GROUP"; then
    log_info "Creating resource group: $WORKSPACE_RESOURCE_GROUP"

    if is_dry_run; then
        dry_run_message "Would create resource group: $WORKSPACE_RESOURCE_GROUP in $WORKSPACE_LOCATION"
    else
        if ! safe_az_cli group create \
            --name "$WORKSPACE_RESOURCE_GROUP" \
            --location "$WORKSPACE_LOCATION" \
            --output none; then
            log_error "Failed to create resource group: $WORKSPACE_RESOURCE_GROUP"
            exit 6
        fi
        log_success "Resource group created: $WORKSPACE_RESOURCE_GROUP"
    fi
else
    log_info "Resource group already exists: $WORKSPACE_RESOURCE_GROUP"
fi

# ========================
# Create Log Analytics Workspace
# ========================

log_info "Creating Log Analytics Workspace..."

if is_dry_run; then
    dry_run_message "Would create workspace: $WORKSPACE_NAME"
    dry_run_message "  Resource Group: $WORKSPACE_RESOURCE_GROUP"
    dry_run_message "  Location: $WORKSPACE_LOCATION"
    dry_run_message "  SKU: $WORKSPACE_SKU"
    dry_run_message "  Retention: $WORKSPACE_RETENTION_DAYS days"

    # Generate mock workspace ID for dry run
    WORKSPACE_ID="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${WORKSPACE_RESOURCE_GROUP}/providers/Microsoft.OperationalInsights/workspaces/${WORKSPACE_NAME}"
    echo "$WORKSPACE_ID" > "$WORKSPACE_ID_FILE"
    log_success "[DRY RUN] Workspace ID written to: $WORKSPACE_ID_FILE"
    exit 0
fi

# Create workspace
CREATE_OUTPUT=$(az monitor log-analytics workspace create \
    --workspace-name "$WORKSPACE_NAME" \
    --resource-group "$WORKSPACE_RESOURCE_GROUP" \
    --location "$WORKSPACE_LOCATION" \
    --sku "$WORKSPACE_SKU" \
    --retention-time "$WORKSPACE_RETENTION_DAYS" \
    --quota "$WORKSPACE_DAILY_CAP_GB" \
    --query '{id:id,provisioningState:provisioningState}' \
    -o json 2>&1) || {
    log_error "Failed to create workspace: $WORKSPACE_NAME"
    log_error "Error output: $CREATE_OUTPUT"
    exit 6
}

WORKSPACE_ID=$(echo "$CREATE_OUTPUT" | jq -r '.id')
PROVISIONING_STATE=$(echo "$CREATE_OUTPUT" | jq -r '.provisioningState')

if [[ -z "$WORKSPACE_ID" ]] || [[ "$WORKSPACE_ID" == "null" ]]; then
    log_error "Failed to parse workspace ID from creation output"
    exit 6
fi

log_success "Workspace created: $WORKSPACE_NAME"
log_info "Workspace ID: $WORKSPACE_ID"
log_info "Provisioning State: $PROVISIONING_STATE"

# ========================
# Wait for provisioning to complete
# ========================

if [[ "$PROVISIONING_STATE" == "Succeeded" ]]; then
    log_success "Workspace provisioning completed immediately"
else
    log_info "Waiting for workspace provisioning to complete..."

    MAX_ATTEMPTS=20
    ATTEMPT=0
    SLEEP_INTERVAL=15

    while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
        ATTEMPT=$((ATTEMPT + 1))
        log_info "Checking provisioning state (attempt $ATTEMPT/$MAX_ATTEMPTS)..."

        CURRENT_STATE=$(safe_az_cli monitor log-analytics workspace show \
            --workspace-name "$WORKSPACE_NAME" \
            --resource-group "$WORKSPACE_RESOURCE_GROUP" \
            --query provisioningState \
            -o tsv 2>/dev/null || echo "Unknown")

        log_info "Current state: $CURRENT_STATE"

        if [[ "$CURRENT_STATE" == "Succeeded" ]]; then
            log_success "Workspace provisioning completed"
            break
        elif [[ "$CURRENT_STATE" == "Failed" ]]; then
            log_error "Workspace provisioning failed"
            exit 6
        fi

        if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; then
            log_info "Waiting ${SLEEP_INTERVAL}s before next check..."
            sleep $SLEEP_INTERVAL
        fi
    done

    if [[ $ATTEMPT -ge $MAX_ATTEMPTS ]]; then
        log_error "Workspace provisioning timed out after $((MAX_ATTEMPTS * SLEEP_INTERVAL)) seconds"
        log_warn "Workspace may still be provisioning. Check Azure Portal."
        exit 7
    fi
fi

# ========================
# Write workspace ID to file
# ========================

echo "$WORKSPACE_ID" > "$WORKSPACE_ID_FILE"
log_success "Workspace ID written to: $WORKSPACE_ID_FILE"

# ========================
# Get workspace key
# ========================

log_info "Retrieving workspace shared keys..."

WORKSPACE_KEY=$(safe_az_cli monitor log-analytics workspace get-shared-keys \
    --workspace-name "$WORKSPACE_NAME" \
    --resource-group "$WORKSPACE_RESOURCE_GROUP" \
    --query primarySharedKey \
    -o tsv 2>/dev/null || echo "")

if [[ -n "$WORKSPACE_KEY" ]]; then
    echo "$WORKSPACE_KEY" > "$WORKSPACE_KEY_FILE"
    chmod 600 "$WORKSPACE_KEY_FILE"
    log_success "Workspace key written to: $WORKSPACE_KEY_FILE (permissions: 0600)"
else
    log_warn "Failed to retrieve workspace key (this may be expected)"
fi

# ========================
# Summary
# ========================

log_success "========================================="
log_success "Module 02 Completed Successfully"
log_success "========================================="
log_success "Workspace: $WORKSPACE_NAME"
log_success "Resource Group: $WORKSPACE_RESOURCE_GROUP"
log_success "Workspace ID: $WORKSPACE_ID"
log_success "Output files:"
log_success "  - $WORKSPACE_ID_FILE"
[[ -n "$WORKSPACE_KEY" ]] && log_success "  - $WORKSPACE_KEY_FILE"

exit 0
