#!/usr/bin/env bash

# ============================================================================
# Bash Common Library Tests for Sentinel Automation (Issue #518)
#
# Tests shared library functions in lib/common.sh:
# - Logging functions
# - Azure CLI checks
# - Resource existence checks
# - Idempotency helpers
#
# These tests will FAIL until lib/common.sh is implemented (TDD methodology)
# ============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_DIR="$(dirname "$SCRIPT_DIR")"
LIB_DIR="$MODULES_DIR/lib"
TEST_WORK_DIR="/tmp/sentinel-lib-test-$$"

# Create test work directory
mkdir -p "$TEST_WORK_DIR"

# Cleanup on exit
cleanup() {
    rm -rf "$TEST_WORK_DIR"
}
trap cleanup EXIT

# Source the library
# shellcheck source=../lib/common.sh
source "$LIB_DIR/common.sh" 2>/dev/null || {
    echo "ERROR: Cannot source $LIB_DIR/common.sh - file does not exist yet"
    exit 1
}

# ============================================================================
# Test Utilities
# ============================================================================

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
    TESTS_RUN=$((TESTS_RUN + 1))
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

assert_exit_code() {
    local expected=$1
    local actual=$2
    local test_name=$3

    if [ "$expected" -eq "$actual" ]; then
        log_pass "$test_name - Exit code: $actual"
        return 0
    else
        log_fail "$test_name - Expected exit code $expected, got $actual"
        return 1
    fi
}

assert_contains() {
    local haystack=$1
    local needle=$2
    local test_name=$3

    if echo "$haystack" | grep -q "$needle"; then
        log_pass "$test_name - Output contains: $needle"
        return 0
    else
        log_fail "$test_name - Output does not contain: $needle"
        echo "Expected to find: $needle"
        echo "In output: $haystack"
        return 1
    fi
}

assert_not_contains() {
    local haystack=$1
    local needle=$2
    local test_name=$3

    if echo "$haystack" | grep -q "$needle"; then
        log_fail "$test_name - Output should not contain: $needle"
        return 1
    else
        log_pass "$test_name - Output does not contain: $needle"
        return 0
    fi
}

# ============================================================================
# Logging Functions Tests
# ============================================================================

test_log_info_output_format() {
    log_test "log_info() output format"

    # Capture output
    output=$(log_info "Test message" 2>&1)

    # Should contain [INFO] prefix and message
    assert_contains "$output" "[INFO]" "Contains [INFO] prefix"
    assert_contains "$output" "Test message" "Contains message"
}

test_log_error_output_format() {
    log_test "log_error() output format"

    # Capture output (stderr)
    output=$(log_error "Error message" 2>&1)

    # Should contain [ERROR] prefix and message
    assert_contains "$output" "[ERROR]" "Contains [ERROR] prefix"
    assert_contains "$output" "Error message" "Contains message"
}

test_log_success_output_format() {
    log_test "log_success() output format"

    # Capture output
    output=$(log_success "Success message" 2>&1)

    # Should contain success indicator and message
    assert_contains "$output" "Success message" "Contains message"
}

test_log_debug_respects_debug_flag() {
    log_test "log_debug() respects DEBUG flag"

    # Without DEBUG flag
    unset DEBUG || true
    output=$(log_debug "Debug message" 2>&1)
    assert_not_contains "$output" "Debug message" "Debug message hidden without DEBUG=1"

    # With DEBUG flag
    export DEBUG=1
    output=$(log_debug "Debug message" 2>&1)
    assert_contains "$output" "Debug message" "Debug message shown with DEBUG=1"

    unset DEBUG
}

# ============================================================================
# Azure CLI Check Tests
# ============================================================================

test_check_az_cli_version_validation() {
    log_test "check_az_cli() validates Azure CLI version"

    # Check if az CLI is available
    if ! command -v az &>/dev/null; then
        echo "Skipping test - Azure CLI not installed"
        return 0
    fi

    # Run check
    set +e
    output=$(check_az_cli 2>&1)
    exit_code=$?
    set -e

    # Should succeed if az CLI is installed
    assert_exit_code 0 $exit_code "check_az_cli with installed CLI"
    assert_contains "$output" "Azure CLI" "Mentions Azure CLI"
}

