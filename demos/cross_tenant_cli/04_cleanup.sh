#!/bin/bash
set -e

# Demo script for cleaning up deployed resources
# This demonstrates cleanup after cross-tenant IaC deployment

TARGET_TENANT_ID="${TARGET_TENANT_ID:-506f82b2-e2e7-40a2-b0be-ea6f8cb908f8}"
RESOURCE_GROUP="${RESOURCE_GROUP:-SimuLand-Replica}"
IAC_DIR="${IAC_DIR:-./output/iac}"

echo "=========================================="
echo "Azure Tenant Grapher - Cleanup Demo"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Target Tenant: $TARGET_TENANT_ID"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  IaC Directory: $IAC_DIR"
echo ""

# Warning prompt
echo "⚠️  WARNING: This will destroy all resources in $RESOURCE_GROUP"
echo ""
read -p "Are you sure you want to proceed? (yes/no) " -r
echo
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Check if IaC directory exists
if [ ! -d "$IAC_DIR" ]; then
    echo "Warning: IaC directory not found: $IAC_DIR"
    echo "Will attempt to delete resource group using Azure CLI directly."
    USE_AZURE_CLI=1
else
    USE_AZURE_CLI=0
fi

# Step 1: Switch to target tenant
echo "Step 1: Switching to target tenant..."
echo ""
az account set --tenant "$TARGET_TENANT_ID"
az account show
echo ""

# Step 2: Destroy using IaC tool or Azure CLI
if [ "$USE_AZURE_CLI" = "1" ]; then
    echo "Step 2: Deleting resource group using Azure CLI..."
    echo ""

    # Check if RG exists
    if az group exists --name "$RESOURCE_GROUP" | grep -q "true"; then
        echo "Resource group $RESOURCE_GROUP exists. Deleting..."
        az group delete --name "$RESOURCE_GROUP" --yes --no-wait
        echo "Deletion initiated (running in background)"
        echo ""
        echo "To monitor deletion status:"
        echo "  az group list --query \"[?name=='$RESOURCE_GROUP'].{Name:name, State:properties.provisioningState}\" -o table"
    else
        echo "Resource group $RESOURCE_GROUP does not exist. Nothing to delete."
    fi
else
    # Detect IaC format
    if ls "$IAC_DIR"/*.tf >/dev/null 2>&1; then
        IAC_FORMAT="terraform"
    elif ls "$IAC_DIR"/*.bicep >/dev/null 2>&1; then
        IAC_FORMAT="bicep"
    elif ls "$IAC_DIR"/*.json >/dev/null 2>&1; then
        IAC_FORMAT="arm"
    else
        echo "Error: Cannot detect IaC format in $IAC_DIR"
        exit 1
    fi

    echo "Step 2: Destroying resources using $IAC_FORMAT..."
    echo ""

    case "$IAC_FORMAT" in
        terraform)
            cd "$IAC_DIR"
            echo "Running terraform destroy..."
            terraform destroy -auto-approve
            ;;
        bicep)
            echo "Deleting resource group (Bicep doesn't have destroy command)..."
            az group delete --name "$RESOURCE_GROUP" --yes --no-wait
            ;;
        arm)
            echo "Deleting resource group (ARM doesn't have destroy command)..."
            az group delete --name "$RESOURCE_GROUP" --yes --no-wait
            ;;
    esac
fi

echo ""
echo "=========================================="
echo "Cleanup initiated!"
echo ""
echo "Note: Resource deletion may take several minutes."
echo "Use 'az group list' to monitor deletion progress."
echo "=========================================="
