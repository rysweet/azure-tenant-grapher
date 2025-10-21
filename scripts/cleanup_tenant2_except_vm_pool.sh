#!/bin/bash
# Cleanup script for DefenderATEVET12 tenant
# Deletes ALL resource groups EXCEPT rysweet-linux-vm-pool and its iteration variants
#
# Usage:
#   ./scripts/cleanup_tenant2_except_vm_pool.sh --dry-run    # Preview only
#   ./scripts/cleanup_tenant2_except_vm_pool.sh              # Execute deletion
#   ./scripts/cleanup_tenant2_except_vm_pool.sh --force      # Skip confirmations

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
FORCE=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            # Unknown option
            ;;
    esac
done

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}DefenderATEVET12 Tenant Cleanup${NC}"
echo -e "${BLUE}Excludes: rysweet-linux-vm-pool (all variants)${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Get all resource groups
echo -e "${YELLOW}Fetching all resource groups...${NC}"
ALL_RGS=$(az group list --query "[].name" -o tsv)
TOTAL_RGS=$(echo "$ALL_RGS" | wc -l)

# Filter out rysweet-linux-vm-pool and its variants
RGS_TO_DELETE=$(echo "$ALL_RGS" | grep -v "rysweet-linux-vm-pool" || true)
DELETE_COUNT=$(echo "$RGS_TO_DELETE" | grep -v '^$' | wc -l)
EXCLUDED_COUNT=$((TOTAL_RGS - DELETE_COUNT))

echo -e "${GREEN}Total resource groups: ${TOTAL_RGS}${NC}"
echo -e "${GREEN}Resource groups to DELETE: ${DELETE_COUNT}${NC}"
echo -e "${YELLOW}Resource groups to PRESERVE: ${EXCLUDED_COUNT}${NC}"
echo ""

# Show preserved resource groups
echo -e "${YELLOW}=== PRESERVED Resource Groups ===${NC}"
echo "$ALL_RGS" | grep "rysweet-linux-vm-pool" || echo "None"
echo ""

# Preview mode
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}=== DRY RUN MODE - NO CHANGES WILL BE MADE ===${NC}"
    echo ""
    echo -e "${RED}Resource groups that would be DELETED:${NC}"
    echo "$RGS_TO_DELETE" | head -20
    if [ "$DELETE_COUNT" -gt 20 ]; then
        echo "... and $((DELETE_COUNT - 20)) more"
    fi
    echo ""
    echo -e "${GREEN}Run without --dry-run to execute the deletion.${NC}"
    exit 0
fi

# Confirmation prompt
if [ "$FORCE" = false ]; then
    echo -e "${RED}WARNING: This will DELETE ${DELETE_COUNT} resource groups!${NC}"
    echo -e "${YELLOW}This action CANNOT be undone!${NC}"
    echo ""
    read -p "Type 'DELETE ALL' to confirm: " CONFIRMATION

    if [ "$CONFIRMATION" != "DELETE ALL" ]; then
        echo -e "${YELLOW}Aborted. No changes made.${NC}"
        exit 0
    fi
    echo ""
fi

# Execute deletion
echo -e "${RED}Starting deletion of ${DELETE_COUNT} resource groups...${NC}"
echo -e "${YELLOW}This may take a LONG time (potentially hours)...${NC}"
echo ""

DELETED=0
FAILED=0
FAILED_RGS=()

# Create a temporary file to track progress
PROGRESS_FILE="/tmp/cleanup_progress_$$.txt"
echo "0" > "$PROGRESS_FILE"

# Delete resource groups in parallel (batches of 10)
BATCH_SIZE=10
CURRENT_BATCH=0

while IFS= read -r RG_NAME; do
    [ -z "$RG_NAME" ] && continue

    ((CURRENT_BATCH++))

    (
        echo -e "${YELLOW}[$CURRENT_BATCH/$DELETE_COUNT] Deleting: ${RG_NAME}${NC}"

        if az group delete --name "$RG_NAME" --yes --no-wait 2>/dev/null; then
            echo -e "${GREEN}[$CURRENT_BATCH/$DELETE_COUNT] Initiated deletion: ${RG_NAME}${NC}"
            PROGRESS=$(cat "$PROGRESS_FILE")
            echo "$((PROGRESS + 1))" > "$PROGRESS_FILE"
        else
            echo -e "${RED}[$CURRENT_BATCH/$DELETE_COUNT] Failed to initiate: ${RG_NAME}${NC}"
            echo "$RG_NAME" >> "$PROGRESS_FILE.failed"
        fi
    ) &

    # Wait for batch to complete before starting next batch
    if [ $((CURRENT_BATCH % BATCH_SIZE)) -eq 0 ]; then
        wait
        echo ""
        echo -e "${BLUE}Completed batch of $BATCH_SIZE deletions...${NC}"
        echo ""
    fi
done <<< "$RGS_TO_DELETE"

# Wait for remaining jobs
wait

echo ""
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}Deletion initiated for all resource groups${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Summary
INITIATED=$(cat "$PROGRESS_FILE")
echo -e "${GREEN}Successfully initiated: ${INITIATED}${NC}"

if [ -f "$PROGRESS_FILE.failed" ]; then
    FAILED=$(wc -l < "$PROGRESS_FILE.failed")
    echo -e "${RED}Failed to initiate: ${FAILED}${NC}"
    echo ""
    echo -e "${RED}Failed resource groups:${NC}"
    cat "$PROGRESS_FILE.failed"
else
    echo -e "${GREEN}Failed: 0${NC}"
fi

echo ""
echo -e "${YELLOW}Note: Deletions are running asynchronously in Azure.${NC}"
echo -e "${YELLOW}Use 'az group list' to check progress.${NC}"
echo -e "${YELLOW}It may take hours for all resources to be fully deleted.${NC}"
echo ""
echo -e "${GREEN}Preserved resource groups (rysweet-linux-vm-pool):${NC}"
echo "$ALL_RGS" | grep "rysweet-linux-vm-pool"

# Cleanup temp files
rm -f "$PROGRESS_FILE" "$PROGRESS_FILE.failed"

echo ""
echo -e "${GREEN}Cleanup script completed!${NC}"
