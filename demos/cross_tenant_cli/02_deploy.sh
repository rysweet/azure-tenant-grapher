#!/bin/bash
set -e

# Demo script for deploying IaC to target tenant
# This demonstrates the new 'atg deploy' command for multi-tenant IaC deployment

TARGET_TENANT_ID="${TARGET_TENANT_ID:-506f82b2-e2e7-40a2-b0be-ea6f8cb908f8}"
RESOURCE_GROUP="${RESOURCE_GROUP:-SimuLand-Replica}"
LOCATION="${LOCATION:-eastus}"
IAC_DIR="${IAC_DIR:-./output/iac}"

echo "=========================================="
echo "Azure Tenant Grapher - IaC Deployment Demo"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Target Tenant: $TARGET_TENANT_ID"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  IaC Directory: $IAC_DIR"
echo ""

# Check if IaC directory exists
if [ ! -d "$IAC_DIR" ]; then
    echo "Error: IaC directory not found: $IAC_DIR"
    echo "Please generate IaC first using:"
    echo "  uv run atg generate-iac --tenant-id <TENANT_ID> --output $IAC_DIR"
    exit 1
fi

# Step 1: Dry-run deployment (plan/validate only)
echo "Step 1: Running dry-run deployment (plan/validate only)..."
echo ""

uv run atg deploy \
  --iac-dir "$IAC_DIR" \
  --target-tenant-id "$TARGET_TENANT_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --dry-run

echo ""
echo "=========================================="
echo "Dry-run completed successfully!"
echo ""
echo "To deploy for real, run:"
echo "  uv run atg deploy \\"
echo "    --iac-dir $IAC_DIR \\"
echo "    --target-tenant-id $TARGET_TENANT_ID \\"
echo "    --resource-group $RESOURCE_GROUP \\"
echo "    --location $LOCATION"
echo ""
echo "Or set DEPLOY_FOR_REAL=1 and re-run this script:"
echo "  DEPLOY_FOR_REAL=1 ./demos/cross_tenant_cli/02_deploy.sh"
echo "=========================================="

# Step 2: Actual deployment (if DEPLOY_FOR_REAL is set)
if [ "${DEPLOY_FOR_REAL}" = "1" ]; then
    echo ""
    echo "DEPLOY_FOR_REAL is set. Proceeding with actual deployment..."
    echo ""

    read -p "Are you sure you want to deploy to $TARGET_TENANT_ID? (yes/no) " -r
    echo
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi

    echo "Deploying IaC to target tenant..."

    uv run atg deploy \
      --iac-dir "$IAC_DIR" \
      --target-tenant-id "$TARGET_TENANT_ID" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION"

    echo ""
    echo "=========================================="
    echo "Deployment complete!"
    echo "=========================================="
fi
