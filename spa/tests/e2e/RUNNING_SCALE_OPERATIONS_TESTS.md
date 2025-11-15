# Running Scale Operations E2E Tests

## Quick Start

```bash
# Navigate to spa directory
cd spa

# Start the development server (in one terminal)
npm run dev

# Run all Scale Operations tests (in another terminal)
npm run test:e2e -- scale-operations
```

## Test Files

1. **scale-operations-interaction.spec.ts** - Component interactions (33 tests)
2. **scale-operations-workflow.spec.ts** - Complete workflows (24 tests)
3. **scale-operations-actions.spec.ts** - Quick actions (51 tests)
4. **scale-operations-a11y.spec.ts** - Accessibility (57 tests)

**Total: 165 tests across 2,742 lines of code**

## Running Individual Test Suites

### Component Interaction Tests
```bash
npm run test:e2e -- scale-operations-interaction.spec.ts
```

### Workflow Tests
```bash
npm run test:e2e -- scale-operations-workflow.spec.ts
```

### Quick Actions Tests
```bash
npm run test:e2e -- scale-operations-actions.spec.ts
```

### Accessibility Tests
```bash
npm run test:e2e -- scale-operations-a11y.spec.ts
```

## Running Specific Test Cases

```bash
# Run tests matching a pattern
npm run test:e2e -- scale-operations-interaction.spec.ts -g "Mode Toggle"

# Run tests matching "keyboard"
npm run test:e2e -- scale-operations -g "keyboard"

# Run tests matching "dialog"
npm run test:e2e -- scale-operations -g "dialog"
```

## Interactive Mode (UI Mode)

```bash
# Run with Playwright UI for debugging
npm run test:e2e:ui -- scale-operations
```

This opens an interactive browser where you can:
- See tests running in real-time
- Pause and step through tests
- Inspect elements
- View screenshots and traces

## Debug Mode

```bash
# Run with debug mode (step-through)
npm run test:e2e:debug -- scale-operations-interaction.spec.ts
```

## Viewing Test Reports

```bash
# After running tests, view the HTML report
npx playwright show-report
```

## Test Options

### Run in Headed Mode (See Browser)
```bash
npm run test:e2e -- scale-operations --headed
```

### Run on Specific Browser
```bash
npm run test:e2e -- scale-operations --project=chromium
npm run test:e2e -- scale-operations --project=firefox
npm run test:e2e -- scale-operations --project=webkit
```

### Run with Tracing
```bash
npm run test:e2e -- scale-operations --trace=on
```

### Update Screenshots (if any)
```bash
npm run test:e2e -- scale-operations --update-snapshots
```

## Common Issues

### Issue: "Target page closed" or "Navigation timeout"
**Solution**: Make sure the dev server is running on `http://localhost:5173`

```bash
# Start dev server first
npm run dev
```

### Issue: Tests fail with "Backend not available"
**Solution**: This is expected behavior. Many tests gracefully handle missing backend and log informative messages. These tests verify UI behavior, not backend operations.

### Issue: "Element not found" errors
**Solution**: The UI may have changed. Check:
1. Is the Scale Operations tab visible?
2. Have component structures changed?
3. Are selectors still valid?

### Issue: Tests are slow
**Solution**:
- Reduce timeout values in test configuration
- Run specific test suites instead of all tests
- Use `--workers=1` for serial execution (slower but more stable)

```bash
npm run test:e2e -- scale-operations --workers=1
```

## Test Coverage by Category

### Functionality (33 tests)
- Mode toggling
- Strategy/algorithm selection
- Parameter validation
- Form interactions
- Error handling

### Workflows (24 tests)
- Complete scale-up flows
- Complete scale-down flows
- Preview and execute
- Clean and validate
- Error recovery

### Quick Actions (51 tests)
- Clean synthetic data
- Validate graph
- Show statistics
- Help dialog
- Dialog interactions

### Accessibility (57 tests)
- Keyboard navigation (12 tests)
- Screen reader labels (10 tests)
- Focus management (7 tests)
- ARIA attributes (10 tests)
- Semantic HTML (6 tests)
- Color contrast (5 tests)
- Touch targets (3 tests)
- Announcements (3 tests)
- Reduced motion (1 test)

## Test Results Interpretation

### All Pass ✅
Great! The Scale Operations UI is working correctly.

### Some Fail Due to "Backend not available" ⚠️
Expected behavior. These tests verify UI handles missing backend gracefully.

### Accessibility Tests Fail ❌
Important! Review failures - may indicate WCAG compliance issues.

### Interaction Tests Fail ❌
Critical! These indicate broken UI functionality that needs fixing.

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Scale Operations E2E Tests
  run: |
    cd spa
    npm run dev &
    npx wait-on http://localhost:5173
    npm run test:e2e -- scale-operations
```

## Performance Considerations

- **Total test execution time**: ~10-15 minutes (all 165 tests)
- **Individual suite time**: 2-5 minutes per test file
- **Memory usage**: ~500MB-1GB for Playwright browsers
- **Parallel execution**: Tests can run in parallel (default: 4 workers)

## Debugging Tips

1. **Use UI Mode** for visual debugging
2. **Add `await page.pause()`** in tests to stop execution
3. **Take screenshots** with `await page.screenshot({ path: 'debug.png' })`
4. **Enable trace viewer** with `--trace=on`
5. **Reduce timeout** temporarily to fail fast: `await page.waitForTimeout(100)`

## Contributing

When adding new Scale Operations features:

1. Add interaction tests for new components
2. Add workflow tests for new user flows
3. Add accessibility tests for new UI elements
4. Update this README with new test information

## References

- [Playwright Documentation](https://playwright.dev)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Scale Operations Test Summary](./SCALE_OPERATIONS_TEST_SUMMARY.md)

---

**Last Updated**: 2025-11-11
**Test Framework**: Playwright v1.40+
**Node Version**: 18+ required
