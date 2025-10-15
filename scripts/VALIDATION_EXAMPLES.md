# IaC Validation Script - Usage Examples

## Quick Start

```bash
# Validate IaC directory
uv run python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
```

## Real-World Examples

### Example 1: Clean IaC (All Checks Pass)

**Command**:
```bash
uv run python scripts/validate_generated_iac.py demos/clean_iac
```

**Output**:
```
IaC Validation Results
╭───────────────────────────┬────────┬────────┬──────────╮
│ Check                     │ Status │ Errors │ Warnings │
├───────────────────────────┼────────┼────────┼──────────┤
│ No Placeholders           │  PASS  │      - │        - │
│ Valid Tenant IDs          │  PASS  │      - │        - │
│ Valid Subscription IDs    │  PASS  │      - │        - │
│ Subnet CIDR Validation    │  PASS  │      - │        - │
│ No Duplicate Resources    │  PASS  │      - │        - │
│ Required Fields Populated │  PASS  │      - │        - │
│ Valid Resource References │  PASS  │      - │        - │
╰───────────────────────────┴────────┴────────┴──────────╯

╭─────────────────── Summary ───────────────────╮
│ Total Checks: 7                               │
│ Passed: 7                                     │
│ Failed: 0                                     │
│ Total Errors: 0                               │
│ Total Warnings: 0                             │
╰───────────────────────────────────────────────╯

✓ All validations passed! IaC is ready for deployment.
```

**Exit Code**: `0`

---

### Example 2: IaC with Placeholder Issues

**Command**:
```bash
uv run python scripts/validate_generated_iac.py demos/iac_with_placeholders
```

**Output**:
```
IaC Validation Results
╭───────────────────────────┬────────┬────────┬──────────╮
│ Check                     │ Status │ Errors │ Warnings │
├───────────────────────────┼────────┼────────┼──────────┤
│ No Placeholders           │  FAIL  │      3 │        - │
│ Valid Tenant IDs          │  PASS  │      - │        - │
│ Valid Subscription IDs    │  FAIL  │      1 │        - │
│ Subnet CIDR Validation    │  PASS  │      - │        - │
│ No Duplicate Resources    │  PASS  │      - │        - │
│ Required Fields Populated │  PASS  │      - │        - │
│ Valid Resource References │  PASS  │      - │        - │
╰───────────────────────────┴────────┴────────┴──────────╯

Detailed Issues:

No Placeholders:
  ERROR: Found placeholder '\bxxx\b' in generated code
    File: main.tf.json | Line: 42
  ERROR: Found placeholder '\bTODO\b' in generated code
    File: main.tf.json | Line: 156
  ERROR: Found placeholder '\bFIXME\b' in generated code
    File: main.tf.json | Line: 298

Valid Subscription IDs:
  ERROR: Found placeholder subscription ID: xxx
    File: main.tf.json
```

**Exit Code**: `1`

**Fix**: Replace all placeholder values with actual values or regenerate IaC.

---

### Example 3: Subnet CIDR Issues (Real Example from Iteration 16)

**Command**:
```bash
uv run python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
```

**Output**:
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

Subnet CIDR Validation:
  ERROR: Subnet CIDR '10.8.0.0/24' is outside VNet address space ['10.0.0.0/16']
    Resource: azurerm_subnet.Ubuntu_vnet_default | Field: address_prefixes
  ERROR: Subnet CIDR '10.8.1.0/26' is outside VNet address space ['10.0.0.0/16']
    Resource: azurerm_subnet.Ubuntu_vnet_AzureBastionSubnet | Field: address_prefixes
  ERROR: Subnet CIDR '10.6.0.0/24' is outside VNet address space ['10.0.0.0/16']
    Resource: azurerm_subnet.DC001_vnet_default | Field: address_prefixes
  ERROR: Subnet CIDR '10.6.1.0/26' is outside VNet address space ['10.0.0.0/16']
    Resource: azurerm_subnet.DC001_vnet_AzureBastionSubnet | Field: address_prefixes
```

**Exit Code**: `1`

**Fix**:
```bash
# Regenerate IaC with auto-fix enabled
uv run atg generate-iac --tenant-id <TENANT_ID> --auto-fix-subnets
```

---

### Example 4: JSON Output for CI/CD

**Command**:
```bash
uv run python scripts/validate_generated_iac.py --json demos/simuland_iteration3/iteration16 | jq
```

**Output** (formatted):
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
      "name": "Subnet CIDR Validation",
      "passed": false,
      "errors": 4,
      "warnings": 0,
      "issues": [
        {
          "severity": "error",
          "message": "Subnet CIDR '10.8.0.0/24' is outside VNet address space ['10.0.0.0/16']",
          "file": null,
          "line": null,
          "resource_type": "azurerm_subnet",
          "resource_name": "Ubuntu_vnet_default",
          "field": "address_prefixes"
        }
      ]
    }
  ]
}
```

**Use in Script**:
```bash
#!/bin/bash

# Run validation and capture JSON
RESULT=$(uv run python scripts/validate_generated_iac.py --json demos/simuland_iteration3/iteration16)

# Parse summary
FAILED_CHECKS=$(echo "$RESULT" | jq '.summary.failed_checks')

if [ "$FAILED_CHECKS" -gt 0 ]; then
    echo "Validation failed with $FAILED_CHECKS failed checks"
    echo "$RESULT" | jq '.checks[] | select(.passed == false)'
    exit 1
fi

echo "Validation passed!"
```

