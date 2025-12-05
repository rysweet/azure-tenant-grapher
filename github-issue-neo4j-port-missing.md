# GitHub Issue: RuntimeError NEO4J_PORT Environment Variable Missing

## Issue Created by AI Agent

**Agent:** Roo Code  
**Mode:** Code  
**Created:** 2025-10-02T19:24:00Z

## Description

The CLI command `azure-tenant-grapher scan` fails with a RuntimeError because it expects `NEO4J_PORT` to be set in the environment, but the `.env.example` file only provides `NEO4J_URI`.

## Context

User attempted to run `azure-tenant-grapher scan` but encountered a stacktrace due to missing environment variable configuration. The application successfully detects that Docker is not available but then fails when checking for the `NEO4J_PORT` environment variable.

## Steps to Reproduce

1. Run `azure-tenant-grapher scan` without setting `NEO4J_PORT` environment variable
2. Observe the stacktrace

## Expected Behavior

The application should either:
- Include `NEO4J_PORT` in `.env.example` with a default value (e.g., 7687)
- Extract the port from `NEO4J_URI` if `NEO4J_PORT` is not explicitly set
- Provide clearer error messaging about required environment variables

## Actual Behavior

Application crashes with:
```
RuntimeError: NEO4J_PORT must be set in the environment (see .env.example)
```

But `.env.example` does not contain `NEO4J_PORT`.

## Agent Reasoning

The issue stems from a mismatch between what the code expects (`NEO4J_PORT`) and what the documentation/example provides (`NEO4J_URI`). The `ensure_neo4j_running` function in [`src/utils/neo4j_startup.py`](src/utils/neo4j_startup.py:19) checks for `NEO4J_PORT` but the [`.env.example`](.env.example:9) only includes `NEO4J_URI=bolt://localhost:7687`.

## Acceptance Criteria

- [ ] Add `NEO4J_PORT=7687` to `.env.example`
- [ ] OR modify [`src/utils/neo4j_startup.py`](src/utils/neo4j_startup.py:19) to extract port from `NEO4J_URI` when `NEO4J_PORT` is not set
- [ ] Update error message to be more helpful about which environment variables are actually required
- [ ] Ensure `azure-tenant-grapher scan` works with just the variables from `.env.example`

## Additional Information

**Full Stacktrace:**
```
{"event": "Could not connect to Docker daemon: Error while fetching server API version: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))", "timestamp": "2025-10-02T19:22:43.636594Z", "level": "warning"}
{"event": "Setting up Neo4j container...", "timestamp": "2025-10-02T19:22:43.637473Z", "level": "info"}
{"event": "Attempting to start Neo4j container with name: azure-tenant-grapher-neo4j", "timestamp": "2025-10-02T19:22:43.637517Z", "level": "info"}
{"event": "Docker is not available", "timestamp": "2025-10-02T19:22:43.637545Z", "level": "error"}
NoneType: None
Traceback (most recent call last):
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/bin/azure-tenant-grapher", line 10, in <module>
    sys.exit(main())
             ^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/scripts/cli.py", line 1142, in main
    result = cli()  # type: ignore[reportCallIssue]
             ^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/lib/python3.12/site-packages/click/core.py", line 1442, in __call__
    return self.main(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/lib/python3.12/site-packages/click/core.py", line 1363, in main
    rv = self.invoke(ctx)
         ^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/lib/python3.12/site-packages/click/core.py", line 1830, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/lib/python3.12/site-packages/click/core.py", line 1226, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/lib/python3.12/site-packages/click/core.py", line 794, in invoke
    return callback(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/.venv/lib/python3.12/site-packages/click/decorators.py", line 34, in new_func
    return f(get_current_context(), *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/scripts/cli.py", line 151, in wrapper
    result = asyncio.run(f(*args, **kwargs))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.12/3.12.11_1/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/runners.py", line 195, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.12/3.12.11_1/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.12/3.12.11_1/Frameworks/Python.framework/Versions/3.12/lib/python3.12/asyncio/base_events.py", line 691, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/scripts/cli.py", line 504, in scan
    result = await build_command_handler(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/csiska/repos/azure-tenant-grapher/src/cli_commands.py", line 86, in build_command_handler
    ensure_neo4j_running(debug)
  File "/Users/csiska/repos/azure-tenant-grapher/src/utils/neo4j_startup.py", line 21, in ensure_neo4j_running
    raise RuntimeError(
RuntimeError: NEO4J_PORT must be set in the environment (see .env.example)
```

## Related Files/Components

- [`src/utils/neo4j_startup.py`](src/utils/neo4j_startup.py) - Contains the failing check
- [`.env.example`](.env.example) - Missing the required NEO4J_PORT variable
- [`scripts/cli.py`](scripts/cli.py) - CLI entry point
- [`src/cli_commands.py`](src/cli_commands.py) - Command handler that calls ensure_neo4j_running

## Labels
- ai-created

---

**To create this issue on GitHub:**
1. Install GitHub CLI: `brew install gh`
2. Authenticate: `gh auth login`
3. Create issue: `gh issue create --title "[AI] RuntimeError: NEO4J_PORT must be set in environment but .env.example doesn't include it" --body-file github-issue-neo4j-port-missing.md --label "ai-created"`