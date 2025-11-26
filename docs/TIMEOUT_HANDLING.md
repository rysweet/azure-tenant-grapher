# Timeout Handling

This document describes the timeout handling strategy for Azure Tenant Grapher to prevent indefinite hangs during external operations.

## Overview

All external operations (subprocess calls, API requests, database queries) have explicit timeout values to ensure the application never hangs indefinitely. Timeouts are centralized in `src/timeout_config.py` and are configurable via environment variables.

## Timeout Categories

### Quick Operations (10-30 seconds)
- Version checks (`docker --version`, `terraform --version`)
- Health checks (MCP server health, database connectivity)
- Simple CLI queries

### Standard Operations (30-60 seconds)
- Azure CLI queries (`az account show`, `az account set`)
- Neo4j queries (standard CRUD operations)
- Docker commands (`docker ps`, `docker compose up`)

### Infrastructure Init (120 seconds / 2 minutes)
- Terraform init (downloads providers and modules)
- Initial database migrations

### Build/Plan Operations (300 seconds / 5 minutes)
- Terraform plan (analyzes state and generates plan)
- npm install (downloads dependencies)
- npm build (compiles application)
- Bicep/ARM validation

### Long Deployment Operations (1800 seconds / 30 minutes)
- Terraform apply (creates/updates resources)
- Bicep deployments
- ARM template deployments

## Environment Variables

All timeout values can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ATG_TIMEOUT_QUICK` | 30s | Quick operations |
| `ATG_TIMEOUT_STANDARD` | 60s | Standard API calls |
| `ATG_TIMEOUT_INIT` | 120s | Infrastructure init |
| `ATG_TIMEOUT_BUILD` | 300s | Build/plan operations |
| `ATG_TIMEOUT_DEPLOY` | 1800s | Long deployments |
| `ATG_TIMEOUT_NEO4J_CONNECTION` | 30s | Neo4j connection |
| `ATG_TIMEOUT_NEO4J_QUERY` | 60s | Neo4j queries |
| `ATG_TIMEOUT_TERRAFORM_VALIDATE` | 60s | Terraform validate |
| `ATG_TIMEOUT_NPM_INSTALL` | 300s | npm install |
| `ATG_TIMEOUT_HTTP_CONNECT` | 10s | HTTP connection |
| `ATG_TIMEOUT_HTTP_READ` | 30s | HTTP read |

## Usage

### In Subprocess Calls

```python
from src.timeout_config import Timeouts, log_timeout_event
import subprocess

try:
    result = subprocess.run(
        ["terraform", "init"],
        cwd=iac_dir,
        capture_output=True,
        text=True,
        timeout=Timeouts.TERRAFORM_INIT,
    )
except subprocess.TimeoutExpired:
    log_timeout_event("terraform_init", Timeouts.TERRAFORM_INIT, ["terraform", "init"])
    raise RuntimeError(f"Terraform init timed out after {Timeouts.TERRAFORM_INIT}s")
```

### In Neo4j Operations

```python
from src.timeout_config import Timeouts
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    uri,
    auth=auth,
    connection_timeout=Timeouts.NEO4J_CONNECTION,
)
```

### In HTTP Requests

```python
from src.timeout_config import Timeouts
import requests

response = requests.get(
    url,
    timeout=(Timeouts.HTTP_CONNECT, Timeouts.HTTP_READ),
)
```

## Exception Handling

When a timeout occurs, the code should:

1. Log the timeout event with context (operation name, timeout value, command)
2. Raise an appropriate exception with helpful error message
3. Clean up any resources (processes, connections) if needed

Example:
```python
from src.timeout_config import Timeouts, TimeoutError as ATGTimeoutError, log_timeout_event

try:
    result = subprocess.run(cmd, timeout=Timeouts.TERRAFORM_APPLY)
except subprocess.TimeoutExpired:
    log_timeout_event("terraform_apply", Timeouts.TERRAFORM_APPLY, cmd)
    raise ATGTimeoutError(
        "Terraform apply timed out",
        operation="terraform_apply",
        timeout_value=Timeouts.TERRAFORM_APPLY,
        command=cmd,
    )
```

## Files Updated

The following files have been updated to include timeout handling:

- `src/deployment/orchestrator.py` - Terraform, Bicep, ARM deployments
- `src/container_manager.py` - Docker and compose commands
- `src/cli_commands.py` - npm install, npm build
- `src/deployment/background_manager.py` - Background process management
- `src/iac/cli_handler.py` - IaC CLI operations
- `src/iac/importers/terraform_importer.py` - Terraform import operations
- `src/migration_runner.py` - Database migrations
- `src/utils/session_manager.py` - Neo4j session management

## Testing Timeouts

To test timeout behavior:

1. Set a very short timeout via environment variable:
   ```bash
   ATG_TIMEOUT_QUICK=1 python -c "from src.timeout_config import Timeouts; print(Timeouts.QUICK)"
   ```

2. Run the operation and verify it times out as expected

3. Verify the error message includes helpful context

## Debugging

If operations are timing out unexpectedly:

1. Check the current timeout values:
   ```python
   from src.timeout_config import Timeouts
   print(f"Terraform apply timeout: {Timeouts.TERRAFORM_APPLY}s")
   ```

2. Increase the timeout via environment variable:
   ```bash
   export ATG_TIMEOUT_DEPLOY=3600  # 1 hour
   ```

3. Check logs for timeout events (search for "timed out")

## Related Issues

- Issue #485: Missing timeout handling in deployment can cause hangs
