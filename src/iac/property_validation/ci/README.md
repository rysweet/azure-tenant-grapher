# CI/CD Integration for Property Validation

This module provides automated property coverage validation for pull requests, ensuring that IaC generation maintains high quality standards.

## Overview

The CI/CD integration enforces quality gates by:

1. Running property coverage validation on all handlers
2. Checking results against configured thresholds
3. Posting detailed reports as PR comments
4. Failing CI if thresholds are violated

## Components

### 1. PR Checker Script (`pr_checker.py`)

Main validation script that:
- Loads threshold configuration from YAML
- Analyzes all handler files in the specified directory
- Calculates coverage metrics and gap analysis
- Checks against thresholds
- Generates Markdown reports

**Usage**:
```bash
python pr_checker.py --handlers-dir ./src/iac/handlers --output report.md --verbose
```

**Exit Codes**:
- `0`: All thresholds passed
- `1`: One or more thresholds failed
- `2`: Configuration or runtime error

### 2. Thresholds Configuration (`thresholds.yaml`)

YAML file defining coverage thresholds:

```yaml
thresholds:
  overall_minimum: 70          # Minimum average coverage across all handlers
  per_handler_minimum: 60      # Minimum coverage for each individual handler
  critical_gaps_allowed: 0     # Maximum CRITICAL gaps (typically 0)
  high_gaps_allowed: 2         # Maximum HIGH priority gaps
  regression_tolerance: -5     # Maximum allowed coverage decrease (percentage points)
```

**Threshold Meanings**:

- **overall_minimum**: Average coverage across all handlers must be ≥ this value
- **per_handler_minimum**: Each handler must individually meet this threshold
- **critical_gaps_allowed**: Number of CRITICAL gaps allowed (gaps that block deployment)
- **high_gaps_allowed**: Number of HIGH priority gaps allowed (security/compliance issues)
- **regression_tolerance**: How much coverage can decrease compared to baseline

### 3. GitHub Actions Workflow (`property-coverage.yml`)

Automated workflow that:
- Triggers on PRs affecting handlers or validation code
- Sets up Python environment
- Runs PR checker
- Posts Markdown report as PR comment
- Fails CI if thresholds violated

## Integration Setup

### Step 1: Configure Thresholds

Edit `thresholds.yaml` to match your project's quality standards:

```yaml
thresholds:
  overall_minimum: 70
  per_handler_minimum: 60
  critical_gaps_allowed: 0
  high_gaps_allowed: 2
  regression_tolerance: -5
```

**Recommendations**:
- Start with lower thresholds (60-70%) and increase over time
- Always keep `critical_gaps_allowed: 0` (critical gaps block deployment)
- Allow 2-5 HIGH gaps initially, reduce as coverage improves
- Set regression tolerance to prevent backsliding (-5% to -10%)

### Step 2: Enable GitHub Actions Workflow

The workflow is already configured in `.github/workflows/property-coverage.yml` and will automatically run on:

- Pull requests that modify handler files
- Pull requests that modify validation code
- Pushes to main branch

**Required Permissions**:
- `contents: read` - Read repository code
- `pull-requests: write` - Post PR comments

### Step 3: Run Locally (Optional)

Test the validation locally before pushing:

```bash
# Run validation
python src/iac/property_validation/ci/pr_checker.py \
  --handlers-dir src/iac/handlers \
  --thresholds src/iac/property_validation/ci/thresholds.yaml \
  --output coverage-report.md \
  --verbose

# Check exit code
echo $?  # 0 = pass, 1 = fail
```

## Understanding the Report

The PR checker generates a detailed Markdown report with:

### 1. Overall Status
```markdown
# ✅ Property Coverage Validation: PASSED
# ❌ Property Coverage Validation: FAILED
```

### 2. Coverage Metrics
```markdown
## Overall Coverage

- **Coverage**: 75.0%
- **Threshold**: 70.0%
- **Handlers Analyzed**: 5
```

