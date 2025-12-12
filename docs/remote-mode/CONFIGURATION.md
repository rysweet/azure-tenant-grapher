# ATG Remote Mode Configuration Guide

## Configuration Methods

ATG remote mode can be configured through multiple methods, with the following priority order (highest to lowest):

1. **Command-line flags** (highest priority)
2. **Environment variables**
3. **`.env` file** in current directory
4. **`~/.atg/config` file** (user-level defaults)
5. **System defaults** (lowest priority)

## .env File Configuration

The recommended way to configure remote mode be through a `.env` file in yer project directory:

```bash
# Remote Mode Configuration

# Enable remote mode (values: local, remote)
ATG_MODE=remote

# Remote service endpoint
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net

# API authentication
ATG_API_KEY=atg_dev_abc123def456ghi789jkl012mno345pqr678

# Environment selection (values: dev, integration)
ATG_ENVIRONMENT=dev

# Connection settings
ATG_TIMEOUT=300                    # API request timeout in seconds
ATG_WS_RECONNECT_ATTEMPTS=5        # WebSocket reconnection attempts
ATG_WS_RECONNECT_DELAY=2           # Seconds between reconnection attempts

# Optional: Custom Neo4j connection (if using external database)
# ATG_NEO4J_URI=bolt://custom-neo4j.example.com:7687
# ATG_NEO4J_USER=neo4j
# ATG_NEO4J_PASSWORD=yer-password

# Optional: Progress streaming settings
ATG_PROGRESS_ENABLED=true          # Enable real-time progress updates
ATG_PROGRESS_VERBOSE=false         # Show detailed progress messages

# Optional: Retry and resilience
ATG_MAX_RETRIES=3                  # Number of request retries on failure
ATG_RETRY_BACKOFF=2                # Exponential backoff multiplier
```

## Environment Variables

Set configuration through environment variables:

```bash
# Required for remote mode
export ATG_MODE=remote
export ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net
export ATG_API_KEY=atg_dev_abc123def456ghi789jkl012mno345pqr678
export ATG_ENVIRONMENT=dev

# Optional connection settings
export ATG_TIMEOUT=300
export ATG_WS_RECONNECT_ATTEMPTS=5
```

Environment variables override `.env` file settings but be overridden by command-line flags.

## Command-Line Flags

Override configuration for specific commands:

```bash
# Override mode
atg scan --mode remote --tenant-id <TENANT_ID>

# Override endpoint
atg scan --remote-url https://atg-integration.example.com --tenant-id <TENANT_ID>

# Override environment
atg scan --environment integration --tenant-id <TENANT_ID>

# Multiple overrides
atg generate-iac \
  --mode remote \
  --environment dev \
  --api-key $MY_API_KEY \
  --format terraform
```

## API Key Management

### Obtaining API Keys

API keys be generated and managed by yer ATG administrator. Request access through:

1. **Azure Key Vault**: Keys stored in dedicated Key Vault
2. **ATG Admin Portal**: Web interface for key management (if deployed)
3. **Azure CLI**: Generate keys via deployment scripts

### API Key Formats

ATG uses prefixed API keys to identify the environment:

```
atg_dev_<64-character-hex-string>         # Dev environment keys
atg_integration_<64-character-hex-string> # Integration environment keys
```

**Note**: The integration environment be production-ready - there be no separate production environment in the simplified architecture.

### Storing API Keys Securely

**Recommended: Environment Variable**

```bash
# Add to ~/.bashrc or ~/.zshrc
export ATG_API_KEY=atg_dev_abc123...
```

**Recommended: Azure Key Vault**

```bash
# Retrieve API key from Key Vault
export ATG_API_KEY=$(az keyvault secret show \
  --vault-name my-keyvault \
  --name atg-api-key \
  --query value -o tsv)

atg scan --tenant-id <TENANT_ID>
```

**Recommended: GitHub Secrets (CI/CD)**

```yaml
# .github/workflows/scan.yml
env:
  ATG_API_KEY: ${{ secrets.ATG_API_KEY }}
```

**Not Recommended: Plain text .env file**

