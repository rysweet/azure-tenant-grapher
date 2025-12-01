# Azure Sentinel Troubleshooting Guide

Complete troubleshooting reference for Azure Sentinel and Log Analytics automation issues.

## Quick Diagnostic Steps

When encountering errors:

1. **Enable debug mode**: Add `--debug` flag to see detailed execution logs
2. **Try dry-run**: Use `--dry-run` to preview without making changes
3. **Check prerequisites**: Run validation script manually
4. **Verify authentication**: Ensure `az login` is current
5. **Check permissions**: Verify service principal has required roles

## Common Error Messages

### Provider Registration Errors

#### Error: Provider Not Registered

**Error Message:**

```
Error: The subscription is not registered to use namespace 'Microsoft.SecurityInsights'
Code: MissingSubscriptionRegistration
```

**Cause:** Required Azure resource provider is not registered in the subscription.

**Solution:**

```bash
# Option 1: Let the tool register automatically (recommended)
uv run atg setup-sentinel --tenant-id <TENANT_ID>
# When prompted, select "Yes" to register providers

# Option 2: Register manually
az provider register --namespace Microsoft.SecurityInsights
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Insights

# Verify registration status (can take 5-10 minutes)
az provider show \
  --namespace Microsoft.SecurityInsights \
  --query "registrationState" \
  --output tsv
```

**Check Registration Status:**

```bash
# Check all required providers
az provider list \
  --query "[?namespace=='Microsoft.SecurityInsights' || namespace=='Microsoft.OperationalInsights' || namespace=='Microsoft.Insights'].{Namespace:namespace, State:registrationState}" \
  --output table

# Expected output:
# Namespace                         State
# --------------------------------  -----------
# Microsoft.SecurityInsights        Registered
# Microsoft.OperationalInsights     Registered
# Microsoft.Insights                Registered
```

**Bypass Provider Check:**

```bash
# Skip provider validation (not recommended)
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --skip-provider-check
```

---

### Permission Errors

#### Error: Authorization Failed for Workspace Creation

**Error Message:**

```
Error: The client '<client-id>' with object id '<object-id>' does not have authorization
to perform action 'Microsoft.OperationalInsights/workspaces/write' over scope
'/subscriptions/<sub-id>/resourceGroups/<rg-name>'
Code: AuthorizationFailed
```

**Cause:** Service principal or user lacks required permissions.

**Solution:**

```bash
# Check current account
az account show --output table

# Assign required role to service principal
az role assignment create \
  --assignee <service-principal-id> \
  --role "Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/sentinel-rg"

# Or use custom role with minimal permissions
az role assignment create \
  --assignee <service-principal-id> \
  --role "Log Analytics Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/sentinel-rg"
```

**Required Permissions:**

- `Microsoft.OperationalInsights/workspaces/write`
- `Microsoft.OperationalInsights/workspaces/read`
- `Microsoft.Insights/diagnosticSettings/write`
- `Microsoft.Insights/diagnosticSettings/read`
- `Microsoft.SecurityInsights/*/write`
- `Microsoft.Resources/subscriptions/resourceGroups/read`

**Verify Permissions:**

```bash
# List role assignments for service principal
az role assignment list \
  --assignee <service-principal-id> \
  --output table

# Check specific permission
az role definition list \
  --name "Contributor" \
  --query "[].permissions[].actions" \
  --output json
```

---

#### Error: Insufficient Privileges to Complete Operation

**Error Message:**

```
Error: Insufficient privileges to complete the operation.
Code: InsufficientPrivileges
```

**Cause:** Attempting operations that require elevated permissions.

**Solution:**

```bash
# Request elevation of privileges from Azure AD admin
# Or use an account with Owner/Contributor role

# Verify current role
az role assignment list \
  --assignee $(az account show --query user.name -o tsv) \
  --scope /subscriptions/<subscription-id> \
  --output table
```

---

### Workspace Errors