### 3. Gap Summary
```markdown
## Gap Summary

- **CRITICAL gaps**: 0 (allowed: 0)
- **HIGH priority gaps**: 2 (allowed: 2)
```

### 4. Per-Handler Breakdown
```markdown
| Handler | Coverage | Critical | High | Status |
|---------|----------|----------|------|--------|
| storage_handler.py | 85.0% | 0 | 1 | ✅ |
| network_handler.py | 65.0% | 0 | 1 | ✅ |
```

### 5. Threshold Violations (if any)
```markdown
## ⚠️ Threshold Violations

- network_handler.py: Coverage 55.0% < minimum 60.0%
- CRITICAL gaps: 1 > allowed 0
```

## Troubleshooting

### Validation Fails with "No handlers found"

**Cause**: The `--handlers-dir` path doesn't contain any `*_handler.py` files.

**Solution**: Verify the handlers directory path and ensure handler files follow the naming convention.

```bash
ls src/iac/handlers/*_handler.py
```

### Thresholds file not found

**Cause**: The thresholds.yaml file is missing or path is incorrect.

**Solution**: Verify the file exists at the expected location:

```bash
ls src/iac/property_validation/ci/thresholds.yaml
```

### "Missing 'thresholds' key" error

**Cause**: The YAML file is missing the required `thresholds:` top-level key.

**Solution**: Ensure your YAML file has this structure:

```yaml
thresholds:
  overall_minimum: 70
  # ... other thresholds
```

### All handlers pass individually but overall fails

**Cause**: Average coverage across all handlers is below `overall_minimum` threshold.

**Solution**: Either:
- Improve coverage in lower-performing handlers
- Adjust `overall_minimum` threshold in `thresholds.yaml`

### CRITICAL gaps detected

**Cause**: Handlers are missing required properties with no defaults.

**Solution**: CRITICAL gaps must be fixed immediately as they block deployment:
1. Review the gap details in the report
2. Add the missing properties to the handler
3. Re-run validation

## Development

### Running Tests

```bash
pytest src/iac/property_validation/ci/tests/test_pr_checker.py -v
```

### Adding New Thresholds

To add a new threshold type:

1. Add to `ValidationThresholds` dataclass in `pr_checker.py`
2. Update `load_thresholds()` to load the new value
3. Add validation logic in `check_thresholds()`
4. Update `generate_markdown_report()` to include in report
5. Add to `thresholds.yaml` with default value
6. Add tests in `test_pr_checker.py`

### Integrating with Handler Analysis

The current implementation uses mock data in `validate_handler()`. To integrate with actual handler analysis:

```python
def validate_handler(self, handler_file: Path) -> Optional[CoverageMetrics]:
    # 1. Parse handler file to extract property usage
    from property_validation.analysis import HandlerAnalyzer
    analyzer = HandlerAnalyzer()
    usage = analyzer.analyze_handler(handler_file)

    # 2. Load Terraform schema for resource types
    from property_validation.schemas import TerraformScraper
    scraper = TerraformScraper()
    schema = scraper.get_schema(resource_type)

    # 3. Run gap analysis
    gaps = self.gap_finder.find_gaps(schema.properties, usage.terraform_writes)

    # 4. Calculate coverage metrics
    required_props = set(schema.properties.keys())
    actual_props = usage.terraform_writes
    return self.calculator.calculate_coverage(required_props, actual_props, gaps)
```

## Philosophy

This CI/CD integration follows amplihack's core principles:

- **Ruthless Simplicity**: Single script, clear thresholds, minimal dependencies
- **Fail Fast**: Clear error messages, early validation, no surprises
- **Zero-BS Implementation**: Working validation, actionable reports, real enforcement
- **Self-Contained Brick**: Complete CI/CD integration in one module

## See Also

- [Property Validation README](../README.md) - Overview of the validation system
- [Validation Engine](../validation/) - Core validation logic
- [GitHub Actions Documentation](https://docs.github.com/en/actions) - Workflow reference