If ye must store keys in `.env`, ensure:
- `.env` be in `.gitignore`
- File permissions be `600` (read/write for owner only)
- Directory not shared or exposed

```bash
chmod 600 .env
```

### Key Rotation

API keys should be rotated regularly:

```bash
# Test new key before replacing old one
ATG_API_KEY=new-key atg remote status

# If successful, update configuration
export ATG_API_KEY=new-key
```

## Environment Selection

ATG remote service supports multiple isolated environments:

### Dev Environment

**Purpose**: Development, testing, experimentation

**Configuration**:
```bash
ATG_ENVIRONMENT=dev
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net
```

**Use for**:
- Feature testing
- Learning ATG
- Temporary scans
- Personal development

**Retention**: Data may be cleared periodically (weekly)

### Integration Environment (Production-Ready)

**Purpose**: Team collaboration, production workloads - this be the production-ready environment

**Configuration**:
```bash
ATG_ENVIRONMENT=integration
ATG_REMOTE_URL=https://atg-integration.azurecontainerinstances.net
```

**Use for**:
- Production tenant scans
- Team shared graphs
- CI/CD pipelines
- Long-term storage

**Retention**: Data retained per policy (90+ days)

**Note**: In the simplified 2-environment architecture, integration be the production-ready environment. There be no separate "production" or "live" environment.

### Custom Environments (Optional)

**Note**: The default 2-environment model (dev + integration) be sufficient fer most use cases. Only deploy custom environments if ye have specific requirements beyond the standard setup.

Organizations can deploy additional custom environments:

```bash
ATG_ENVIRONMENT=custom
ATG_REMOTE_URL=https://atg-custom.example.com
ATG_API_KEY=atg_custom_key123...
```

## Connection Settings

### Timeout Configuration

Control request and operation timeouts:

```bash
# API request timeout (seconds)
ATG_TIMEOUT=300                    # Default: 5 minutes

# Long operation timeout (seconds)
ATG_OPERATION_TIMEOUT=3600         # Default: 1 hour

# WebSocket message timeout (seconds)
ATG_WS_TIMEOUT=30                  # Default: 30 seconds
```

**Recommendations**:
- Small tenants (< 500 resources): `ATG_TIMEOUT=180`
- Medium tenants (500-2000 resources): `ATG_TIMEOUT=600`
- Large tenants (> 2000 resources): `ATG_TIMEOUT=1800`

### Retry Configuration

Configure automatic retry behavior:

```bash
# Number of retries for failed requests
ATG_MAX_RETRIES=3

# Exponential backoff multiplier
ATG_RETRY_BACKOFF=2

# Retry only on specific status codes
ATG_RETRY_STATUS_CODES=408,429,500,502,503,504
```

Retry timing calculation:
```
Attempt 1: immediate
Attempt 2: 2 seconds (ATG_RETRY_BACKOFF ^ 1)
Attempt 3: 4 seconds (ATG_RETRY_BACKOFF ^ 2)
Attempt 4: 8 seconds (ATG_RETRY_BACKOFF ^ 3)
```

### WebSocket Configuration

Configure real-time progress streaming:

```bash
# Enable progress streaming
ATG_PROGRESS_ENABLED=true

# Reconnection attempts if WebSocket drops
ATG_WS_RECONNECT_ATTEMPTS=5

# Delay between reconnection attempts (seconds)
ATG_WS_RECONNECT_DELAY=2

# Show verbose progress messages
ATG_PROGRESS_VERBOSE=false

# Buffer size for progress messages
ATG_WS_BUFFER_SIZE=8192
```

## User-Level Configuration

Store default configuration in `~/.atg/config`:

```bash
# Create user config directory
mkdir -p ~/.atg

# Create default configuration
cat > ~/.atg/config << 'EOF'
# ATG User Configuration

# Default mode
ATG_MODE=remote

# Default environment
ATG_ENVIRONMENT=dev

# Default remote URL
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net

# Connection preferences
ATG_TIMEOUT=300
ATG_MAX_RETRIES=3
ATG_PROGRESS_ENABLED=true
EOF
```