#### Error: Workspace Already Exists

**Error Message:**

```
Error: The workspace 'sentinel-workspace' already exists in resource group 'sentinel-rg'
Code: WorkspaceAlreadyExists
```

**Cause:** Workspace with the same name already exists.

**Solution:**

```bash
# Option 1: Use existing workspace (recommended)
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --workspace-name sentinel-workspace \
  --resource-group sentinel-rg

# The tool will detect and reuse the existing workspace

# Option 2: Use different workspace name
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --workspace-name sentinel-workspace-2

# Option 3: Delete existing workspace (caution: data loss)
az monitor log-analytics workspace delete \
  --resource-group sentinel-rg \
  --workspace-name sentinel-workspace \
  --yes
```

---

#### Error: Invalid Workspace Name

**Error Message:**

```
Error: Workspace name must be 4-63 characters, alphanumeric and hyphens only
Code: InvalidWorkspaceName
```

**Cause:** Workspace name doesn't meet Azure naming requirements.

**Solution:**

```bash
# ❌ Invalid names
sentinel_workspace  # No underscores
sen                # Too short (< 4 chars)
my-sentinel-workspace-with-a-very-long-name-that-exceeds-limit  # Too long (> 63 chars)

# ✅ Valid names
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --workspace-name sentinel-prod-001
```

**Naming Rules:**

- 4-63 characters
- Alphanumeric and hyphens only
- Must start with letter or number
- No underscores or special characters

---

#### Error: Workspace SKU Not Available

**Error Message:**

```
Error: The SKU 'CapacityReservation' is not available in location 'eastus'
Code: SkuNotAvailable
```

**Cause:** Selected pricing tier not available in the region.

**Solution:**

```bash
# Use PerGB2018 (available in all regions)
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --sku PerGB2018

# Or change region
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --location westus2 \
  --sku CapacityReservation
```

**Available SKUs:**

- `PerGB2018`: Pay-per-GB (available everywhere)
- `CapacityReservation`: Commitment tiers (limited regions)
- `Free`: Free tier (deprecated, not recommended)

---

### Diagnostic Settings Errors

#### Error: Resource Type Doesn't Support Diagnostic Settings

**Error Message:**

```
Warning: Resource type 'Microsoft.Network/publicIPAddresses' doesn't support diagnostic settings
Code: DiagnosticSettingsNotSupported
```

**Cause:** Some resource types don't support diagnostic settings.

**Solution:**

```bash
# Option 1: Continue with --no-strict mode (recommended)
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --no-strict

# This will skip unsupported resources and continue

# Option 2: Filter resource types in config
cat > config.json <<EOF
{
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.Network/networkSecurityGroups",
      "Microsoft.KeyVault/vaults"
    ]
  }
}
EOF

uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --config-file config.json
```

**Supported Resource Types:**

Most common resource types support diagnostic settings:

- Virtual Machines
- Network Security Groups
- Key Vaults
- Storage Accounts
- SQL Databases
- App Services
- Function Apps
- Container Registries

Check Azure documentation for complete list.

---

#### Error: Diagnostic Settings Already Exist

**Error Message:**

```
Warning: Diagnostic setting 'sentinel-diag-vm001' already exists on resource
Code: DiagnosticSettingAlreadyExists
```

**Cause:** Diagnostic settings already configured (tool is idempotent).

**Solution:**

This is expected behavior. The tool will:

1. Detect existing diagnostic settings
2. Update if configuration differs
3. Skip if configuration matches

No action needed - this is not an error.

```bash
# To see what would change, use dry-run
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --dry-run

# Output shows:
# Resource: vm001
# Status: SKIPPED (diagnostic settings already exist with matching config)
```

---

#### Error: Maximum Diagnostic Settings Limit Reached

**Error Message:**

```
Error: The maximum number of diagnostic settings (5) for resource has been reached
Code: DiagnosticSettingsLimitReached
```

