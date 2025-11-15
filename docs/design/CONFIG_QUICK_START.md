# Configuration System Quick Start

Quick reference for using the scale operations configuration system.

## Installation

No additional dependencies needed - uses existing packages (pydantic, PyYAML).

## Basic Usage

### 1. Load Default Configuration

```python
from src.config import load_config

# Load with all defaults
config = load_config()

# Access settings
print(f"Scale factor: {config.scale_up.default_scale_factor}")
print(f"Algorithm: {config.scale_down.default_algorithm}")
```

### 2. Load from Custom File

```python
from pathlib import Path
from src.config import load_config

# Load from specific file
config = load_config(config_path=Path("/path/to/config.yaml"))
```

### 3. Override with CLI Arguments

```python
from src.config import load_config

# Load and apply CLI overrides
config = load_config(
    cli_args={
        "scale_up": {
            "default_scale_factor": 3.0
        },
        "scale_down": {
            "default_algorithm": "mhrw"
        }
    }
)
```

### 4. Create Default Config File

```python
from src.config import create_default_config

# Create at default location
path = create_default_config()
print(f"Created config at: {path}")

# Force overwrite existing
path = create_default_config(force=True)
```

### 5. Get Tenant-Specific Config

```python
from src.config import load_config

config = load_config()

# Get config for specific tenant
tenant_config = config.get_tenant_config("my-tenant-id")
```

## Configuration Priority

```
CLI Arguments (highest priority)
  ↓
Environment Variables
  ↓
Configuration File
  ↓
Default Values (lowest priority)
```

## Environment Variables

Set configuration via environment:

```bash
# Scale-up settings
export ATG_SCALE_SCALE_UP__DEFAULT_STRATEGY="template"
export ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR="3.0"

# Scale-down settings
export ATG_SCALE_SCALE_DOWN__DEFAULT_ALGORITHM="forest-fire"
export ATG_SCALE_SCALE_DOWN__DEFAULT_TARGET_SIZE="0.2"

# Performance settings
export ATG_SCALE_PERFORMANCE__BATCH_SIZE="1000"
export ATG_SCALE_PERFORMANCE__MAX_WORKERS="8"
```

## Minimal Config File

Create `~/.config/azure-tenant-grapher/scale-config.yaml`:

```yaml
scale_up:
  default_scale_factor: 2.0

scale_down:
  default_target_size: 0.1
```

## Full CLI Integration Example

```python
import click
from pathlib import Path
from src.config import load_config, ConfigError

@click.command()
@click.option("--tenant-id", required=True)
@click.option("--scale-factor", type=float, help="Scale factor override")
@click.option("--config", type=Path, help="Config file path")
def scale_up(tenant_id: str, scale_factor: float, config: Path):
    """Scale up operation with configuration."""
    try:
        # Build CLI args
        cli_args = {}
        if scale_factor:
            cli_args["scale_up"] = {"default_scale_factor": scale_factor}

        # Load configuration with overrides
        config_obj = load_config(config_path=config, cli_args=cli_args)

        # Get tenant-specific config
        tenant_config = config_obj.get_tenant_config(tenant_id)

        # Use configuration
        strategy = tenant_config.scale_up.default_strategy
        factor = tenant_config.scale_up.default_scale_factor

        print(f"Using strategy: {strategy}")
        print(f"Scale factor: {factor}")

        # ... perform scale operation ...

    except ConfigError as e:
        print(f"Configuration error: {e}")
        raise click.Abort()
```

## Common Patterns

### Pattern 1: Override Algorithm

```python
config = load_config(
    cli_args={
        "scale_down": {
            "default_algorithm": "mhrw",
            "mhrw": {
                "alpha": 1.5,
                "seed": 12345
            }
        }
    }
)
```

### Pattern 2: Performance Tuning

```python
config = load_config(
    cli_args={
        "performance": {
            "batch_size": 2000,
            "memory_limit_mb": 8192,
            "max_workers": 16,
            "timeout_seconds": 1200
        }
    }
)
```

### Pattern 3: Multi-Tenant Setup

```yaml
# config.yaml
scale_up:
  default_scale_factor: 2.0

tenant_overrides:
  - tenant_id: "prod-tenant"
    scale_up:
      default_scale_factor: 1.5

  - tenant_id: "dev-tenant"
    scale_up:
      default_scale_factor: 10.0
```

```python
config = load_config(config_path=Path("config.yaml"))

prod_config = config.get_tenant_config("prod-tenant")
# prod_config.scale_up.default_scale_factor == 1.5

dev_config = config.get_tenant_config("dev-tenant")
# dev_config.scale_up.default_scale_factor == 10.0
```

## Error Handling

```python
from src.config import load_config, ConfigError

try:
    config = load_config()
except ConfigError as e:
    # Handle validation errors, file errors, etc.
    print(f"Configuration error: {e}")
    # Error message includes:
    # - Field name with path
    # - Expected type/range
    # - Actual value provided
```

## Default Values Reference

### Scale-Up
- `default_strategy`: `template`
- `default_scale_factor`: `2.0`
- `batch_size`: `500`
- `template.preserve_proportions`: `true`
- `template.variation_percentage`: `0.1`

### Scale-Down
- `default_algorithm`: `forest-fire`
- `default_target_size`: `0.1`
- `output_format`: `yaml`
- `forest_fire.burning_probability`: `0.4`
- `forest_fire.seed`: `42`

### Performance
- `batch_size`: `500`
- `memory_limit_mb`: `2048`
- `timeout_seconds`: `300`
- `max_workers`: `4`

### Validation
- `pre_operation`: `true`
- `post_operation`: `true`
- `strict_mode`: `true`

## Available Strategies & Algorithms

### Scale-Up Strategies
- `template` - Maintain structure, scale proportionally
- `scenario` - Use predefined scenario templates
- `random` - Generate random resources

### Scale-Down Algorithms
- `forest-fire` - Forest Fire sampling (default)
- `mhrw` - Metropolis-Hastings Random Walk
- `random-node` - Random node sampling
- `random-edge` - Random edge sampling

## Files Created

- **Source Code**:
  - `/src/config/models.py` - Pydantic models
  - `/src/config/loader.py` - Configuration loader
  - `/src/config/__init__.py` - Public API

- **Documentation**:
  - `/docs/SCALE_CONFIG_REFERENCE.md` - Complete reference
  - `/docs/design/CONFIG_SYSTEM_DESIGN.md` - Design document
  - `/docs/design/CONFIG_QUICK_START.md` - This file

- **Examples**:
  - `/docs/examples/scale-config-minimal.yaml`
  - `/docs/examples/scale-config-hub-spoke.yaml`
  - `/docs/examples/scale-config-multi-tenant.yaml`

- **Tests**:
  - `/tests/test_config.py` - Comprehensive unit tests

## Next Steps

1. **Integrate with CLI**: Add `--config` flag to scale commands
2. **Test with Real Data**: Load example configs and verify behavior
3. **Add Validation**: Hook into pre-operation validation
4. **Documentation**: Update main README with config info

## See Also

- [Complete Configuration Reference](../SCALE_CONFIG_REFERENCE.md)
- [Design Document](CONFIG_SYSTEM_DESIGN.md)
- [Example Configurations](../examples/)
