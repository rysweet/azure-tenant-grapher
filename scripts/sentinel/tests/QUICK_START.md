# Sentinel Test Suite - Quick Start Guide

**Ahoy, builder matey! 🏴‍☠️**

This guide will get ye started with the Sentinel test suite in 5 minutes.

---

## Prerequisites

Before runnin' the tests, make sure ye have:

```bash
# Python 3.11+
python3 --version

# pytest
pip install pytest pytest-asyncio pytest-cov

# For bash tests
command -v jq || sudo apt install jq  # Ubuntu
command -v jq || brew install jq      # macOS
```

---

## Running Tests (TL;DR)

```bash
# Quick test (unit tests only - 5 seconds)
pytest tests/commands/test_sentinel.py -v

# All tests except E2E (~1 minute)
./scripts/sentinel/tests/run_all_tests.sh

# With coverage report
./scripts/sentinel/tests/run_all_tests.sh --coverage

# Fast mode (unit tests only)
./scripts/sentinel/tests/run_all_tests.sh --fast

# E2E tests (requires Azure - ~10 minutes)
./scripts/sentinel/tests/run_all_tests.sh --e2e
```

---

## Expected Results RIGHT NOW

**All tests should FAIL** because implementation doesn't exist yet:

```bash
$ pytest tests/commands/test_sentinel.py -v

FAILED test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name
  ModuleNotFoundError: No module named 'src.commands.sentinel'

========== 40 failed in 0.23s ==========
```

**This is CORRECT and EXPECTED!** 🎉

