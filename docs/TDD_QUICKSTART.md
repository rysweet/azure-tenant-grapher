# TDD Technical Debt Elimination - Quick Start Guide

## Overview

This guide helps you get started with the Test-Driven Development (TDD) approach to eliminating technical debt in Azure Tenant Grapher.

**Principle**: Write FAILING tests FIRST, then fix the code to make them pass.

## Current Status

### ✅ Tests Created (Phase 1)
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/tests/test_meta_collection.py` - Test collection validation

### ❌ Tests Failing (As Expected!)
```
FAILED tests/test_meta_collection.py::TestTestCollectionIntegrity::test_all_e2e_tests_can_be_collected
FAILED tests/test_meta_collection.py::TestTestCollectionIntegrity::test_auth_security_tests_import_successfully
FAILED tests/test_meta_collection.py::TestTestCollectionIntegrity::test_lifecycle_tests_import_successfully
FAILED tests/test_meta_collection.py::TestTestCollectionIntegrity::test_spa_tabs_tests_import_successfully
FAILED tests/test_meta_collection.py::TestTestCollectionIntegrity::test_neo4j_integration_tests_import_successfully
FAILED tests/test_meta_collection.py::TestDependencyInstallation::test_playwright_is_installed
FAILED tests/test_meta_collection.py::TestDependencyInstallation::test_all_dev_dependencies_are_installed
```

**This is GOOD! This is TDD. Tests fail first, then we fix the code.**

## Quick Start: Fix Phase 1 Issues

### Step 1: Install Missing Dependencies

```bash
# Add playwright
uv add --dev playwright

# Install playwright browsers
uv run playwright install

# Verify installation
uv run python -c "import playwright; print('✅ playwright installed')"
```

### Step 2: Fix Cryptography API Usage

**Problem**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/tests/e2e/auth_security/conftest.py` uses deprecated API

**Change this:**
```python
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryptionAvailable,  # ❌ WRONG - deprecated
    PrivateFormat,
    PublicFormat,
)

# Usage:
private_pem = private_key.private_bytes(
    encoding=Encoding.PEM,
    format=PrivateFormat.PKCS8,
    encryption_algorithm=NoEncryptionAvailable()  # ❌ WRONG
)
```

**To this:**
```python
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,  # ✅ CORRECT
    PrivateFormat,
    PublicFormat,
)

# Usage:
private_pem = private_key.private_bytes(
    encoding=Encoding.PEM,
    format=PrivateFormat.PKCS8,
    encryption_algorithm=NoEncryption()  # ✅ CORRECT
)
```

### Step 3: Fix Neo4jContainer Import

**Problem**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/tests/e2e/neo4j_integration/conftest.py` may have missing import

**Check the file and ensure proper import:**
```python
# At the top of conftest.py
try:
    from testcontainers.neo4j import Neo4jContainer
except ImportError:
    # Provide a mock or skip these tests
    Neo4jContainer = None
```

### Step 4: Verify Fixes

```bash
# Run the meta-collection tests again
uv run pytest tests/test_meta_collection.py -v

# Expected: More tests passing!
# Goal: All 17 tests PASS
```

## Next Steps After Phase 1 Passes

### Phase 2: Create Logging Standards Tests

**File**: `tests/test_meta_logging_standards.py` (already specified in strategy document)

This will test for:
- No DEBUG print statements in src/
- All modules use structlog
- Structured JSON logging output

### Phase 3: Create Exception Handling Tests

**File**: `tests/test_meta_exception_handling.py` (already specified in strategy document)

This will test for:
- No bare "except: pass"
- All exceptions logged with context
- Critical exceptions propagate

## Validation Commands

### Run Just Phase 1 Tests
```bash
uv run pytest tests/test_meta_collection.py -v
```

### Check Specific Issue
```bash
# Check if playwright is installed
uv run python -c "import playwright; print('OK')"

# Check cryptography API
uv run python -c "from cryptography.hazmat.primitives.serialization import NoEncryption; print('OK')"

# Check testcontainers
uv run python -c "from testcontainers.neo4j import Neo4jContainer; print('OK')"
```

### Find Files to Fix
```bash
# Find files with DEBUG prints
grep -r "print.*DEBUG" src/ | wc -l

# Find files with except: pass
grep -A1 "except.*:" src/ | grep -c "pass"

