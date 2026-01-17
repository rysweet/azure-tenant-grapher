#!/bin/bash
# Verify hash tracking installation
#
# This script checks that all components of hash tracking are installed
# and working correctly.

set -e

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Hash Tracking Installation Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function for test results
test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Test 1: Check if hash_tracker.py exists
echo -e "${YELLOW}Test 1: Checking hash_tracker.py exists...${NC}"
if [ -f "$PROJECT_ROOT/src/version_tracking/hash_tracker.py" ]; then
    test_result 0 "hash_tracker.py found"
else
    test_result 1 "hash_tracker.py not found"
fi
echo ""

# Test 2: Check if detector.py has hash validation
echo -e "${YELLOW}Test 2: Checking detector.py enhancements...${NC}"
if grep -q "_validate_construction_hash" "$PROJECT_ROOT/src/version_tracking/detector.py"; then
    test_result 0 "detector.py has hash validation"
else
    test_result 1 "detector.py missing hash validation"
fi
echo ""

# Test 3: Check if version file has hash field
echo -e "${YELLOW}Test 3: Checking .atg_graph_version format...${NC}"
if [ -f "$PROJECT_ROOT/.atg_graph_version" ]; then
    if grep -q "construction_hash" "$PROJECT_ROOT/.atg_graph_version"; then
        test_result 0 ".atg_graph_version has hash field"
    else
        test_result 1 ".atg_graph_version missing hash field"
    fi
else
    test_result 1 ".atg_graph_version not found"
fi
echo ""

# Test 4: Check if pre-commit hook exists
echo -e "${YELLOW}Test 4: Checking pre-commit hook...${NC}"
if [ -f "$PROJECT_ROOT/hooks/pre-commit-version-check.sh" ]; then
    if [ -x "$PROJECT_ROOT/hooks/pre-commit-version-check.sh" ]; then
        test_result 0 "pre-commit hook found and executable"
    else
        test_result 1 "pre-commit hook found but not executable"
    fi
else
    test_result 1 "pre-commit hook not found"
fi
echo ""

# Test 5: Check if installation script exists
echo -e "${YELLOW}Test 5: Checking installation script...${NC}"
if [ -f "$PROJECT_ROOT/scripts/install-version-hooks.sh" ]; then
    if [ -x "$PROJECT_ROOT/scripts/install-version-hooks.sh" ]; then
        test_result 0 "installation script found and executable"
    else
        test_result 1 "installation script found but not executable"
    fi
else
    test_result 1 "installation script not found"
fi
echo ""

# Test 6: Check if tests exist
echo -e "${YELLOW}Test 6: Checking test files...${NC}"
if [ -f "$PROJECT_ROOT/tests/unit/version_tracking/test_hash_tracker.py" ]; then
    test_result 0 "test_hash_tracker.py found"
else
    test_result 1 "test_hash_tracker.py not found"
fi

if [ -f "$PROJECT_ROOT/tests/unit/version_tracking/test_detector_hash.py" ]; then
    test_result 0 "test_detector_hash.py found"
else
    test_result 1 "test_detector_hash.py not found"
fi
echo ""

# Test 7: Check if Python imports work
echo -e "${YELLOW}Test 7: Checking Python imports...${NC}"
cd "$PROJECT_ROOT"
if python3 -c "from src.version_tracking import HashTracker, calculate_construction_hash" 2>/dev/null; then
    test_result 0 "Python imports work"
else
    test_result 1 "Python imports failed"
fi
echo ""

# Test 8: Check if hash calculation works
echo -e "${YELLOW}Test 8: Testing hash calculation...${NC}"
HASH_OUTPUT=$(python3 -c "from src.version_tracking.hash_tracker import calculate_construction_hash; print(calculate_construction_hash())" 2>/dev/null)
if [ ${#HASH_OUTPUT} -eq 64 ]; then
    test_result 0 "Hash calculation works (output: ${HASH_OUTPUT:0:16}...)"
else
    test_result 1 "Hash calculation failed or wrong length"
fi
echo ""

# Test 9: Check if documentation exists
echo -e "${YELLOW}Test 9: Checking documentation...${NC}"
if [ -f "$PROJECT_ROOT/src/version_tracking/README.md" ]; then
    test_result 0 "README.md found"
else
    test_result 1 "README.md not found"
fi
echo ""

# Test 10: Check if examples exist
echo -e "${YELLOW}Test 10: Checking examples...${NC}"
if [ -f "$PROJECT_ROOT/examples/version_tracking_workflow.py" ]; then
    test_result 0 "Example workflow found"
else
    test_result 1 "Example workflow not found"
fi
echo ""

# Test 11: Check if hook is installed
echo -e "${YELLOW}Test 11: Checking git hook installation...${NC}"
if [ -f "$PROJECT_ROOT/.git/hooks/pre-commit" ]; then
    if grep -q "pre-commit-version-check" "$PROJECT_ROOT/.git/hooks/pre-commit"; then
        test_result 0 "Git hook installed"
    else
        echo -e "${YELLOW}⚠️  INFO${NC}: Git hook exists but not our version check"
        echo "   Run: ./scripts/install-version-hooks.sh to install"
    fi
else
    echo -e "${YELLOW}⚠️  INFO${NC}: Git hook not installed yet"
    echo "   Run: ./scripts/install-version-hooks.sh to install"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Install git hook: ./scripts/install-version-hooks.sh"
    echo "  2. Run tests: uv run pytest tests/unit/version_tracking/ -v"
    echo "  3. Try example: PYTHONPATH=. python3 examples/version_tracking_workflow.py"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    echo ""
    echo -e "${YELLOW}Please check the failures above and ensure all components are installed.${NC}"
    echo ""
    exit 1
fi
