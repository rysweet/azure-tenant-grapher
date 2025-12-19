# Installation Guide

## Prerequisites

- Python **3.8+**
- [uv](https://docs.astral.sh/uv/) (recommended for dependency management)
- Docker & Docker Compose (for Neo4j)
- Azure CLI & Bicep CLI (for authentication and IaC deployment)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/rysweet/pr600.git
cd pr600
```

### 2. Install Dependencies

```bash
# Using uv (recommended)
uv sync
source .venv/bin/activate

# Or using pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set required variables:
# - AZURE_TENANT_ID
# - AZURE_CLIENT_ID
# - AZURE_CLIENT_SECRET
# - NEO4J_PASSWORD
# - NEO4J_PORT
```

### 4. Authenticate with Azure

```bash
az login --tenant <your-tenant-id>
```

### 5. Start Neo4j

```bash
# Neo4j will start automatically when you run atg commands
# Or start manually with Docker:
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/<your-password> \
  neo4j:latest
```

## Verify Installation

```bash
# Check that atg is installed
atg --version

# Run the doctor command to verify dependencies
atg doctor
```

## Next Steps

- [Quick Start Tutorial](quick-start.md) - Your first scan in 15 minutes
- [First Autonomous Deployment](AGENT_DEPLOYMENT_TUTORIAL.md) - Deploy with AI-powered agent

## Troubleshooting

### Command Not Found

If `atg` command is not found:

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Or use full path
python -m src.cli
```

### Docker Issues

If Neo4j fails to start:

```bash
# Check Docker is running
docker ps

# Check Neo4j logs
docker logs neo4j

# Restart Neo4j
docker restart neo4j
```

### Azure Authentication

If Azure authentication fails:

```bash
# Clear cached credentials
az account clear

# Login again
az login --tenant <your-tenant-id>

# Verify access
az account show
```

For more help, see [Documentation Index](../INDEX.md) or file an issue on GitHub.
