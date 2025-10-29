# Demo Walkthrough Modules

Production-ready modular components for the Azure Tenant Grapher demo orchestration system.

## Architecture

Following the "bricks and studs" philosophy, each module is:
- **Self-contained**: All code, tests, and documentation in one place
- **Single responsibility**: Each module does one thing well
- **Clear contracts**: Well-defined public interfaces
- **Regeneratable**: Can be rebuilt from specification without breaking connections

## Modules

### 🔧 config_manager
**Purpose**: Handle environment-specific configurations and validation

**Public Interface**:
```python
config_manager = ConfigManager("config.yaml")
config = config_manager.load_config()
value = config_manager.get("app.url", default="http://localhost:3000")
config_manager.validate()
```

**Key Features**:
- YAML configuration loading
- Environment variable expansion
- Dot notation access
- Configuration validation
- Type checking

---

### 🏥 health_checker
**Purpose**: Verify service availability and dependencies before running demos

**Public Interface**:
```python
checker = HealthChecker(config)
healthy = await checker.check_all()
summary = checker.get_summary()
failed = checker.get_failed_checks()
```

**Health Checks**:
- Python version compatibility
- Required package dependencies
- Service availability (HTTP endpoints)
- Azure authentication status
- Playwright browser installation
- Available disk space
- File permissions

---

### 🚀 service_manager
**Purpose**: Start, stop, and manage application services

**Public Interface**:
```python
manager = ServiceManager(config)
await manager.start_service("frontend", ["npm", "run", "dev"])
await manager.stop_service("frontend")
status = manager.get_status()
await manager.stop_all()
```

**Features**:
- Process lifecycle management
- Health check monitoring
- Graceful shutdown with timeout
- Service log collection
- Retry logic for startup
- Dependency ordering

---

### 🎬 scenario_runner
**Purpose**: Execute demo scenarios with proper error handling and retry logic

**Public Interface**:
```python
runner = ScenarioRunner(config)
scenario = runner.load_scenario("login.yaml")
result = await runner.run_scenario(scenario, page)
scenarios = runner.get_scenario_list()
```

**Capabilities**:
- YAML scenario loading
- Step-by-step execution
- Retry logic per step
- Screenshot capture
- Assertion validation
- Error recovery
- Optional steps

---

### 📊 error_reporter
**Purpose**: Provide clear, actionable error messages with remediation steps

**Public Interface**:
```python
reporter = ErrorReporter()
report = reporter.report_error(exception, context)
formatted = reporter.format_for_console(report)
reporter.save_error_log("errors.json")
```

**Error Types with Remediation**:
- Connection refused → Start service instructions
- Authentication failed → Azure CLI login steps
- Browser launch failed → Playwright installation
- Timeout → Configuration adjustments
- Element not found → Selector debugging
- Configuration error → File validation
- Permission denied → File permission fixes

## Usage Example

```python
from modules import (
    ConfigManager,
    HealthChecker,
    ServiceManager,
    ScenarioRunner,
    ErrorReporter
)

# Initialize modules
config_manager = ConfigManager("config.yaml")
config = config_manager.load_config()

error_reporter = ErrorReporter()
health_checker = HealthChecker(config)
service_manager = ServiceManager(config)
scenario_runner = ScenarioRunner(config)

# Run health checks
if not await health_checker.check_all():
    print(health_checker.get_summary())
    sys.exit(1)

# Start services
await service_manager.start_all(config["services"]["definitions"])

try:
    # Run scenario
    scenario = scenario_runner.load_scenario("login")
    result = await scenario_runner.run_scenario(scenario, page)

    if not result.success:
        for error in result.errors:
            report = error_reporter.report_error(Exception(error))
            print(error_reporter.format_for_console(report))

finally:
    # Cleanup
    await service_manager.stop_all()
```

## Configuration

Each module accepts configuration through the standard `config.yaml`:

```yaml
# Health check configuration
health:
  timeout: 5
  checks: [python_version, dependencies, services]

# Service configuration
services:
  startup_timeout: 30
  definitions:
    - name: "frontend"
      command: ["npm", "run", "dev"]
      health_check: "http://localhost:3000"

# Scenario configuration
scenarios:
  stop_on_failure: false
  retry_count: 3
  screenshot_on_failure: true

# Error reporting
errors:
  capture_stack_trace: true
  provide_suggestions: true
```

## Error Handling

All modules follow consistent error handling patterns:

1. **Specific exceptions** for module-specific errors (e.g., `ConfigurationError`)
2. **Error context** with relevant details for debugging
3. **Remediation suggestions** for common issues
4. **Graceful degradation** when possible
5. **Clear logging** at appropriate levels

## Testing

Each module includes comprehensive tests:

```bash
# Run all module tests
pytest modules/tests/

# Run specific module tests
pytest modules/tests/test_config_manager.py

# Run with coverage
pytest modules/tests/ --cov=modules --cov-report=html
```

## Module Contracts

### Input/Output Specifications

Each module defines clear contracts:

| Module | Input | Output | Side Effects |
|--------|-------|--------|--------------|
| config_manager | YAML file path | Config dictionary | None |
| health_checker | Config dict | HealthCheck list | Network calls |
| service_manager | Service definitions | Process handles | Spawns processes |
| scenario_runner | Scenario YAML | ScenarioResult | Browser automation |
| error_reporter | Exception, context | ErrorReport | Log files |

### Regeneration Specification

Any module can be regenerated from this specification:
- Public interface remains unchanged
- Internal implementation can be completely rewritten
- Tests validate contract compliance
- No breaking changes to consumers

## Best Practices

1. **Use modules, don't modify them** - Treat as black boxes
2. **Check health before running** - Always run health checks
3. **Handle errors gracefully** - Use error_reporter for all errors
4. **Clean up resources** - Always stop services after use
5. **Log appropriately** - Use module loggers, not print()

## Future Enhancements

Planned improvements maintaining backward compatibility:

- [ ] Parallel scenario execution
- [ ] Service dependency graph
- [ ] Custom health check plugins
- [ ] Error pattern learning
- [ ] Performance profiling
- [ ] Distributed execution
- [ ] Cloud service integration
- [ ] Real-time progress dashboard

## Contributing

When modifying modules:

1. Maintain the public interface
2. Update tests for new functionality
3. Document changes in this README
4. Ensure backward compatibility
5. Follow the single responsibility principle

## License

Part of the Azure Tenant Grapher project.
