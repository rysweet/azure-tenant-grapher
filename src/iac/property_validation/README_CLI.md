# Property Validation CLI

Ahoy there! This CLI tool ties together all 5 bricks o' the property validation system into a comprehensive command-line interface.

## Architecture

The CLI integrates these bricks:
1. **Schema Loader** (Azure + Terraform scrapers)
2. **Handler Analyzer** (AST-based property extraction)
3. **Validation Engine** (Gap finder + Critical classifier)
4. **Coverage Reporter** (Metrics calculation)
5. **Manifest Generator** (YAML schema generation)

## Installation

```bash
# Install the package
pip install -e .

# Or use uv
uv pip install -e .
```

## Usage

### Validate Handlers

```bash
# Validate all handlers
python -m iac.property_validation validate

# Validate specific handler
python -m iac.property_validation validate --handler src/iac/handlers/storage_account_handler.py
```

**Output**:
- ✓ PASSED - No critical gaps, quality score >= 70
- ✗ FAILED - Critical gaps found or quality score < 70
- ⚠ WARNING - Issues that don't block deployment

### Generate Coverage Report

```bash
# Generate HTML report
python -m iac.property_validation report --output report.html
```

Creates visual HTML report showing:
- Overall coverage percentage
- Gap breakdown by criticality
- Per-handler analysis
- Quality trends

### Generate Manifest

```bash
# Generate manifest for resource type
python -m iac.property_validation generate-manifest --resource storage_account

# Specify output directory
python -m iac.property_validation generate-manifest --resource storage_account --output-dir manifests/
```

Creates YAML manifest with:
- Azure resource type mapping
- Terraform parameter mapping
- Property criticality classification
- Provider version constraints

### Check CI Thresholds

```bash
# Check if coverage meets thresholds
python -m iac.property_validation check-thresholds
```

Exit codes:
- 0 = All thresholds passed
- 1 = Some thresholds failed

Default thresholds:
- Minimum coverage: 80%
- Maximum critical gaps: 0
- Minimum quality score: 70

### Clear Schema Cache

```bash
# Clear all cached schemas
python -m iac.property_validation clear-cache

# Clear specific provider
python -m iac.property_validation clear-cache --provider Microsoft.Storage
```

## Features

### Pretty Output

The CLI uses colored terminal output:
- 🟢 Green: Success messages
- 🔴 Red: Error messages
- 🟡 Yellow: Warnings
- 🔵 Blue: Info messages
- 🟣 Magenta: Section headers

### Progress Indicators

For long-running operations, progress is shown:
```
Validating: storage_account_handler.py
  Properties found: 15
  Terraform writes: 12
  Azure reads: 15
  Coverage: 80.0%
  Quality score: 75.0/100
  ✓ PASSED
```

### Error Handling

Clear error messages with actionable guidance:
```
✗ Handler file not found: invalid_path.py

  Suggestions:
  - Check the file path
  - Ensure handler file exists
  - Use relative path from project root
```

### Exit Codes

Proper exit codes for CI/CD integration:
- 0 = Success
- 1 = Failure
- 130 = Interrupted by user (Ctrl+C)

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Property Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e .

      - name: Validate property coverage
        run: |
          python -m iac.property_validation validate

      - name: Check thresholds
        run: |
          python -m iac.property_validation check-thresholds

      - name: Generate report
        if: always()
        run: |
          python -m iac.property_validation report --output coverage_report.html

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: coverage-report
          path: coverage_report.html
```

### Pre-commit Hook Example

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: property-validation
        name: Validate property coverage
        entry: python -m iac.property_validation validate
        language: system
        pass_filenames: false
```

## Development

### Testing the CLI

```bash
# Run all tests
pytest src/iac/property_validation/tests/

# Test CLI commands
python -m iac.property_validation --help
python -m iac.property_validation validate --handler test_handler.py
```

### Adding New Commands

1. Add function to `cli.py`:
```python
def new_command(args) -> int:
    """New command implementation."""
    # Implementation
    return 0
```

2. Register in `main()`:
```python
new_parser = subparsers.add_parser("new-command", help="Help text")
new_parser.add_argument("--option", help="Option help")
```

3. Add command handler:
```python
if args.command == "new-command":
    return new_command(args)
```

## Troubleshooting

### Import Errors

If ye see `ModuleNotFoundError: No module named 'iac'`:

```bash
# Ensure package is installed
pip install -e .

# Or use PYTHONPATH
export PYTHONPATH=/path/to/atg2/src:$PYTHONPATH
python -m iac.property_validation validate
```

### Cache Issues

If schema cache seems stale:

```bash
# Clear cache and re-fetch
python -m iac.property_validation clear-cache
python -m iac.property_validation validate
```

### Permission Errors

If cache directory is not writable:

```bash
# Check cache location
ls -la ~/.atg2/schemas/

# Fix permissions
chmod -R u+w ~/.atg2/
```

## Examples

### Example 1: Basic Validation

```bash
$ python -m iac.property_validation validate

============================================================
Property Validation
============================================================
ℹ Found 5 handler(s) to validate

Validating: storage_account_handler.py
  Properties found: 15
  Terraform writes: 12
  Azure reads: 15
  Coverage: 80.0%
  Quality score: 75.0/100
  ✓ PASSED

Validating: virtual_machine_handler.py
  Properties found: 25
  Terraform writes: 20
  Azure reads: 25
  Coverage: 80.0%
  Quality score: 70.0/100
  ⚠ [CRITICAL] vm_size: Required property with no default - blocks deployment
  ✗ FAILED: 1 critical gap(s)

============================================================
Validation Summary
============================================================

Handlers validated: 5
Passed: 4
Failed: 1
```

### Example 2: Generate Manifest

```bash
$ python -m iac.property_validation generate-manifest --resource storage_account

============================================================
Generating Manifest: storage_account
============================================================
ℹ Output: manifests/storage_account.yaml
✓ Manifest generated: manifests/storage_account.yaml
ℹ Edit the manifest to add property mappings
```

### Example 3: CI Threshold Check

```bash
$ python -m iac.property_validation check-thresholds

============================================================
CI/CD Threshold Check
============================================================
ℹ Thresholds:
  min_coverage: 80.0
  max_critical_gaps: 0
  min_quality_score: 70.0

ℹ Actual values:
✓ Coverage: 85.0% >= 80.0%
✓ Critical gaps: 0 <= 0
✓ Quality score: 75.0 >= 70.0

============================================================
Result
============================================================
✓ All thresholds PASSED
```

## Philosophy

The CLI follows amplihack philosophy:
- **Ruthless simplicity**: Direct, clear commands
- **Zero-BS**: Working functionality, no stubs
- **Brick & studs**: Integrates 5 self-contained modules
- **Quality over speed**: Proper validation and error handling

## Support

For issues or questions:
1. Check troubleshooting section
2. Review examples
3. Open GitHub issue with:
   - Command that failed
   - Full error message
   - Environment details (Python version, OS)

Happy validatin', matey! ⚓
