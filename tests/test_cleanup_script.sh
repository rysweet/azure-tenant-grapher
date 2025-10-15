#!/usr/bin/env bash
# test_cleanup_script.sh
# Test suite for cleanup_iteration_resources.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLEANUP_SCRIPT="$SCRIPT_DIR/scripts/cleanup_iteration_resources.sh"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

log_test() {
    echo -e "${BLUE}[TEST]${NC} $*"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    ((TESTS_FAILED++))
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

# Test 1: Script exists and is executable
test_script_exists() {
    log_test "Script exists and is executable"

    if [ -f "$CLEANUP_SCRIPT" ]; then
        log_pass "Script file exists at: $CLEANUP_SCRIPT"
    else
        log_fail "Script file not found at: $CLEANUP_SCRIPT"
        return 1
    fi

    if [ -x "$CLEANUP_SCRIPT" ]; then
        log_pass "Script is executable"
    else
        log_fail "Script is not executable"
        return 1
    fi
}

# Test 2: Help message works
test_help_message() {
    log_test "Help message displays correctly"

    if "$CLEANUP_SCRIPT" --help > /dev/null 2>&1; then
        log_pass "Help message displays without error"
    else
        log_fail "Help message failed"
        return 1
    fi

    local help_output
    help_output=$("$CLEANUP_SCRIPT" --help 2>&1)

    if echo "$help_output" | grep -q "Usage:"; then
        log_pass "Help contains usage information"
    else
        log_fail "Help missing usage information"
        return 1
    fi

    if echo "$help_output" | grep -q "dry-run"; then
        log_pass "Help documents --dry-run flag"
    else
        log_fail "Help missing --dry-run flag"
        return 1
    fi
}

# Test 3: Missing prefix argument
test_missing_prefix() {
    log_test "Script rejects missing prefix argument"

    if "$CLEANUP_SCRIPT" 2>&1 | grep -q "Missing ITERATION_PREFIX"; then
        log_pass "Script properly rejects missing prefix"
    else
        log_fail "Script should reject missing prefix"
        return 1
    fi
}

# Test 4: Dry-run mode (doesn't require Azure CLI)
test_dry_run_flag() {
    log_test "Dry-run flag is recognized"

    # This test will fail if Azure CLI is not installed or not logged in
    # but will verify the flag is parsed
    if "$CLEANUP_SCRIPT" TEST_PREFIX_ --dry-run 2>&1 | grep -q "Dry-run mode enabled"; then
        log_pass "Dry-run mode is enabled by flag"
    else
        log_fail "Dry-run flag not working"
        return 1
    fi
}

# Test 5: Invalid option handling
test_invalid_option() {
    log_test "Script rejects invalid options"

    if "$CLEANUP_SCRIPT" TEST_PREFIX_ --invalid-option 2>&1 | grep -q "Unknown option"; then
        log_pass "Script properly rejects invalid options"
    else
        log_fail "Script should reject invalid options"
        return 1
    fi
}

# Test 6: Script dependencies (Azure CLI check)
test_azure_cli_check() {
    log_test "Script checks for Azure CLI"

    # Temporarily rename az if it exists
    local az_found=false
    if command -v az &> /dev/null; then
        az_found=true
        log_info "Azure CLI is installed"
    fi

    if [ "$az_found" = true ]; then
        # Test that script uses Azure CLI
        if "$CLEANUP_SCRIPT" TEST_PREFIX_ --dry-run 2>&1 | grep -q "Checking prerequisites"; then
            log_pass "Script checks prerequisites"
        else
            log_fail "Script should check prerequisites"
            return 1
        fi
    else
        log_info "Skipping Azure CLI test (not installed)"
    fi
}

# Test 7: Subscription flag parsing
test_subscription_flag() {
    log_test "Subscription flag is parsed correctly"

    if "$CLEANUP_SCRIPT" TEST_PREFIX_ --subscription test-sub-id --dry-run 2>&1 | grep -q "test-sub-id"; then
        log_pass "Subscription flag parsed correctly"
    else
        log_fail "Subscription flag not parsed"
        return 1
    fi
}

# Test 8: Verbose flag
test_verbose_flag() {
    log_test "Verbose flag is recognized"

    local output
    output=$("$CLEANUP_SCRIPT" TEST_PREFIX_ --verbose --dry-run 2>&1 || true)

    # Verbose flag should be parsed without error
    if echo "$output" | grep -q "Dry-run mode enabled"; then
        log_pass "Verbose flag accepted"
    else
        log_fail "Verbose flag not working"
        return 1
    fi
}

# Test 9: Skip confirmation flag
test_skip_confirmation_flag() {
    log_test "Skip confirmation flag is recognized"

    if "$CLEANUP_SCRIPT" TEST_PREFIX_ --skip-confirmation --dry-run 2>&1 | grep -q "Confirmation prompts disabled"; then
        log_pass "Skip confirmation flag works"
    else
        log_fail "Skip confirmation flag not working"
        return 1
    fi
}

# Test 10: Script structure validation
test_script_structure() {
    log_test "Script has required functions"

    local required_functions=(
        "check_prerequisites"
        "list_resource_groups"
        "delete_resource_groups"
        "list_deleted_keyvaults"
        "purge_deleted_keyvaults"
        "list_storage_accounts"
        "delete_storage_accounts"
        "generate_summary"
    )

    local missing_functions=()
    for func in "${required_functions[@]}"; do
        if ! grep -q "^${func}()" "$CLEANUP_SCRIPT"; then
            missing_functions+=("$func")
        fi
    done

    if [ ${#missing_functions[@]} -eq 0 ]; then
        log_pass "All required functions present"
    else
        log_fail "Missing functions: ${missing_functions[*]}"
        return 1
    fi
}

# Test 11: Color output codes
test_color_output() {
    log_test "Script defines color codes"

    if grep -q "RED=" "$CLEANUP_SCRIPT" && \
       grep -q "GREEN=" "$CLEANUP_SCRIPT" && \
       grep -q "YELLOW=" "$CLEANUP_SCRIPT" && \
       grep -q "BLUE=" "$CLEANUP_SCRIPT"; then
        log_pass "Color codes defined"
    else
        log_fail "Missing color codes"
        return 1
    fi
}

# Test 12: Error handling
test_error_handling() {
    log_test "Script uses set -euo pipefail"

    if head -n 20 "$CLEANUP_SCRIPT" | grep -q "set -euo pipefail"; then
        log_pass "Proper error handling enabled"
    else
        log_fail "Missing 'set -euo pipefail'"
        return 1
    fi
}

# Test 13: Logging functions
test_logging_functions() {
    log_test "Script defines logging functions"

    local required_logs=(
        "log_info"
        "log_success"
        "log_warning"
        "log_error"
    )

    local missing_logs=()
    for log_func in "${required_logs[@]}"; do
        if ! grep -q "^${log_func}()" "$CLEANUP_SCRIPT"; then
            missing_logs+=("$log_func")
        fi
    done

    if [ ${#missing_logs[@]} -eq 0 ]; then
        log_pass "All logging functions present"
    else
        log_fail "Missing logging functions: ${missing_logs[*]}"
        return 1
    fi
}

# Test 14: jq dependency check
test_jq_usage() {
    log_test "Script uses jq for JSON parsing"

    if grep -q "jq" "$CLEANUP_SCRIPT"; then
        log_pass "Script uses jq for JSON parsing"
    else
        log_fail "Script should use jq for JSON parsing"
        return 1
    fi
}

# Test 15: Safety confirmations
test_safety_confirmations() {
    log_test "Script includes confirmation prompts"

    if grep -q "confirm_deletion" "$CLEANUP_SCRIPT"; then
        log_pass "Confirmation function present"
    else
        log_fail "Missing confirmation function"
        return 1
    fi

    if grep -q "Are you sure?" "$CLEANUP_SCRIPT"; then
        log_pass "Confirmation prompt text present"
    else
        log_fail "Missing confirmation prompt"
        return 1
    fi
}

# Run all tests
run_all_tests() {
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║          Cleanup Script Test Suite                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo

    # Basic tests (don't require Azure CLI)
    test_script_exists || true
    test_help_message || true
    test_missing_prefix || true
    test_dry_run_flag || true
    test_invalid_option || true
    test_subscription_flag || true
    test_verbose_flag || true
    test_skip_confirmation_flag || true

    # Structure tests
    test_script_structure || true
    test_color_output || true
    test_error_handling || true
    test_logging_functions || true
    test_jq_usage || true
    test_safety_confirmations || true

    # Azure CLI tests (may be skipped)
    test_azure_cli_check || true

    echo
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                        Test Results                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo
    echo -e "${GREEN}Tests Passed:${NC} $TESTS_PASSED"
    echo -e "${RED}Tests Failed:${NC} $TESTS_FAILED"
    echo

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed.${NC}"
        return 1
    fi
}

# Main execution
main() {
    if [ $# -gt 0 ] && [ "$1" = "--help" ]; then
        echo "Test suite for cleanup_iteration_resources.sh"
        echo
        echo "Usage: $0"
        echo
        echo "Runs comprehensive tests on the cleanup script including:"
        echo "  - Script existence and permissions"
        echo "  - Command-line argument parsing"
        echo "  - Help message and documentation"
        echo "  - Function structure and completeness"
        echo "  - Safety features and confirmations"
        echo
        exit 0
    fi

    run_all_tests
}

main "$@"
