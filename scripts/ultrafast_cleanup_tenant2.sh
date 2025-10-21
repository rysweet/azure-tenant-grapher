#!/bin/bash
# Ultra-fast parallel cleanup for DefenderATEVET12 tenant
# Deletes ALL resource groups EXCEPT rysweet-linux-vm-pool variants
# Uses GNU parallel for maximum throughput
#
# Usage:
#   ./scripts/ultrafast_cleanup_tenant2.sh --dry-run
#   ./scripts/ultrafast_cleanup_tenant2.sh
#   ./scripts/ultrafast_cleanup_tenant2.sh --jobs 50    # Custom parallelism

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default settings
DRY_RUN=false
PARALLEL_JOBS=100  # Delete 100 resource groups simultaneously

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --jobs)
            PARALLEL_JOBS="$2"
            shift 2
            ;;
        *)
            ;;
    esac
done

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}ULTRA-FAST DefenderATEVET12 Cleanup${NC}"
echo -e "${BLUE}Parallel jobs: ${PARALLEL_JOBS}${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Fetch all resource groups
echo -e "${YELLOW}Fetching resource groups...${NC}"
ALL_RGS=$(az group list --query "[].name" -o tsv)
RGS_TO_DELETE=$(echo "$ALL_RGS" | grep -v "rysweet-linux-vm-pool" || true)
DELETE_COUNT=$(echo "$RGS_TO_DELETE" | grep -c . || echo 0)
PRESERVE_COUNT=$(echo "$ALL_RGS" | grep -c "rysweet-linux-vm-pool" || echo 0)

echo -e "${GREEN}Total: $(echo "$ALL_RGS" | wc -l)${NC}"
echo -e "${RED}To DELETE: ${DELETE_COUNT}${NC}"
echo -e "${YELLOW}To PRESERVE: ${PRESERVE_COUNT}${NC}"
echo ""

# Dry run
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}=== DRY RUN ===${NC}"
    echo "$RGS_TO_DELETE" | head -20
    [ "$DELETE_COUNT" -gt 20 ] && echo "... and $((DELETE_COUNT - 20)) more"
    exit 0
fi

# Create deletion function for parallel execution
delete_rg() {
    local RG_NAME=$1
    local INDEX=$2
    local TOTAL=$3

    if az group delete --name "$RG_NAME" --yes --no-wait 2>/dev/null; then
        echo -e "${GREEN}[$INDEX/$TOTAL] ✓ Initiated: $RG_NAME${NC}"
        return 0
    else
        echo -e "${RED}[$INDEX/$TOTAL] ✗ Failed: $RG_NAME${NC}"
        return 1
    fi
}

export -f delete_rg
export GREEN RED YELLOW NC

# Execute parallel deletion using xargs
echo -e "${RED}Deleting ${DELETE_COUNT} resource groups with ${PARALLEL_JOBS} parallel jobs...${NC}"
echo ""

START_TIME=$(date +%s)

# Use xargs for parallel execution
INDEX=0
echo "$RGS_TO_DELETE" | while read -r RG; do
    [ -z "$RG" ] && continue
    INDEX=$((INDEX + 1))
    echo "$RG $INDEX $DELETE_COUNT"
done | xargs -P "$PARALLEL_JOBS" -n 3 bash -c 'delete_rg "$0" "$1" "$2"'

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}Deletion initiated for all ${DELETE_COUNT} resource groups${NC}"
echo -e "${YELLOW}Time taken: ${DURATION} seconds${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${YELLOW}Deletions are async. Monitor with: az group list --query \"[?properties.provisioningState=='Deleting'].name\"${NC}"
echo ""
echo -e "${GREEN}Preserved: rysweet-linux-vm-pool variants${NC}"
