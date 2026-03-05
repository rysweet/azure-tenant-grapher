#!/usr/bin/env bash
#
# Cleanup Target Tenant Resources
#
# This script deletes ALL resources from your currently logged-in Azure subscription.
# It's designed to prepare a target tenant for architecture-based replication.
#
# WARNING: THIS IS DESTRUCTIVE! All resources will be deleted.
#
# Usage:
#   ./scripts/cleanup_target_tenant.sh
#
# Or with automatic confirmation (use with caution):
#   ./scripts/cleanup_target_tenant.sh --yes

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SKIP_CONFIRM=false

# Parse arguments
if [ "$1" = "--yes" ] || [ "$1" = "-y" ]; then
    SKIP_CONFIRM=true
fi

echo -e "${RED}======================================================${NC}"
echo -e "${RED}WARNING: TARGET TENANT CLEANUP${NC}"
echo -e "${RED}======================================================${NC}"
echo

# Check Azure login
echo -e "${YELLOW}[1/5] Checking Azure login...${NC}"
if ! az account show &>/dev/null; then
    echo -e "${RED}✗ Not logged in to Azure CLI${NC}"
    echo "Please run: az login"
    exit 1
fi

# Get current subscription details
SUBSCRIPTION_JSON=$(az account show -o json)
SUBSCRIPTION_ID=$(echo "$SUBSCRIPTION_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
SUBSCRIPTION_NAME=$(echo "$SUBSCRIPTION_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['name'])")
TENANT_ID=$(echo "$SUBSCRIPTION_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['tenantId'])")
USER_NAME=$(echo "$SUBSCRIPTION_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['user']['name'])")

echo -e "${GREEN}✓ Logged in as: $USER_NAME${NC}"
echo
echo "Current Azure Context:"
echo "  Tenant ID:       $TENANT_ID"
echo "  Subscription ID: $SUBSCRIPTION_ID"
echo "  Subscription:    $SUBSCRIPTION_NAME"
echo

# Count existing resources
echo -e "${YELLOW}[2/5] Scanning existing resources...${NC}"
RESOURCE_COUNT=$(az resource list --query 'length(@)' -o tsv 2>/dev/null || echo "0")
RG_COUNT=$(az group list --query 'length(@)' -o tsv 2>/dev/null || echo "0")

echo "Found:"
echo "  Resource Groups: $RG_COUNT"
echo "  Total Resources: $RESOURCE_COUNT"
echo

if [ "$RESOURCE_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ Subscription is already empty!${NC}"
    exit 0
fi

# List resource groups
echo "Resource Groups:"
az group list --query '[].{Name:name, Location:location, Resources:length(properties.resources)}' -o table 2>/dev/null || echo "Could not list resource groups"
echo

# Confirmation
if [ "$SKIP_CONFIRM" = false ]; then
    echo -e "${YELLOW}[3/5] Confirmation required...${NC}"
    echo
    echo -e "${RED}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  THIS WILL DELETE ALL RESOURCES IN THIS TENANT!   ║${NC}"
    echo -e "${RED}║                                                    ║${NC}"
    echo -e "${RED}║  • All $RG_COUNT resource groups                 ║${NC}"
    echo -e "${RED}║  • All $RESOURCE_COUNT resources                  ║${NC}"
    echo -e "${RED}║  • Cannot be undone!                              ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════╝${NC}"
    echo
    echo "Subscription to clean: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"
    echo
    echo -n "Type 'DELETE ALL RESOURCES' to continue: "
    read CONFIRMATION

    if [ "$CONFIRMATION" != "DELETE ALL RESOURCES" ]; then
        echo -e "${YELLOW}Cancelled by user${NC}"
        exit 1
    fi

    echo
    echo -n "Are you absolutely sure? Type 'YES' to proceed: "
    read FINAL_CONFIRM

    if [ "$FINAL_CONFIRM" != "YES" ]; then
        echo -e "${YELLOW}Cancelled by user${NC}"
        exit 1
    fi
fi

# Delete resources
echo
echo -e "${YELLOW}[4/5] Deleting resources...${NC}"
echo

# Get list of resource groups
RESOURCE_GROUPS=$(az group list --query '[].name' -o tsv)

if [ -z "$RESOURCE_GROUPS" ]; then
    echo -e "${GREEN}✓ No resource groups to delete${NC}"
else
    # Count for progress
    TOTAL_RGS=$(echo "$RESOURCE_GROUPS" | wc -l | tr -d ' ')
    CURRENT_RG=0

    echo "Deleting $TOTAL_RGS resource groups..."
    echo

    for RG in $RESOURCE_GROUPS; do
        CURRENT_RG=$((CURRENT_RG + 1))
        echo -e "${BLUE}[$CURRENT_RG/$TOTAL_RGS] Deleting resource group: $RG${NC}"

        # Delete with --no-wait for parallel deletion
        az group delete --name "$RG" --yes --no-wait 2>&1 | grep -v "WARNING" || true

        echo "  Started deletion (async)..."
    done

    echo
    echo -e "${YELLOW}Waiting for all deletions to complete...${NC}"
    echo "This may take several minutes depending on the number of resources."
    echo

    # Wait for all deletions
    for RG in $RESOURCE_GROUPS; do
        echo -n "  Waiting for: $RG... "

        # Poll until resource group is gone
        while az group show --name "$RG" &>/dev/null; do
            sleep 5
        done

        echo -e "${GREEN}✓ Deleted${NC}"
    done
fi

# Verify cleanup
echo
echo -e "${YELLOW}[5/5] Verifying cleanup...${NC}"

REMAINING_RGS=$(az group list --query 'length(@)' -o tsv 2>/dev/null || echo "0")
REMAINING_RESOURCES=$(az resource list --query 'length(@)' -o tsv 2>/dev/null || echo "0")

if [ "$REMAINING_RGS" -eq 0 ] && [ "$REMAINING_RESOURCES" -eq 0 ]; then
    echo -e "${GREEN}✓ Cleanup complete!${NC}"
    echo
    echo "Subscription is now empty:"
    echo "  Resource Groups: 0"
    echo "  Total Resources: 0"
    echo
    echo -e "${GREEN}Ready for architecture-based replication!${NC}"
else
    echo -e "${YELLOW}⚠ Cleanup incomplete${NC}"
    echo "  Resource Groups: $REMAINING_RGS"
    echo "  Total Resources: $REMAINING_RESOURCES"
    echo
    echo "Some resources may still be deleting. Run this script again or check manually:"
    echo "  az group list"
fi

echo
echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}Cleanup Summary${NC}"
echo -e "${BLUE}======================================================${NC}"
echo "Subscription:  $SUBSCRIPTION_NAME"
echo "Deleted RGs:   $(($RG_COUNT - $REMAINING_RGS))"
echo "Remaining RGs: $REMAINING_RGS"
echo "Deleted Resources: $(($RESOURCE_COUNT - $REMAINING_RESOURCES))"
echo "Remaining Resources: $REMAINING_RESOURCES"
echo -e "${BLUE}======================================================${NC}"
