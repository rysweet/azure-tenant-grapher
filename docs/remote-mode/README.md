# ATG Remote Mode Documentation

Ahoy! Welcome to the Azure Tenant Grapher remote mode documentation. These here scrolls will guide ye through using ATG with a powerful remote service instead of yer local machine.

## What is Remote Mode?

Remote mode lets ye run ATG operations on a dedicated server with 64GB RAM and 8 vCPUs, perfect fer scanning large Azure tenants without overwhelming yer laptop. The CLI on yer machine acts as a client, streaming progress updates in real-time via WebSocket.

## Documentation Index

### Getting Started

📘 **[User Guide](./USER_GUIDE.md)** - Start here!
- What is remote mode and when to use it
- Quick start guide
- Example workflows
- Switching between local and remote mode

### Configuration

⚙️ **[Configuration Guide](./CONFIGURATION.md)** - Set it up right
- `.env` file configuration
- API key management and security
- Environment selection (dev vs integration)
- Connection settings and timeouts

### Deployment

🚢 **[Deployment Guide](./DEPLOYMENT.md)** - Deploy yer own service
- Prerequisites and architecture
- GitHub Actions automated deployment
- Manual deployment with Azure CLI
- Environment setup and verification

### Troubleshooting

🔧 **[Troubleshooting Guide](./TROUBLESHOOTING.md)** - Fix common issues
- Connection problems
- Authentication errors
- Performance issues
- WebSocket troubles
- Error codes and solutions

### API Reference

📖 **[API Reference](./API_REFERENCE.md)** - For developers
- REST API endpoints
- WebSocket protocol
- Request/response formats
- Error codes
- SDK examples (Python, JavaScript)

## Quick Links

**Common Tasks:**
- [First time setup](./USER_GUIDE.md#quick-start)
- [Get an API key](./CONFIGURATION.md#api-key-management)
- [Deploy to Azure](./DEPLOYMENT.md#method-1-github-actions-recommended)
- [Fix connection errors](./TROUBLESHOOTING.md#connection-issues)
- [Use the REST API directly](./API_REFERENCE.md#api-endpoints)

**Configuration Files:**
```bash
# Minimal .env for remote mode
ATG_MODE=remote
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net
ATG_API_KEY=yer-api-key-here
ATG_ENVIRONMENT=dev
```

**Common Commands:**
```bash
# Check connection
atg remote status

# Scan tenant remotely
atg scan --tenant-id <TENANT_ID>

# List operations
atg remote operations

# Generate IaC
atg generate-iac --format terraform --output ./deployment
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Local Machine                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ATG CLI (Client)                                      │ │
│  │  - Sends commands via HTTPS                            │ │
│  │  - Receives progress via WebSocket                     │ │
│  │  - Downloads results                                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS/WSS (TLS encrypted)
                              │ API Key Authentication
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure Container Instance (64GB RAM)             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ATG Remote Service                                    │ │
│  │  - REST API (FastAPI)                                  │ │
│  │  - WebSocket Server                                    │ │
│  │  - Operation Queue                                     │ │
│  │  - Result Storage                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│                              │ Neo4j Protocol                │
│                              ▼                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Neo4j Database (Dedicated)                            │ │
│  │  - Graph storage                                       │ │
│  │  - Cypher queries                                      │ │
│  │  - Relationship indexing                               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Feature Comparison

| Feature | Local Mode | Remote Mode |
|---------|------------|-------------|
| **Resource Requirements** | 8GB+ RAM on yer laptop | 64GB RAM on remote service |
| **Tenant Size** | Small (< 500 resources) | Any size (tested to 10K+) |
| **Performance** | Depends on yer machine | Consistent, high-performance |
| **Network** | Direct Azure API calls | Calls from Azure datacenter |
| **Collaboration** | Individual only | Team shared graphs |
| **Availability** | Must keep laptop running | Service always available |
| **Cost** | Free (yer hardware) | Azure infrastructure costs |
| **Setup** | None | Configuration required |

## Benefits of Remote Mode

**Performance**: 3-5x faster for large tenants with dedicated 64GB RAM

**Reliability**: No laptop sleep/hibernation interrupting long scans

**Collaboration**: Multiple team members access same graph data

**Consistency**: Reproducible results from same environment

**Automation**: Perfect fer CI/CD pipelines and scheduled scans

**Resource Freedom**: Free up yer laptop fer other work while scans run

## When to Use Each Mode

**Use Local Mode When:**
- Learning ATG or exploring features
- Scanning small tenants (< 500 resources)
- Quick one-off analysis
- No remote service available
- Offline work required

**Use Remote Mode When:**
- Scanning large tenants (500+ resources)
- Production deployments
- Team collaboration needed
- CI/CD automation
- Consistent performance required
- Long-running operations (> 30 minutes)

## Getting Help

**Documentation Issues**: Create issue on [GitHub](https://github.com/<ORG>/azure-tenant-grapher/issues)

**Service Problems**: Check [Troubleshooting Guide](./TROUBLESHOOTING.md) first

**Feature Requests**: Open issue with `enhancement` label

**Questions**: Check existing docs and GitHub issues first

## What's Next?

1. **Read the [User Guide](./USER_GUIDE.md)** to understand remote mode
2. **Follow the [Configuration Guide](./CONFIGURATION.md)** to set up yer client
3. **Try a test scan** with a small tenant
4. **Review [Troubleshooting](./TROUBLESHOOTING.md)** if ye hit snags
5. **Explore [API Reference](./API_REFERENCE.md)** fer advanced usage

Fair winds and following seas! ⚓
