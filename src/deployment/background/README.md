# Background Deployment Manager

Modular background deployment management system with focused, self-contained components.

## Architecture

This package follows the **Brick & Studs** pattern - each module is a self-contained brick with clear public interfaces (studs).

```
background/
├── __init__.py          # BackgroundDeploymentManager (orchestrator)
├── job_spawner.py       # JobSpawner - process spawning
├── job_tracker.py       # JobTracker - status tracking & listing
├── log_streamer.py      # LogStreamer - log streaming
├── process_manager.py   # ProcessManager - process lifecycle
└── state_manager.py     # StateManager - state persistence
```

## Components

### BackgroundDeploymentManager (Orchestrator)

Main orchestrator that delegates to specialized components. Provides a unified API for all background deployment operations.

**Location**: `__init__.py`
**Lines**: ~336 (thin delegation layer)

**Public API**:
- `spawn_deployment()` - Start background deployment
- `get_status()` - Get job status
- `list_deployments()` - List all jobs
- `stream_logs()` - Stream log output
- `cancel_deployment()` - Cancel running job
- `cleanup_old_jobs()` - Remove old completed jobs
- `get_job_config()` - Get job configuration

### JobSpawner

Handles spawning deployment processes in background with proper detachment and environment setup.

**Location**: `job_spawner.py`
**Lines**: ~327
**Responsibility**: Process creation only

**Public API**:
- `spawn_deployment()` - Create detached subprocess with config/status files

### JobTracker

Tracks job status, checks process health, and provides job listing with filtering.

**Location**: `job_tracker.py`
**Lines**: ~201
**Responsibility**: Status tracking and queries

**Public API**:
- `get_status()` - Get current job status (checks PID, updates state)
- `list_deployments()` - List all jobs with optional filtering
- `is_job_running()` - Check if specific job is running

**Dependencies**: StateManager, ProcessManager

### LogStreamer

Streams log output from job files with follow mode support (like `tail -f`).

**Location**: `log_streamer.py`
**Lines**: ~113
**Responsibility**: Log file reading and streaming

**Public API**:
- `stream_logs()` - Stream log lines with optional follow and tail

### ProcessManager

Cross-platform process lifecycle management (Windows/Unix).

**Location**: `process_manager.py`
**Lines**: ~132
**Responsibility**: Process checking and termination

**Public API**:
- `check_pid()` - Check if process is running
- `terminate_process()` - Terminate process by PID

### StateManager

Handles all state persistence - reading/writing job state, config, and cleanup.

**Location**: `state_manager.py`
**Lines**: ~213
**Responsibility**: File I/O and state management

**Public API**:
- `read_status()` / `write_status()` - Job status persistence
- `get_job_config()` - Read job configuration
- `get_log_file()` / `get_pid_file()` - Get file paths
- `list_job_dirs()` - List all job directories
- `cleanup_old_jobs()` - Remove old completed jobs

## Usage Example

```python
from pathlib import Path
from src.deployment.background import BackgroundDeploymentManager

# Initialize manager
manager = BackgroundDeploymentManager()

# Spawn deployment
job = manager.spawn_deployment(
    job_id="deploy-123",
    iac_dir=Path("./terraform"),
    target_tenant_id="tenant-id",
    resource_group="my-rg",
    location="eastus"
)
print(f"Started job {job['job_id']} with PID {job['pid']}")

# Check status
status = manager.get_status("deploy-123")
print(f"Job status: {status['status']}")

# Stream logs (follow mode)
for line in manager.stream_logs("deploy-123", follow=True):
    print(line)

# Cancel if needed
manager.cancel_deployment("deploy-123")

# List all running jobs
running_jobs = manager.list_deployments(status_filter="running")
for job in running_jobs:
    print(f"{job['job_id']}: {job['status']}")
```

## Design Principles

### Modular Design (Bricks & Studs)
- Each component has ONE clear responsibility
- Components are self-contained and regeneratable
- Public API defined via `__all__` exports

### Zero-BS Implementation
- No stubs or placeholders
- Every function works or doesn't exist
- No TODOs in production code

### Cross-Platform Support
- Windows and Unix/Linux process management
- Platform-specific implementations isolated in ProcessManager

## Testing

Comprehensive test suite verifies zero breaking changes from original implementation:

```bash
uv run pytest tests/deployment/test_background_manager.py -v
```

**Coverage**: 24 tests covering all public APIs and error conditions.

## Migration from Monolithic Version

This modular version maintains **100% API compatibility** with the original `background_manager.py`.

**What changed**:
- Split 650-line monolith into 6 focused modules
- Improved separation of concerns
- Better testability and maintainability
- Same public API surface

**What stayed the same**:
- All method signatures
- All behavior and side effects
- File structure and state management
- Job lifecycle and status tracking

**To migrate**:
```python
# Old import
from src.deployment.background_manager import BackgroundDeploymentManager

# New import (same class name!)
from src.deployment.background import BackgroundDeploymentManager

# All code works identically
manager = BackgroundDeploymentManager()
```

## File Structure

Each job gets its own directory:
```
.deployments/jobs/{job_id}/
├── config.json      # Job configuration
├── status.json      # Current job status
├── output.log       # Deployment output
└── pid.lock         # Process PID
```

## Philosophy Alignment

✅ **Ruthless Simplicity**: Each module < 350 lines, focused responsibility
✅ **Bricks & Studs**: Clear boundaries, standard interfaces
✅ **Zero-BS**: No placeholders, all functions work
✅ **Regeneratable**: Each module can be rebuilt from this spec

## Line Count Summary

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `__init__.py` | 336 | Orchestration & delegation |
| `job_spawner.py` | 327 | Process spawning |
| `job_tracker.py` | 201 | Status tracking |
| `state_manager.py` | 213 | State persistence |
| `process_manager.py` | 132 | Process lifecycle |
| `log_streamer.py` | 113 | Log streaming |
| **Total** | **1322** | *vs 650 original* |

The increase is due to comprehensive docstrings, improved error handling, and modular separation. Each module is still under 350 lines and highly focused.
