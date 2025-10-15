# IaC Pre-flight Validation Script

## Overview

The `validate_generated_iac.py` script performs comprehensive validation of generated Infrastructure-as-Code (IaC) files before deployment. It catches common errors that would cause `terraform plan` or `terraform apply` to fail, saving time and preventing deployment issues.

## Purpose

Based on ITERATION 15 error analysis, this script catches:
- Placeholder values ("xxx", "TODO", etc.)
- Invalid tenant/subscription IDs
- Subnet CIDR misconfigurations
- Duplicate resource declarations
- Missing required fields
- Invalid resource references

## Usage

### Basic Usage

```bash
# Validate IaC in a directory
python scripts/validate_generated_iac.py <iac_directory>

# Example
python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
```

### JSON Output

```bash
# Get JSON output for CI/CD integration
python scripts/validate_generated_iac.py --json <iac_directory>
```

### With uv

```bash
uv run python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
```

## Exit Codes

- **0**: All validations passed
- **1**: One or more validations failed
- **2**: Script error (invalid arguments, file not found, etc.)

## Validation Checks

### 1. No Placeholders

**Purpose**: Detects placeholder values that need to be replaced

**Patterns Detected**:
- `xxx`, `XXX`
- `TODO`, `FIXME`
- `CHANGEME`, `PLACEHOLDER`

**Example Issue**:
```
ERROR: Found placeholder 'xxx' in generated code
  File: main.tf.json | Line: 495
```

### 2. Valid Tenant IDs

**Purpose**: Ensures tenant IDs are valid UUIDs

**Checks**:
- Not all zeros (00000000-0000-0000-0000-000000000000)
- Valid UUID format

**Example Issue**:
```
ERROR: Invalid tenant_id (all zeros): 00000000-0000-0000-0000-000000000000
  Resource: azurerm_key_vault.SimuLand | Field: tenant_id
```

### 3. Valid Subscription IDs

**Purpose**: Validates subscription IDs in resource paths

**Checks**:
- Not placeholders ("xxx")
- Valid UUID format in `/subscriptions/` paths

**Example Issue**:
```
ERROR: Found placeholder subscription ID: xxx
  File: main.tf.json
```

### 4. Subnet CIDR Validation

**Purpose**: Verifies subnets fall within VNet address spaces

**Checks**:
- Subnet CIDR is within parent VNet address space
- Valid CIDR notation
- VNet address space is valid

**Example Issue**:
```
ERROR: Subnet CIDR '10.8.0.0/24' is outside VNet address space ['10.0.0.0/16']
  Resource: azurerm_subnet.Ubuntu_vnet_default | Field: address_prefixes
```

### 5. No Duplicate Resources

**Purpose**: Detects duplicate resource declarations

**Checks**:
- No duplicate resource names within the same type

**Example Issue**:
```
ERROR: Duplicate resource declaration
  Resource: azurerm_resource_group.test_rg
```

### 6. Required Fields Populated

**Purpose**: Ensures critical fields aren't empty or null

**Fields Checked by Resource Type**:
- `azurerm_resource_group`: name, location
- `azurerm_virtual_network`: name, location, address_space
- `azurerm_subnet`: name, address_prefixes, virtual_network_name
- `azurerm_linux_virtual_machine`: name, location, size, admin_username
- `azurerm_storage_account`: name, location, account_tier, account_replication_type
- `azurerm_key_vault`: name, location, tenant_id, sku_name

**Example Issue**:
```
ERROR: Required field 'name' is empty or null
  Resource: azurerm_resource_group.test_rg | Field: name
```

### 7. Valid Resource References

**Purpose**: Checks resource references point to existing resources

**Checks**:
- `depends_on` references exist
- Interpolation references (`${azurerm_...}`) exist

**Example Issue**:
```
WARNING: Dependency references non-existent resource: azurerm_resource_group.missing_rg
  Resource: azurerm_virtual_network.test_vnet | Field: depends_on
```

## Output Format

### Table Format (Default)

```
IaC Validation Results
╭───────────────────────────┬────────┬────────┬──────────╮
│ Check                     │ Status │ Errors │ Warnings │
├───────────────────────────┼────────┼────────┼──────────┤
│ No Placeholders           │  FAIL  │      2 │        - │
│ Valid Tenant IDs          │  FAIL  │      1 │        - │
│ Valid Subscription IDs    │  FAIL  │      1 │        - │
│ Subnet CIDR Validation    │  FAIL  │      4 │        - │
│ No Duplicate Resources    │  PASS  │      - │        - │
│ Required Fields Populated │  PASS  │      - │        - │
│ Valid Resource References │  PASS  │      - │        - │
╰───────────────────────────┴────────┴────────┴──────────╯

╭─────────────────── Summary ───────────────────╮
│ Total Checks: 7                               │
│ Passed: 3                                     │
│ Failed: 4                                     │
│ Total Errors: 8                               │
│ Total Warnings: 0                             │
╰───────────────────────────────────────────────╯

Detailed Issues:

No Placeholders:
  ERROR: Found placeholder '\bxxx\b' in generated code
    File: main.tf.json | Line: 495
```

