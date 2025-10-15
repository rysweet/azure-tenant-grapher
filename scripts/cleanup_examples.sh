#!/usr/bin/env bash
# cleanup_examples.sh
# Quick reference examples for cleanup_iteration_resources.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_SCRIPT="$SCRIPT_DIR/cleanup_iteration_resources.sh"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

show_example() {
    local title="$1"
    local command="$2"
    echo
    echo -e "${BLUE}Example: $title${NC}"
    echo -e "${GREEN}Command:${NC}"
    echo "  $command"
    echo
}

cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════╗
║           Iteration Resource Cleanup - Quick Examples               ║
╚══════════════════════════════════════════════════════════════════════╝

EOF

show_example \
    "1. DRY-RUN (Always Start Here)" \
    "$CLEANUP_SCRIPT ITERATION15_ --dry-run"

show_example \
    "2. Interactive Cleanup (With Confirmations)" \
    "$CLEANUP_SCRIPT ITERATION15_"

show_example \
    "3. Automated Cleanup (No Confirmations)" \
    "$CLEANUP_SCRIPT ITERATION15_ --skip-confirmation"

show_example \
    "4. Cleanup in Specific Subscription" \
    "$CLEANUP_SCRIPT ITERATION15_ --subscription xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

show_example \
    "5. Verbose Logging" \
    "$CLEANUP_SCRIPT ITERATION15_ --verbose"

show_example \
    "6. CI/CD Pipeline Usage" \
    "$CLEANUP_SCRIPT ITERATION15_ --skip-confirmation --verbose || true"

echo
echo "════════════════════════════════════════════════════════════════════"
echo " Common Workflows"
echo "════════════════════════════════════════════════════════════════════"
echo

echo "Before Deploying New Iteration:"
echo "  1. $CLEANUP_SCRIPT ITERATION15_ --dry-run"
echo "  2. $CLEANUP_SCRIPT ITERATION15_"
echo "  3. az group list --query \"[?starts_with(name, 'ITERATION15_')]\""
echo "  4. uv run atg create-tenant --spec spec.md"
echo

echo "Cleanup Multiple Iterations:"
echo "  for i in {10..15}; do"
echo "    $CLEANUP_SCRIPT ITERATION\${i}_ --skip-confirmation"
echo "  done"
echo

echo "Verify Cleanup:"
echo "  az group list --query \"[?starts_with(name, 'ITERATION15_')]\" -o table"
echo "  az keyvault list-deleted --query \"[?starts_with(name, 'iteration15')]\" -o table"
echo

echo "════════════════════════════════════════════════════════════════════"
echo

# If arguments provided, run the actual cleanup script
if [ $# -gt 0 ]; then
    echo "Running cleanup with arguments: $*"
    echo
    exec "$CLEANUP_SCRIPT" "$@"
fi
EOF
