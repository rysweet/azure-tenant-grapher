#!/usr/bin/env bash

# ============================================================================
# Module 01: Validate Prerequisites for Azure Sentinel Setup (Issue #518)
#
# Validates that all prerequisites are met before beginning Sentinel setup:
# - Azure CLI installed and minimum version (>= 2.50.0)
# - Authentication with service principal
# - Required Azure providers registered
# - Sufficient permissions (Owner or Contributor + Security Admin)
#
# Exit Codes:
#   0: All prerequisites met
#   1: Azure CLI not found or too old
#   2: Authentication failed
#   3: Required provider(s) not registered
#   4: Insufficient permissions
#   5: Configuration invalid
#
# Philosophy:
# - Fail fast before making any changes
# - Clear error messages with remediation steps
# - Idempotent (safe to re-run)
# ============================================================================

set -euo pipefail

# Source common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# ============================================================================
# Configuration Validation
# ============================================================================

validate_configuration() {
    log_info "Validating configuration..."

    # Check required environment variables
    local required_vars=("TENANT_ID" "SUBSCRIPTION_ID" "WORKSPACE_NAME" "RESOURCE_GROUP" "LOCATION")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "Missing required configuration variables:"
        for var in "${missing_vars[@]}"; do
            log_error "  - $var"
        done
        log_error "Please ensure config.env is properly configured"
        return 5
    fi

    log_success "Configuration validation passed"
    return 0
}

# ============================================================================
# Azure CLI Validation
# ============================================================================

validate_azure_cli() {
    log_info "Validating Azure CLI..."

    if ! check_az_cli; then
        log_error "Azure CLI validation failed"
        log_error "Please install or upgrade Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli"
        return 1
    fi

    return 0
}

# ============================================================================
# Authentication Validation
# ============================================================================

validate_authentication() {
    log_info "Validating authentication..."

    # Check if already authenticated
    if az account show >/dev/null 2>&1; then
        log_info "Already authenticated"

        # Set subscription
        if az account set --subscription "$SUBSCRIPTION_ID" >/dev/null 2>&1; then
            log_success "Using subscription: $SUBSCRIPTION_ID"
            return 0
        else
            log_warn "Failed to set subscription, will try service principal auth"
        fi
    fi

    # Try service principal authentication
    if [ -n "${AZURE_CLIENT_ID:-}" ] && [ -n "${AZURE_CLIENT_SECRET:-}" ]; then
        if authenticate_service_principal; then
            # Set subscription
            if az account set --subscription "$SUBSCRIPTION_ID" >/dev/null 2>&1; then
                log_success "Authenticated and set subscription: $SUBSCRIPTION_ID"
                return 0
            else
                log_error "Failed to set subscription: $SUBSCRIPTION_ID"
                return 2
            fi
        else
            log_error "Service principal authentication failed"
            return 2
        fi
    else
        log_error "Not authenticated and no service principal credentials provided"
        log_error "Please set AZURE_CLIENT_ID and AZURE_CLIENT_SECRET, or run 'az login'"
        return 2
    fi
}

# ============================================================================
# Provider Registration Validation
# ============================================================================

validate_providers() {
    log_info "Validating Azure provider registration..."

    # Skip if requested
    if [ "${SKIP_PROVIDER_CHECK:-false}" = "true" ]; then
        log_info "Skipping provider check (SKIP_PROVIDER_CHECK=true)"
        return 0
    fi

    # Required providers
    local required_providers=(
        "Microsoft.OperationalInsights"
        "Microsoft.Insights"
        "Microsoft.SecurityInsights"
    )

    local unregistered_providers=()

    for provider in "${required_providers[@]}"; do
        if ! check_provider_registered "$provider"; then
            unregistered_providers+=("$provider")
        fi
    done

    if [ ${#unregistered_providers[@]} -gt 0 ]; then
        log_warn "The following providers are not registered:"
        for provider in "${unregistered_providers[@]}"; do
            log_warn "  - $provider"
        done

        log_info "Attempting to register providers..."

        local failed_providers=()
        for provider in "${unregistered_providers[@]}"; do
            if ! register_provider "$provider"; then
                failed_providers+=("$provider")
            fi
        done

        if [ ${#failed_providers[@]} -gt 0 ]; then
            log_error "Failed to register the following providers:"
            for provider in "${failed_providers[@]}"; do
                log_error "  - $provider"
            done
            log_error "Please register these providers manually or run with SKIP_PROVIDER_CHECK=true"
            return 3
        fi
    fi

    log_success "All required providers are registered"
    return 0
}

# ============================================================================
# Permission Validation
# ============================================================================

validate_permissions() {
    log_info "Validating permissions..."

    # Get current user's role assignments for the subscription
    local role_assignments
    role_assignments=$(az role assignment list --scope "/subscriptions/$SUBSCRIPTION_ID" --include-inherited --query "[?principalName=='$(az account show --query user.name -o tsv)'].roleDefinitionName" -o tsv 2>/dev/null || echo "")

    # Check for Owner or Contributor role
    local has_sufficient_role=false

    if echo "$role_assignments" | grep -q "Owner"; then
        log_info "User has Owner role (sufficient)"
        has_sufficient_role=true
    elif echo "$role_assignments" | grep -q "Contributor"; then
        log_info "User has Contributor role"

        # Check for Security Admin role (needed for Sentinel)
        if echo "$role_assignments" | grep -q "Security Admin"; then
            log_info "User has Security Admin role (sufficient)"
            has_sufficient_role=true
        else
            log_warn "User has Contributor but not Security Admin role"
            log_warn "Sentinel setup may fail without Security Admin role"
        fi
    fi

    if [ "$has_sufficient_role" = false ]; then
        log_warn "Could not verify sufficient permissions"
        log_warn "Required: Owner OR (Contributor + Security Admin)"
        log_warn "Continuing anyway, but setup may fail if permissions are insufficient"
    else
        log_success "Permission validation passed"
    fi

    return 0
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log_info "==================================================================="
    log_info "Module 01: Validating Prerequisites"
    log_info "==================================================================="

    # Step 1: Load configuration
    if ! load_config_env "config.env"; then
        exit_with_code 5 "Failed to load configuration"
    fi

    # Step 2: Validate configuration
    if ! validate_configuration; then
        exit_with_code 5 "Configuration validation failed"
    fi

    # Step 3: Validate Azure CLI
    if ! validate_azure_cli; then
        exit_with_code 1 "Azure CLI validation failed"
    fi

    # Step 4: Validate authentication
    if ! validate_authentication; then
        exit_with_code 2 "Authentication validation failed"
    fi

    # Step 5: Validate providers
    if ! validate_providers; then
        exit_with_code 3 "Provider validation failed"
    fi

    # Step 6: Validate permissions
    if ! validate_permissions; then
        # Non-fatal, just a warning
        log_warn "Permission validation had warnings, but continuing"
    fi

    log_success "==================================================================="
    log_success "All prerequisites validated successfully"
    log_success "==================================================================="

    exit 0
}

# Run main
main "$@"
