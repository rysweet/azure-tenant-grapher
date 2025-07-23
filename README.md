# Azure Tenant Grapher

Azure Tenant Grapher is a tool for generating Infrastructure-as-Code (IaC) for Azure Active Directory tenants.

## CLI Usage

The CLI provides commands to generate IaC for your Azure tenant. AAD mode is always set to **manual** by default. The `--aad-mode` flag has been removed; all operations assume manual mode.

Example usage:

```sh
uv run azure-tenant-grapher generate-iac --tenant-id <TENANT_ID>
```

## Features

- Generates Terraform code for Azure AD tenants
- Manual AAD mode is always used (no automatic mode available)
- No CLI flag required for AAD mode

## Testing and Development

- Use `uv` for environment and package management
- Run tests with `uv run pytest`
- Lint and type-check with `ruff` and `pyright`
- All changes must pass pre-commit hooks

### Automated Test Output and Artifacts

All test runs (local and CI) use a unified workflow to capture and report test output:

- **Command:**
  ```bash
  uv run pytest --junitxml=pytest-results.xml --html=pytest-report.html 2>&1 | tee pytest-output.log
  ```
- **Artifacts Generated:**
  - `pytest-output.log` — Full raw test output (stdout/stderr)
  - `pytest-results.xml` — JUnit XML for structured CI reporting
  - `pytest-report.html` — Rich HTML report (viewable in browser)

**In CI:**
These files are uploaded as workflow artifacts and can be downloaded from the GitHub Actions run summary.

**Locally:**
You can run the above command directly, or use the provided helper script (`scripts/run_tests_with_artifacts.sh`) for convenience.

All test output artifacts are excluded from version control via `.gitignore`.
## Documentation

For more details, see the source code and tests.
