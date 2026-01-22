# Azure Tenant Grapher Devcontainer Configuration

This directory contains the devcontainer configuration for GitHub Codespaces and VS Code Dev Containers, providing a fully configured development environment with all required dependencies pre-installed.

## Minimum Machine Specification

Codespaces for this repository require at least:
- **16 CPUs**
- **32 GB RAM**
- **128 GB storage**

This ensures smooth operation for Python development, Azure resource scanning, Neo4j graph operations, and Docker-based workflows including large-scale integration tests and data processing.

## Dependencies Installed

### Base Image
- **Image**: `mcr.microsoft.com/devcontainers/dotnet:9.0-bookworm`
- **Python**: 3.13 (via devcontainer feature)
- **Operating System**: Debian Bookworm

### Core Development Tools
- **Azure CLI**: Latest version with Bicep CLI
- **Bicep CLI**: Azure-native IaC tool (upgraded via Azure CLI)
- **Docker-in-Docker**: For building and running containers (mounts `/var/run/docker.sock`)
- **Terraform**: Infrastructure-as-Code tool
- **PowerShell**: For scripting and automation
- **GitHub CLI (`gh`)**: For GitHub operations and PR management
- **Git**: Version control

### Python Environment
- **uv**: Fast Python package installer and dependency manager
- **pre-commit**: Git hooks framework for code quality
- **pytest**: Testing framework
- **Python dependencies**: Installed from `requirements.txt` and `requirements-dev.txt` via `uv sync`
- **Virtual environment**: Created at `.venv` and activated automatically

### CLI Utilities
- **jq**: JSON processor for parsing API responses
- **tree**: Directory tree viewer
- **unzip**: Archive extraction
- **less**: File viewer

## Auto-Configuration

The `post-create.sh` script automatically:

1. Creates Python virtual environment (`.venv`)
2. Installs core Python tools (pip, uv, pre-commit, pytest)
3. Syncs all Python dependencies via `uv sync` (with fallback to pip)
4. Installs and configures pre-commit hooks
5. Upgrades Bicep CLI to latest version
6. Installs GitHub CLI if not present
7. Symlinks Bicep binary to `/usr/local/bin/bicep` for global access
8. Adds user to `docker` group for Docker-in-Docker access
9. Verifies all critical dependencies (Docker, Bicep, Azure CLI)
10. Displays version information for all installed tools

## Post-Create Verification

After the devcontainer builds, the following verification checks run automatically:

✅ **Python**: Version 3.13 available
✅ **Azure CLI**: Installed and version displayed
✅ **Bicep CLI**: Installed via Azure CLI and symlinked to PATH
✅ **GitHub CLI**: Installed and version displayed
✅ **Docker**: Docker daemon running and accessible
✅ **Terraform**: Installed and available
✅ **PowerShell**: Installed and available

The script will **exit with error** if Docker or Bicep CLI are not available, ensuring the environment is fully functional before development begins.

## Port Forwarding

The following ports are automatically forwarded for Neo4j access:

- **7474**: Neo4j HTTP browser interface
- **7687**: Neo4j Bolt protocol (graph database connections)

## VS Code Extensions

The following VS Code extensions are automatically installed:

- **ms-python.python**: Python language support with IntelliSense
- **ms-azuretools.vscode-docker**: Docker support for container management
- **ms-azuretools.vscode-bicep**: Bicep language support with validation
- **hashicorp.terraform**: Terraform language support
- **redhat.vscode-yaml**: YAML language support
- **esbenp.prettier-vscode**: Code formatter
- **ms-toolsai.jupyter**: Jupyter notebooks support
- **roocode.roo**: Roo Code AI assistant

## Environment Variables

The devcontainer checks for the following environment variables at startup:

- **AZURE_TENANT_ID**: Your Azure tenant ID (displays warning if not set)

Create a `.env` file in the project root with your configuration (displays warning if missing).

## Development Workflow

1. **First Launch**: Wait for `post-create.sh` to complete (watch terminal output for progress)
2. **Authenticate Azure**: Run `az login --tenant <your-tenant-id>` to authenticate with Azure
3. **Start Neo4j**: Run `docker-compose up -d` to start Neo4j container
4. **Activate venv**: Virtual environment is auto-activated, or run `source .venv/bin/activate`
5. **Start Development**: All dependencies are ready! Run `azure-tenant-grapher --help` to get started

## SSH Key Mounting

Your host machine's `~/.ssh` directory is automatically mounted to `/home/vscode/.ssh` in the container for seamless Git operations with SSH keys.

## Docker-in-Docker

The devcontainer runs in privileged mode with `/var/lib/docker` volume mounted to support building and running Docker containers inside the devcontainer.

## Troubleshooting

### Docker not available
If Docker is not running or accessible:
```bash
sudo service docker start
# Verify Docker is running
docker info
```

### Bicep CLI not found
If Bicep CLI is not in PATH after post-create:
```bash
az bicep upgrade
sudo ln -s $(az bicep version --query path -o tsv) /usr/local/bin/bicep
bicep --version
```

### Pre-commit hooks not installed
If pre-commit hooks are missing or not running:
```bash
pre-commit install
pre-commit run --all-files  # Test hooks
```

### GitHub CLI not authenticated
To authenticate GitHub CLI for PR operations:
```bash
gh auth login
gh auth status  # Verify authentication
```

### Python dependencies not synced
If Python dependencies are missing or outdated:
```bash
source .venv/bin/activate
uv sync
# Or fallback to pip
pip install -r requirements.txt -r requirements-dev.txt
```

## Testing the Devcontainer

After the devcontainer builds, verify all dependencies:

```bash
# Python
python --version

# Azure CLI
az --version

# Bicep CLI
bicep --version

# Docker
docker info

# GitHub CLI
gh --version

# Terraform
terraform --version

# PowerShell
pwsh --version

# uv (Python package manager)
uv --version

# pre-commit
pre-commit --version
```

## File Structure

```
.devcontainer/
├── devcontainer.json    # Devcontainer configuration and features
├── post-create.sh       # Post-create automation script
└── README.md            # This file (comprehensive documentation)
```

## Notes

- If you need to run Docker Compose, use the CLI as usual inside the Codespace terminal
- If your organization restricts machine types, ensure at least one available type meets the minimum spec (16 CPU, 32GB RAM, 128GB storage)
- The `post-create.sh` script is idempotent and can be re-run if needed
- Virtual environment (`.venv`) is created inside the repository for isolation
- Python interpreter path is configured in VS Code settings to use `.venv/bin/python`

## References

- [Dev Containers Documentation](https://containers.dev/)
- [GitHub Codespaces Documentation](https://docs.github.com/en/codespaces)
- [Setting minimum machine spec](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/configuring-dev-containers/setting-a-minimum-specification-for-codespace-machines)
- [Azure Tenant Grapher Documentation](../docs/)
- [Azure CLI Documentation](https://learn.microsoft.com/en-us/cli/azure/)
- [Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