**Cause:** Azure limits diagnostic settings to 5 per resource.

**Solution:**

```bash
# List existing diagnostic settings
az monitor diagnostic-settings list \
  --resource <resource-id> \
  --output table

# Delete unused diagnostic settings
az monitor diagnostic-settings delete \
  --resource <resource-id> \
  --name <setting-name>

# Then retry setup
uv run atg setup-sentinel --tenant-id <TENANT_ID>
```

---

### Sentinel Enablement Errors

#### Error: Sentinel Solution Already Installed

**Error Message:**

```
Info: Sentinel solution 'SecurityInsights' already installed on workspace
Code: SolutionAlreadyInstalled
```

**Cause:** Sentinel is already enabled (tool is idempotent).

**Solution:**

This is expected behavior - no action needed. The tool will verify the solution is properly configured.

```bash
# To skip Sentinel enablement entirely
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --skip-sentinel
```

---

#### Error: Sentinel License Required

**Error Message:**

```
Error: Sentinel requires a valid Azure subscription with Security Center enabled
Code: SentinelLicenseRequired
```

**Cause:** Subscription doesn't have Defender for Cloud enabled.

**Solution:**

```bash
# Enable Microsoft Defender for Cloud
az security pricing create \
  --name VirtualMachines \
  --tier Standard

# Verify enablement
az security pricing list --output table

# Then retry Sentinel setup
uv run atg setup-sentinel --tenant-id <TENANT_ID>
```

---

### Authentication Errors

#### Error: Authentication Expired

**Error Message:**

```
Error: AADSTS700082: The refresh token has expired due to inactivity.
Code: AuthenticationExpired
```

**Cause:** Azure CLI authentication has expired.

**Solution:**

```bash
# Re-authenticate
az login

# For service principal
az login \
  --service-principal \
  --username <client-id> \
  --password <client-secret> \
  --tenant <tenant-id>

# Verify authentication
az account show --output table

# Then retry
uv run atg setup-sentinel --tenant-id <TENANT_ID>
```

---

#### Error: Wrong Tenant Context

**Error Message:**

```
Error: Tenant '<tenant-id>' not found in current authentication context
Code: TenantNotFound
```

**Cause:** Not authenticated to the correct tenant.

**Solution:**

```bash
# Login to specific tenant
az login --tenant <tenant-id>

# For cross-tenant scenarios, login to both
az login --tenant <source-tenant-id>
az login --tenant <target-tenant-id> --allow-no-subscriptions

# List available tenants
az account list --output table

# Switch tenant
az account set --subscription <subscription-id>

# Verify
az account show --output table
```

---

### Neo4j Connection Errors

#### Error: Cannot Connect to Neo4j

**Error Message:**

```
Error: Failed to connect to Neo4j at bolt://localhost:7687
Code: Neo4jConnectionError
```

**Cause:** Neo4j container is not running or accessible.

**Solution:**

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Start Neo4j container
uv run atg doctor  # This will start Neo4j

# Or manually start
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Verify connection
docker logs neo4j

# Test connection
uv run atg validate-neo4j

# Then retry
uv run atg setup-sentinel --tenant-id <TENANT_ID>
```

---

#### Error: No Resources Found in Neo4j

**Error Message:**

```
Warning: No resources found in Neo4j graph for tenant '<tenant-id>'
Falling back to Azure Resource Graph API
Code: NoResourcesInGraph
```

**Cause:** Tenant hasn't been scanned yet.

**Solution:**

```bash
# Scan tenant first to populate Neo4j
uv run atg scan --tenant-id <TENANT_ID>

# Verify resources in graph
uv run atg visualize --tenant-id <TENANT_ID>

# Then retry Sentinel setup
uv run atg setup-sentinel --tenant-id <TENANT_ID>
```

---

### Configuration Errors

#### Error: Invalid Configuration File

**Error Message:**

```
Error: Failed to parse configuration file: Unexpected token at line 12
Code: InvalidConfiguration
```

**Cause:** JSON/YAML syntax error in configuration file.

**Solution:**

```bash
# Validate JSON syntax
cat config.json | python -m json.tool

