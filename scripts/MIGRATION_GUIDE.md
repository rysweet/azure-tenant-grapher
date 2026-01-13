# Scripts Migration Guide

## Overview
All shell scripts have been reorganized from a flat structure into categorized subdirectories for better organization and maintainability.

## Migration Quick Reference

If you have scripts or documentation that reference old script locations, use this guide to update them.

### Deployment Scripts
| Old Path | New Path |
|----------|----------|
| `./auto-complete-deployment.sh` | `./scripts/deployment/auto-complete-deployment.sh` |
| `./auto-monitor-and-complete.sh` | `./scripts/deployment/auto-monitor-and-complete.sh` |
| `./monitor-scan-progress.sh` | `./scripts/deployment/monitor-scan-progress.sh` |
| `./test-deployment-script.sh` | `./scripts/deployment/test-deployment-script.sh` |
| `./scripts/master_orchestrator.sh` | `./scripts/deployment/master_orchestrator.sh` |

### Development Scripts
| Old Path | New Path |
|----------|----------|
| `./continuous_loop.sh` | `./scripts/development/continuous_loop.sh` |
| `./keep_working_loop.sh` | `./scripts/development/keep_working_loop.sh` |
| `./monitor_and_continue.sh` | `./scripts/development/monitor_and_continue.sh` |
| `./test_cli_flags.sh` | `./scripts/development/test_cli_flags.sh` |
| `./scripts/autonomous_loop.sh` | `./scripts/development/autonomous_loop.sh` |
| `./scripts/persistent_monitor.sh` | `./scripts/development/persistent_monitor.sh` |
| `./scripts/run_master_engine.sh` | `./scripts/development/run_master_engine.sh` |
| `./scripts/run_persistent_orchestrator.sh` | `./scripts/development/run_persistent_orchestrator.sh` |

### Setup Scripts
| Old Path | New Path |
|----------|----------|
| `./setup-codespace.sh` | `./scripts/setup/setup-codespace.sh` |
| `./scripts/setup_service_principal.sh` | `./scripts/setup/setup_service_principal.sh` |

### Tools Scripts
| Old Path | New Path |
|----------|----------|
| `./run-grapher.sh` | `./scripts/tools/run-grapher.sh` |
| `./run-grapher.ps1` | `./scripts/tools/run-grapher.ps1` |
| `./start-neo4j.bat` | `./scripts/tools/start-neo4j.bat` |
| `./scripts/check_ci_status.sh` | `./scripts/tools/check_ci_status.sh` |
| `./scripts/cleanup_examples.sh` | `./scripts/tools/cleanup_examples.sh` |
| `./scripts/cleanup_iteration_resources.sh` | `./scripts/tools/cleanup_iteration_resources.sh` |
| `./scripts/scan_technical_debt.sh` | `./scripts/tools/scan_technical_debt.sh` |
| `./scripts/status_check.sh` | `./scripts/tools/status_check.sh` |
| `./scripts/run_tests_with_artifacts.sh` | `./scripts/tools/run_tests_with_artifacts.sh` |

## New Directory Structure

```
scripts/
├── deployment/       # Deployment automation scripts
├── development/      # Development workflow scripts
├── setup/           # Environment setup scripts
├── tools/           # Utility and maintenance tools
└── MIGRATION_GUIDE.md
```

## Usage Examples

### Before
```bash
./auto-complete-deployment.sh
./continuous_loop.sh
./setup-codespace.sh
./run-grapher.sh
```

### After
```bash
./scripts/deployment/auto-complete-deployment.sh
./scripts/development/continuous_loop.sh
./scripts/setup/setup-codespace.sh
./scripts/tools/run-grapher.sh
```

## Finding Scripts

To find a script by name:
```bash
find scripts -name "scriptname.sh"
```

To list all scripts in a category:
```bash
ls scripts/deployment/
ls scripts/development/
ls scripts/setup/
ls scripts/tools/
```

## Notes

- All moves preserve git history (moved with `git mv`)
- Script functionality remains unchanged
- No references in tracked files required updating
- This reorganization improves discoverability and maintainability
