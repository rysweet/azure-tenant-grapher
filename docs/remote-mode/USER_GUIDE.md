# ATG Remote Mode User Guide

## What is Remote Mode?

Remote mode allows ye to run Azure Tenant Grapher operations on a powerful remote server instead of yer local machine. The ATG CLI on yer laptop acts as a client, sending commands to a remote ATG service running in Azure Container Instances with dedicated resources.

## When to Use Remote Mode

**Use Remote Mode When:**

- **Large tenant scans**: Scanning tenants with thousands of resources that would overwhelm yer local machine
- **Limited local resources**: Yer laptop lacks sufficient RAM (8GB+) or CPU for intensive graph operations
- **Unreliable connectivity**: Local Azure API calls timeout or fail due to network issues
- **Team collaboration**: Multiple team members need to work with the same graph database
- **CI/CD pipelines**: Automated workflows need consistent, powerful execution environment

**Use Local Mode When:**

- **Small tenants**: Less than 500 resources
- **Quick exploration**: Testing ATG features or learning the tool
- **Offline work**: No internet connectivity to remote service
- **Privacy requirements**: Cannot send tenant data to external service (even within yer own Azure)

## Remote Mode Architecture

```
┌─────────────────┐         HTTPS/WebSocket         ┌──────────────────────┐
│   Your Laptop   │────────────────────────────────>│  Azure Container     │
│   (ATG CLI)     │<────────────────────────────────│  Instance (64GB RAM) │
└─────────────────┘                                  └──────────────────────┘
                                                              │
                                                              │ Neo4j Protocol
                                                              ▼
                                                     ┌──────────────────────┐
                                                     │   Neo4j Database     │
                                                     │   (Dedicated)        │
                                                     └──────────────────────┘
```

## Quick Start

### Step 1: Configure Remote Access

Create or edit `.env` file in yer project directory:

```bash
# Enable remote mode
ATG_MODE=remote

# Remote service endpoint
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net

# Authentication
ATG_API_KEY=yer-api-key-here

# Optional: Environment selection (dev or integration)
ATG_ENVIRONMENT=dev
```

**Getting yer API key**: Contact yer ATG administrator or check the Azure Key Vault where API keys be stored.

### Step 2: Verify Connection

Test yer connection to the remote service:

```bash
atg remote status
```

Ye should see output like:

```
✓ Remote service: https://atg-dev.azurecontainerinstances.net
✓ Authentication: Valid (API key)
✓ Environment: dev
✓ Service health: OK
✓ Neo4j database: Connected
✓ Available memory: 58.2 GB / 64.0 GB
✓ Active operations: 0
```

### Step 3: Run Commands Normally

Once configured, use ATG commands exactly as ye would in local mode. The CLI automatically routes everything to the remote service:

```bash
# Scan tenant (runs on remote service)
atg scan --tenant-id <YOUR_TENANT_ID>

# Generate IaC (runs on remote service)
atg generate-iac --format terraform --output ./my-deployment

# Visualize graph (downloads data for local viewing)
atg visualize
```

## Example Workflows

### Workflow 1: Large Tenant Scan

Scan a large Azure tenant without overwhelming yer laptop:

```bash
# 1. Configure remote mode
export ATG_MODE=remote
export ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net
export ATG_API_KEY=yer-api-key

# 2. Start scan (runs remotely)
atg scan --tenant-id <TENANT_ID>

# Real-time progress appears in yer terminal via WebSocket:
# Scanning subscription 1/5...
# Discovered 250 resources...
# Building graph relationships...
# Scan complete: 1,247 resources, 3,892 relationships

# 3. Generate IaC from remote graph
atg generate-iac --format terraform --output ./deployment
```

### Workflow 2: Team Collaboration

Multiple team members working with the same tenant:

```bash
# Team member 1: Scan tenant (creates shared graph)
export ATG_ENVIRONMENT=dev
atg scan --tenant-id <TENANT_ID>

# Team member 2: Generate IaC from same graph (no re-scan needed)
export ATG_ENVIRONMENT=dev
atg generate-iac --format bicep --output ./bicep-deployment

# Team member 3: Run threat model analysis
export ATG_ENVIRONMENT=dev
atg threat-model --output ./threat-report.md
```

### Workflow 3: CI/CD Integration

Automate ATG in GitHub Actions or Azure Pipelines:

```yaml
# .github/workflows/scan-tenant.yml
name: Scan Azure Tenant

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install ATG
        run: pip install azure-tenant-grapher

      - name: Configure Remote Mode
        env:
          ATG_API_KEY: ${{ secrets.ATG_API_KEY }}
        run: |
          echo "ATG_MODE=remote" >> .env
          echo "ATG_REMOTE_URL=${{ secrets.ATG_REMOTE_URL }}" >> .env
          echo "ATG_API_KEY=$ATG_API_KEY" >> .env
          echo "ATG_ENVIRONMENT=integration" >> .env

      - name: Scan Tenant
        run: atg scan --tenant-id ${{ secrets.AZURE_TENANT_ID }}

      - name: Generate IaC
        run: atg generate-iac --format terraform --output ./iac

      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: terraform-templates
          path: ./iac
```