### JSON Format

```json
{
  "summary": {
    "total_checks": 7,
    "passed_checks": 3,
    "failed_checks": 4,
    "total_errors": 8,
    "total_warnings": 0
  },
  "checks": [
    {
      "name": "No Placeholders",
      "passed": false,
      "errors": 2,
      "warnings": 0,
      "issues": [
        {
          "severity": "error",
          "message": "Found placeholder '\\bxxx\\b' in generated code",
          "file": "main.tf.json",
          "line": 495,
          "resource_type": null,
          "resource_name": null,
          "field": null
        }
      ]
    }
  ]
}
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Validate Generated IaC
  run: |
    uv run python scripts/validate_generated_iac.py ${{ env.IAC_DIR }}

- name: Upload Validation Report (on failure)
  if: failure()
  run: |
    uv run python scripts/validate_generated_iac.py --json ${{ env.IAC_DIR }} > validation_report.json

- name: Archive Validation Report
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: validation-report
    path: validation_report.json
```

### Pre-deployment Script

```bash
#!/bin/bash
set -e

IAC_DIR="demos/simuland_iteration3/iteration16"

echo "Running pre-flight validation..."
uv run python scripts/validate_generated_iac.py "$IAC_DIR"

if [ $? -eq 0 ]; then
    echo "✓ Validation passed, proceeding with terraform plan"
    cd "$IAC_DIR"
    terraform plan
else
    echo "✗ Validation failed, fix errors before deployment"
    exit 1
fi
```

## Testing

The script includes comprehensive unit tests:

```bash
# Run tests
uv run pytest tests/test_validate_generated_iac.py -v

# Run specific test
uv run pytest tests/test_validate_generated_iac.py::test_check_subnet_cidrs_fail_out_of_range -v
```

## Dependencies

Required Python packages:
- `rich>=13.0.0` - For formatted console output
- `ipaddress` - For CIDR validation (stdlib)

## Error Severity

### Errors (Fail Validation)
- Placeholders in code
- Invalid tenant/subscription IDs
- Subnet CIDRs outside VNet range
- Duplicate resources
- Missing required fields
- Invalid CIDRs

### Warnings (Pass with Warnings)
- Invalid resource references (may be valid Terraform)
- Missing VNet for subnet validation

## Common Issues and Solutions

### Issue: Subnet Outside VNet Range

**Error**:
```
ERROR: Subnet CIDR '10.8.0.0/24' is outside VNet address space ['10.0.0.0/16']
```

**Solution**:
- Use `--auto-fix-subnets` flag during IaC generation
- Or manually adjust subnet CIDRs to fall within VNet range

### Issue: Placeholder Subscription ID

**Error**:
```
ERROR: Found placeholder subscription ID: xxx
```

**Solution**:
- This indicates IaC generation couldn't determine the subscription ID
- Check that the resource has a valid subscription context in Neo4j
- Regenerate IaC with proper subscription metadata

### Issue: All-Zeros Tenant ID

**Error**:
```
ERROR: Invalid tenant_id (all zeros): 00000000-0000-0000-0000-000000000000
```

**Solution**:
- Ensure tenant ID is properly set during Azure scan
- Check Neo4j graph for correct tenant ID metadata
- Regenerate IaC with correct tenant information

## Extending the Validator

### Adding a New Check

```python
def check_custom_validation(self) -> ValidationResult:
    """Check for custom validation logic."""
    result = ValidationResult(
        check_name="Custom Validation",
        passed=True,
    )

    resources = self.terraform_data.get("resource", {})

    # Your validation logic here
    for resource_type, resources_dict in resources.items():
        for resource_name, resource_config in resources_dict.items():
            # Check conditions
            if some_condition:
                result.passed = False
                result.issues.append(
                    ValidationIssue(
                        check_name="Custom Validation",
                        severity="error",
                        message="Description of issue",
                        resource_type=resource_type,
                        resource_name=resource_name,
                    )
                )

    return result
```

Then add to `validate_all()`:

```python
def validate_all(self) -> List[ValidationResult]:
    results = [
        self.check_no_placeholders(),
        # ... other checks ...
        self.check_custom_validation(),  # Add here
    ]
    return results
```

## Related Documentation

- [Subnet Validation](../src/iac/validators/subnet_validator.py) - Runtime subnet validation
- [IaC Generation](../CLAUDE.md#modifying-iac-generation) - IaC generation process
- [CI/CD Pipeline](../.github/workflows/ci.yml) - GitHub Actions integration

## Support

For issues or questions:
1. Check validation output for specific error messages
2. Review this README for common issues
3. Examine the actual Terraform JSON for the flagged resources
4. Check Neo4j graph data for source resource metadata
