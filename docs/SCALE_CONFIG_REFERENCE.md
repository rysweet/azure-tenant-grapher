# Scale Operations Configuration Reference

Complete reference for Azure Tenant Grapher scale operations configuration.

## Table of Contents

- [Overview](#overview)
- [Configuration Loading](#configuration-loading)
- [Configuration Schema](#configuration-schema)
- [Environment Variables](#environment-variables)
- [CLI Override](#cli-override)
- [Validation](#validation)
- [Examples](#examples)

## Overview

The scale operations configuration system provides:

- **Type-safe configuration** using Pydantic models
- **Multi-source loading** with priority: CLI > Env > File > Defaults
- **Validation** with clear error messages
- **Tenant-specific overrides** for multi-tenant deployments
- **Sensible defaults** for all parameters

## Configuration Loading

### Default Location

```
~/.config/azure-tenant-grapher/scale-config.yaml
```

### Override Locations

1. **Environment variable**: `SCALE_CONFIG_PATH=/path/to/config.yaml`
2. **CLI flag**: `--config /path/to/config.yaml`

### Priority Order

Configuration sources are merged with this priority (highest to lowest):

1. **CLI Arguments** (e.g., `--scale-factor 3.0`)
2. **Environment Variables** (e.g., `ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR=3.0`)
3. **Configuration File** (YAML file at specified location)
4. **Default Values** (hardcoded sensible defaults)

### Creating Default Configuration

```bash
# Create default configuration file
uv run atg scale-up --create-default-config

# Force overwrite existing file
uv run atg scale-up --create-default-config --force
```

## Configuration Schema

### Root Configuration

```yaml
# Optional: Default tenant ID when not specified
default_tenant_id: "00000000-0000-0000-0000-000000000000"

# Scale-up operation settings
scale_up:
  # ... (see Scale-Up section)

# Scale-down operation settings
scale_down:
  # ... (see Scale-Down section)

# Performance and resource limits
performance:
  # ... (see Performance section)

# Validation settings
validation:
  # ... (see Validation section)

# Tenant-specific overrides
tenant_overrides:
  # ... (see Tenant Overrides section)
```

### Scale-Up Configuration

```yaml
scale_up:
  # Default strategy: template, scenario, or random
  # Default: template
  default_strategy: template

  # Default scale factor (multiplier for resource counts)
  # Must be > 0, cannot exceed 1000
  # Default: 2.0
  default_scale_factor: 2.0

  # Number of resources to process per batch
  # Must be > 0
  # Default: 500
  batch_size: 500

  # Template strategy settings
  template:
    # Maintain relative proportions of resource types
    # Default: true
    preserve_proportions: true

    # Amount of random variation to introduce (0.0-1.0)
    # Default: 0.1
    variation_percentage: 0.1

  # Scenario strategy settings
  scenario:
    # Default scenario template to use
    # Default: "hub-spoke"
    default_scenario: "hub-spoke"

    # Optional: Path to custom scenario library
    scenario_library_path: "/path/to/scenarios"

  # Random strategy settings
  random:
    # Default target resource count
    # Must be > 0
    # Default: 1000
    default_target_count: 1000

    # Optional: Random seed for reproducible generation
    seed: 42
```

### Scale-Down Configuration

```yaml
scale_down:
  # Default algorithm: forest-fire, mhrw, random-node, or random-edge
  # Default: forest-fire
  default_algorithm: forest-fire

  # Default target size as fraction of original (0.0-1.0)
  # Must be > 0.0 and <= 1.0
  # Default: 0.1
  default_target_size: 0.1

  # Output format: yaml or json
  # Default: yaml
  output_format: yaml

  # Forest Fire algorithm settings
  forest_fire:
    # Probability of 'burning' (selecting) a neighbor (0.0-1.0)
    # Default: 0.4
    burning_probability: 0.4

    # Random seed for reproducible sampling
    # Default: 42
    seed: 42

    # Whether to treat graph as directed
    # Default: false
    directed: false

  # Metropolis-Hastings Random Walk settings
  mhrw:
    # Bias parameter (α=1 for unbiased walk)
    # Must be >= 0.0
    # Default: 1.0
    alpha: 1.0

    # Random seed for reproducible sampling
    # Default: 42
    seed: 42

    # Maximum walk iterations
    # Must be > 0
    # Default: 1000000
    max_iterations: 1000000

  # Random node sampling settings
  random_node:
    # Random seed for reproducible sampling
    # Default: 42
    seed: 42

    # Attempt to preserve graph connectivity
    # Default: false
    preserve_connectivity: false

  # Random edge sampling settings
  random_edge:
    # Random seed for reproducible sampling
    # Default: 42
    seed: 42
```

### Performance Configuration

```yaml
performance:
  # Default batch size for operations
  # Must be > 0
  # Default: 500
  batch_size: 500

  # Memory limit in megabytes
  # Must be > 0
  # Default: 2048
  memory_limit_mb: 2048

  # Operation timeout in seconds
  # Must be > 0
  # Default: 300
  timeout_seconds: 300

  # Maximum number of worker threads/processes (1-32)
  # Default: 4
  max_workers: 4
```

### Validation Configuration

```yaml
validation:
  # Validate configuration before operation
  # Default: true
  pre_operation: true

  # Validate results after operation
  # Default: true
  post_operation: true

  # Fail on validation warnings (not just errors)
  # Default: true
  strict_mode: true
```

### Tenant Overrides

```yaml
tenant_overrides:
  # Each override applies to a specific tenant
  - tenant_id: "tenant-1-id"

    # Override scale-up settings (all fields optional)
    scale_up:
      default_scale_factor: 3.0
      template:
        variation_percentage: 0.05

    # Override scale-down settings (all fields optional)
    scale_down:
      default_algorithm: mhrw
      default_target_size: 0.2

    # Override performance settings (all fields optional)
    performance:
      batch_size: 1000
      timeout_seconds: 600

  - tenant_id: "tenant-2-id"
    scale_up:
      default_strategy: random
```

**Important**: Tenant IDs must be unique in the `tenant_overrides` list.

## Environment Variables

All configuration can be overridden via environment variables with the prefix `ATG_SCALE_`.

### Format

- Use double underscores (`__`) to separate nested keys
- Keys are case-insensitive
- Values are auto-converted to appropriate types (bool, int, float, str)

### Examples

```bash
# Set default tenant ID
export ATG_SCALE_DEFAULT_TENANT_ID="my-tenant-id"

# Set scale-up strategy
export ATG_SCALE_SCALE_UP__DEFAULT_STRATEGY="scenario"

# Set scale factor
export ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR="3.0"

# Set algorithm
export ATG_SCALE_SCALE_DOWN__DEFAULT_ALGORITHM="mhrw"

# Set performance settings
export ATG_SCALE_PERFORMANCE__BATCH_SIZE="1000"
export ATG_SCALE_PERFORMANCE__MEMORY_LIMIT_MB="4096"
export ATG_SCALE_PERFORMANCE__MAX_WORKERS="8"

# Set validation mode
export ATG_SCALE_VALIDATION__STRICT_MODE="false"

# Set algorithm-specific settings
export ATG_SCALE_SCALE_DOWN__FOREST_FIRE__BURNING_PROBABILITY="0.3"
export ATG_SCALE_SCALE_DOWN__MHRW__ALPHA="1.5"
```

### Boolean Values

Environment variables accept multiple formats for booleans:

- **True**: `true`, `yes`, `1`
- **False**: `false`, `no`, `0`

## CLI Override

CLI arguments have the highest priority and override all other sources.

### Example

```bash
# Override scale factor via CLI
uv run atg scale-up \
  --tenant-id my-tenant \
  --scale-factor 3.0 \
  --strategy template

# Override algorithm via CLI
uv run atg scale-down \
  --tenant-id my-tenant \
  --target-size 0.2 \
  --algorithm mhrw
```

## Validation

### Schema Validation

All configuration is validated against Pydantic models with:

- **Type checking**: Ensures correct data types
- **Range validation**: Numeric values within valid ranges
- **Enum validation**: String values from allowed sets
- **Required fields**: Ensures mandatory fields are present

### Validation Errors

Clear error messages indicate:

1. **Field name** causing the error
2. **Expected type/range**
3. **Actual value provided**
4. **Location** in configuration (file, env, CLI)

### Example Error

```
Configuration validation failed: 2 validation errors for ScaleConfig
scale_up.default_scale_factor
  Input should be greater than 0 [type=greater_than, input_value=-1.0]
scale_down.default_target_size
  Input should be less than or equal to 1.0 [type=less_than_equal, input_value=1.5]
```

### Strict Mode

When `validation.strict_mode = true`:

- Warnings are treated as errors
- Unknown fields in YAML are rejected (via `extra = "forbid"`)
- Operations fail early on invalid configuration

When `strict_mode = false`:

- Warnings are logged but don't fail operations
- More permissive validation

## Examples

### Minimal Configuration

```yaml
scale_up:
  default_scale_factor: 2.0

scale_down:
  default_target_size: 0.1
```

### Production Configuration

```yaml
default_tenant_id: "prod-tenant-id"

scale_up:
  default_strategy: template
  default_scale_factor: 1.5

  template:
    preserve_proportions: true
    variation_percentage: 0.05  # Low variation

scale_down:
  default_algorithm: forest-fire
  default_target_size: 0.2  # Conservative reduction

  forest_fire:
    burning_probability: 0.3
    seed: 12345

performance:
  batch_size: 1000
  memory_limit_mb: 4096
  timeout_seconds: 600
  max_workers: 8

validation:
  pre_operation: true
  post_operation: true
  strict_mode: true
```

### Development Configuration

```yaml
default_tenant_id: "dev-tenant-id"

scale_up:
  default_strategy: random
  default_scale_factor: 5.0

  random:
    default_target_count: 5000
    seed: 42

scale_down:
  default_algorithm: random-node
  default_target_size: 0.05  # Aggressive reduction

performance:
  batch_size: 2000
  memory_limit_mb: 8192
  timeout_seconds: 1200
  max_workers: 16

validation:
  strict_mode: false  # Permissive for dev
```

For more examples, see:
- `docs/examples/scale-config-minimal.yaml`
- `docs/examples/scale-config-hub-spoke.yaml`
- `docs/examples/scale-config-multi-tenant.yaml`

## Best Practices

### 1. Start Minimal

Begin with minimal configuration and add settings as needed:

```yaml
scale_up:
  default_scale_factor: 2.0
```

### 2. Use Tenant Overrides

For multi-tenant deployments, define global defaults and override per tenant:

```yaml
# Global defaults
scale_up:
  default_scale_factor: 2.0

# Tenant-specific
tenant_overrides:
  - tenant_id: "special-tenant"
    scale_up:
      default_scale_factor: 5.0
```

### 3. Version Control

- Check configuration files into version control
- Use different configs for different environments (dev/staging/prod)
- Document why specific values are chosen (via YAML comments)

### 4. Validation

- Always run with `validation.strict_mode: true` in production
- Test configuration changes in non-prod first
- Use `--dry-run` flag to validate without executing

### 5. Performance Tuning

- Start with default `batch_size` (500)
- Increase `max_workers` for parallel operations on multi-core machines
- Adjust `memory_limit_mb` based on graph size
- Increase `timeout_seconds` for very large graphs

### 6. Reproducibility

- Always set `seed` values for reproducible operations
- Document seed values used for production operations
- Use same configuration for repeated operations

## Troubleshooting

### Configuration Not Loading

1. Check file path: `ls -la ~/.config/azure-tenant-grapher/scale-config.yaml`
2. Check YAML syntax: Use a YAML linter
3. Check environment variables: `env | grep ATG_SCALE`
4. Enable debug mode: `--debug` flag

### Validation Errors

1. Read error message carefully (field, type, value)
2. Check field type (string, int, float, bool)
3. Check numeric ranges (0.0-1.0 for fractions, > 0 for counts)
4. Check enum values (strategy names, algorithm names)

### Unexpected Values

1. Check priority order (CLI > Env > File > Defaults)
2. Verify environment variables aren't overriding
3. Check for tenant-specific overrides
4. Use `--debug` to see effective configuration

### Performance Issues

1. Reduce `batch_size` if memory is constrained
2. Increase `timeout_seconds` for large graphs
3. Reduce `max_workers` if CPU is saturated
4. Check `memory_limit_mb` against available RAM

## API Usage

### Python API

```python
from pathlib import Path
from src.config import load_config, ConfigError

try:
    # Load from default location
    config = load_config()

    # Load from specific file
    config = load_config(config_path=Path("/path/to/config.yaml"))

    # Load with CLI overrides
    config = load_config(
        cli_args={
            "scale_up": {
                "default_scale_factor": 3.0
            }
        }
    )

    # Get tenant-specific config
    tenant_config = config.get_tenant_config("my-tenant-id")

    # Access settings
    print(f"Scale factor: {config.scale_up.default_scale_factor}")
    print(f"Algorithm: {config.scale_down.default_algorithm}")

except ConfigError as e:
    print(f"Configuration error: {e}")
```

### Create Default Config

```python
from src.config import create_default_config, ConfigError

try:
    # Create default config
    path = create_default_config()
    print(f"Created config at: {path}")

    # Force overwrite
    path = create_default_config(force=True)

except ConfigError as e:
    print(f"Error: {e}")
```

## Visualization Configuration

### Synthetic Node Visualization

Synthetic nodes created during scale operations are automatically detected and styled in the graph visualizer. No configuration is required, but you can customize the appearance:

**Default Colors:**
- Primary: Orange (`#FFA500`)
- Border: Gold (`#FFD700`)
- Style: Dashed border with 'S' indicator

**Show/Hide Synthetic Nodes:**
- Use the toggle in the graph visualization UI
- Or filter in the 3D HTML visualization

For detailed information on visualization features, see [Synthetic Node Visualization Guide](SYNTHETIC_NODE_VISUALIZATION.md).

## See Also

- [Scale Operations Specification](SCALE_OPERATIONS_SPEC.md)
- [Scale-Up Command Reference](SCALE_UP_REFERENCE.md)
- [Scale-Down Command Reference](SCALE_DOWN_REFERENCE.md)
- [Synthetic Node Visualization](SYNTHETIC_NODE_VISUALIZATION.md)
- [Example Configurations](examples/)