# Or use online validator: jsonlint.com

# Check YAML syntax
cat config.yaml | python -c "import yaml, sys; yaml.safe_load(sys.stdin)"

# Fix syntax errors and retry
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --config-file config.json
```

---

#### Error: Required Configuration Field Missing

**Error Message:**

```
Error: Missing required field 'workspace.name' in configuration
Code: MissingRequiredField
```

**Cause:** Configuration file is missing required fields.

**Solution:**

```json
// Add required fields
{
  "workspace": {
    "name": "sentinel-workspace",  // ← Required
    "location": "eastus"            // ← Required
  }
}
```

See [SENTINEL_CONFIGURATION.md](./SENTINEL_CONFIGURATION.md) for complete schema.

---

### Rate Limiting Errors

#### Error: Azure API Rate Limit Exceeded

**Error Message:**

```
Error: Rate limit exceeded. Retry after 60 seconds.
Code: TooManyRequests
```

**Cause:** Too many API requests in short period.

**Solution:**

The tool automatically handles rate limiting with exponential backoff. If you see this error:

```bash
# Wait and retry (tool will auto-retry)
# Or reduce parallel operations in config
cat > config.json <<EOF
{
  "execution": {
    "parallel_operations": 2,
    "retry_delay_seconds": 10
  }
}
EOF

uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --config-file config.json
```

---

### Resource Discovery Errors

#### Error: Resource Group Not Found

**Error Message:**

```
Error: Resource group 'sentinel-rg' not found in subscription
Code: ResourceGroupNotFound
```

**Cause:** Specified resource group doesn't exist.

**Solution:**

```bash
# Option 1: Create resource group
az group create \
  --name sentinel-rg \
  --location eastus

# Option 2: Use existing resource group
az group list --output table

uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --resource-group existing-rg
```

---

#### Error: Subscription Not Found

**Error Message:**

```
Error: Subscription '<subscription-id>' not found or not accessible
Code: SubscriptionNotFound
```

**Cause:** Specified subscription doesn't exist or lacks permissions.

**Solution:**

```bash
# List available subscriptions
az account list --output table

# Set correct subscription
az account set --subscription <subscription-id>

# Verify
az account show --output table

# Or specify in command
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --subscription-id <valid-subscription-id>
```

---

## Debugging Techniques

### Enable Debug Mode

```bash
# Maximum verbosity
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --debug

# Output includes:
# - Configuration resolution details
# - API request/response bodies
# - Bash script execution logs
# - Neo4j query results
# - Detailed error traces
```

### Dry Run Preview

```bash
# Preview without making changes
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --dry-run

# Shows:
# - What resources would be created
# - What diagnostic settings would be configured
# - What Sentinel solutions would be installed
# - Estimated cost impact
```

### Manual Script Execution

```bash
# Generate scripts for manual execution
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --generate-script \
  --output-dir ./sentinel-scripts

# Review generated scripts
cd ./sentinel-scripts
ls -la
# 1_validate_prerequisites.sh
# 2_create_workspace.sh
# 3_configure_diagnostics.sh
# 4_enable_sentinel.sh
# 5_verify_deployment.sh
# common.sh

# Execute manually with debugging
bash -x 1_validate_prerequisites.sh
bash -x 2_create_workspace.sh
```

### Check Prerequisites

```bash
# Run validation script directly
bash scripts/sentinel/1_validate_prerequisites.sh

# Output shows:
# ✓ Azure CLI installed: 2.54.0
# ✓ Authenticated to tenant: <tenant-id>
# ✓ Required providers registered
# ✓ Permissions validated
```

### Verify Azure CLI Version

```bash
# Check version
az version

# Upgrade if needed
# macOS
brew upgrade azure-cli

