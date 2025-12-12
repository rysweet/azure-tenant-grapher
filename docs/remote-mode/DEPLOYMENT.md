# ATG Remote Service Deployment Guide

## Overview

This guide covers deploying the ATG remote service to Azure Container Instances. The service provides a REST API and WebSocket server for remote ATG operations.

## Prerequisites

Before deploying the remote service, ensure ye have:

- **Azure Subscription**: With Contributor or Owner access
- **Azure CLI**: Version 2.40.0 or later (`az --version`)
- **Docker**: For local testing (optional)
- **GitHub Repository Access**: For automated deployments
- **Resource Group**: Created in target Azure region

```bash
# Verify prerequisites
az --version
az account show
az account list-locations -o table
```

## Architecture Components

The remote service consists of:

1. **API Service**: FastAPI application handling REST requests
2. **WebSocket Server**: Real-time progress streaming
3. **Neo4j Database**: Graph database (separate container)
4. **Azure Container Instance**: 64GB RAM, 8 vCPUs
5. **Azure Key Vault**: Secure storage for API keys and secrets
6. **Azure Container Registry**: Docker image storage (optional)

## Deployment Methods

### Method 1: GitHub Actions (Recommended)

Automated deployment triggered by git tags.

#### Step 1: Configure GitHub Secrets

Add the following secrets to yer GitHub repository (`Settings` > `Secrets and variables` > `Actions`):

```
AZURE_CREDENTIALS          # Service principal JSON
AZURE_SUBSCRIPTION_ID      # Azure subscription ID
AZURE_TENANT_ID           # Azure tenant ID
ATG_API_KEY               # Generated API key for authentication
NEO4J_PASSWORD            # Neo4j database password
```

#### Step 2: Create Service Principal

```bash
# Create service principal with Contributor access
az ad sp create-for-rbac \
  --name "atg-deployment-sp" \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID> \
  --sdk-auth

# Output (save as AZURE_CREDENTIALS secret):
# {
#   "clientId": "...",
#   "clientSecret": "...",
#   "subscriptionId": "...",
#   "tenantId": "...",
#   "activeDirectoryEndpointUrl": "...",
#   "resourceManagerEndpointUrl": "...",
#   "activeDirectoryGraphResourceId": "...",
#   "sqlManagementEndpointUrl": "...",
#   "galleryEndpointUrl": "...",
#   "managementEndpointUrl": "..."
# }
```

#### Step 3: Deploy with Git Tag

```bash
# Tag for dev environment
git tag -a v1.0.0-dev -m "Deploy to dev environment"
git push origin v1.0.0-dev

# Tag for integration environment
git tag -a v1.0.0 -m "Deploy to integration environment"
git push origin v1.0.0
```

The GitHub Actions workflow automatically:
1. Builds Docker image
2. Pushes to Azure Container Registry
3. Deploys to Azure Container Instances
4. Configures networking and DNS
5. Sets up Neo4j database
6. Validates deployment

#### Step 4: Verify Deployment

```bash
# Check GitHub Actions run
# Navigate to: https://github.com/<ORG>/<REPO>/actions

# Check container status
az container show \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --query "instanceView.state" -o tsv

# Test endpoint
curl https://atg-dev.azurecontainerinstances.net/health
```

### Method 2: Manual Deployment

Deploy manually using Azure CLI and deployment scripts.

#### Step 1: Prepare Environment

```bash
# Clone repository
git clone https://github.com/<ORG>/azure-tenant-grapher.git
cd azure-tenant-grapher

# Set deployment variables
export AZURE_SUBSCRIPTION_ID=<YOUR_SUBSCRIPTION_ID>
export RESOURCE_GROUP=atg-remote-dev
export LOCATION=eastus
export ENVIRONMENT=dev
```

#### Step 2: Create Resource Group

```bash
# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION \
  --tags environment=$ENVIRONMENT project=atg
```

#### Step 3: Deploy Neo4j Database

```bash
# Deploy Neo4j container
az container create \
  --resource-group $RESOURCE_GROUP \
  --name atg-neo4j-$ENVIRONMENT \
  --image neo4j:5.12.0 \
  --cpu 4 \
  --memory 16 \
  --ports 7474 7687 \
  --environment-variables \
    NEO4J_AUTH=neo4j/$NEO4J_PASSWORD \
    NEO4J_server_memory_heap_max__size=12G \
    NEO4J_server_memory_pagecache_size=4G \
  --dns-name-label atg-neo4j-$ENVIRONMENT

# Get Neo4j connection string
export NEO4J_URI=$(az container show \
  --resource-group $RESOURCE_GROUP \
  --name atg-neo4j-$ENVIRONMENT \
  --query "ipAddress.fqdn" -o tsv)

echo "Neo4j URI: bolt://$NEO4J_URI:7687"
```

#### Step 4: Build and Push Docker Image

