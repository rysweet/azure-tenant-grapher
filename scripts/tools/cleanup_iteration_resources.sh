#!/usr/bin/env bash
set -euo pipefail

# cleanup_iteration_resources.sh
# Delete all Azure resources from previous iterations to prevent "already exists" errors
#
# Usage:
#   ./scripts/cleanup_iteration_resources.sh ITERATION15_
#   ./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run
#   ./scripts/cleanup_iteration_resources.sh ITERATION15_ --skip-confirmation
#   ./scripts/cleanup_iteration_resources.sh ITERATION15_ --subscription <subscription-id>

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=false
SKIP_CONFIRMATION=false
SUBSCRIPTION=""
PREFIX=""
VERBOSE=false

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[VERBOSE]${NC} $*"
    fi
}

# Help message
show_help() {
    cat << EOF
Usage: $0 <ITERATION_PREFIX> [OPTIONS]

Delete all Azure resources from a specific iteration to prevent conflicts.

Arguments:
    ITERATION_PREFIX    Resource prefix to match (e.g., "ITERATION15_")

Options:
    --dry-run              Show what would be deleted without making changes
    --skip-confirmation    Skip confirmation prompts (dangerous!)
    --subscription <id>    Use specific Azure subscription
    --verbose              Enable verbose logging
    -h, --help            Show this help message

Examples:
    # Dry run to see what would be deleted
    $0 ITERATION15_ --dry-run

    # Delete with confirmation
    $0 ITERATION15_

    # Delete without confirmation (CI/CD)
    $0 ITERATION15_ --skip-confirmation

    # Delete in specific subscription
    $0 ITERATION15_ --subscription xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

Safety Features:
    - Dry-run mode to preview deletions
    - Confirmation prompts before destructive operations
    - Comprehensive logging of all actions
    - Parallel deletion with progress reporting
    - Automatic purge of soft-deleted Key Vaults

Cleanup Actions:
    1. List and delete resource groups matching prefix
    2. Purge soft-deleted Key Vaults
    3. Delete orphaned storage accounts
    4. Delete individual resources if RG deletion is blocked

EOF
}

# Parse command line arguments
parse_args() {
    if [ $# -eq 0 ]; then
        log_error "Missing ITERATION_PREFIX argument"
        show_help
        exit 1
    fi

    PREFIX="$1"
    shift

    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                log_info "Dry-run mode enabled"
                ;;
            --skip-confirmation)
                SKIP_CONFIRMATION=true
                log_warning "Confirmation prompts disabled"
                ;;
            --subscription)
                shift
                SUBSCRIPTION="$1"
                log_info "Using subscription: $SUBSCRIPTION"
                ;;
            --verbose)
                VERBOSE=true
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done

    if [ -z "$PREFIX" ]; then
        log_error "ITERATION_PREFIX cannot be empty"
        exit 1
    fi
}

# Check Azure CLI is installed and logged in
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v az &> /dev/null; then
        log_error "Azure CLI (az) not found. Please install it first."
        exit 1
    fi

    # Check if logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi

    # Set subscription if specified
    if [ -n "$SUBSCRIPTION" ]; then
        log_info "Setting subscription to: $SUBSCRIPTION"
        if [ "$DRY_RUN" = false ]; then
            az account set --subscription "$SUBSCRIPTION"
        fi
    fi

    local current_sub
    current_sub=$(az account show --query name -o tsv)
    log_success "Using subscription: $current_sub"
}

# Confirm deletion with user
confirm_deletion() {
    local resource_type="$1"
    local count="$2"

    if [ "$SKIP_CONFIRMATION" = true ]; then
        return 0
    fi

    echo
    log_warning "About to delete $count $resource_type with prefix '$PREFIX'"
    read -r -p "Are you sure? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            log_info "Deletion cancelled by user"
            return 1
            ;;
    esac
}

