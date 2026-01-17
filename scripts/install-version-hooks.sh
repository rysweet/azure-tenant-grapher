#!/bin/bash
# Install version tracking git hooks
#
# This script installs the pre-commit hook that enforces version updates
# when graph construction files are modified.

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if we're in a git repo
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo -e "${RED}❌ Error: Not in a git repository${NC}"
    exit 1
fi

# Create pre-commit hook file
HOOK_SRC="$PROJECT_ROOT/hooks/pre-commit-version-check.sh"
HOOK_DEST="$PROJECT_ROOT/.git/hooks/pre-commit"

if [ ! -f "$HOOK_SRC" ]; then
    echo -e "${RED}❌ Error: Hook source not found: $HOOK_SRC${NC}"
    exit 1
fi

# Check if pre-commit hook already exists
if [ -f "$HOOK_DEST" ]; then
    echo -e "${YELLOW}⚠️  Pre-commit hook already exists${NC}"
    echo "Existing hook will be backed up to: $HOOK_DEST.backup"
    cp "$HOOK_DEST" "$HOOK_DEST.backup"
fi

# Install the hook
cp "$HOOK_SRC" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

echo -e "${GREEN}✅ Version tracking hooks installed${NC}"
echo ""
echo "The pre-commit hook will now enforce version updates when:"
echo "  - src/relationship_rules/ files change"
echo "  - src/services/azure_discovery_service.py changes"
echo "  - src/resource_processor.py changes"
echo "  - src/azure_tenant_grapher.py changes"
echo ""
echo "To bypass the check, use: git commit --no-verify"
