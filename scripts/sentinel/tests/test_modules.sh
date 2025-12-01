#!/usr/bin/env bash

# ============================================================================
# Bash Module Integration Tests for Sentinel Automation (Issue #518)
#
# Tests each bash module in isolation to verify:
# - Prerequisites validation
# - Idempotency
# - Error handling
# - Output format
#
# These tests will FAIL until bash modules are implemented (TDD methodology)
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
TEST_WORK_DIR="/tmp/sentinel-test-$$"

# Create test work directory
mkdir -p "$TEST_WORK_DIR"

# Cleanup on exit
cleanup() {
    rm -rf "$TEST_WORK_DIR"
}
trap cleanup EXIT

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

assert_file_exists() {
    local file=$1
    local test_name=$2

    if [ -f "$file" ]; then
        log_pass "$test_name - File exists: $file"
        return 0
    else
        log_fail "$test_name - File not found: $file"
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
        return 1
    fi
}

# ============================================================================
# Module 01: Prerequisites Validation Tests
# ============================================================================

test_01_prerequisites_detects_missing_azure_cli() {
    log_test "Module 01: Detects missing Azure CLI"

    # Mock az command to simulate not installed
    export PATH="/tmp/fake-path:$PATH"

    # Run module
    set +e
    output=$("$MODULES_DIR/01-validate-prerequisites.sh" 2>&1)
    exit_code=$?
    set -e

    # Should fail with non-zero exit code
    assert_exit_code 1 $exit_code "Prerequisites check with missing az CLI"
    assert_contains "$output" "Azure CLI" "Error message mentions Azure CLI"
}

test_01_prerequisites_detects_authentication_failure() {
    log_test "Module 01: Detects authentication failure"

    # Set invalid credentials
    export AZURE_TENANT_ID="invalid-tenant-id"
    export AZURE_CLIENT_ID="invalid-client-id"
    export AZURE_CLIENT_SECRET="invalid-secret"

    # Run module
    set +e
    output=$("$MODULES_DIR/01-validate-prerequisites.sh" 2>&1)
    exit_code=$?
    set -e

    # Should fail with authentication error
    assert_exit_code 1 $exit_code "Prerequisites check with invalid credentials"
    assert_contains "$output" "authentication" "Error message mentions authentication"
}

test_01_prerequisites_passes_with_valid_setup() {
    log_test "Module 01: Passes with valid setup"

    # Assume valid Azure credentials are in environment
    # Run module
    set +e
    output=$("$MODULES_DIR/01-validate-prerequisites.sh" 2>&1)
    exit_code=$?
    set -e

    # Should succeed
    assert_exit_code 0 $exit_code "Prerequisites check with valid setup"
    assert_contains "$output" "Prerequisites validated" "Success message"
}

# ============================================================================
# Module 02: Workspace Creation Tests
# ============================================================================

test_02_workspace_creation_idempotency() {
    log_test "Module 02: Workspace creation is idempotent"

    # Set test configuration
    export WORKSPACE_NAME="test-workspace-$$"
    export RESOURCE_GROUP="test-rg-$$"
    export LOCATION="eastus"
    export RETENTION_DAYS="30"
    export SKU="PerGB2018"

    # First run - create workspace
    set +e
    output1=$("$MODULES_DIR/02-create-workspace.sh" 2>&1)
    exit_code1=$?
    set -e

    assert_exit_code 0 $exit_code1 "First workspace creation"

    # Extract workspace ID from output
    workspace_id=$(echo "$output1" | jq -r '.workspace_id')

    # Second run - should detect existing workspace
    set +e
    output2=$("$MODULES_DIR/02-create-workspace.sh" 2>&1)
    exit_code2=$?
    set -e

    assert_exit_code 0 $exit_code2 "Second workspace creation (idempotent)"
    assert_contains "$output2" "$workspace_id" "Same workspace ID returned"
    assert_contains "$output2" "already exists" "Skipped creation message"

    # Cleanup
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>/dev/null || true
}

test_02_workspace_creation_with_existing_workspace() {
    log_test "Module 02: Handles existing workspace gracefully"

    export WORKSPACE_NAME="existing-workspace-$$"
    export RESOURCE_GROUP="existing-rg-$$"
    export LOCATION="eastus"

    # Pre-create resource group and workspace using Azure CLI
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null 2>&1
    az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --location "$LOCATION" >/dev/null 2>&1

    # Run module
    set +e
    output=$("$MODULES_DIR/02-create-workspace.sh" 2>&1)
    exit_code=$?
    set -e

    assert_exit_code 0 $exit_code "Workspace creation with existing workspace"
    assert_contains "$output" "already exists" "Detected existing workspace"

    # Cleanup
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>/dev/null || true
}

test_02_workspace_outputs_valid_json() {
    log_test "Module 02: Outputs valid JSON"

    export WORKSPACE_NAME="test-workspace-json-$$"
    export RESOURCE_GROUP="test-rg-json-$$"
    export LOCATION="eastus"

    # Run module
    set +e
    output=$("$MODULES_DIR/02-create-workspace.sh" 2>&1)
    exit_code=$?
    set -e

    assert_exit_code 0 $exit_code "Workspace creation"

    # Validate JSON output
    echo "$output" | jq . >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_pass "Output is valid JSON"
    else
        log_fail "Output is not valid JSON"
    fi

    # Verify required fields
    workspace_id=$(echo "$output" | jq -r '.workspace_id')
    workspace_name=$(echo "$output" | jq -r '.workspace_name')

    if [ -n "$workspace_id" ] && [ "$workspace_id" != "null" ]; then
        log_pass "workspace_id field present"
    else
        log_fail "workspace_id field missing or null"
    fi

    if [ -n "$workspace_name" ] && [ "$workspace_name" != "null" ]; then
        log_pass "workspace_name field present"
    else
        log_fail "workspace_name field missing or null"
    fi

    # Cleanup
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>/dev/null || true
}