# Find files without structlog
grep -L "structlog" src/*.py | grep -v __init__
```

## Progress Tracking

### Phase 1: Test Collection (Current)
- [ ] Install playwright
- [ ] Fix cryptography API in auth_security/conftest.py
- [ ] Fix Neo4jContainer import in neo4j_integration/conftest.py
- [ ] All test_meta_collection.py tests pass

### Phase 2: Logging Standards (Next)
- [ ] Write test_meta_logging_standards.py
- [ ] Run tests (expect ALL to fail)
- [ ] Fix cli_commands.py (30+ print statements)
- [ ] Fix tenant_creator.py
- [ ] Fix container_manager.py
- [ ] Fix resource_processor.py
- [ ] All logging tests pass

### Phase 3: Exception Handling
- [ ] Write test_meta_exception_handling.py
- [ ] Run tests (expect ALL to fail)
- [ ] Fix all 7 files with except: pass
- [ ] Add logging to all exception handlers
- [ ] All exception handling tests pass

### Phase 4: Integration Tests
- [ ] Write test_logging_integration.py
- [ ] Write test_exception_handling_integration.py
- [ ] Run and fix until all pass

### Phase 5: E2E Tests
- [ ] Write test_logging_e2e.py
- [ ] Run and fix until all pass

## Expected Timeline

- **Week 1**: Fix Phase 1 (test collection) ✅ In progress
- **Week 2**: Create and fix Phase 2 (logging standards)
- **Week 3**: Create and fix Phase 3 (exception handling)
- **Week 4**: Create and fix Phases 4-5 (integration & E2E)

## Key TDD Principles

1. **Red**: Write a test that fails
2. **Green**: Write minimal code to make it pass
3. **Refactor**: Clean up the code while keeping tests passing

### Example TDD Cycle

```bash
# 1. RED - Write failing test
echo "def test_no_debug_prints(): assert False" >> tests/test_meta_logging_standards.py
uv run pytest tests/test_meta_logging_standards.py::test_no_debug_prints
# ❌ FAILS (as expected)

# 2. GREEN - Implement the test properly and fix the code
# Edit test to check for DEBUG prints in src/
# Remove DEBUG prints from source code
uv run pytest tests/test_meta_logging_standards.py::test_no_debug_prints
# ✅ PASSES

# 3. REFACTOR - Clean up while maintaining passing tests
# Improve logging structure
# Add helper functions
uv run pytest tests/test_meta_logging_standards.py::test_no_debug_prints
# ✅ STILL PASSES
```

## Getting Help

### View Full Strategy
```bash
cat docs/TDD_TEST_STRATEGY_TECH_DEBT.md
```

### Run All Tests
```bash
# Run everything (expect many failures initially)
uv run pytest tests/ -v

# Run only meta-tests (our new TDD tests)
uv run pytest tests/test_meta_*.py -v

# Run with coverage
uv run pytest tests/test_meta_*.py --cov=src --cov-report=term-missing
```

### Check Progress
```bash
# Count passing vs failing tests
uv run pytest tests/test_meta_collection.py --tb=no -q | tail -1
```

## Success Metrics

### Phase 1 Complete When:
- ✅ All 17 tests in test_meta_collection.py pass
- ✅ E2E tests collect without import errors
- ✅ pytest exit code 0 for `pytest tests/e2e/ --collect-only`

### Phase 2 Complete When:
- ✅ Zero DEBUG print statements in src/
- ✅ All production modules use structlog
- ✅ All logs are structured JSON

### Phase 3 Complete When:
- ✅ Zero bare "except: pass" in src/
- ✅ All exceptions logged with context
- ✅ Critical exceptions propagate properly

### Overall Complete When:
- ✅ All 100+ tests pass
- ✅ No technical debt in targeted areas
- ✅ Code coverage ≥40% (maintained)
- ✅ Modified code has 100% coverage

## Tips

1. **Run tests frequently**: After every small change
2. **One test at a time**: Fix one failing test before moving to next
3. **Commit often**: Commit after each test passes
4. **Keep notes**: Document why tests failed and how you fixed them

## Common Issues

### "Coverage failure: total of 0 is less than fail-under=40"
- **Cause**: Running meta-tests that don't execute source code
- **Fix**: Disable coverage for meta-tests: `pytest --no-cov`
- **Or**: Run with specific coverage path: `pytest --cov=src/specific_module.py`

### "ModuleNotFoundError: No module named 'playwright'"
- **Fix**: `uv add --dev playwright && uv run playwright install`

### "ImportError: cannot import name 'NoEncryptionAvailable'"
- **Fix**: Change to `NoEncryption` in the import statement

## Resources

- **Full Strategy**: `docs/TDD_TEST_STRATEGY_TECH_DEBT.md`
- **Project Guide**: `CLAUDE.md`
- **Test Files**: `tests/test_meta_*.py`

---

**Remember**: Failing tests are GOOD in TDD! They tell us what needs to be fixed.

**Current Status**: Phase 1 - Test Collection 🔴 RED (tests failing as expected)
**Next Goal**: Phase 1 - Test Collection 🟢 GREEN (all tests passing)