# List resource groups matching prefix
list_resource_groups() {
    log_info "Searching for resource groups with prefix: $PREFIX"

    local rgs
    rgs=$(az group list --query "[?starts_with(name, '$PREFIX')].{Name:name, Location:location, State:properties.provisioningState}" -o json)

    local count
    count=$(echo "$rgs" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        log_info "No resource groups found with prefix: $PREFIX"
        echo "[]"
        return
    fi

    log_success "Found $count resource group(s):"
    echo "$rgs" | jq -r '.[] | "  - \(.Name) (\(.Location)) - \(.State)"'
    echo "$rgs"
}

# Delete resource groups
delete_resource_groups() {
    local rgs="$1"
    local count
    count=$(echo "$rgs" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        return
    fi

    if ! confirm_deletion "resource group(s)" "$count"; then
        return
    fi

    log_info "Deleting $count resource group(s)..."

    local rg_names
    rg_names=$(echo "$rgs" | jq -r '.[].Name')

    local deleted=0
    local failed=0

    while IFS= read -r rg_name; do
        log_info "Deleting resource group: $rg_name"

        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] Would delete resource group: $rg_name"
            ((deleted++))
        else
            if az group delete --name "$rg_name" --yes --no-wait 2>&1 | tee /dev/stderr; then
                log_success "Initiated deletion of: $rg_name (async)"
                ((deleted++))
            else
                log_error "Failed to delete resource group: $rg_name"
                ((failed++))
            fi
        fi
    done <<< "$rg_names"

    log_success "Initiated deletion of $deleted resource group(s)"
    if [ "$failed" -gt 0 ]; then
        log_warning "$failed resource group(s) failed to delete"
    fi

    if [ "$DRY_RUN" = false ] && [ "$deleted" -gt 0 ]; then
        log_info "Resource group deletions are running in background (async)"
        log_info "You can monitor progress with: az group list --query \"[?starts_with(name, '$PREFIX')]\""
    fi
}

# List soft-deleted Key Vaults
list_deleted_keyvaults() {
    log_info "Searching for soft-deleted Key Vaults with prefix: $PREFIX"

    local kvs
    kvs=$(az keyvault list-deleted --query "[?starts_with(name, '$PREFIX')].{Name:name, Location:properties.location, DeletionDate:properties.deletionDate, ScheduledPurgeDate:properties.scheduledPurgeDate}" -o json 2>/dev/null || echo "[]")

    local count
    count=$(echo "$kvs" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        log_info "No soft-deleted Key Vaults found with prefix: $PREFIX"
        echo "[]"
        return
    fi

    log_success "Found $count soft-deleted Key Vault(s):"
    echo "$kvs" | jq -r '.[] | "  - \(.Name) (\(.Location)) - Deleted: \(.DeletionDate)"'
    echo "$kvs"
}

# Purge soft-deleted Key Vaults
purge_deleted_keyvaults() {
    local kvs="$1"
    local count
    count=$(echo "$kvs" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        return
    fi

    if ! confirm_deletion "soft-deleted Key Vault(s)" "$count"; then
        return
    fi

    log_info "Purging $count soft-deleted Key Vault(s)..."

    local purged=0
    local failed=0

    echo "$kvs" | jq -r '.[] | "\(.Name)|\(.Location)"' | while IFS='|' read -r kv_name kv_location; do
        log_info "Purging Key Vault: $kv_name (location: $kv_location)"

        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] Would purge Key Vault: $kv_name"
            ((purged++))
        else
            if az keyvault purge --name "$kv_name" --location "$kv_location" --no-wait 2>&1 | tee /dev/stderr; then
                log_success "Initiated purge of: $kv_name (async)"
                ((purged++))
            else
                log_error "Failed to purge Key Vault: $kv_name"
                ((failed++))
            fi
        fi
    done

    log_success "Initiated purge of $purged Key Vault(s)"
    if [ "$failed" -gt 0 ]; then
        log_warning "$failed Key Vault(s) failed to purge"
    fi
}

# List storage accounts matching prefix
list_storage_accounts() {
    log_info "Searching for storage accounts with prefix: $PREFIX"

    # Convert prefix to lowercase (storage account names must be lowercase)
    local prefix_lower
    prefix_lower=$(echo "$PREFIX" | tr '[:upper:]' '[:lower:]')

    local storage_accounts
    storage_accounts=$(az storage account list --query "[?starts_with(name, '$prefix_lower')].{Name:name, ResourceGroup:resourceGroup, Location:location, Kind:kind}" -o json)

    local count
    count=$(echo "$storage_accounts" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        log_info "No storage accounts found with prefix: $prefix_lower"
        echo "[]"
        return
    fi

    log_success "Found $count storage account(s):"
    echo "$storage_accounts" | jq -r '.[] | "  - \(.Name) (RG: \(.ResourceGroup), Location: \(.Location))"'
    echo "$storage_accounts"
}

# Delete orphaned storage accounts
delete_storage_accounts() {
    local storage_accounts="$1"
    local count
    count=$(echo "$storage_accounts" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        return
    fi

    if ! confirm_deletion "storage account(s)" "$count"; then
        return
    fi

    log_info "Deleting $count storage account(s)..."

    local deleted=0
    local failed=0

    echo "$storage_accounts" | jq -r '.[] | "\(.Name)|\(.ResourceGroup)"' | while IFS='|' read -r sa_name sa_rg; do
        log_info "Deleting storage account: $sa_name (RG: $sa_rg)"

        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] Would delete storage account: $sa_name"
            ((deleted++))
        else
            if az storage account delete --name "$sa_name" --resource-group "$sa_rg" --yes 2>&1 | tee /dev/stderr; then
                log_success "Deleted storage account: $sa_name"
                ((deleted++))
            else
                log_error "Failed to delete storage account: $sa_name"
                ((failed++))
            fi
        fi
    done

    log_success "Deleted $deleted storage account(s)"
    if [ "$failed" -gt 0 ]; then
        log_warning "$failed storage account(s) failed to delete"
    fi
}

# List individual resources in resource groups (for fallback deletion)
list_individual_resources() {
    local rg_name="$1"

    log_verbose "Listing resources in resource group: $rg_name"

    local resources
    resources=$(az resource list --resource-group "$rg_name" --query "[].{Name:name, Type:type, Id:id}" -o json)

    echo "$resources"
}

# Delete individual resources if RG deletion is blocked
delete_individual_resources() {
    local rg_name="$1"

    log_info "Attempting to delete individual resources in: $rg_name"

    local resources
    resources=$(list_individual_resources "$rg_name")

    local count
    count=$(echo "$resources" | jq '. | length')

    if [ "$count" -eq 0 ]; then
        log_info "No resources found in resource group: $rg_name"
        return
    fi

    log_info "Found $count resource(s) in $rg_name"

    local deleted=0
    local failed=0

    echo "$resources" | jq -r '.[] | "\(.Id)|\(.Name)|\(.Type)"' | while IFS='|' read -r resource_id resource_name resource_type; do
        log_verbose "Deleting resource: $resource_name (Type: $resource_type)"

        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY-RUN] Would delete resource: $resource_name"
            ((deleted++))
        else
            if az resource delete --ids "$resource_id" --no-wait 2>&1 | tee /dev/stderr; then
                log_success "Initiated deletion of: $resource_name"
                ((deleted++))
            else
                log_error "Failed to delete resource: $resource_name"
                ((failed++))
            fi
        fi
    done

    log_success "Initiated deletion of $deleted resource(s) in $rg_name"
    if [ "$failed" -gt 0 ]; then
        log_warning "$failed resource(s) failed to delete in $rg_name"
    fi
}

# Wait for resource group deletions to complete
wait_for_deletions() {
    if [ "$DRY_RUN" = true ]; then
        return
    fi

    log_info "Waiting for resource group deletions to complete..."
    log_info "Press Ctrl+C to stop waiting (deletions will continue in background)"

    local max_wait=1800  # 30 minutes
    local elapsed=0
    local interval=10

    while [ $elapsed -lt $max_wait ]; do
        local remaining_rgs
        remaining_rgs=$(az group list --query "[?starts_with(name, '$PREFIX')]" -o json)
        local count
        count=$(echo "$remaining_rgs" | jq '. | length')

        if [ "$count" -eq 0 ]; then
            log_success "All resource groups have been deleted"
            return
        fi

        log_info "Still waiting for $count resource group(s) to be deleted... (${elapsed}s elapsed)"
        sleep $interval
        ((elapsed += interval))
    done

    log_warning "Timeout waiting for deletions. Some resource groups may still be deleting."
    log_info "Check status with: az group list --query \"[?starts_with(name, '$PREFIX')]\""
}

# Generate summary report
generate_summary() {
    local rg_count="$1"
    local kv_count="$2"
    local sa_count="$3"

    echo
    echo "========================================"
    log_info "Cleanup Summary"
    echo "========================================"
    echo "Prefix:              $PREFIX"
    echo "Dry-run mode:        $DRY_RUN"
    echo "Resource Groups:     $rg_count"
    echo "Key Vaults:          $kv_count"
    echo "Storage Accounts:    $sa_count"
    echo "========================================"
    echo

    if [ "$DRY_RUN" = true ]; then
        log_warning "This was a DRY-RUN. No resources were actually deleted."
        log_info "Run without --dry-run to perform actual deletion."
    else
        log_success "Cleanup initiated successfully!"
        log_info "Monitor progress with:"
        echo "  az group list --query \"[?starts_with(name, '$PREFIX')]\""
    fi
}

# Main cleanup function
main() {
    # Check for help flag first (before parse_args)
    for arg in "$@"; do
        if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
            show_help
            exit 0
        fi
    done

    parse_args "$@"

    echo "========================================"
    log_info "Azure Iteration Resource Cleanup"
    echo "========================================"
    echo

    check_prerequisites

    # Step 1: List and delete resource groups
    log_info "Step 1: Processing resource groups..."
    local rgs
    rgs=$(list_resource_groups)
    local rg_count
    rg_count=$(echo "$rgs" | jq '. | length')

    if [ "$rg_count" -gt 0 ]; then
        delete_resource_groups "$rgs"
    fi
    echo

    # Step 2: List and purge soft-deleted Key Vaults
    log_info "Step 2: Processing soft-deleted Key Vaults..."
    local kvs
    kvs=$(list_deleted_keyvaults)
    local kv_count
    kv_count=$(echo "$kvs" | jq '. | length')

    if [ "$kv_count" -gt 0 ]; then
        purge_deleted_keyvaults "$kvs"
    fi
    echo

    # Step 3: List and delete orphaned storage accounts
    log_info "Step 3: Processing storage accounts..."
    local storage_accounts
    storage_accounts=$(list_storage_accounts)
    local sa_count
    sa_count=$(echo "$storage_accounts" | jq '. | length')

    if [ "$sa_count" -gt 0 ]; then
        delete_storage_accounts "$storage_accounts"
    fi
    echo

    # Step 4: Wait for deletions (optional)
    if [ "$rg_count" -gt 0 ] && [ "$DRY_RUN" = false ]; then
        log_info "Step 4: Monitoring deletion progress..."
        wait_for_deletions
    fi

    # Generate summary
    generate_summary "$rg_count" "$kv_count" "$sa_count"
}

# Run main function
main "$@"