# ============================================================================
# Module 03: Sentinel Enablement Tests
# ============================================================================

test_03_sentinel_enablement_with_existing_sentinel() {
    log_test "Module 03: Handles existing Sentinel gracefully"

    export WORKSPACE_NAME="test-sentinel-workspace-$$"
    export RESOURCE_GROUP="test-sentinel-rg-$$"
    export LOCATION="eastus"

    # Create workspace
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null 2>&1
    az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --location "$LOCATION" >/dev/null 2>&1

    # Get workspace ID
    workspace_id=$(az monitor log-analytics workspace show \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --query id -o tsv)

    export WORKSPACE_ID="$workspace_id"

    # Enable Sentinel (first time)
    set +e
    output1=$("$MODULES_DIR/03-enable-sentinel.sh" 2>&1)
    exit_code1=$?
    set -e

    assert_exit_code 0 $exit_code1 "First Sentinel enablement"

    # Enable Sentinel again (should be idempotent)
    set +e
    output2=$("$MODULES_DIR/03-enable-sentinel.sh" 2>&1)
    exit_code2=$?
    set -e

    assert_exit_code 0 $exit_code2 "Second Sentinel enablement (idempotent)"
    assert_contains "$output2" "already enabled" "Detected existing Sentinel"

    # Cleanup
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>/dev/null || true
}

test_03_sentinel_enablement_requires_workspace_id() {
    log_test "Module 03: Fails without WORKSPACE_ID"

    # Unset WORKSPACE_ID
    unset WORKSPACE_ID || true

    # Run module
    set +e
    output=$("$MODULES_DIR/03-enable-sentinel.sh" 2>&1)
    exit_code=$?
    set -e

    # Should fail
    assert_exit_code 1 $exit_code "Sentinel enablement without WORKSPACE_ID"
    assert_contains "$output" "WORKSPACE_ID" "Error message mentions WORKSPACE_ID"
}

# ============================================================================
# Module 04: Data Connectors Tests
# ============================================================================

test_04_data_connectors_configuration() {
    log_test "Module 04: Configures data connectors"

    export WORKSPACE_NAME="test-connectors-workspace-$$"
    export RESOURCE_GROUP="test-connectors-rg-$$"
    export LOCATION="eastus"

    # Create workspace and enable Sentinel
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null 2>&1
    az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --location "$LOCATION" >/dev/null 2>&1

    workspace_id=$(az monitor log-analytics workspace show \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --query id -o tsv)

    export WORKSPACE_ID="$workspace_id"

    # Run module
    set +e
    output=$("$MODULES_DIR/04-configure-data-connectors.sh" 2>&1)
    exit_code=$?
    set -e

    assert_exit_code 0 $exit_code "Data connectors configuration"
    assert_contains "$output" "configured" "Confirmation message"

    # Cleanup
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>/dev/null || true
}

# ============================================================================
# Module 05: Diagnostic Settings Tests
# ============================================================================

test_05_diagnostic_settings_per_resource() {
    log_test "Module 05: Creates diagnostic settings per resource"

    export WORKSPACE_NAME="test-diagnostics-workspace-$$"
    export RESOURCE_GROUP="test-diagnostics-rg-$$"
    export LOCATION="eastus"

    # Create workspace
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null 2>&1
    az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --location "$LOCATION" >/dev/null 2>&1

    workspace_id=$(az monitor log-analytics workspace show \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$WORKSPACE_NAME" \
        --query id -o tsv)

    export WORKSPACE_ID="$workspace_id"

    # Create resources JSON file with test resources
    resources_file="$TEST_WORK_DIR/resources.json"
    cat >"$resources_file" <<EOF
[
    {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "name": "test-vm"
    }
]
EOF

    export RESOURCES_FILE="$resources_file"

    # Run module
    set +e
    output=$("$MODULES_DIR/05-configure-diagnostics.sh" 2>&1)
    exit_code=$?
    set -e

    assert_exit_code 0 $exit_code "Diagnostic settings configuration"
    assert_contains "$output" "diagnostic settings" "Confirmation message"

    # Cleanup
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait 2>/dev/null || true
}

# ============================================================================
# Run All Tests
# ============================================================================

echo "========================================"
echo "Sentinel Bash Module Tests"
echo "========================================"
echo ""

# Run prerequisites tests
test_01_prerequisites_detects_missing_azure_cli
test_01_prerequisites_detects_authentication_failure
test_01_prerequisites_passes_with_valid_setup

# Run workspace creation tests
test_02_workspace_creation_idempotency
test_02_workspace_creation_with_existing_workspace
test_02_workspace_outputs_valid_json

# Run Sentinel enablement tests
test_03_sentinel_enablement_with_existing_sentinel
test_03_sentinel_enablement_requires_workspace_id

# Run data connectors tests
test_04_data_connectors_configuration

# Run diagnostic settings tests
test_05_diagnostic_settings_per_resource

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
