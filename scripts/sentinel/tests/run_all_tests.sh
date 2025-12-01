#!/usr/bin/env bash

# ============================================================================
# Test Runner for Sentinel Automation Tests (Issue #518)
#
# Runs all test suites:
# - Python unit tests
# - Python integration tests
# - Python E2E tests (optional, slow)
# - Bash module tests
# - Bash library tests
#
# Usage:
#   ./run_all_tests.sh              # Run all tests except E2E
#   ./run_all_tests.sh --e2e        # Include E2E tests (requires Azure)
#   ./run_all_tests.sh --fast       # Only unit tests (fastest)
#   ./run_all_tests.sh --coverage   # Run with coverage report
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests/commands"

# Test options
RUN_E2E=0
FAST_MODE=0
WITH_COVERAGE=0
VERBOSE=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
    --e2e)
        RUN_E2E=1
        shift
        ;;
    --fast)
        FAST_MODE=1
        shift
        ;;
    --coverage)
        WITH_COVERAGE=1
        shift
        ;;
    --verbose | -v)
        VERBOSE=1
        shift
        ;;
    --help | -h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --e2e         Include E2E tests (requires Azure credentials)"
        echo "  --fast        Only run unit tests (fastest)"
        echo "  --coverage    Generate coverage report"
        echo "  --verbose     Verbose output"
        echo "  --help        Show this help message"
        exit 0
        ;;
    *)
        echo "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"

    # Check for Python and pytest
    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}Error: python3 not found${NC}"
        exit 1
    fi

    if ! python3 -m pytest --version &>/dev/null; then
        echo -e "${RED}Error: pytest not found. Install with: pip install pytest${NC}"
        exit 1
    fi

    # Check for bash
    if ! command -v bash &>/dev/null; then
        echo -e "${RED}Error: bash not found${NC}"
        exit 1
    fi

    # Check for jq (needed for bash tests)
    if ! command -v jq &>/dev/null; then
        echo -e "${YELLOW}Warning: jq not found. Some bash tests may fail.${NC}"
        echo -e "${YELLOW}Install with: sudo apt install jq (Ubuntu) or brew install jq (macOS)${NC}"
    fi

    echo -e "${GREEN}Prerequisites OK${NC}"
    echo ""
}

# Run Python unit tests
run_python_unit_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Running Python Unit Tests (60% of pyramid)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    local pytest_args="-v"
    if [ $VERBOSE -eq 1 ]; then
        pytest_args="$pytest_args -s"
    fi

    if [ $WITH_COVERAGE -eq 1 ]; then
        pytest_args="$pytest_args --cov=src/commands/sentinel --cov-report=term-missing"
    fi

    python3 -m pytest $pytest_args "$TESTS_DIR/test_sentinel.py" || {
        echo -e "${RED}Python unit tests failed${NC}"
        return 1
    }

    echo -e "${GREEN}Python unit tests passed${NC}"
    echo ""
}

# Run Python integration tests
run_python_integration_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Running Python Integration Tests (30% of pyramid)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    local pytest_args="-v"
    if [ $VERBOSE -eq 1 ]; then
        pytest_args="$pytest_args -s"
    fi

    python3 -m pytest $pytest_args "$TESTS_DIR/test_sentinel_integration.py" || {
        echo -e "${RED}Python integration tests failed${NC}"
        return 1
    }

    echo -e "${GREEN}Python integration tests passed${NC}"
    echo ""
}

# Run Python E2E tests
run_python_e2e_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Running Python E2E Tests (10% of pyramid)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${YELLOW}WARNING: E2E tests will create real Azure resources${NC}"
    echo -e "${YELLOW}Ensure you have valid Azure credentials set${NC}"
    echo ""

    # Check for Azure credentials
    if [ -z "${AZURE_TENANT_ID:-}" ] || [ -z "${AZURE_SUBSCRIPTION_ID:-}" ]; then
        echo -e "${RED}Error: Missing Azure credentials${NC}"
        echo -e "${RED}Set AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET${NC}"
        return 1
    fi

    cd "$PROJECT_ROOT"

    local pytest_args="-v -m slow"
    if [ $VERBOSE -eq 1 ]; then
        pytest_args="$pytest_args -s"
    fi

    python3 -m pytest $pytest_args "$TESTS_DIR/test_sentinel_e2e.py" || {
        echo -e "${RED}Python E2E tests failed${NC}"
        return 1
    }

    echo -e "${GREEN}Python E2E tests passed${NC}"
    echo ""
}

# Run bash module tests
run_bash_module_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Running Bash Module Tests${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    cd "$SCRIPT_DIR"

    chmod +x test_modules.sh

    ./test_modules.sh || {
        echo -e "${RED}Bash module tests failed${NC}"
        return 1
    }

    echo -e "${GREEN}Bash module tests passed${NC}"
    echo ""
}

# Run bash library tests
run_bash_library_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Running Bash Library Tests${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    cd "$SCRIPT_DIR"

    chmod +x test_common_lib.sh

    ./test_common_lib.sh || {
        echo -e "${RED}Bash library tests failed${NC}"
        return 1
    }

    echo -e "${GREEN}Bash library tests passed${NC}"
    echo ""
}

# Main test execution
main() {
    local start_time=$(date +%s)
    local failed_suites=()

    echo -e "${BLUE}========================================"
    echo "Sentinel Automation Test Suite"
    echo "========================================${NC}"
    echo ""

    if [ $FAST_MODE -eq 1 ]; then
        echo -e "${YELLOW}Running in FAST mode (unit tests only)${NC}"
        echo ""
    fi

    if [ $RUN_E2E -eq 1 ]; then
        echo -e "${YELLOW}E2E tests ENABLED (will create real Azure resources)${NC}"
        echo ""
    fi

    # Check prerequisites
    check_prerequisites

    # Run test suites
    echo -e "${BLUE}Starting test execution...${NC}"
    echo ""

    # Always run unit tests
    run_python_unit_tests || failed_suites+=("Python Unit Tests")

    # Skip remaining tests in fast mode
    if [ $FAST_MODE -eq 0 ]; then
        run_python_integration_tests || failed_suites+=("Python Integration Tests")
        run_bash_library_tests || failed_suites+=("Bash Library Tests")
        run_bash_module_tests || failed_suites+=("Bash Module Tests")

        # Run E2E tests if requested
        if [ $RUN_E2E -eq 1 ]; then
            run_python_e2e_tests || failed_suites+=("Python E2E Tests")
        fi
    fi

    # Calculate duration
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Summary
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Test Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "Duration: ${duration}s"
    echo ""

    if [ ${#failed_suites[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ All test suites passed!${NC}"
        echo ""

        if [ $FAST_MODE -eq 1 ]; then
            echo -e "${YELLOW}Note: Fast mode enabled - only unit tests were run${NC}"
            echo -e "${YELLOW}Run without --fast to execute all tests${NC}"
        elif [ $RUN_E2E -eq 0 ]; then
            echo -e "${YELLOW}Note: E2E tests were skipped${NC}"
            echo -e "${YELLOW}Run with --e2e to include E2E tests${NC}"
        fi

        exit 0
    else
        echo -e "${RED}✗ Failed test suites:${NC}"
        for suite in "${failed_suites[@]}"; do
            echo -e "${RED}  - $suite${NC}"
        done
        echo ""
        exit 1
    fi
}

# Run main
main "$@"
