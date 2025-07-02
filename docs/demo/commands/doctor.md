## doctor

The `doctor` command checks for the presence of required CLI tools (terraform, az, bicep) and reports their status. This is useful for verifying your environment before running other commands.

```bash
uv run azure-tenant-grapher doctor
```

**Output:**
```text
Checking for 'terraform' CLI...
✅ terraform is installed.
Checking for 'az' CLI...
✅ az is installed.
Checking for 'bicep' CLI...
✅ bicep is installed.
Doctor check complete.
```

**Troubleshooting:**
- If any required CLI is missing, install it using your system package manager or the official instructions for that tool.
