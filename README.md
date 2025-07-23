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

## Documentation

For more details, see the source code and tests.