```bash
# Build ATG service image
docker build -t atg-service:latest -f Dockerfile.remote .

# Tag for Azure Container Registry (if using ACR)
docker tag atg-service:latest <ACR_NAME>.azurecr.io/atg-service:latest

# Push to ACR
az acr login --name <ACR_NAME>
docker push <ACR_NAME>.azurecr.io/atg-service:latest
```

#### Step 5: Deploy ATG Service

```bash
# Generate API key (use environment-specific prefix)
export ATG_API_KEY=atg_dev_$(openssl rand -hex 32)  # For dev environment
# Or: export ATG_API_KEY=atg_integration_$(openssl rand -hex 32)  # For integration environment

# Deploy ATG service container
az container create \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --image <ACR_NAME>.azurecr.io/atg-service:latest \
  --cpu 8 \
  --memory 64 \
  --ports 8000 \
  --environment-variables \
    ATG_ENVIRONMENT=$ENVIRONMENT \
    NEO4J_URI=$NEO4J_URI \
    NEO4J_PASSWORD=$NEO4J_PASSWORD \
    ATG_API_KEY=$ATG_API_KEY \
  --dns-name-label atg-service-$ENVIRONMENT \
  --registry-login-server <ACR_NAME>.azurecr.io \
  --registry-username <ACR_USERNAME> \
  --registry-password <ACR_PASSWORD>

# Get service URL
export ATG_REMOTE_URL=$(az container show \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --query "ipAddress.fqdn" -o tsv)

echo "ATG Service URL: https://$ATG_REMOTE_URL"
```

#### Step 6: Configure DNS and SSL

```bash
# Create DNS record (if using custom domain)
az network dns record-set a add-record \
  --resource-group $RESOURCE_GROUP \
  --zone-name example.com \
  --record-set-name atg-$ENVIRONMENT \
  --ipv4-address $(az container show \
    --resource-group $RESOURCE_GROUP \
    --name atg-service-$ENVIRONMENT \
    --query "ipAddress.ip" -o tsv)

# Configure SSL certificate (Azure Front Door or Application Gateway)
# See: https://docs.microsoft.com/azure/container-instances/container-instances-ssl
```

## Environment Setup

### Dev Environment

```bash
# Resource configuration
RESOURCE_GROUP=atg-remote-dev
LOCATION=eastus
ENVIRONMENT=dev
CONTAINER_CPU=8
CONTAINER_MEMORY=64
NEO4J_CPU=4
NEO4J_MEMORY=16

# Deploy dev environment
./scripts/deploy-remote-service.sh \
  --environment dev \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

### Integration Environment

```bash
# Resource configuration
RESOURCE_GROUP=atg-remote-integration
LOCATION=westus2
ENVIRONMENT=integration
CONTAINER_CPU=8
CONTAINER_MEMORY=64
NEO4J_CPU=8
NEO4J_MEMORY=32

# Deploy integration environment
./scripts/deploy-remote-service.sh \
  --environment integration \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

## Configuration Management

### Azure Key Vault Integration

Store sensitive configuration in Azure Key Vault:

```bash
# Create Key Vault
az keyvault create \
  --name atg-vault-$ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Store secrets
az keyvault secret set \
  --vault-name atg-vault-$ENVIRONMENT \
  --name atg-api-key \
  --value $ATG_API_KEY

az keyvault secret set \
  --vault-name atg-vault-$ENVIRONMENT \
  --name neo4j-password \
  --value $NEO4J_PASSWORD

# Grant container access to Key Vault
az keyvault set-policy \
  --name atg-vault-$ENVIRONMENT \
  --object-id <CONTAINER_IDENTITY_OBJECT_ID> \
  --secret-permissions get list
```

### Environment Variables

Configure service through environment variables:

```bash
# Required
ATG_ENVIRONMENT=dev              # Environment name
NEO4J_URI=bolt://neo4j:7687     # Neo4j connection
NEO4J_PASSWORD=secret            # Neo4j password
ATG_API_KEY=atg_dev_...         # API authentication key (use atg_dev_ or atg_integration_)

# Optional
ATG_LOG_LEVEL=INFO              # Logging level
ATG_MAX_WORKERS=4               # Worker processes
ATG_REQUEST_TIMEOUT=300         # Request timeout (seconds)
ATG_ENABLE_METRICS=true         # Enable Prometheus metrics
ATG_CORS_ORIGINS=*              # CORS allowed origins
```

## Verification Steps

### Step 1: Health Check

```bash
# Check service health
curl https://atg-$ENVIRONMENT.azurecontainerinstances.net/health

# Expected output:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "environment": "dev",
#   "neo4j": "connected",
#   "uptime": 3600
# }
```

### Step 2: API Authentication

```bash
# Test API authentication
curl -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-$ENVIRONMENT.azurecontainerinstances.net/api/v1/status

# Expected output:
# {
#   "authenticated": true,
#   "environment": "dev",
#   "operations": {
#     "active": 0,
#     "queued": 0
#   }
# }
```