---

### Example 5: Pre-deployment Workflow

**Complete workflow script**:

```bash
#!/bin/bash
# pre_deploy.sh - Complete pre-deployment validation workflow

set -e

IAC_DIR="${1:-demos/simuland_iteration3/iteration16}"
TENANT_ID="${2:-your-tenant-id}"

echo "==================================="
echo "Pre-deployment Validation Workflow"
echo "==================================="
echo ""

# Step 1: Generate IaC with auto-fix
echo "Step 1: Generating IaC..."
uv run atg generate-iac \
    --tenant-id "$TENANT_ID" \
    --auto-fix-subnets \
    --output "$IAC_DIR"

echo "✓ IaC generated"
echo ""

# Step 2: Run validation
echo "Step 2: Running pre-flight validation..."
if uv run python scripts/validate_generated_iac.py "$IAC_DIR"; then
    echo "✓ Pre-flight validation passed"
else
    echo "✗ Pre-flight validation failed"
    echo ""
    echo "Generating detailed JSON report..."
    uv run python scripts/validate_generated_iac.py --json "$IAC_DIR" > validation_report.json
    echo "Report saved to validation_report.json"
    exit 1
fi
echo ""

# Step 3: Run terraform init
echo "Step 3: Running terraform init..."
cd "$IAC_DIR"
terraform init -upgrade

echo "✓ Terraform initialized"
echo ""

# Step 4: Run terraform validate
echo "Step 4: Running terraform validate..."
terraform validate

echo "✓ Terraform validation passed"
echo ""

# Step 5: Run terraform plan
echo "Step 5: Running terraform plan..."
terraform plan -out=tfplan

echo "✓ Terraform plan created"
echo ""

echo "==================================="
echo "Pre-deployment validation complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "  1. Review terraform plan: cd $IAC_DIR && terraform show tfplan"
echo "  2. Apply changes: cd $IAC_DIR && terraform apply tfplan"
```

**Usage**:
```bash
chmod +x pre_deploy.sh
./pre_deploy.sh demos/my_iac my-tenant-id
```

---

### Example 6: Filtering Specific Checks in CI/CD

**Python script to check specific validations**:

```python
#!/usr/bin/env python3
"""
check_critical_only.py - Check only critical validations
"""

import json
import subprocess
import sys

def main():
    iac_dir = sys.argv[1] if len(sys.argv) > 1 else "demos/simuland_iteration3/iteration16"

    # Run validation with JSON output
    result = subprocess.run(
        ["uv", "run", "python", "scripts/validate_generated_iac.py", "--json", iac_dir],
        capture_output=True,
        text=True
    )

    data = json.loads(result.stdout)

    # Define critical checks
    critical_checks = [
        "No Placeholders",
        "Valid Tenant IDs",
        "Valid Subscription IDs",
        "Subnet CIDR Validation",
    ]

    failed_critical = []

    for check in data["checks"]:
        if check["name"] in critical_checks and not check["passed"]:
            failed_critical.append(check)

    if failed_critical:
        print(f"❌ {len(failed_critical)} critical checks failed:")
        for check in failed_critical:
            print(f"\n{check['name']}:")
            for issue in check["issues"]:
                print(f"  - {issue['message']}")
        sys.exit(1)

    print("✅ All critical checks passed!")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Example 7: Integration with Terraform Workflow

**Makefile example**:

```makefile
.PHONY: validate plan apply clean

IAC_DIR ?= demos/simuland_iteration3/iteration16

validate:
	@echo "Running pre-flight validation..."
	@uv run python scripts/validate_generated_iac.py $(IAC_DIR)

init:
	@echo "Initializing Terraform..."
	@cd $(IAC_DIR) && terraform init

plan: validate init
	@echo "Creating Terraform plan..."
	@cd $(IAC_DIR) && terraform plan -out=tfplan

apply: plan
	@echo "Applying Terraform plan..."
	@cd $(IAC_DIR) && terraform apply tfplan

clean:
	@echo "Cleaning Terraform artifacts..."
	@cd $(IAC_DIR) && rm -rf .terraform .terraform.lock.hcl tfplan

all: validate init plan
```

**Usage**:
```bash
# Validate only
make validate IAC_DIR=demos/my_iac

# Full workflow
make all IAC_DIR=demos/my_iac

# Apply after validation
make apply IAC_DIR=demos/my_iac
```

---

## Error Code Reference

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | All validations passed | Proceed with deployment |
| 1 | One or more validations failed | Fix errors and re-run |
| 2 | Script error (missing files, etc.) | Check arguments and file paths |

## Quick Tips

1. **Always validate before `terraform plan`**: Catch issues early
   ```bash
   uv run python scripts/validate_generated_iac.py <dir> && cd <dir> && terraform plan
   ```

2. **Use JSON output in CI/CD**: Easier to parse programmatically
   ```bash
   uv run python scripts/validate_generated_iac.py --json <dir> > report.json
   ```

3. **Auto-fix subnets during generation**: Prevent CIDR issues
   ```bash
   uv run atg generate-iac --auto-fix-subnets
   ```

4. **Save validation reports**: Keep history of validation results
   ```bash
   uv run python scripts/validate_generated_iac.py --json <dir> > validation_$(date +%Y%m%d_%H%M%S).json
   ```
