# ATG Remote Service - Infrastructure

This directory contains infrastructure-as-code for deploying the ATG Remote Service to Azure Container Instances (ACI).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions CI/CD                      │
│  (Tag-based deployment: v*-dev or v*-int)                   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├──► Build Docker Image
                 │    (GitHub Container Registry)
                 │
                 ├──► Deploy with Bicep
                 │    (Azure Container Instances)
                 │
                 └──► Verify Health Check
                      (Health endpoint + API docs)

┌─────────────────────────────────────────────────────────────┐
│              Azure Container Instance (ACI)                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  ATG Service Container                             │    │
│  │  - FastAPI server (port 8000)                      │    │
│  │  - CPU: 4 cores                                    │    │
│  │  - RAM: 64GB                                       │    │
│  │  - Public IP with FQDN                             │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          │ (connects to)                     │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Neo4j Database (Separate Instance)                │    │
│  │  - Bolt protocol (port 7687)                       │    │
│  │  - Per-environment database                        │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Environments

Two deployment environments are supported:

| Environment | Tag Pattern | Neo4j DB | Purpose | Protection |
|-------------|-------------|----------|---------|------------|
| **dev** | `v*-dev` (e.g., `v1.0.0-dev`) | Separate dev DB | Development/testing | None - immediate deploy |
| **integration** | `v*-int` (e.g., `v1.0.0-int`) | Separate int DB | Production-ready | Required reviewer + 5 min wait |

**Note:** NO production environment yet - only dev and integration!

## Files

### Core Infrastructure

- **`aci.bicep`** - Azure Container Instance template
  - Deploys container with 64GB RAM
  - Configures public IP and DNS
  - Sets environment variables from secrets
  - Health checks and restart policies

### GitHub Actions

- **`.github/workflows/deploy.yml`** - Automated deployment pipeline
  - Triggered by git tags (`v*-dev` or `v*-int`)
  - Builds and pushes Docker image to GHCR
  - Deploys to ACI with Bicep
  - Verifies health endpoint

- **`.github/environments/dev.yml`** - Dev environment config
- **`.github/environments/integration.yml`** - Integration environment config

### Local Development

- **`docker-compose.yml`** - Local testing environment
  - ATG service + Neo4j database
  - Volume mounts for development
  - Health checks and dependencies

- **`scripts/deploy.sh`** - Manual deployment script
  - Build, tag, push Docker image
  - Deploy to Azure with validation
  - Health check verification

## Quick Start

### Prerequisites

1. **Azure Resources** (must exist before deployment):
   ```bash
   # Create resource groups
   az group create --name atg-dev --location eastus
   az group create --name atg-int --location eastus
   ```

2. **GitHub Secrets** (configure in repository settings):
   - `AZURE_CREDENTIALS` - Service principal credentials (JSON)
   - `AZURE_SUBSCRIPTION_ID` - Azure subscription ID
   - `NEO4J_URI` - Neo4j connection string (e.g., `bolt://your-neo4j.com:7687`)
   - `NEO4J_PASSWORD` - Neo4j password
   - `API_KEY` - API authentication key
   - `TARGET_TENANT_ID` - Azure tenant ID for scanning

3. **GitHub Environments** (configure protection rules):
   - Create `dev` environment (no restrictions)
   - Create `integration` environment (require 1 reviewer, 5 min wait)

### Deployment Methods

#### Method 1: Automated (Recommended)

Deploy by creating and pushing a git tag:

```bash
# Deploy to dev
git tag v1.0.0-dev
git push origin v1.0.0-dev

# Deploy to integration
git tag v1.0.0-int
git push origin v1.0.0-int
```

GitHub Actions will automatically:
1. Build Docker image
2. Push to GitHub Container Registry
3. Deploy to Azure Container Instances
4. Verify health check
5. Display service URL

#### Method 2: Manual Deployment

Use the deployment script for manual deployments:

```bash
# Set required environment variables
export NEO4J_URI="bolt://your-neo4j.com:7687"
export NEO4J_PASSWORD="your-password"  # pragma: allowlist secret
export API_KEY="your-api-key"  # pragma: allowlist secret
export TARGET_TENANT_ID="your-tenant-id"
export GITHUB_TOKEN="your-github-token"  # pragma: allowlist secret

# Deploy to dev
./scripts/deploy.sh dev v1.0.0-dev

# Deploy to integration
./scripts/deploy.sh integration v1.0.0-int
```

#### Method 3: Local Testing

Test locally with Docker Compose:

```bash
# Set environment variables
export NEO4J_PASSWORD="local-password"  # pragma: allowlist secret
export API_KEY="local-api-key"  # pragma: allowlist secret
export TARGET_TENANT_ID="your-tenant-id"

# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/api/v1/health

# View logs
docker-compose logs -f atg-service

# Stop services
docker-compose down
```

## Deployment Workflow

### 1. Tag-Based Deployment

```bash
# Create tag
git tag v1.2.3-dev

# Push tag (triggers deployment)
git push origin v1.2.3-dev
```

### 2. GitHub Actions Pipeline

```
┌──────────────────────────────────────────────────────────┐
│ Detect Environment (from tag suffix)                     │
│ - v*-dev → dev environment                               │
│ - v*-int → integration environment                       │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ Build & Push Docker Image                                │
│ - Build from docker/Dockerfile                           │
│ - Push to ghcr.io/org/atg-service:tag                    │
│ - Use GitHub Actions cache for speed                     │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ Deploy to Azure Container Instances                      │
│ - Use Bicep template (infrastructure/aci.bicep)         │
│ - Inject secrets from GitHub environment                 │
│ - Deploy to resource group: atg-{environment}            │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│ Verify Deployment                                        │
│ - Wait 30 seconds for startup                            │
│ - Retry health check 5 times (10s intervals)            │
│ - Display service URL and endpoints                      │
└──────────────────────────────────────────────────────────┘
```