We're using **Test-Driven Development (TDD)**:
1. ✅ Write failing tests (DONE - that's these tests!)
2. ⏳ Implement code to make tests pass (YOUR JOB)
3. ⏳ Refactor and improve (AFTER TESTS PASS)

---

## TDD Workflow Example

### Step 1: Pick a Test

Start with the simplest test:

```bash
pytest tests/commands/test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name -v
```

**Current result**: FAILS with `ModuleNotFoundError`

### Step 2: Implement Just Enough Code

Create `src/commands/sentinel.py`:

```python
"""Azure Sentinel and Log Analytics automation."""

class SentinelConfig:
    """Configuration for Sentinel setup."""

    def __init__(self, tenant_id: str, subscription_id: str, **kwargs):
        self.tenant_id = tenant_id
        self.subscription_id = subscription_id

        # Auto-generate workspace name if not provided
        if "workspace_name" not in kwargs:
            location = kwargs.get("location", "eastus")
            self.workspace_name = f"{tenant_id[:8]}-sentinel-law-{location}"
        else:
            self.workspace_name = kwargs["workspace_name"]
```

### Step 3: Run Test Again

```bash
pytest tests/commands/test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name -v
```

**Expected result**: PASS ✅

### Step 4: Move to Next Test

```bash
pytest tests/commands/test_sentinel.py::TestSentinelConfig::test_explicit_workspace_name_overrides_auto -v
```

**Repeat**: Implement → Test → Pass → Next test

---

## Test Organization

```
tests/commands/
├── test_sentinel.py              # 40 unit tests (START HERE)
│   ├── TestSentinelConfig        # 21 tests - Configuration
│   ├── TestResourceDiscovery     # 9 tests - Resource discovery
│   └── TestSentinelSetupOrchestrator  # 10 tests - Orchestration
│
├── test_sentinel_integration.py  # 12 integration tests (SECOND)
│   ├── TestPythonToBashIntegration    # 4 tests
│   ├── TestNeo4jIntegration           # 3 tests
│   └── TestCLIIntegration             # 5 tests
│
└── test_sentinel_e2e.py          # 5 E2E tests (LAST)
    ├── TestStandaloneE2E         # 3 tests
    └── TestIntegratedE2E         # 2 tests

scripts/sentinel/tests/
├── test_common_lib.sh            # 15 bash library tests
├── test_modules.sh               # 10 bash module tests
└── run_all_tests.sh              # Unified test runner
```

---

## Running Specific Test Categories

### Unit Tests Only (Fastest - 5 seconds)

```bash
# All unit tests
pytest tests/commands/test_sentinel.py -v

# Specific class
pytest tests/commands/test_sentinel.py::TestSentinelConfig -v

# Specific test
pytest tests/commands/test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name -v
```

### Integration Tests (Medium - 30 seconds)

```bash
# Python integration tests
pytest tests/commands/test_sentinel_integration.py -v

# Bash library tests
./scripts/sentinel/tests/test_common_lib.sh

# Bash module tests
./scripts/sentinel/tests/test_modules.sh
```

### E2E Tests (Slow - 10 minutes, requires Azure)

```bash
# Set Azure credentials first
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"  # pragma: allowlist secret

# Run E2E tests
pytest tests/commands/test_sentinel_e2e.py -v -m e2e
```

---

## Watching Test Progress

### Option 1: pytest-watch

```bash
pip install pytest-watch
ptw tests/commands/test_sentinel.py -- -v
```

Now every time you save a file, tests auto-run!

### Option 2: entr

```bash
# Install entr
sudo apt install entr  # Ubuntu
brew install entr      # macOS

# Watch for changes
ls tests/commands/test_sentinel.py src/commands/sentinel.py | entr -c pytest tests/commands/test_sentinel.py -v
```

---

## Understanding Test Output

### Failing Test (Before Implementation)

```
FAILED test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name
>   from src.commands.sentinel import SentinelConfig
E   ModuleNotFoundError: No module named 'src.commands.sentinel'
```

**What this means**: You need to create `src/commands/sentinel.py`

### Passing Test (After Implementation)

```
test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name PASSED [1/40]
```

**What this means**: That specific functionality works! Move to next test.

### Test with Assertion Failure

```
FAILED test_sentinel.py::TestSentinelConfig::test_validate_retention_days_too_low
>   with pytest.raises(ValueError, match="Retention days must be between 30 and 730"):
E   Failed: DID NOT RAISE ValueError
```

**What this means**: Your `validate()` method isn't raising the error it should. Add validation!

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Implementing Too Much at Once

Don't implement all classes at once. Implement just enough to make ONE test pass.

```python
# BAD: Implementing everything
class SentinelConfig:
    def __init__(...):
        # 100 lines of code
        pass

# GOOD: Just enough for first test
class SentinelConfig:
    def __init__(self, tenant_id, subscription_id, **kwargs):
        self.tenant_id = tenant_id
        self.subscription_id = subscription_id
```

### ❌ Mistake 2: Skipping Tests

Don't skip tests! They're your implementation checklist.

```bash
# BAD: Skipping a failing test
pytest tests/commands/test_sentinel.py -v -k "not test_validate_retention"

# GOOD: Fix each test in order
pytest tests/commands/test_sentinel.py -v
```

### ❌ Mistake 3: Changing Tests to Make Them Pass

Don't modify tests to make them pass! Tests define the contract.

```python
# BAD: Changing test expectation
assert config.workspace_name == "any-name"  # Changed to pass

# GOOD: Fix implementation to match test
assert config.workspace_name == "12345678-sentinel-law-eastus"  # Original
```

---

## Implementation Order (Recommended)

Follow this order for best results:

### Phase 1: Python Unit Tests (Day 1)

1. `SentinelConfig` class
   - Constructor and defaults
   - Workspace name generation
   - Validation methods
   - Environment variable conversion

2. `ResourceDiscovery` class
   - Neo4j discovery
   - Azure API discovery
   - Strategy selection

3. `SentinelSetupOrchestrator` class
   - Prerequisites validation
   - Config file generation
   - Module execution (subprocess)
   - Error handling

### Phase 2: Bash Implementation (Day 2)

1. `lib/common.sh` library
   - Logging functions
   - Azure CLI checks
   - Resource existence checks
   - JSON output helpers

2. Bash modules (in order)
   - `01-validate-prerequisites.sh`
   - `02-create-workspace.sh`
   - `03-enable-sentinel.sh`
   - `04-configure-data-connectors.sh`
   - `05-configure-diagnostics.sh`

### Phase 3: Integration Tests (Day 3)

1. Python-to-Bash integration
2. Neo4j integration
3. CLI integration

### Phase 4: E2E Tests (Day 4 - optional)

1. Standalone workflow
2. Integration with generate-iac
3. Integration with create-tenant

---

## Debugging Failed Tests

### Enable Verbose Output

```bash
# Show print statements
pytest tests/commands/test_sentinel.py -v -s

# Show full diff on assertion failures
pytest tests/commands/test_sentinel.py -v --tb=long

# Stop at first failure
pytest tests/commands/test_sentinel.py -v -x
```

### Debug Specific Test

```bash
# Run with Python debugger
pytest tests/commands/test_sentinel.py::TestSentinelConfig::test_auto_generate_workspace_name -v --pdb

# Add breakpoint in test
import pdb; pdb.set_trace()
```

### Check Mock Calls

Tests use mocks - verify they're being called correctly:

```python
# In test:
mock_run.assert_called_once()
mock_run.assert_called_with(
    ["bash", script_path],
    env=expected_env,
    capture_output=True,
    text=True,
)
```

---

## Coverage Report

### Generate Coverage

```bash
pytest tests/commands/test_sentinel.py --cov=src/commands/sentinel --cov-report=html

# View report
open htmlcov/index.html
```

### Target Coverage

- **Minimum**: 80%
- **Good**: 90%+
- **Excellent**: 95%+

**Don't chase 100%** - Focus on meaningful coverage of critical paths.

---

## When Are You Done?

You're done implementing when:

✅ All unit tests pass (40/40)
✅ All integration tests pass (27/27)
✅ All E2E tests pass (5/5)
✅ Coverage > 80%
✅ Test execution < 1 minute (excluding E2E)
✅ All bash tests pass (25/25)

**Check with**:

```bash
./scripts/sentinel/tests/run_all_tests.sh

# Should output:
# ========================================
# Test Summary
# ========================================
# Duration: 45s
# ✓ All test suites passed!
```

---

## Getting Help

**Documentation**:
- `tests/commands/SENTINEL_TESTS_README.md` - Full test documentation
- `TEST_SUITE_SUMMARY.md` - High-level summary
- `docs/sentinel/SENTINEL_AUTOMATION_ARCHITECTURE.md` - Architecture
- `docs/sentinel/SENTINEL_AUTOMATION_TECH_SPEC.md` - Technical spec

**Troubleshooting**:
- Check `tests/commands/SENTINEL_TESTS_README.md` troubleshooting section
- Look at similar tests in `tests/commands/`
- Check existing command implementations in `src/commands/`

---

## Quick Reference

```bash
# Run specific test category
pytest tests/commands/test_sentinel.py -v              # Unit tests
pytest tests/commands/test_sentinel_integration.py -v  # Integration tests
pytest tests/commands/test_sentinel_e2e.py -v -m e2e   # E2E tests

# Run all tests
./scripts/sentinel/tests/run_all_tests.sh

# Fast mode (unit tests only)
./scripts/sentinel/tests/run_all_tests.sh --fast

# With coverage
./scripts/sentinel/tests/run_all_tests.sh --coverage

# Stop at first failure
pytest tests/commands/test_sentinel.py -v -x

# Show print statements
pytest tests/commands/test_sentinel.py -v -s

# Watch mode (auto-run on save)
ptw tests/commands/test_sentinel.py -- -v
```

---

**Now go make those tests pass, ye scurvy developer! 🏴‍☠️**

Remember: **Red → Green → Refactor**

Start with the simplest test and work your way up!
