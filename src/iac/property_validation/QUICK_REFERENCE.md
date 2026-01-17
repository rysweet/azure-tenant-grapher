# Property Validation CLI - Quick Reference

## Installation
```bash
pip install -e .
```

## Commands

### Validate All Handlers
```bash
python -m iac.property_validation validate
```

### Validate Specific Handler
```bash
python -m iac.property_validation validate --handler path/to/handler.py
```

### Generate Coverage Report
```bash
python -m iac.property_validation report --output report.html
```

### Generate Manifest
```bash
python -m iac.property_validation generate-manifest --resource storage_account
python -m iac.property_validation generate-manifest --resource storage_account --output-dir manifests/
```

### Check CI Thresholds
```bash
python -m iac.property_validation check-thresholds
```

### Clear Schema Cache
```bash
python -m iac.property_validation clear-cache
python -m iac.property_validation clear-cache --provider Microsoft.Storage
```

## Exit Codes
- `0` = Success
- `1` = Failure
- `130` = Interrupted

## Output Colors
- 🟢 **Green** = Success
- 🔴 **Red** = Error
- 🟡 **Yellow** = Warning
- 🔵 **Blue** = Info

## Default Thresholds
- Minimum coverage: **80%**
- Maximum critical gaps: **0**
- Minimum quality score: **70**

## Files
- **CLI**: `src/iac/property_validation/cli.py`
- **Entry point**: `src/iac/property_validation/__main__.py`
- **Docs**: `src/iac/property_validation/README_CLI.md`

## CI/CD Example
```yaml
- name: Validate properties
  run: python -m iac.property_validation validate

- name: Check thresholds
  run: python -m iac.property_validation check-thresholds
```