### Step 3: WebSocket Connection

```bash
# Test WebSocket connection (requires wscat)
npm install -g wscat

wscat -c wss://atg-$ENVIRONMENT.azurecontainerinstants.net/ws/progress \
  -H "Authorization: Bearer $ATG_API_KEY"

# Type messages or wait for server events
```

### Step 4: Neo4j Connectivity

```bash
# Test Neo4j connection
docker run --rm \
  -e NEO4J_URI=$NEO4J_URI \
  -e NEO4J_PASSWORD=$NEO4J_PASSWORD \
  neo4j:5.12.0 \
  cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  -a $NEO4J_URI \
  "RETURN 'Connected!' as status"
```

### Step 5: End-to-End Test

```bash
# Configure client
export ATG_MODE=remote
export ATG_REMOTE_URL=https://atg-$ENVIRONMENT.azurecontainerinstances.net
export ATG_API_KEY=$ATG_API_KEY
export ATG_ENVIRONMENT=$ENVIRONMENT

# Run test scan
atg scan --tenant-id $TEST_TENANT_ID --dry-run

# Check operation completed
atg remote operations
```

## Monitoring and Logging

### Azure Container Logs

```bash
# View container logs
az container logs \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --follow

# View Neo4j logs
az container logs \
  --resource-group $RESOURCE_GROUP \
  --name atg-neo4j-$ENVIRONMENT \
  --follow
```

### Application Insights (Optional)

```bash
# Create Application Insights
az monitor app-insights component create \
  --app atg-insights-$ENVIRONMENT \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP

# Get instrumentation key
export APPINSIGHTS_KEY=$(az monitor app-insights component show \
  --app atg-insights-$ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --query "instrumentationKey" -o tsv)

# Configure container to use Application Insights
az container create \
  ... \
  --environment-variables \
    APPINSIGHTS_INSTRUMENTATIONKEY=$APPINSIGHTS_KEY
```

### Prometheus Metrics (Optional)

```bash
# Enable Prometheus endpoint
export ATG_ENABLE_METRICS=true

# Access metrics
curl https://atg-$ENVIRONMENT.azurecontainerinstances.net/metrics

# Sample metrics:
# atg_requests_total{method="POST",endpoint="/api/v1/scan"} 42
# atg_request_duration_seconds{method="POST"} 12.5
# atg_active_operations 2
```

## Maintenance and Updates

### Update Service

```bash
# Pull latest code
git pull origin main

# Tag new version
git tag -a v1.0.1-dev -m "Update to v1.0.1"
git push origin v1.0.1-dev

# GitHub Actions automatically deploys
```

### Manual Update

```bash
# Build new image
docker build -t atg-service:v1.0.1 -f Dockerfile.remote .

# Push to registry
docker tag atg-service:v1.0.1 <ACR_NAME>.azurecr.io/atg-service:v1.0.1
docker push <ACR_NAME>.azurecr.io/atg-service:v1.0.1

# Update container
az container create \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --image <ACR_NAME>.azurecr.io/atg-service:v1.0.1 \
  ...
```

### Backup Neo4j Database

```bash
# Create backup
az container exec \
  --resource-group $RESOURCE_GROUP \
  --name atg-neo4j-$ENVIRONMENT \
  --exec-command "neo4j-admin dump --database=neo4j --to=/backups/neo4j-$(date +%Y%m%d).dump"

# Copy backup to Azure Storage
az container exec \
  --resource-group $RESOURCE_GROUP \
  --name atg-neo4j-$ENVIRONMENT \
  --exec-command "az storage blob upload ..."
```

## Troubleshooting Deployment

**Container won't start**:
```bash
# Check container events
az container show \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --query "instanceView.events" -o table

# Check environment variables
az container show \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --query "containers[0].environmentVariables" -o table
```

**Neo4j connection fails**:
```bash
# Verify Neo4j container running
az container show \
  --resource-group $RESOURCE_GROUP \
  --name atg-neo4j-$ENVIRONMENT \
  --query "instanceView.state" -o tsv

# Test Neo4j connectivity
curl http://<NEO4J_FQDN>:7474
```

**API authentication errors**:
```bash
# Verify API key configured
az container show \
  --resource-group $RESOURCE_GROUP \
  --name atg-service-$ENVIRONMENT \
  --query "containers[0].environmentVariables[?name=='ATG_API_KEY']" -o table

# Test with curl
curl -v -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-$ENVIRONMENT.azurecontainerinstances.net/api/v1/status
```

## Next Steps

- [User Guide](./USER_GUIDE.md) - Learn how to use the deployed service
- [Configuration Guide](./CONFIGURATION.md) - Configure client access
- [API Reference](./API_REFERENCE.md) - API documentation
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues
