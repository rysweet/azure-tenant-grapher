#!/bin/bash
# Pre-commit hook: Enforce version update when construction files change
#
# This hook prevents commits when graph construction files are modified
# but the version file (.atg_graph_version) is not updated.

set -e

# Patterns that match graph construction files
CONSTRUCTION_PATTERNS="src/relationship_rules/|src/services/azure_discovery_service.py|src/resource_processor.py|src/azure_tenant_grapher.py"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if construction files changed
construction_changed=$(git diff --cached --name-only | grep -E "$CONSTRUCTION_PATTERNS" || true)

if [ -n "$construction_changed" ]; then
    # Check if .atg_graph_version also changed
    version_changed=$(git diff --cached --name-only | grep -q ".atg_graph_version" && echo "yes" || echo "no")

    if [ "$version_changed" = "no" ]; then
        echo -e "${RED}❌ ERROR: Graph construction files changed but .atg_graph_version not updated!${NC}"
        echo ""
        echo -e "${YELLOW}Construction files modified:${NC}"
        echo "$construction_changed" | sed 's/^/  - /'
        echo ""
        echo -e "${YELLOW}Please update .atg_graph_version:${NC}"
        echo "  1. Bump version (MAJOR.MINOR.PATCH)"
        echo "  2. Update last_modified timestamp"
        echo "  3. Update construction_hash (run: python3 -c 'from src.version_tracking.hash_tracker import calculate_construction_hash; print(calculate_construction_hash())')"
        echo "  4. Add description of changes"
        echo ""
        echo -e "${YELLOW}Or skip check:${NC} git commit --no-verify"
        exit 1
    fi

    echo -e "${GREEN}✅ Version file updated with construction changes${NC}"
fi

# Success - allow commit
exit 0
