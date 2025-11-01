#!/bin/bash
# Example: Deploy Azure resources from source tenant to target tenant
#
# This script demonstrates the complete workflow for cross-tenant deployment:
# 1. Scan source tenant to discover resources
# 2. Generate IaC with translation for target tenant
# 3. Validate and deploy the generated Terraform
#
# PREREQUISITES:
# - Azure CLI authenticated to both source and target tenants
# - Neo4j container running (or use --no-container flag)
# - uv package manager installed
# - Terraform installed
#
# USAGE:
#   ./examples/cross_tenant_deployment.sh
#
# Or with custom configuration:
#   SOURCE_TENANT_ID=xxx TARGET_TENANT_ID=yyy ./examples/cross_tenant_deployment.sh

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# =============================================================================
# Configuration
# =============================================================================

# Source tenant (where resources are discovered from)
SOURCE_TENANT_ID="${SOURCE_TENANT_ID:-${AZURE_TENANT_ID:-}}"
SOURCE_SUBSCRIPTION="${SOURCE_SUBSCRIPTION:-}"  # Optional: auto-detected from scan

# Target tenant (where resources will be deployed to)
TARGET_TENANT_ID="${TARGET_TENANT_ID:-}"
TARGET_SUBSCRIPTION="${TARGET_SUBSCRIPTION:-}"

# Identity mapping file (optional, but recommended for production)
IDENTITY_MAPPING_FILE="${IDENTITY_MAPPING_FILE:-examples/identity_mapping_example.json}"

# Import strategy for existing resources
# Options: none, resource_groups, all_resources, selective
IMPORT_STRATEGY="${IMPORT_STRATEGY:-resource_groups}"

# Output directory (will be created with timestamp)
OUTPUT_BASE="outputs"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        log_error "uv is not installed. Install from: https://github.com/astral-sh/uv"
        exit 1
    fi

    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_warning "Terraform is not installed. The script will attempt to install it."
    fi

    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Install from: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

validate_configuration() {
    log_info "Validating configuration..."

    if [ -z "$SOURCE_TENANT_ID" ]; then
        log_error "SOURCE_TENANT_ID is not set. Set it via environment variable or .env file."
        echo "  Example: export SOURCE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        exit 1
    fi

    if [ -z "$TARGET_TENANT_ID" ]; then
        log_error "TARGET_TENANT_ID is not set. Set it via environment variable."
        echo "  Example: export TARGET_TENANT_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
        exit 1
    fi

    if [ -z "$TARGET_SUBSCRIPTION" ]; then
        log_error "TARGET_SUBSCRIPTION is not set. Set it via environment variable."
        echo "  Example: export TARGET_SUBSCRIPTION=zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"
        exit 1
    fi

    log_success "Configuration validated"
    echo "  Source Tenant: $SOURCE_TENANT_ID"
    echo "  Target Tenant: $TARGET_TENANT_ID"
    echo "  Target Subscription: $TARGET_SUBSCRIPTION"

    if [ -f "$IDENTITY_MAPPING_FILE" ]; then
        log_info "Identity mapping file found: $IDENTITY_MAPPING_FILE"
    else
        log_warning "Identity mapping file not found: $IDENTITY_MAPPING_FILE"
        log_warning "Proceeding without identity mapping. Entra ID object references may not work."
    fi
}

authenticate_azure() {
    log_info "Checking Azure authentication..."

    # Check if authenticated to source tenant
    log_info "Authenticating to source tenant..."
    az login --tenant "$SOURCE_TENANT_ID" --allow-no-subscriptions > /dev/null 2>&1 || {
        log_error "Failed to authenticate to source tenant: $SOURCE_TENANT_ID"
        exit 1
    }
    log_success "Authenticated to source tenant"

    # Check if authenticated to target tenant
    log_info "Authenticating to target tenant..."
    az login --tenant "$TARGET_TENANT_ID" --allow-no-subscriptions > /dev/null 2>&1 || {
        log_error "Failed to authenticate to target tenant: $TARGET_TENANT_ID"
        exit 1
    }
    log_success "Authenticated to target tenant"

    # Set active subscription to target
    az account set --subscription "$TARGET_SUBSCRIPTION" || {
        log_error "Failed to set active subscription to: $TARGET_SUBSCRIPTION"
        exit 1
    }
    log_success "Set active subscription to target"
}

# =============================================================================
# Step 1: Scan Source Tenant
# =============================================================================

scan_source_tenant() {
    log_info "Step 1: Scanning source tenant for resources..."

    # Run the scan command
    if ! uv run atg scan --tenant-id "$SOURCE_TENANT_ID"; then
        log_error "Failed to scan source tenant"
        exit 1
    fi

    log_success "Source tenant scan completed successfully"
}