## Progress Streaming

Remote mode provides real-time progress updates via WebSocket connection:

```bash
atg scan --tenant-id <TENANT_ID>

# Ye'll see live updates:
[12:34:01] Connecting to remote service...
[12:34:02] Starting scan operation (operation_id: op-a1b2c3d4)
[12:34:05] Authenticated with Azure...
[12:34:06] Discovering subscriptions... [████████░░] 80%
[12:34:15] Scanning subscription 1/5: Production
[12:34:18] └── Discovered 125 resources
[12:34:25] Scanning subscription 2/5: Development
[12:34:28] └── Discovered 87 resources
[12:35:10] Building graph relationships...
[12:35:45] Scan complete!
[12:35:45] Summary: 1,247 resources, 3,892 relationships
```

Press `Ctrl+C` to disconnect from progress stream. The operation continues running on the remote service.

## Switching Between Local and Remote

Ye can easily switch between local and remote mode:

```bash
# Use remote mode
export ATG_MODE=remote
atg scan --tenant-id <TENANT_ID>

# Switch to local mode
export ATG_MODE=local
atg scan --tenant-id <TENANT_ID>

# Or use command-line override
atg scan --tenant-id <TENANT_ID> --mode remote
atg scan --tenant-id <TENANT_ID> --mode local
```

## Environment Isolation

ATG remote service uses a **2-environment architecture**:

- **dev**: Development environment for testing and experimentation
- **integration**: Production-ready environment for team collaboration and real workloads

**Important**: In this simplified architecture, integration be the production-ready environment. There be no separate "production" or "live" environment.

Each environment has:
- Separate Neo4j database
- Isolated operation queues
- Independent resource limits

```bash
# Use dev environment
export ATG_ENVIRONMENT=dev
atg scan --tenant-id <TENANT_ID>

# Use integration environment
export ATG_ENVIRONMENT=integration
atg scan --tenant-id <TENANT_ID>
```

## Data Locality and Security

**What stays local:**
- Azure credentials (never sent to remote service)
- Generated IaC templates (downloaded from remote service)
- Visualization data (downloaded for local rendering)

**What goes to remote:**
- Tenant ID and scan parameters
- Azure resource metadata discovered during scan
- Graph query requests

**Authentication:**
- API key authentication for all requests
- TLS encryption for all communications
- API keys stored in Azure Key Vault

**Note**: The remote service uses yer Azure credentials through Azure CLI or environment variables on yer local machine. The service never stores or logs yer credentials.

## Checking Operation Status

Monitor long-running operations:

```bash
# List recent operations
atg remote operations

# Output:
# Operation ID    Type         Status      Started              Duration
# op-a1b2c3d4     scan         completed   2025-12-09 12:34:00  11m 45s
# op-e5f6g7h8     generate-iac running     2025-12-09 12:45:00  2m 15s

# Check specific operation
atg remote operation op-e5f6g7h8

# Reconnect to running operation's progress stream
atg remote attach op-e5f6g7h8
```

## Performance Comparison

**Local Mode (8GB RAM laptop):**
- Small tenant (< 500 resources): 5-10 minutes
- Medium tenant (500-2000 resources): 15-30 minutes, possible out-of-memory
- Large tenant (> 2000 resources): Often fails with OOM errors

**Remote Mode (64GB RAM container):**
- Small tenant (< 500 resources): 3-5 minutes
- Medium tenant (500-2000 resources): 8-15 minutes
- Large tenant (2000-10000 resources): 20-45 minutes
- Extra-large tenant (> 10000 resources): 1-3 hours

## Best Practices

1. **Use remote mode for production**: Consistent performance and reliability
2. **Use local mode for learning**: Quick iteration when exploring features
3. **Set environment explicitly**: Always specify `dev` or `integration`
4. **Store API keys securely**: Use environment variables or secret managers
5. **Monitor operation status**: Check progress with `atg remote operations`
6. **Clean up old operations**: Remove completed operations to free resources

## Troubleshooting

**Connection Issues**: See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

**Authentication Problems**: Verify API key with `atg remote status`

**Slow Performance**: Check service health with `atg remote status` and review [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#performance-issues)

**Environment Confusion**: Use `atg remote status` to confirm which environment ye're connected to

## Next Steps

- [Configuration Guide](./CONFIGURATION.md) - Detailed configuration options
- [API Reference](./API_REFERENCE.md) - Direct API usage
- [Deployment Guide](./DEPLOYMENT.md) - Deploy yer own remote service
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions
