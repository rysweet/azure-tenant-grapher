# Integration with Gadugi Agentic Test Framework

This demo walkthrough system integrates seamlessly with the existing gadugi-agentic-test framework in the SPA.

## Integration Points

### 1. Shared Test Infrastructure

The demo system leverages the existing test framework from `spa/agentic-testing/`:

```javascript
// Using existing gadugi test runner
const { GadugiTestRunner } = require('../../spa/agentic-testing/src/runner');
```

### 2. Scenario Compatibility

Our YAML scenarios are compatible with gadugi's scenario format:

```yaml
# Both formats work
gadugi_scenario:
  steps:
    - action: click
      target: "#button"

our_scenario:
  steps:
    - action: "click"
      selector: "#button"
```

### 3. Assertion Reuse

We extend gadugi's assertion capabilities:

```python
from spa.agentic_testing.assertions import BaseAssertions

class ExtendedAssertions(BaseAssertions):
    def custom_azure_assertion(self, page, params):
        # Azure-specific validations
        pass
```

## Running with Gadugi

### Option 1: Direct Integration

```bash
# Run using gadugi runner with our scenarios
cd spa
node run-gadugi-test.js --scenario ../demos/walkthrough/scenarios/03_scan.yaml
```

### Option 2: Python Orchestrator

```bash
# Run using our Python orchestrator
cd demos/walkthrough
python orchestrator.py --story full_walkthrough
```

### Option 3: Hybrid Approach

```javascript
// hybrid_runner.js
const gadugiRunner = require('./spa/agentic-testing/smart-ui-test');
const pythonScenarios = require('./demos/walkthrough/scenarios');

async function runHybrid() {
    // Run gadugi tests
    await gadugiRunner.runTests();

    // Run Python scenarios
    const { spawn } = require('child_process');
    spawn('python', ['demos/walkthrough/orchestrator.py']);
}
```

## Shared Screenshot Management

Both systems use the same screenshot directory structure:

```
screenshots/
├── gadugi/          # Gadugi test screenshots
├── walkthrough/     # Demo walkthrough screenshots
└── gallery.html     # Combined gallery
```

## Test Results Integration

### Unified Reporting

```python
# In orchestrator.py
def integrate_gadugi_results():
    # Read gadugi results
    with open('spa/agentic-testing/test-results.json') as f:
        gadugi_results = json.load(f)

    # Merge with our results
    combined_results = {
        'gadugi': gadugi_results,
        'walkthrough': self.results
    }

    # Generate unified report
    generate_unified_report(combined_results)
```

## CI/CD Pipeline Integration

```yaml
# .github/workflows/test.yml
name: Complete Testing

jobs:
  test:
    steps:
      - name: Run Gadugi Tests
        run: |
          cd spa
          npm run test:gadugi

      - name: Run Demo Walkthrough
        run: |
          cd demos/walkthrough
          python orchestrator.py --headless --story full_walkthrough

      - name: Merge Results
        run: |
          python demos/walkthrough/merge_results.py

      - name: Upload Combined Report
        uses: actions/upload-artifact@v3
        with:
          name: test-reports
          path: reports/
```

## Development Workflow

### Adding New Tests

1. **For UI interaction tests**: Add to gadugi scenarios
2. **For comprehensive demos**: Add to walkthrough scenarios
3. **For both**: Create in compatible YAML format

### Debugging

Both systems support the same debugging flags:

```bash
# Gadugi
GADUGI_DEBUG=true node run-gadugi-test.js

# Walkthrough
python orchestrator.py --debug
```

## Best Practices

1. **Keep scenarios modular** - One feature per scenario file
2. **Use consistent selectors** - data-testid attributes preferred
3. **Share test data** - Use same fixtures for both systems
4. **Coordinate screenshots** - Avoid filename conflicts
5. **Unified assertions** - Use compatible assertion formats

## Future Enhancements

- [ ] Real-time result streaming between systems
- [ ] Unified test runner CLI
- [ ] Shared test data generation
- [ ] Combined performance metrics
- [ ] Cross-system dependency management