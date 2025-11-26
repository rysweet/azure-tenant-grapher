# Security Guidelines: Subprocess Execution

This document describes the secure subprocess execution patterns used in Azure Tenant Grapher.

## Overview

All subprocess calls in this codebase follow secure practices to prevent command injection vulnerabilities (CWE-78).

## Rules

### Rule 1: Never Use shell=True

All subprocess calls MUST use `shell=False` (the default). Using `shell=True` creates command injection vulnerabilities.

**Bad (NEVER DO THIS):**
```python
subprocess.run(f"command {user_input}", shell=True)  # Command injection risk!
```

**Good:**
```python
subprocess.run(["command", user_input])  # Safe - no shell interpretation
```

### Rule 2: Use List-Based Commands

Commands MUST be passed as lists, not strings:

**Bad:**
```python
subprocess.run("terraform init")  # Will fail without shell=True anyway
```

**Good:**
```python
subprocess.run(["terraform", "init"])
```

### Rule 3: Expand Paths Before Execution

For paths with tilde (`~`) or environment variables, expand them in Python:

```python
import os

# Expand ~ to home directory
path = os.path.expanduser("~/.local/bin/tool")
subprocess.run([path, "arg1"])

# Expand environment variables
path = os.path.expandvars("$HOME/.config/tool")
subprocess.run([path, "arg1"])
```

### Rule 4: Handle Shell Redirection with Python

Instead of using shell redirection operators, use subprocess parameters:

**Bad:**
```python
subprocess.run("command > output.log 2>&1", shell=True)
```

**Good:**
```python
with open("output.log", "w") as f:
    subprocess.run(["command"], stdout=f, stderr=subprocess.STDOUT)
```

### Rule 5: Use shlex for String Commands (When Unavoidable)

If you receive a command as a string from a trusted source, use `shlex.split()`:

```python
import shlex

cmd_string = "terraform init -upgrade"
subprocess.run(shlex.split(cmd_string))
```

**Note:** This should only be used with trusted input, never user-provided strings.

### Rule 6: Background Processes with Popen

`subprocess.Popen` already runs asynchronously. The shell `&` operator is unnecessary:

**Bad:**
```python
subprocess.Popen("command &", shell=True)
```

**Good:**
```python
process = subprocess.Popen(["command"])
# process runs in background, can be monitored/terminated later
```

## Testing

A security test exists to prevent future `shell=True` usage:

```bash
uv run pytest tests/security/test_no_shell_true.py -v
```

This test scans the entire codebase and fails if any `shell=True` pattern is found in Python files.

## Files Modified (Issue #477)

The following files were updated to follow these guidelines:

1. `scripts/autonomous_tenant_replicator.py` - `send_imessage()` method
2. `scripts/autonomous_replication_loop.py` - `spawn_fix_workstream()` method
3. `src/utils/cli_installer.py` - `install_tool()` function

## References

- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [Python subprocess security](https://docs.python.org/3/library/subprocess.html#security-considerations)
- [Bandit B602: subprocess_popen_with_shell_equals_true](https://bandit.readthedocs.io/en/latest/plugins/b602_subprocess_popen_with_shell_equals_true.html)
