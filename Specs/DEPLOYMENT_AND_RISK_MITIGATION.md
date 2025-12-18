# ATG Client-Server: Deployment Architecture & Risk Mitigation

**Version**: 1.0
**Date**: 2025-12-09

## Table of Contents

1. [Deployment Architecture](#1-deployment-architecture)
2. [Infrastructure as Code](#2-infrastructure-as-code)
3. [CI/CD Pipeline](#3-cicd-pipeline)
4. [Environment Configuration](#4-environment-configuration)
5. [Risk Analysis](#5-risk-analysis)
6. [Disaster Recovery](#6-disaster-recovery)
7. [Operational Runbook](#7-operational-runbook)

---

## 1. Deployment Architecture

### 1.1 Azure Container Instances Setup

**Architecture Components**:

```
┌────────────────────────────────────────────────────────────────┐
│                    Azure Subscription                          │
│                   (DefenderATEVET17)                          │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │         Resource Group: atg-infrastructure               │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────┐     │ │
│  │  │    Container Group: atg-service-dev            │     │ │
│  │  │                                                │     │ │
│  │  │  Containers:                                   │     │ │
│  │  │  • atg-api        (4 CPU, 64GB RAM)          │     │ │
│  │  │  • neo4j          (2 CPU, 32GB RAM)          │     │ │
│  │  │  • redis          (1 CPU, 4GB RAM)           │     │ │
│  │  │                                                │     │ │
│  │  │  Network:                                      │     │ │
│  │  │  • Virtual Network: atg-vnet                  │     │ │
│  │  │  • Subnet: atg-subnet                         │     │ │
│  │  │  • Public IP: atg-service-dev-ip              │     │ │
│  │  └────────────────────────────────────────────────┘     │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────┐     │ │
│  │  │    Storage Account: atgstoragedev              │     │ │
│  │  │  • neo4j-data-dev (File Share, 1TB)          │     │ │
│  │  │  • artifacts-dev (Blob Container)             │     │ │
│  │  └────────────────────────────────────────────────┘     │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────┐     │ │
│  │  │    Key Vault: atg-keyvault-dev                 │     │ │
│  │  │  • API Keys                                    │     │ │
│  │  │  • Neo4j Password                              │     │ │
│  │  │  • Service Principal Secrets                   │     │ │
│  │  └────────────────────────────────────────────────┘     │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────┐     │ │
│  │  │    Managed Identity                            │     │ │
│  │  │  • Permissions: Reader on target tenant        │     │ │
│  │  │  • Key Vault access                            │     │ │
│  │  └────────────────────────────────────────────────┘     │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 Container Specifications

**ATG API Container**:
- **Image**: `ghcr.io/yourorg/atg:latest`
- **CPU**: 4 cores
- **Memory**: 64GB
- **Ports**: 8000 (HTTPS)
- **Health Check**: `/health` endpoint
- **Restart Policy**: Always

**Neo4j Container**:
- **Image**: `neo4j:5.15-community`
- **CPU**: 2 cores
- **Memory**: 32GB
- **Ports**: 7687 (Bolt)
- **Volume Mount**: Azure File Share
- **Restart Policy**: Always

**Redis Container**:
- **Image**: `redis:7-alpine`
- **CPU**: 1 core
- **Memory**: 4GB
- **Ports**: 6379
- **Restart Policy**: Always

### 1.3 Network Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Internet                                │
└───────────────────────────┬────────────────────────────────┘
                            │
                            │ HTTPS (Port 443)
                            │
┌───────────────────────────▼────────────────────────────────┐
│              Application Gateway (Optional)                │
│  • TLS Termination                                         │
│  • WAF Protection                                          │
│  • Rate Limiting                                           │
└───────────────────────────┬────────────────────────────────┘
                            │
                            │ HTTP (Port 8000)
                            │
┌───────────────────────────▼────────────────────────────────┐
│                   Virtual Network                          │
│                  (10.0.0.0/16)                            │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │          Container Subnet (10.0.1.0/24)            │   │
│  │                                                    │   │
│  │  Container Group (Private IPs)                     │   │
│  │  • ATG API:    10.0.1.4                           │   │
│  │  • Neo4j:      10.0.1.5                           │   │
│  │  • Redis:      10.0.1.6                           │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │        Storage Subnet (10.0.2.0/24)                │   │
│  │  • Storage Account (Private Endpoint)              │   │
│  │  • Key Vault (Private Endpoint)                    │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure as Code

### 2.1 Bicep Template Structure

```
infrastructure/
├── main.bicep                  # Main template
├── modules/
│   ├── container-group.bicep   # Container instance
│   ├── storage.bicep           # Storage account
│   ├── keyvault.bicep          # Key vault
│   ├── network.bicep           # VNet and subnets
│   └── identity.bicep          # Managed identity
├── parameters/
│   ├── dev.json                # Dev environment
│   ├── integration.json        # Integration environment
│   └── prod.json               # Production environment
└── scripts/
    ├── deploy.sh               # Deployment script
    └── rollback.sh             # Rollback script
```

### 2.2 Main Bicep Template

```bicep
// infrastructure/main.bicep
param environment string = 'dev'
param location string = resourceGroup().location
param targetTenantId string
param apiKeys array
param neo4jPassword string

var nameSuffix = '${environment}-${uniqueString(resourceGroup().id)}'

// Networking
module network 'modules/network.bicep' = {
  name: 'network-deployment'
  params: {
    location: location
    nameSuffix: nameSuffix
  }
}

// Storage
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    location: location
    nameSuffix: nameSuffix
  }
}

// Key Vault
module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    location: location
    nameSuffix: nameSuffix
    secrets: [
      {
        name: 'neo4j-password'
        value: neo4jPassword
      }
      {
        name: 'api-keys'
        value: join(apiKeys, ',')
      }
    ]
  }
}

// Managed Identity
module identity 'modules/identity.bicep' = {
  name: 'identity-deployment'
  params: {
    location: location
    nameSuffix: nameSuffix
    targetTenantId: targetTenantId
  }
}

// Container Group
module containers 'modules/container-group.bicep' = {
  name: 'containers-deployment'
  params: {
    location: location
    environment: environment
    nameSuffix: nameSuffix
    targetTenantId: targetTenantId
    subnetId: network.outputs.containerSubnetId
    storageAccountName: storage.outputs.storageAccountName
    storageAccountKey: storage.outputs.storageAccountKey
    managedIdentityId: identity.outputs.identityId
    keyvaultName: keyvault.outputs.keyvaultName
  }
}

output containerGroupFqdn string = containers.outputs.fqdn
output containerGroupId string = containers.outputs.id
```

### 2.3 Container Group Module

```bicep
// infrastructure/modules/container-group.bicep
param location string
param environment string
param nameSuffix string
param targetTenantId string
param subnetId string
param storageAccountName string
param storageAccountKey string
param managedIdentityId string
param keyvaultName string

var containerGroupName = 'atg-service-${nameSuffix}'
var imageTag = environment == 'prod' ? 'stable' : 'latest'

resource containerGroup 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: containerGroupName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    osType: 'Linux'
    restartPolicy: 'Always'
    ipAddress: {
      type: 'Public'
      ports: [
        {
          protocol: 'TCP'
          port: 8000
        }
      ]
      dnsNameLabel: containerGroupName
    }
    subnetIds: [
      {
        id: subnetId
      }
    ]
    containers: [
      {
        name: 'atg-api'
        properties: {
          image: 'ghcr.io/yourorg/atg:${imageTag}'
          resources: {
            requests: {
              cpu: 4
              memoryInGB: 64
            }
          }
          ports: [
            {
              protocol: 'TCP'
              port: 8000
            }
          ]
          environmentVariables: [
            {
              name: 'ATG_SERVER_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'ATG_SERVER_PORT'
              value: '8000'
            }
            {
              name: 'ATG_TARGET_TENANT_ID'
              value: targetTenantId
            }
            {
              name: 'ATG_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'REDIS_URL'
              value: 'redis://localhost:6379'
            }
            {
              name: 'NEO4J_URI'
              value: 'bolt://localhost:7687'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyvaultName
            }
          ]
          livenessProbe: {
            httpGet: {
              path: '/health'
              port: 8000
              scheme: 'HTTP'
            }
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3
          }
        }
      }
      {
        name: 'neo4j'
        properties: {
          image: 'neo4j:5.15-community'
          resources: {
            requests: {
              cpu: 2
              memoryInGB: 32
            }
          }
          ports: [
            {
              protocol: 'TCP'
              port: 7687
            }
          ]
          environmentVariables: [
            {
              name: 'NEO4J_AUTH'
              secureValue: 'neo4j/${reference(resourceId('Microsoft.KeyVault/vaults/secrets', keyvaultName, 'neo4j-password')).value}'
            }
            {
              name: 'NEO4J_dbms_memory_heap_max__size'
              value: '16G'
            }
          ]
          volumeMounts: [
            {
              name: 'neo4j-data'
              mountPath: '/data'
            }
          ]
        }
      }
      {
        name: 'redis'
        properties: {
          image: 'redis:7-alpine'
          resources: {
            requests: {
              cpu: 1
              memoryInGB: 4
            }
          }
          ports: [
            {
              protocol: 'TCP'
              port: 6379
            }
          ]
        }
      }
    ]
    volumes: [
      {
        name: 'neo4j-data'
        azureFile: {
          shareName: 'neo4j-data-${environment}'
          storageAccountName: storageAccountName
          storageAccountKey: storageAccountKey
        }
      }
    ]
  }
}

output fqdn string = containerGroup.properties.ipAddress.fqdn
output id string = containerGroup.id
```

---

## 3. CI/CD Pipeline

### 3.1 GitHub Actions Workflow

```yaml
# .github/workflows/deploy-service.yml
name: Deploy ATG Service

on:
  push:
    branches:
      - main        # → dev environment
      - integration # → integration environment
      - prod        # → production environment
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - dev
          - integration
          - prod

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  determine-environment:
    runs-on: ubuntu-latest
    outputs:
      environment: ${{ steps.set-env.outputs.environment }}
      tenant-id: ${{ steps.set-env.outputs.tenant-id }}
    steps:
      - name: Determine environment from branch
        id: set-env
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            ENV="${{ github.event.inputs.environment }}"
          elif [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
            ENV="dev"
          elif [[ "${{ github.ref }}" == "refs/heads/integration" ]]; then
            ENV="integration"
          elif [[ "${{ github.ref }}" == "refs/heads/prod" ]]; then
            ENV="prod"
          else
            echo "Unknown branch: ${{ github.ref }}"
            exit 1
          fi

          echo "environment=$ENV" >> $GITHUB_OUTPUT

          # Set tenant ID based on environment
          case $ENV in
            dev)
              echo "tenant-id=${{ secrets.DEV_TENANT_ID }}" >> $GITHUB_OUTPUT
              ;;
            integration)
              echo "tenant-id=${{ secrets.INT_TENANT_ID }}" >> $GITHUB_OUTPUT
              ;;
            prod)
              echo "tenant-id=${{ secrets.PROD_TENANT_ID }}" >> $GITHUB_OUTPUT
              ;;
          esac

  build-and-push:
    runs-on: ubuntu-latest
    needs: determine-environment
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=${{ needs.determine-environment.outputs.environment }}
            type=sha,prefix=${{ needs.determine-environment.outputs.environment }}-

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-infrastructure:
    runs-on: ubuntu-latest
    needs: [determine-environment, build-and-push]
    environment: ${{ needs.determine-environment.outputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy Infrastructure
        uses: azure/arm-deploy@v1
        with:
          subscriptionId: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          resourceGroupName: atg-infrastructure
          template: infrastructure/main.bicep
          parameters: >
            environment=${{ needs.determine-environment.outputs.environment }}
            targetTenantId=${{ needs.determine-environment.outputs.tenant-id }}
            apiKeys='["${{ secrets.ATG_API_KEY_1 }}","${{ secrets.ATG_API_KEY_2 }}"]'
            neo4jPassword=${{ secrets.NEO4J_PASSWORD }}
          failOnStdErr: true

      - name: Get Deployment Output
        id: deployment
        run: |
          FQDN=$(az deployment group show \
            --resource-group atg-infrastructure \
            --name main \
            --query properties.outputs.containerGroupFqdn.value \
            --output tsv)
          echo "fqdn=$FQDN" >> $GITHUB_OUTPUT

      - name: Wait for service to be healthy
        run: |
          MAX_ATTEMPTS=30
          ATTEMPT=0
          until curl -f https://${{ steps.deployment.outputs.fqdn }}/health || [ $ATTEMPT -eq $MAX_ATTEMPTS ]; do
            ATTEMPT=$((ATTEMPT + 1))
            echo "Waiting for service to be healthy... ($ATTEMPT/$MAX_ATTEMPTS)"
            sleep 10
          done

          if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            echo "Service failed to become healthy"
            exit 1
          fi

  smoke-tests:
    runs-on: ubuntu-latest
    needs: [determine-environment, deploy-infrastructure]
    environment: ${{ needs.determine-environment.outputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install httpx pytest pytest-asyncio

      - name: Run smoke tests
        env:
          SERVICE_URL: https://${{ needs.deploy-infrastructure.outputs.fqdn }}
          API_KEY: ${{ secrets.ATG_API_KEY_1 }}
        run: |
          pytest tests/smoke/ -v

  notify:
    runs-on: ubuntu-latest
    needs: [determine-environment, smoke-tests]
    if: always()
    steps:
      - name: Send notification
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: |
            Deployment to ${{ needs.determine-environment.outputs.environment }} ${{ job.status }}
            Service URL: https://${{ needs.deploy-infrastructure.outputs.fqdn }}
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### 3.2 Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
COPY requirements-server.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-server.txt

# Copy application code
COPY src/ src/
COPY scripts/ scripts/

# Create non-root user
RUN useradd -m -u 1000 atg && chown -R atg:atg /app
USER atg

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 4. Environment Configuration

### 4.1 Environment Variables by Environment

**Development (main branch)**:
```bash
# Service Configuration
ATG_SERVER_HOST=0.0.0.0
ATG_SERVER_PORT=8000
ATG_SERVER_WORKERS=4

# Target Tenant
ATG_TARGET_TENANT_ID=<DefenderATEVET17-tenant-id>
ATG_TARGET_SUBSCRIPTION_ID=<dev-subscription-id>

# Authentication
ATG_USE_MANAGED_IDENTITY=true
ATG_API_KEYS=<loaded-from-keyvault>

# Job Queue
REDIS_URL=redis://localhost:6379
ATG_MAX_CONCURRENT_JOBS=3

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=<loaded-from-keyvault>
NEO4J_PORT=7687

# Monitoring
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

**Integration (integration branch)**:
```bash
# Same as dev but with different tenant/subscription
ATG_TARGET_TENANT_ID=<target-tenant-a-id>
ATG_TARGET_SUBSCRIPTION_ID=<int-subscription-id>
```

**Production (prod branch)**:
```bash
# Same as integration but with production tenant
ATG_TARGET_TENANT_ID=<target-tenant-b-id>
ATG_TARGET_SUBSCRIPTION_ID=<prod-subscription-id>
ATG_SERVER_WORKERS=8
ATG_MAX_CONCURRENT_JOBS=5
LOG_LEVEL=WARNING
```

### 4.2 Secret Management

**GitHub Secrets (per environment)**:
- `AZURE_CREDENTIALS`: Service principal for deployment
- `AZURE_SUBSCRIPTION_ID`: Target subscription
- `DEV_TENANT_ID` / `INT_TENANT_ID` / `PROD_TENANT_ID`: Target tenants
- `ATG_API_KEY_1`, `ATG_API_KEY_2`: API keys for authentication
- `NEO4J_PASSWORD`: Neo4j database password
- `SLACK_WEBHOOK`: Notification webhook

**Azure Key Vault** (runtime secrets):
- `neo4j-password`: Neo4j authentication
- `api-keys`: Comma-separated API keys
- `azure-client-secret`: Service principal secret (if not using managed identity)

---

## 5. Risk Analysis

### 5.1 Risk Matrix

| Risk ID | Risk Description | Impact | Likelihood | Mitigation | Owner |
|---------|-----------------|--------|------------|------------|-------|
| R1 | Breaking existing CLI behavior | **High** | Medium | Extensive testing, opt-in remote mode, feature flags | Dev Team |
| R2 | Service downtime affects all users | **High** | Low | Multi-environment strategy, health checks, auto-restart | DevOps |
| R3 | Azure API rate limiting during scans | Medium | **High** | Job queue with concurrency limits, exponential backoff | Dev Team |
| R4 | Large artifact downloads fail | Medium | Medium | Chunked downloads, resume capability, artifact expiration | Dev Team |
| R5 | Authentication compromise (API key leak) | **High** | Low | Key rotation, separate keys per env, audit logging | Security |
| R6 | Neo4j database corruption | **High** | Low | Daily backups, separate DB per environment, point-in-time recovery | DevOps |
| R7 | Job queue overflow (memory exhaustion) | Medium | Low | Queue depth monitoring, job timeout, max concurrent limit | Dev Team |
| R8 | Container restart loses in-progress jobs | Medium | Medium | Job persistence in Redis, resume capability | Dev Team |
| R9 | Cross-tenant data leakage | **High** | **Very Low** | Separate DBs, job isolation, access controls | Security |
| R10 | Managed identity permission escalation | **High** | **Very Low** | Principle of least privilege, audit trails | Security |

### 5.2 Mitigation Details

#### R1: Breaking Existing CLI Behavior
**Mitigation Strategy**:
- Remote mode is **opt-in** (requires `--remote` flag or env var)
- Comprehensive backward compatibility test suite
- Feature flag to disable remote mode if issues arise
- Gradual rollout (dev → integration → prod)

**Monitoring**:
- Track CLI command success rate (local vs remote)
- Alert on increased error rates

#### R2: Service Downtime
**Mitigation Strategy**:
- Three separate environments (no single point of failure)
- Container restart policy: Always
- Health checks with automatic restart
- Graceful degradation: CLI falls back to local mode

**Monitoring**:
- Uptime monitoring per environment
- Alert on health check failures
- Auto-restart on 3 consecutive failures

#### R3: Azure API Rate Limiting
**Mitigation Strategy**:
- Job queue limits concurrent operations
- Exponential backoff on rate limit errors
- Configurable `max_concurrent_jobs` per environment
- Monitor Azure API usage metrics

**Monitoring**:
- Track Azure API calls per minute
- Alert on 429 (rate limit) responses
- Dashboard for API quota usage

#### R5: Authentication Compromise
**Mitigation Strategy**:
- API keys stored in Azure Key Vault
- Support multiple keys (allows rotation without downtime)
- Separate keys per environment
- Audit logging of all authenticated requests
- Keys never logged or printed

**Response Plan**:
1. Detect: Monitor for unusual API usage patterns
2. Revoke: Remove compromised key from Key Vault
3. Rotate: Generate new key and update clients
4. Investigate: Review audit logs for unauthorized access

#### R6: Neo4j Database Corruption
**Mitigation Strategy**:
- Daily automated backups to Azure Storage
- Separate database per environment (isolation)
- Point-in-time recovery capability
- Database health checks

**Recovery Plan**:
1. Detect: Health check fails or data corruption reported
2. Isolate: Stop container group
3. Restore: Deploy from latest good backup
4. Verify: Run data integrity checks
5. Resume: Start container group

---

## 6. Disaster Recovery

### 6.1 Backup Strategy

**Neo4j Backups**:
```bash
# Daily backup script (runs as cron job in container)
#!/bin/bash
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="/backups/neo4j-${BACKUP_DATE}.dump"

# Create backup
neo4j-admin database dump neo4j --to-path=/backups

# Upload to Azure Storage
az storage blob upload \
  --account-name atgstoragedev \
  --container-name neo4j-backups \
  --file "$BACKUP_PATH" \
  --name "neo4j-${BACKUP_DATE}.dump"

# Keep last 30 days of backups
find /backups -name "neo4j-*.dump" -mtime +30 -delete
```

**Backup Schedule**:
- **Frequency**: Daily at 2 AM UTC
- **Retention**: 30 days
- **Location**: Azure Blob Storage (GRS replication)
- **Encryption**: At-rest encryption enabled

### 6.2 Recovery Procedures

**Scenario 1: Container Failure**
```bash
# Automatic recovery via restart policy
# No manual intervention needed

# If restart fails, redeploy container group:
az deployment group create \
  --resource-group atg-infrastructure \
  --template-file infrastructure/main.bicep \
  --parameters environment=dev
```

**Scenario 2: Database Corruption**
```bash
# 1. Stop container group
az container stop --resource-group atg-infrastructure --name atg-service-dev

# 2. Download latest backup
az storage blob download \
  --account-name atgstoragedev \
  --container-name neo4j-backups \
  --name neo4j-latest.dump \
  --file /tmp/neo4j-restore.dump

# 3. Restore database
neo4j-admin database load neo4j --from-path=/tmp/neo4j-restore.dump --force

# 4. Start container group
az container start --resource-group atg-infrastructure --name atg-service-dev

# 5. Verify health
curl https://atg-service-dev.azurecontainer.io/health
```

**Scenario 3: Complete Infrastructure Loss**
```bash
# Redeploy entire infrastructure from scratch
./infrastructure/scripts/deploy.sh --environment dev --restore-backup

# Script handles:
# 1. Deploy infrastructure
# 2. Download latest backup from storage
# 3. Restore Neo4j database
# 4. Start services
# 5. Run smoke tests
```

### 6.3 Recovery Time Objectives (RTO/RPO)

| Scenario | RTO (Recovery Time) | RPO (Data Loss) |
|----------|---------------------|-----------------|
| Container crash | < 5 minutes | None (job queue persisted in Redis) |
| Database corruption | < 30 minutes | < 24 hours (daily backup) |
| Infrastructure loss | < 2 hours | < 24 hours |
| Region outage | < 4 hours | < 24 hours (restore in different region) |

---

## 7. Operational Runbook

### 7.1 Deployment

**Standard Deployment (Automated)**:
```bash
# Triggered by git push to main/integration/prod branches
# GitHub Actions handles deployment automatically
git push origin main  # Deploys to dev
```

**Manual Deployment**:
```bash
# Use workflow dispatch for manual deployments
gh workflow run deploy-service.yml \
  --ref main \
  --field environment=dev

# Or deploy directly with Azure CLI
az deployment group create \
  --resource-group atg-infrastructure \
  --template-file infrastructure/main.bicep \
  --parameters @infrastructure/parameters/dev.json
```

### 7.2 Rollback

**Automated Rollback**:
```bash
# GitHub Actions includes automatic rollback on smoke test failure
# Reverts to previous container image

# Manual rollback if needed:
./infrastructure/scripts/rollback.sh --environment dev --version previous
```

**Manual Rollback Steps**:
```bash
# 1. Identify previous working version
az container show \
  --resource-group atg-infrastructure \
  --name atg-service-dev \
  --query containers[0].image

# 2. Redeploy with previous image
az deployment group create \
  --resource-group atg-infrastructure \
  --template-file infrastructure/main.bicep \
  --parameters environment=dev imageTag=dev-abc123

# 3. Verify rollback success
curl https://atg-service-dev.azurecontainer.io/health
```

### 7.3 Monitoring & Alerts

**Health Monitoring**:
```bash
# Check service health
curl https://atg-service-dev.azurecontainer.io/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "neo4j_status": "connected",
  "redis_status": "connected",
  "job_queue_depth": 3
}
```

**Metrics Endpoint**:
```bash
# Get service metrics (requires API key)
curl -H "Authorization: Bearer <api-key>" \
  https://atg-service-dev.azurecontainer.io/metrics

# Metrics include:
# - API request rate and latency
# - Job queue depth
# - Job success/failure rate
# - Neo4j query performance
# - Active worker count
```

**Alert Configuration** (Azure Monitor):
- **CPU > 80%** for 5 minutes → Alert DevOps
- **Memory > 90%** for 5 minutes → Alert DevOps
- **Health check fails** 3 times → Auto-restart + Alert
- **Job queue depth > 50** → Alert Dev Team
- **Error rate > 10%** over 10 minutes → Alert Dev Team

### 7.4 Scaling

**Vertical Scaling** (increase container resources):
```bash
# Update Bicep parameters
# In infrastructure/parameters/prod.json:
{
  "containerCpu": 8,
  "containerMemory": 128
}

# Redeploy
az deployment group create \
  --resource-group atg-infrastructure \
  --template-file infrastructure/main.bicep \
  --parameters @infrastructure/parameters/prod.json
```

**Horizontal Scaling** (not currently supported):
- Future enhancement: Multiple container groups with load balancer
- Requires distributed job queue locking
- Shared Neo4j cluster (not community edition)

### 7.5 Troubleshooting

**Problem: Service not responding**
```bash
# 1. Check container status
az container show \
  --resource-group atg-infrastructure \
  --name atg-service-dev \
  --query instanceView.state

# 2. View container logs
az container logs \
  --resource-group atg-infrastructure \
  --name atg-service-dev \
  --container-name atg-api

# 3. Restart if needed
az container restart \
  --resource-group atg-infrastructure \
  --name atg-service-dev
```

**Problem: Jobs stuck in PENDING**
```bash
# 1. Check worker status via logs
az container logs --name atg-service-dev --container-name atg-api | grep "Worker"

# 2. Check Redis connectivity
az container exec \
  --resource-group atg-infrastructure \
  --name atg-service-dev \
  --container-name atg-api \
  --exec-command "redis-cli -h localhost ping"

# 3. Restart containers if Redis is down
az container restart --name atg-service-dev
```

**Problem: High error rate**
```bash
# 1. Check recent errors
az container logs \
  --resource-group atg-infrastructure \
  --name atg-service-dev \
  --container-name atg-api \
  --tail 100 | grep ERROR

# 2. Check Azure API rate limiting
# Look for "429" status codes in logs

# 3. Reduce max_concurrent_jobs if rate limited
# Update environment variable and restart
```

---

## 8. Security Hardening

### 8.1 Container Security

**Best Practices Implemented**:
- Non-root user in containers
- Read-only filesystem where possible
- Minimal base images (Alpine Linux)
- Regular image scanning (Trivy)
- No secrets in container images

### 8.2 Network Security

**Implemented Controls**:
- Virtual Network isolation
- Private endpoints for storage/keyvault
- Network Security Groups (NSGs)
- Optional Application Gateway with WAF

**Future Enhancements**:
- TLS termination at Application Gateway
- Client certificate authentication
- IP allowlist for API access

### 8.3 Access Controls

**Identity & Access Management**:
- Managed Identity for Azure resource access
- Principle of least privilege (Reader role only)
- Separate API keys per environment
- Key Vault for secret storage

**Audit Logging**:
- All authenticated requests logged
- Azure Monitor integration
- Log retention: 90 days
- Alerts on suspicious activity

---

## 9. Success Criteria

### 9.1 Deployment Success

- ✅ All three environments (dev/int/prod) deployed
- ✅ Health checks passing
- ✅ Smoke tests passing
- ✅ Monitoring and alerts configured
- ✅ Backup jobs running

### 9.2 Operational Success

- ✅ 99.5% uptime SLA met
- ✅ < 5 minute RTO for container failures
- ✅ Zero security incidents
- ✅ < 5% error rate
- ✅ User adoption > 50% within 3 months

---

## 10. Rollout Plan

### Week 1-2: Development Environment
- Deploy to dev environment
- Run integration tests
- Fix any deployment issues
- Team testing

### Week 3-4: Integration Environment
- Deploy to integration environment
- Beta testing with select users
- Performance testing under load
- Documentation finalization

### Week 5: Production Environment
- Deploy to production environment
- Gradual rollout (10% → 50% → 100%)
- Monitor metrics closely
- Ready rollback plan

### Week 6: Full Production
- 100% of users on remote mode (opt-in)
- Gather feedback
- Optimize based on usage patterns
- Plan Phase 2 enhancements
