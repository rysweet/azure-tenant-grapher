# Logging Patterns in Azure Tenant Grapher

## Overview

Azure Tenant Grapher uses structured logging via `structlog` for consistent, filterable, and machine-readable log output. All production code uses the structured logger, not direct `print()` statements.

## Core Principles

1. **Structured Logging Only**: Use `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()` instead of `print()`
2. **Respect Log Levels**: The `--debug` CLI flag controls log verbosity
3. **Contextual Information**: Include relevant context as key-value pairs
4. **Security**: Redact sensitive information (passwords, tokens, secrets) before logging

## Logger Setup

Every module that needs logging should initialize a structured logger:

```python
import structlog

from src.logging_config import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)
```

## Usage Patterns

### Debug Information

Replace debug `print()` statements with `logger.debug()`:

```python
# WRONG - Debug print bypasses log level control
if self.debug:
    print(f"[DEBUG][Neo4jEnv] os.environ: {dict(os.environ)}")

# RIGHT - Structured debug logging respects --log-level flag
logger.debug("Neo4j environment at init", environ=safe_env)
```

### Configuration Debug Output

Log configuration values at debug level:

```python
# WRONG
if debug:
    print(f"[DEBUG][Neo4jConfig] uri={uri}, port={port}")

# RIGHT
logger.debug(
    "Neo4j configuration initialized",
    uri=config.neo4j.uri,
    port=os.getenv('NEO4J_PORT'),
    neo4j_uri_env=os.getenv('NEO4J_URI')
)
```

### Sensitive Data Redaction

Always redact sensitive information before logging:

```python
def should_redact(key: str) -> bool:
    """Check if environment variable should be redacted."""
    sensitive_patterns = {"PASSWORD", "SECRET", "KEY", "TOKEN", "AUTH"}
    return any(pattern in key.upper() for pattern in sensitive_patterns)

safe_env = {
    k: "***REDACTED***" if should_redact(k) else v
    for k, v in os.environ.items()
}

logger.debug("Environment variables", environ=safe_env)
```

### Container Status Logging

Log container state changes at debug level:

```python
# WRONG
if self.debug:
    print(f"[DEBUG] Container {container_name} is running")

# RIGHT
logger.debug(
    "Container status checked",
    container_name=container_name,
    status="running"
)
```

## CLI Output vs Logging

**Important Distinction**:

- **Logging** (`logger.*`): Diagnostic information, debugging, error tracking
- **CLI Output** (`console.print` from Rich): User-facing messages, tables, formatted output

**Use logging for**:
- Debugging information
- Error diagnostics
- State transitions
- Configuration details
- Internal processing steps

**Use console.print for**:
- User-visible progress
- Interactive prompts
- Formatted tables and reports
- Success/failure messages shown to users

## Log Levels

- **`logger.debug()`**: Detailed diagnostic information (only shown with `--debug` flag)
- **`logger.info()`**: General informational messages about operations
- **`logger.warning()`**: Non-critical issues that should be noted
- **`logger.error()`**: Errors that need attention but allow continued operation
- **`logger.exception()`**: Errors with full stack traces (use in exception handlers)

## Controlling Log Output

Users control logging verbosity via CLI flags:

```bash
# Default: INFO level
azure-tenant-grapher scan

# Debug level: Shows all logger.debug() calls
azure-tenant-grapher --debug scan

# Custom log level
azure-tenant-grapher --log-level DEBUG scan
```

## Ruff Configuration

The Ruff linter enforces "no print statements" in production code via rule T20:

```toml
[tool.ruff.lint]
select = ["T20"]  # Detects print statements

[tool.ruff.lint.flake8-print]
# Allow print in scripts/ and examples/
extend-exclude = ["scripts/**", "examples/**", "demos/**"]
```

This prevents accidental `print()` statements from bypassing structured logging.

## Migration Checklist

When converting existing `print()` statements to structured logging:

- [ ] Replace `if self.debug: print(...)` with `logger.debug(...)`
- [ ] Replace `print(f"[DEBUG] ...")` with `logger.debug(...)`
- [ ] Convert format strings to key-value pairs for context
- [ ] Redact sensitive information (passwords, tokens, secrets)
- [ ] Remove `if self.debug:` conditionals (logger handles this)
- [ ] Verify logging respects `--debug` CLI flag
- [ ] Update any tests that assert on stdout to use log capturing instead

## Testing Logging

Test that logging respects debug flag:

```python
import structlog
from structlog.testing import LogCapture

def test_logging_respects_debug_flag(caplog):
    """Verify logger.debug() output controlled by log level."""
    # Configure logger for test
    logger = structlog.get_logger(__name__)

    # Debug level - should capture debug messages
    with caplog.at_level(logging.DEBUG):
        logger.debug("test message", key="value")
        assert "test message" in caplog.text

    # Info level - should NOT capture debug messages
    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.debug("debug message")
        assert "debug message" not in caplog.text
```

## Benefits of Structured Logging

1. **Filterable**: Log levels allow filtering by severity
2. **Redirectable**: Logs can be sent to files, syslog, or monitoring systems
3. **Machine-Readable**: JSON-structured logs for log aggregation tools
4. **Consistent**: All diagnostic output follows the same pattern
5. **Testable**: Log output can be captured and verified in tests
6. **Secure**: Sensitive information redacted before logging

## References

- Structured logging configuration: `src/logging_config.py`
- CLI flag handling: `src/cli.py` (`--debug`, `--log-level`)
- Logger usage examples: `src/container_manager.py`, `src/config_manager.py`
- Ruff configuration: `pyproject.toml` or `ruff.toml`