test_check_az_cli_detects_missing_cli() {
    log_test "check_az_cli() detects missing Azure CLI"

    # Temporarily modify PATH to hide az CLI
    export PATH="/tmp/fake-path"

    # Run check
    set +e
    output=$(check_az_cli 2>&1)
    exit_code=$?
    set -e

    # Restore PATH
    export PATH="/usr/local/bin:/usr/bin:/bin"

    # Should fail
    assert_exit_code 1 $exit_code "check_az_cli with missing CLI"
    assert_contains "$output" "not installed" "Error message"
}

# ============================================================================
# Resource Existence Check Tests
# ============================================================================

test_resource_exists_with_valid_resource() {
    log_test "resource_exists() with valid resource ID"

    # Create test resource
    test_rg="test-rg-exists-$$"
    az group create --name "$test_rg" --location eastus >/dev/null 2>&1

    resource_id="/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$test_rg"

    # Check if resource exists
    set +e
    resource_exists "$resource_id"
    result=$?
    set -e

    assert_exit_code 0 $result "resource_exists returns 0 for existing resource"

    # Cleanup
    az group delete --name "$test_rg" --yes --no-wait 2>/dev/null || true
}

test_resource_exists_with_invalid_resource() {
    log_test "resource_exists() with invalid resource ID"

    resource_id="/subscriptions/fake-sub/resourceGroups/fake-rg/providers/Microsoft.Compute/virtualMachines/fake-vm"

    # Check if resource exists
    set +e
    resource_exists "$resource_id"
    result=$?
    set -e

    # Should return non-zero for non-existent resource
    if [ $result -ne 0 ]; then
        log_pass "resource_exists returns non-zero for non-existent resource"
    else
        log_fail "resource_exists should return non-zero for non-existent resource"
    fi
}

test_resource_exists_with_malformed_id() {
    log_test "resource_exists() with malformed resource ID"

    resource_id="not-a-valid-resource-id"

    # Check if resource exists
    set +e
    output=$(resource_exists "$resource_id" 2>&1)
    result=$?
    set -e

    # Should return non-zero
    if [ $result -ne 0 ]; then
        log_pass "resource_exists returns non-zero for malformed ID"
    else
        log_fail "resource_exists should return non-zero for malformed ID"
    fi
}

# ============================================================================
# Workspace Existence Check Tests
# ============================================================================

test_workspace_exists_idempotency_check() {
    log_test "workspace_exists() idempotency check"

    # Create test workspace
    test_rg="test-workspace-rg-$$"
    test_workspace="test-workspace-$$"

    az group create --name "$test_rg" --location eastus >/dev/null 2>&1
    az monitor log-analytics workspace create \
        --resource-group "$test_rg" \
        --workspace-name "$test_workspace" \
        --location eastus >/dev/null 2>&1

    # Check if workspace exists
    set +e
    workspace_exists "$test_rg" "$test_workspace"
    result=$?
    set -e

    assert_exit_code 0 $result "workspace_exists returns 0 for existing workspace"

    # Cleanup
    az group delete --name "$test_rg" --yes --no-wait 2>/dev/null || true
}

test_workspace_exists_returns_false_for_nonexistent() {
    log_test "workspace_exists() returns false for non-existent workspace"

    test_rg="fake-rg-$$"
    test_workspace="fake-workspace-$$"

    # Check if workspace exists
    set +e
    workspace_exists "$test_rg" "$test_workspace"
    result=$?
    set -e

    # Should return non-zero
    if [ $result -ne 0 ]; then
        log_pass "workspace_exists returns non-zero for non-existent workspace"
    else
        log_fail "workspace_exists should return non-zero for non-existent workspace"
    fi
}

# ============================================================================
# JSON Output Helper Tests
# ============================================================================

