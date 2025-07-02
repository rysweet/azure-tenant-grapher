## test

The `test` command runs a quick validation of your Azure Tenant Grapher setup, processing a limited number of resources. This is useful for verifying that your environment is configured correctly before running a full build. The `--limit` flag restricts the number of resources for faster runs.

```bash
uv run azure-tenant-grapher test --limit 1
```

**Output:**
```text
🧪 Running test mode with up to 1 resources...
Traceback (most recent call last):
  ...
RuntimeError: asyncio.run() cannot be called from a running event loop
sys:1: RuntimeWarning: coroutine 'build' was never awaited
```

**Troubleshooting:**
- If you see a RuntimeError about asyncio, ensure you are not running the CLI from within another event loop (such as in a Jupyter notebook or certain IDEs). This command may require code fixes to run end-to-end in some environments.
