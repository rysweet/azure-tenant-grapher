# Scale Operations Testing Quick Start Guide

**Issue #427 - Scale Operations Testing**

## Quick Command Reference

### Test the Scale Commands (Help Output)

```bash
# All these commands work perfectly
uv run atg scale-stats --help
uv run atg scale-validate --help
uv run atg scale-clean --help
uv run atg scale-up --help
uv run atg scale-up template --help
uv run atg scale-up scenario --help
uv run atg scale-down --help
uv run atg scale-down algorithm --help
uv run atg scale-down pattern --help
```

### Run Agentic Tests

```bash
# Navigate to spa directory
cd spa

# Run smoke tests (26 tests)
npm run test:ui -- scenarios/scale-operations-tests.yaml

# Run E2E tests (38 tests) - requires Neo4j
npm run test:ui -- scenarios/scale-operations-e2e-tests.yaml
```

### Test Files Created

1. **Smoke Tests:** `spa/agentic-testing/scenarios/scale-operations-tests.yaml`
2. **E2E Tests:** `spa/agentic-testing/scenarios/scale-operations-e2e-tests.yaml`
3. **Template:** `test-data/scale-up-template-test.yaml`

## Known Issues

### Issue #1: Commands Hang with --no-container Flag

**Problem:** Scale commands hang indefinitely even with `--no-container` flag.

**Affected Commands:**
- All scale-up subcommands
- All scale-down subcommands
- scale-stats (without Neo4j)
- scale-validate (without Neo4j)
- scale-clean (without Neo4j)

**Workaround:** Ensure Neo4j is running before testing:
```bash
docker ps | grep neo4j
# If not running:
docker start neo4j
```

**Root Cause:** The `--no-container` flag is defined but not used in command handlers. All handlers attempt Neo4j connection regardless of flag.

**Recommended Fix:**
```python
# In src/cli_commands_scale.py
async def scale_up_template_command_handler(..., no_container: bool = False):
    if not no_container:
        # Connect to Neo4j
        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()
    else:
        # Skip Neo4j or use mock mode
        console.print("[yellow]Skipping Neo4j (--no-container)[/yellow]")
```

## Test Coverage Summary

### Smoke Tests (26 steps)
- ✅ Help command output validation
- ✅ Parameter validation
- ✅ Error handling for missing parameters
- ❌ Execution tests (blocked by Issue #1)

### E2E Tests (38 steps)
- ✅ Baseline statistics gathering
- ✅ Template file validation
- ❌ Dry-run execution (blocked by Issue #1)
- ❌ Real execution tests (blocked by Issue #1)
- ✅ JSON output validation
- ✅ Parameter validation

## Next Steps

1. **Fix Issue #1** - Implement --no-container flag properly
2. **Run Full Test Suite** - Execute all tests with Neo4j running
3. **CI Integration** - Add tests to GitHub Actions pipeline
4. **Additional Scenarios** - Add edge case testing

## Documentation

Full documentation available at:
- `docs/testing/SCALE_OPERATIONS_AGENTIC_TESTING.md` - Complete testing guide
- `docs/GADUGI_MIGRATION.md` - Gadugi framework overview
- `spa/agentic-testing/README.md` - Agentic testing system docs

## Support

For questions or issues:
1. Check the full documentation above
2. Review existing test scenarios in `spa/agentic-testing/scenarios/`
3. See `docs/testing/` for additional testing resources