### 3. Post-Deployment Verification

After deployment completes, verify the service:

```bash
# Get container FQDN
FQDN=$(az container show \
  --resource-group atg-dev \
  --name atg-dev \
  --query ipAddress.fqdn -o tsv)

# Check health
curl http://${FQDN}:8000/api/v1/health

# View API documentation
open http://${FQDN}:8000/docs

# Test remote scan
curl -X POST http://${FQDN}:8000/api/v1/scan \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "your-tenant-id"}'
```

## Configuration

### Environment Variables

All sensitive configuration is passed via environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j connection string | `bolt://neo4j.example.com:7687` |
| `NEO4J_PASSWORD` | Neo4j authentication password | `SecurePassword123!` |
| `API_KEY` | API authentication key | `your-secret-api-key` |
| `TARGET_TENANT_ID` | Azure tenant ID for scanning | `12345678-1234-...` |
| `ENVIRONMENT` | Environment marker | `dev`, `integration` |

### Resource Sizing

| Resource | Specification | Rationale |
|----------|---------------|-----------|
| CPU | 4 cores | Parallel resource processing |
| RAM | 64GB | Large graph operations |
| Storage | Ephemeral | Output files only |
| Network | Public IP + FQDN | Remote access |

### Health Checks

The service includes comprehensive health checks:

```
Container Health Check (Docker):
- Endpoint: http://localhost:8000/api/v1/health
- Interval: 30s
- Timeout: 10s
- Retries: 3
- Start period: 40s

Deployment Verification (GitHub Actions):
- 5 retry attempts
- 10 second intervals
- Displays service URL on success
```

## Troubleshooting

### Common Issues

**Issue: Tag push doesn't trigger deployment**
```bash
# Verify tag format
git tag -l "v*-dev" "v*-int"

# Must end with -dev or -int
git tag v1.0.0-dev
git push origin v1.0.0-dev
```

**Issue: Deployment fails with "secrets not found"**
```bash
# Verify secrets are configured in GitHub
# Settings → Secrets and variables → Actions → Environments → [dev/integration]

# Required secrets:
# - AZURE_CREDENTIALS
# - AZURE_SUBSCRIPTION_ID
# - NEO4J_URI
# - NEO4J_PASSWORD
# - API_KEY
# - TARGET_TENANT_ID
```

**Issue: Health check fails after deployment**
```bash
# Check container logs
az container logs \
  --resource-group atg-dev \
  --name atg-dev

# Check container status
az container show \
  --resource-group atg-dev \
  --name atg-dev \
  --query instanceView.state
```

**Issue: Cannot connect to Neo4j**
```bash
# Verify Neo4j is accessible from Azure
# Neo4j must allow connections from Azure IPs

# Test connectivity
az container exec \
  --resource-group atg-dev \
  --name atg-dev \
  --exec-command "curl -v bolt://your-neo4j:7687"
```

### Debugging

**View container logs:**
```bash
az container logs --resource-group atg-dev --name atg-dev --follow
```

**Execute commands in container:**
```bash
az container exec \
  --resource-group atg-dev \
  --name atg-dev \
  --exec-command "/bin/bash"
```

**Check resource group deployments:**
```bash
az deployment group list --resource-group atg-dev --output table
```

**View GitHub Actions logs:**
```
Navigate to: Actions → Deploy ATG Remote Service → [specific run]
```

## Security

### Secrets Management

- All secrets stored in GitHub Secrets (never in code)
- Environment-specific secrets (dev vs integration)
- Service principal with least-privilege access
- API key required for all service endpoints

### Network Security

- Public IP required for remote access
- HTTPS recommended (configure with Azure Front Door)
- Neo4j authentication required
- Health check endpoint is unauthenticated (deliberate)

### Container Security

- Non-root user in container
- Minimal attack surface (slim base image)
- Health checks for automatic restart
- Regular base image updates

## Maintenance

### Updating the Service

```bash
# Create new tag
git tag v1.1.0-dev

# Push to trigger deployment
git push origin v1.1.0-dev

# Deployment is rolling - no downtime
```

### Scaling

Currently using single-container deployment. For horizontal scaling:

1. Use Azure Container Apps instead of ACI
2. Add load balancer
3. Configure Neo4j for concurrent access
4. Update health check for distributed system

### Monitoring

```bash
# View container metrics
az monitor metrics list \
  --resource "$(az container show --resource-group atg-dev --name atg-dev --query id -o tsv)" \
  --metric CPUUsage,MemoryUsage

# View recent logs
az container logs \
  --resource-group atg-dev \
  --name atg-dev \
  --tail 100
```

## Cost Estimation

Approximate monthly costs (East US region):

| Resource | Specification | Monthly Cost |
|----------|---------------|--------------|
| ACI (dev) | 4 vCPU, 64GB RAM, always-on | ~$350 |
| ACI (int) | 4 vCPU, 64GB RAM, always-on | ~$350 |
| Egress | 100GB/month | ~$10 |
| **Total** | | **~$710/month** |

**Cost Optimization:**
- Use consumption-based pricing for dev (stop when not in use)
- Consider Azure Container Apps for auto-scaling
- Use spot instances if availability is not critical

## References

- [Azure Container Instances Documentation](https://docs.microsoft.com/azure/container-instances/)
- [Bicep Templates](https://docs.microsoft.com/azure/azure-resource-manager/bicep/)
- [GitHub Actions Environments](https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

## Support

For issues or questions:
1. Check GitHub Actions logs for deployment failures
2. Review container logs in Azure Portal
3. Verify all secrets are configured correctly
4. Ensure Neo4j database is accessible from Azure