# =============================================================================
# Step 2: Generate IaC with Translation
# =============================================================================

generate_iac() {
    log_info "Step 2: Generating IaC with cross-tenant translation..."

    # Build command with optional parameters
    CMD="uv run atg generate-iac --tenant-id $SOURCE_TENANT_ID --target-subscription $TARGET_SUBSCRIPTION --format terraform"

    # Add identity mapping if available
    if [ -f "$IDENTITY_MAPPING_FILE" ]; then
        log_info "Using identity mapping file: $IDENTITY_MAPPING_FILE"
        # Note: Currently the CLI doesn't have --identity-mapping-file parameter exposed
        # This is a placeholder for when the feature is fully integrated
        log_warning "Identity mapping file support is coming soon. Currently handled internally."
    fi

    # Add import strategy if not 'none'
    if [ "$IMPORT_STRATEGY" != "none" ]; then
        log_info "Using import strategy: $IMPORT_STRATEGY"
        CMD="$CMD --auto-import-existing --import-strategy $IMPORT_STRATEGY"
    fi

    log_info "Running: $CMD"

    # Execute the command
    if ! eval "$CMD"; then
        log_error "Failed to generate IaC"
        exit 1
    fi

    log_success "IaC generation completed successfully"

    # Find the latest output directory
    LATEST_OUTPUT=$(ls -td outputs/iac-out-* 2>/dev/null | head -1)

    if [ -z "$LATEST_OUTPUT" ]; then
        log_error "Could not find generated IaC output directory"
        exit 1
    fi

    log_info "Generated IaC location: $LATEST_OUTPUT"
    echo "$LATEST_OUTPUT"
}

# =============================================================================
# Step 3: Validate Terraform
# =============================================================================

validate_terraform() {
    local output_dir="$1"

    log_info "Step 3: Validating generated Terraform..."

    cd "$output_dir" || {
        log_error "Failed to change to output directory: $output_dir"
        exit 1
    }

    # Initialize Terraform
    log_info "Running: terraform init"
    if ! terraform init; then
        log_error "Terraform init failed"
        cd - > /dev/null
        exit 1
    fi
    log_success "Terraform initialized"

    # Validate Terraform
    log_info "Running: terraform validate"
    if ! terraform validate; then
        log_error "Terraform validation failed"
        cd - > /dev/null
        exit 1
    fi
    log_success "Terraform validation passed"

    cd - > /dev/null
}

# =============================================================================
# Step 4: Plan Deployment
# =============================================================================

plan_deployment() {
    local output_dir="$1"

    log_info "Step 4: Planning Terraform deployment..."

    cd "$output_dir" || {
        log_error "Failed to change to output directory: $output_dir"
        exit 1
    }

    log_info "Running: terraform plan"
    if ! terraform plan -out=tfplan; then
        log_error "Terraform plan failed"
        cd - > /dev/null
        exit 1
    fi

    log_success "Terraform plan completed successfully"
    log_info "Plan saved to: $output_dir/tfplan"

    cd - > /dev/null
}

# =============================================================================
# Step 5: Deploy (Optional)
# =============================================================================

deploy_terraform() {
    local output_dir="$1"

    log_warning "Step 5: Terraform deployment (manual step)"
    echo ""
    echo "To deploy the infrastructure, run the following commands:"
    echo ""
    echo "  cd $output_dir"
    echo "  terraform apply tfplan"
    echo ""
    log_warning "CAUTION: Review the plan carefully before deploying!"
    log_warning "This will create real Azure resources and may incur costs."
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    echo "========================================================================"
    echo "Cross-Tenant Azure Deployment Example"
    echo "========================================================================"
    echo ""

    # Run all steps
    check_prerequisites
    validate_configuration
    authenticate_azure

    echo ""
    echo "========================================================================"
    echo "Beginning Cross-Tenant Deployment Workflow"
    echo "========================================================================"
    echo ""

    scan_source_tenant
    echo ""

    output_dir=$(generate_iac)
    echo ""

    validate_terraform "$output_dir"
    echo ""

    plan_deployment "$output_dir"
    echo ""

    deploy_terraform "$output_dir"
    echo ""

    echo "========================================================================"
    echo "Workflow Completed Successfully!"
    echo "========================================================================"
    echo ""
    log_success "All pre-deployment steps completed successfully"
    log_info "Next steps:"
    echo "  1. Review the generated Terraform in: $output_dir"
    echo "  2. Inspect the plan file: $output_dir/tfplan"
    echo "  3. Deploy when ready: cd $output_dir && terraform apply tfplan"
    echo ""
    log_info "For troubleshooting, see: $output_dir/translation_report.json"
}

# Run main function
main "$@"