User-level config be loaded automatically but can be overridden by project-level `.env` files.

## Azure Credentials Configuration

Remote mode requires Azure credentials for accessing yer tenant. Configure through:

### Method 1: Azure CLI (Recommended)

```bash
# Authenticate with Azure CLI
az login --tenant <YOUR_TENANT_ID>

# ATG automatically uses Azure CLI credentials
atg scan --tenant-id <YOUR_TENANT_ID>
```

### Method 2: Service Principal

```bash
# Set service principal credentials
export AZURE_CLIENT_ID=<APP_ID>
export AZURE_CLIENT_SECRET=<SECRET>
export AZURE_TENANT_ID=<TENANT_ID>

# ATG uses service principal credentials
atg scan --tenant-id <TENANT_ID>
```

### Method 3: Managed Identity

When running in Azure (VM, Container Instance, etc):

```bash
# No configuration needed - uses managed identity
atg scan --tenant-id <TENANT_ID>
```

**Note**: Azure credentials be used locally and never sent to the remote service. The remote service executes operations on yer behalf using these credentials.

## Configuration Validation

Verify yer configuration be correct:

```bash
# Check all configuration
atg config show

# Output:
# Mode: remote
# Remote URL: https://atg-dev.azurecontainerinstances.net
# Environment: dev
# API Key: atg_dev_***...*** (last 4: r678)
# Timeout: 300s
# Max Retries: 3
# Progress Enabled: true
# Azure Auth: az cli (logged in as user@example.com)

# Test remote connection
atg remote status

# Validate configuration and credentials
atg doctor --remote
```

## Configuration Examples

### Example 1: Developer Setup

```bash
# ~/.atg/config
ATG_MODE=remote
ATG_ENVIRONMENT=dev
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net
ATG_PROGRESS_VERBOSE=true
```

### Example 2: CI/CD Pipeline

```bash
# .env (stored in repo, API key from secrets)
ATG_MODE=remote
ATG_ENVIRONMENT=integration
ATG_REMOTE_URL=https://atg-integration.azurecontainerinstants.net
ATG_TIMEOUT=1800
ATG_PROGRESS_ENABLED=false
```

```yaml
# GitHub Actions
env:
  ATG_API_KEY: ${{ secrets.ATG_API_KEY }}
  AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
  AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
  AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
```

### Example 3: Production Operations

```bash
# .env
ATG_MODE=remote
ATG_ENVIRONMENT=integration
ATG_REMOTE_URL=https://atg-prod.example.com
ATG_TIMEOUT=3600
ATG_MAX_RETRIES=5
ATG_RETRY_BACKOFF=3
ATG_PROGRESS_ENABLED=true
ATG_PROGRESS_VERBOSE=false
```

### Example 4: Local Development with Fallback

```bash
# .env (try remote, fall back to local if unavailable)
ATG_MODE=remote
ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net
ATG_FALLBACK_TO_LOCAL=true
```

## Troubleshooting Configuration

**API key not working**:
```bash
# Verify key format
echo $ATG_API_KEY | cut -c1-8
# Should output: atg_dev_ or atg_inte

# Test key with status command
atg remote status --verbose
```

**Connection refused**:
```bash
# Verify URL be correct
echo $ATG_REMOTE_URL
curl $ATG_REMOTE_URL/health

# Check DNS resolution
nslookup atg-dev.azurecontainerinstances.net
```

**Azure authentication failing**:
```bash
# Verify Azure CLI authentication
az account show

# Re-authenticate if needed
az login --tenant <YOUR_TENANT_ID>

# Test with debug output
atg scan --tenant-id <TENANT_ID> --debug
```

**Configuration not loading**:
```bash
# Check which config files exist
ls -la .env
ls -la ~/.atg/config

# Show effective configuration
atg config show

# Debug configuration loading
export ATG_DEBUG=true
atg config show
```

## Next Steps

- [User Guide](./USER_GUIDE.md) - Learn how to use remote mode
- [API Reference](./API_REFERENCE.md) - Direct API usage
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions
