# Property Validation System

Comprehensive property validation for Infrastructure-as-Code generation, ensuring all required properties are present and correctly classified by criticality.

## Overview

This module provides a complete validation engine for analyzing property coverage in generated Terraform code. It identifies missing properties, classifies them by criticality (CRITICAL/HIGH/MEDIUM/LOW), and calculates coverage metrics.

## Architecture (Brick Design)

The module follows the "brick & studs" pattern with three self-contained components:

```
property_validation/
├── models.py              # Data models (PropertyDefinition, PropertyGap, etc.)
├── validation/            # Validation Engine brick
│   ├── critical_classifier.py   # Classify property criticality
│   ├── gap_finder.py            # Identify missing properties
│   └── coverage_calculator.py   # Calculate coverage metrics
├── tests/                 # Comprehensive test suite
└── examples/             # Usage examples
```

## Public API

### Models

- **`Criticality`**: Enum for property criticality levels (CRITICAL, HIGH, MEDIUM, LOW)
- **`PropertyDefinition`**: Schema property definition
- **`PropertyGap`**: Missing property with criticality and suggestion
- **`CoverageMetrics`**: Complete coverage analysis results

### Validation Components

- **`CriticalClassifier`**: Classify property criticality using domain rules
- **`GapFinder`**: Identify missing properties by comparing schema vs actual
- **`CoverageCalculator`**: Calculate coverage percentage and weighted quality score

## Usage

### Basic Example

```python
from iac.property_validation import (
    PropertyDefinition,
    CriticalClassifier,
    GapFinder,
    CoverageCalculator,
)

# 1. Define schema properties (from Terraform provider)
schema = {
    "account_tier": PropertyDefinition(
        name="account_tier",
        required=True,
        has_default=False,
        property_type="string",
    ),
    "tls_version": PropertyDefinition(
        name="tls_version",
        required=False,
        has_default=False,
        property_type="string",
    ),
}

# 2. Get actual properties from generated IaC
actual_properties = {"account_tier"}  # Missing tls_version

# 3. Initialize validation engine
classifier = CriticalClassifier()
finder = GapFinder(classifier)
calculator = CoverageCalculator()

# 4. Find gaps
gaps = finder.find_gaps(schema, actual_properties)

# 5. Calculate metrics
required = set(schema.keys())
metrics = calculator.calculate_coverage(required, actual_properties, gaps)

print(f"Coverage: {metrics.coverage_percentage}%")
print(f"Critical gaps: {metrics.critical_gaps}")
print(f"Quality score: {calculator.calculate_weighted_score(metrics)}/100")
```

### Running Examples

```bash
# Run basic usage example
python3 src/iac/property_validation/examples/basic_usage.py
```

## Criticality Classification

Properties are classified using domain-specific rules:

### CRITICAL (Blocks deployment)

- Required properties with no defaults
- Known deployment-blockers: `account_tier`, `replication_type`, `sku_name`, `sku_tier`

### HIGH (Security/compliance risk)

- Security properties: `tls_version`, `https_only`, `public_network_access`, `encryption`
- Properties containing security keywords: `tls`, `ssl`, `firewall`, `authentication`, etc.

### MEDIUM (Operational impact)

- Operational properties: `tags`, `location`, `zone_redundant`, `backup_enabled`
- Required properties that have defaults

### LOW (Optional features)

- All other optional properties
- Nice-to-have features: `lifecycle_policy`, `versioning`

## Weighted Quality Scoring

The weighted score starts at 100 and deducts points based on gap criticality:

- **CRITICAL gap**: -25 points (blocks deployment)
- **HIGH gap**: -10 points (security risk)
- **MEDIUM gap**: -5 points (operational issue)
- **LOW gap**: -1 point (nice to have)

Score never goes below 0.

## Extending Classification Rules

Dynamically add properties to classification lists:

```python
classifier = CriticalClassifier()

# Add critical property
classifier.add_critical_property("custom_required_prop")

# Add high-priority security property
classifier.add_high_priority_property("custom_security_prop")

# Add security keyword for pattern matching
classifier.add_security_keyword("compliance")
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests (requires pytest)
python -m pytest src/iac/property_validation/tests/ -v

# Run specific test file
python -m pytest src/iac/property_validation/tests/test_critical_classifier.py -v
```

## Philosophy

This module follows the amplihack philosophy:

- **Ruthless simplicity**: Direct set comparison, no fuzzy matching
- **Brick design**: Self-contained with clear public API via `__all__`
- **Zero-BS implementation**: No stubs, all functions work completely
- **Standard library only**: No external dependencies (except local imports)
- **Regeneratable**: Can be rebuilt from this specification

## Contract

### Inputs

- **Schema properties**: Dict of PropertyDefinition objects from Terraform schema
- **Actual properties**: Set of property names found in generated IaC

### Outputs

- **CoverageMetrics**: Complete analysis with coverage %, gaps by criticality
- **PropertyGap list**: Sorted by criticality (CRITICAL first)
- **Quality score**: Weighted 0-100 score based on gap severity

### Guarantees

- Coverage percentage is accurate (total/covered ratio)
- Gaps are sorted by criticality (CRITICAL → HIGH → MEDIUM → LOW)
- Quality score never goes negative
- Empty property sets return 100% coverage (no requirements = perfect)
- All suggested values are sensible defaults for known properties

## Integration Points

This module integrates with:

1. **Schema Loader**: Provides PropertyDefinition objects from Terraform schema
2. **Handler Analyzer**: Provides set of actual properties from generated code
3. **Reporter**: Consumes CoverageMetrics for report generation

## Future Enhancements (Not Implemented)

These are NOT placeholders - they're documented future work:

- Schema loader brick (loads PropertyDefinition from Terraform provider schema)
- Reporter brick (generates human-readable coverage reports)
- Property suggestion engine (ML-based suggestions beyond hardcoded defaults)
- Cross-resource validation (ensure related resources have compatible properties)

---

**Module Status**: ✅ Fully functional, production-ready

**Last Updated**: 2026-01-17

**Contact**: See project maintainers