test_output_json_creates_valid_json() {
    log_test "output_json() creates valid JSON"

    # Create JSON output
    output=$(output_json "workspace_id" "/subscriptions/test/resourceGroups/test/providers/Microsoft.OperationalInsights/workspaces/test" "status" "success")

    # Validate JSON
    echo "$output" | jq . >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_pass "output_json creates valid JSON"
    else
        log_fail "output_json does not create valid JSON"
        echo "Output: $output"
    fi

    # Check field values
    workspace_id=$(echo "$output" | jq -r '.workspace_id')
    status=$(echo "$output" | jq -r '.status')

    if [ "$workspace_id" = "/subscriptions/test/resourceGroups/test/providers/Microsoft.OperationalInsights/workspaces/test" ]; then
        log_pass "workspace_id field is correct"
    else
        log_fail "workspace_id field is incorrect: $workspace_id"
    fi

    if [ "$status" = "success" ]; then
        log_pass "status field is correct"
    else
        log_fail "status field is incorrect: $status"
    fi
}

test_output_json_escapes_special_characters() {
    log_test "output_json() escapes special characters"

    # Create JSON with special characters
    output=$(output_json "message" "Test with \"quotes\" and \$special chars")

    # Should be valid JSON
    echo "$output" | jq . >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_pass "output_json handles special characters"
    else
        log_fail "output_json does not handle special characters correctly"
        echo "Output: $output"
    fi
}

# ============================================================================
# Configuration Validation Tests
# ============================================================================

test_validate_required_env_vars() {
    log_test "validate_required_env_vars() checks required variables"

    # Set all required variables
    export TENANT_ID="test-tenant"
    export SUBSCRIPTION_ID="test-sub"
    export WORKSPACE_NAME="test-workspace"
    export RESOURCE_GROUP="test-rg"
    export LOCATION="eastus"

    # Run validation
    set +e
    output=$(validate_required_env_vars 2>&1)
    result=$?
    set -e

    assert_exit_code 0 $result "validate_required_env_vars with all variables set"

    # Unset a required variable
    unset WORKSPACE_NAME

    # Run validation again
    set +e
    output=$(validate_required_env_vars 2>&1)
    result=$?
    set -e

    # Should fail
    if [ $result -ne 0 ]; then
        log_pass "validate_required_env_vars fails with missing variable"
    else
        log_fail "validate_required_env_vars should fail with missing variable"
    fi

    assert_contains "$output" "WORKSPACE_NAME" "Error mentions missing variable"
}

# ============================================================================
# Error Handling Tests
# ============================================================================

test_error_handler_logs_errors() {
    log_test "Error handler logs errors correctly"

    # Create test function that fails
    test_failing_function() {
        return 1
    }

    # Run with error handler
    set +e
    output=$(
        trap 'handle_error $? $LINENO' ERR
        test_failing_function
    ) 2>&1
    result=$?
    set -e

    # Should have logged error
    if echo "$output" | grep -q "ERROR"; then
        log_pass "Error handler logs errors"
    else
        log_fail "Error handler does not log errors"
    fi
}

# ============================================================================
# Run All Tests
# ============================================================================

echo "========================================"
echo "Sentinel Common Library Tests"
echo "========================================"
echo ""

# Run logging tests
test_log_info_output_format
test_log_error_output_format
test_log_success_output_format
test_log_debug_respects_debug_flag

# Run Azure CLI tests
test_check_az_cli_version_validation
test_check_az_cli_detects_missing_cli

# Run resource existence tests
test_resource_exists_with_valid_resource
test_resource_exists_with_invalid_resource
test_resource_exists_with_malformed_id

# Run workspace existence tests
test_workspace_exists_idempotency_check
test_workspace_exists_returns_false_for_nonexistent

# Run JSON output tests
test_output_json_creates_valid_json
test_output_json_escapes_special_characters

# Run configuration validation tests
test_validate_required_env_vars

# Run error handling tests
test_error_handler_logs_errors

# ============================================================================
# Test Summary
# ============================================================================

echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Tests run: $TESTS_RUN"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
