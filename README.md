# Azure Tenant Resource Grapher

A Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships.

## Features

- **Azure Resource Discovery**: Enumerate all resources across all subscriptions in an Azure tenant
- **Neo4j Graph Database**: Build a comprehensive graph of Azure resources and their relationships  
- **Resource Details**: Capture detailed configuration information for each resource
- **Relationship Mapping**: Identify and map dependencies between Azure resources

## Prerequisites

- Python 3.8+
- Docker and Docker Compose (for Neo4j container)
- Azure CLI (for authentication)
- Azure tenant with appropriate permissions

## Quick Start

### 1. Setup Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Configure Azure credentials
az login

# Copy and edit environment file
cp .env.example .env
# Edit .env with your Azure tenant ID
```

### 2. Start Neo4j Container
The application can automatically manage a Neo4j Docker container for you.

**Option A: Automatic container management (recommended)**
```bash
python azure_tenant_grapher.py --tenant-id your-tenant-id-here
```

**Option B: Start container manually**
```bash
# Start Neo4j container only
python azure_tenant_grapher.py --tenant-id dummy --container-only

# Or use Docker Compose directly
docker-compose up -d neo4j
```

**Option C: Use existing Neo4j instance**
```bash
# Skip container management if you have Neo4j running elsewhere
python azure_tenant_grapher.py --tenant-id your-tenant-id-here --no-container
```

### 3. Access Neo4j Browser
Once Neo4j is running, you can access the browser interface at:
- URL: http://localhost:7474
- Username: `neo4j`
- Password: `azure-grapher-2024` (or your custom password)

## Usage

### Command Line Options

```bash
# Basic usage with automatic container management
python azure_tenant_grapher.py --tenant-id <your-tenant-id>

# Start Neo4j container only (useful for setup)
python azure_tenant_grapher.py --tenant-id dummy --container-only

# Use existing Neo4j instance (skip container management)
python azure_tenant_grapher.py --tenant-id <your-tenant-id> --no-container

# Custom Neo4j connection settings
python azure_tenant_grapher.py \
  --tenant-id <your-tenant-id> \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password your-password
```

### VS Code Tasks

Use Ctrl+Shift+P and search for "Tasks: Run Task" to access:
- **Start Neo4j Container**: Starts the Neo4j Docker container
- **Stop Neo4j Container**: Stops the Neo4j Docker container  
- **Install Dependencies**: Installs Python packages

### PowerShell Script (Windows)

```powershell
# Start container and run grapher
.\run-grapher.ps1 -TenantId "your-tenant-id-here"

# Start container only
.\run-grapher.ps1 -TenantId "dummy" -ContainerOnly

# Use existing Neo4j instance
.\run-grapher.ps1 -TenantId "your-tenant-id-here" -NoContainer
```

## Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and customize:

```bash
# Azure Configuration
AZURE_TENANT_ID=your-tenant-id-here

# Neo4j Configuration (matches docker-compose.yml)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=azure-grapher-2024

# Logging Configuration
LOG_LEVEL=INFO
```

### Docker Compose Configuration

The `docker-compose.yml` file configures Neo4j with:
- **Ports**: 7474 (HTTP), 7687 (Bolt)
- **Authentication**: neo4j/azure-grapher-2024
- **Memory**: 2GB heap, 1GB page cache
- **Plugins**: APOC procedures enabled
- **Persistence**: Data persisted in Docker volumes

You can customize the container by editing `docker-compose.yml`.

## Architecture

The application consists of several key components:

1. **Azure Resource Walker**: Discovers and enumerates resources
2. **Graph Builder**: Creates nodes and relationships in Neo4j
3. **Configuration Manager**: Handles settings and credentials
4. **Resource Mappers**: Transform Azure resource data for graph storage

## Troubleshooting

### Docker Issues

**Error: "Docker is not available"**
- Ensure Docker Desktop is installed and running
- Download from: https://www.docker.com/products/docker-desktop
- On Windows, make sure Docker Desktop is started and the Docker daemon is running

**Error: "docker-compose command not found"**
- Docker Compose is included with Docker Desktop
- Alternatively, use `docker compose` (newer syntax) instead of `docker-compose`

### Neo4j Connection Issues

**Error: "Failed to connect to Neo4j"**
- Check if the Neo4j container is running: `docker ps`
- Verify the connection details in your `.env` file
- Try accessing Neo4j Browser at http://localhost:7474

### Azure Authentication Issues

**Error: "Azure authentication failed"**
- Run `az login` to authenticate with Azure CLI
- Ensure you have the correct permissions in the target tenant
- Verify the tenant ID is correct

### Permission Issues

**Error: "Access denied" when discovering resources**
- Ensure your Azure account has Reader permissions on subscriptions
- Some resources may require additional permissions to read configuration details

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

MIT License