# Linux
curl -L https://aka.ms/InstallAzureCli | bash

# Windows
# Download and run: https://aka.ms/installazurecliwindows

# Minimum required: 2.50.0
```

### Test Neo4j Connection

```bash
# Test connection
docker exec -it neo4j cypher-shell -u neo4j -p password

# Run test query
MATCH (n:Resource) RETURN count(n);

# Should return resource count
# If 0, run scan first
exit
uv run atg scan --tenant-id <TENANT_ID>
```

### Validate Configuration

```bash
# Validate config file syntax
uv run atg validate-sentinel-config \
  --config-file config.json

# Output:
# ✓ Configuration validation: PASSED
# ✓ All required fields present
# ✓ All field types correct
# ✓ All values within valid ranges
```

## Advanced Troubleshooting

### Logging and Diagnostics

```bash
# Enable detailed logging
export SENTINEL_LOG_LEVEL="DEBUG"
export AZURE_CLI_LOG_LEVEL="DEBUG"

uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --debug 2>&1 | tee sentinel-setup.log

# Review log file
grep -i "error" sentinel-setup.log
grep -i "warning" sentinel-setup.log
```

### Network Connectivity

```bash
# Test Azure connectivity
az account show --output table

# Test Neo4j connectivity
nc -zv localhost 7687

# Test Docker
docker ps
docker network ls
```

### Resource State Inspection

```bash
# Check workspace state
az monitor log-analytics workspace show \
  --resource-group sentinel-rg \
  --workspace-name sentinel-workspace \
  --output json

# Check diagnostic settings
az monitor diagnostic-settings list \
  --resource <resource-id> \
  --output table

# Check Sentinel solutions
az monitor log-analytics workspace get-schema \
  --resource-group sentinel-rg \
  --workspace-name sentinel-workspace
```

## Getting Help

### Support Channels

- **Documentation**: [scripts/sentinel/README.md](../scripts/sentinel/README.md)
- **Configuration**: [SENTINEL_CONFIGURATION.md](./SENTINEL_CONFIGURATION.md)
- **Examples**: [SENTINEL_INTEGRATION_EXAMPLES.md](./SENTINEL_INTEGRATION_EXAMPLES.md)
- **GitHub Issues**: Report bugs and request features

### Before Opening an Issue

Include the following information:

1. **Command executed**: Full command with flags
2. **Error message**: Complete error output
3. **Debug log**: Run with `--debug` and attach log
4. **Environment**: Azure CLI version, OS, Python version
5. **Configuration**: Sanitized config file (remove credentials)
6. **Expected vs actual behavior**: What you expected vs what happened

Example issue template:

```markdown
## Command

uv run atg setup-sentinel --tenant-id <ID> --debug

## Error Message

[Paste complete error]

## Debug Log

[Attach or link to debug log]

## Environment

- Azure CLI: 2.54.0
- OS: Ubuntu 22.04
- Python: 3.11.5
- ATG Version: 1.0.0

## Configuration

[Paste sanitized config]

## Expected Behavior

[What you expected to happen]

## Actual Behavior

[What actually happened]
```

## Quick Reference

### Most Common Issues

| Issue                      | Quick Fix                                                       |
| -------------------------- | --------------------------------------------------------------- |
| Provider not registered    | `az provider register --namespace Microsoft.SecurityInsights`  |
| Authentication expired     | `az login`                                                      |
| Workspace already exists   | Rerun (tool is idempotent)                                      |
| Neo4j not running          | `uv run atg doctor`                                             |
| Permission denied          | Assign Contributor role                                         |
| Invalid config file        | Validate JSON/YAML syntax                                       |
| Resource type unsupported  | Use `--no-strict` mode                                          |

### Emergency Recovery

```bash
# Complete reset and retry
az logout
az login
uv run atg doctor
uv run atg scan --tenant-id <TENANT_ID>
uv run atg setup-sentinel --tenant-id <TENANT_ID> --debug
```
