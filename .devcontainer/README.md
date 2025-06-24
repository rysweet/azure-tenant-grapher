# Codespaces & Dev Container Setup

This project is configured for GitHub Codespaces with a minimum machine specification and Docker-in-Docker support.

## Minimum Machine Specification

Codespaces for this repository require at least:
- **8 CPUs**
- **8 GB RAM**
- **32 GB storage**

This ensures smooth operation for Python, .NET, and Docker-based workflows.

## Features

- **Python 3.11** and **.NET 8 SDK** pre-installed
- **Docker-in-Docker** enabled (mounts `/var/run/docker.sock`)
- **Post-create setup**: Installs Python and .NET dependencies automatically
- **Ports 7474, 7687** forwarded (for Neo4j or similar services)

## Usage

1. **Create a Codespace** from this repository. Only machines meeting the minimum spec will be available.
2. The dev container will automatically install dependencies for both Python and .NET.
3. Docker CLI and Docker Compose are available inside the Codespace.
4. You can run integration tests or services that require Docker-in-Docker.

## Notes

- If you need to run Docker Compose, use the CLI as usual inside the Codespace terminal.
- If your organization restricts machine types, ensure at least one available type meets the minimum spec.
- For more details, see [Setting a minimum specification for codespace machines](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/configuring-dev-containers/setting-a-minimum-specification-for-codespace-machines).
