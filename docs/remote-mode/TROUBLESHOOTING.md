# ATG Remote Mode Troubleshooting Guide

This guide helps ye diagnose and resolve common issues when using ATG remote mode.

## Quick Diagnostics

Run these commands first to identify the problem:

```bash
# Check configuration
atg config show

# Test remote connection
atg remote status

# Verify Azure authentication
az account show

# Run full diagnostic
atg doctor --remote
```

## Connection Issues

### Problem: "Connection refused" or "Unable to connect to remote service"

**Symptoms:**
```
Error: Failed to connect to https://atg-dev.azurecontainerinstances.net
Connection refused (ConnectionRefusedError)
```

**Possible Causes:**
1. Remote service be down or not deployed
2. Incorrect URL in configuration
3. Network firewall blocking connection
4. DNS resolution failure

**Solutions:**

**Check service status:**
```bash
# Verify service be deployed and running
az container show \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --query "instanceView.state" -o tsv

# Should output: Running
```

**Verify URL:**
```bash
# Check configured URL
echo $ATG_REMOTE_URL

# Should match actual service URL
az container show \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --query "ipAddress.fqdn" -o tsv
```

**Test connectivity:**
```bash
# Test HTTP connectivity
curl -v https://atg-dev.azurecontainerinstances.net/health

# Test DNS resolution
nslookup atg-dev.azurecontainerinstances.net

# Test from different network
# (if behind corporate firewall, try from personal device/network)
```

**Fix URL in configuration:**
```bash
# Update .env file
export ATG_REMOTE_URL=https://atg-dev.azurecontainerinstances.net

# Or update command
atg scan --remote-url https://atg-dev.azurecontainerinstances.net --tenant-id <ID>
```

### Problem: "SSL certificate verification failed"

**Symptoms:**
```
Error: SSL: CERTIFICATE_VERIFY_FAILED
Unable to verify SSL certificate for https://atg-dev.azurecontainerinstances.net
```

**Solutions:**

**Update CA certificates:**
```bash
# macOS
brew install ca-certificates
export SSL_CERT_FILE=/usr/local/etc/ca-certificates/cert.pem

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install ca-certificates

# Windows
# Download and install: https://curl.se/docs/caextract.html
```

**Temporary workaround (not recommended for production):**
```bash
# Disable SSL verification (INSECURE)
export ATG_VERIFY_SSL=false
atg scan --tenant-id <ID>
```

### Problem: "Connection timeout"

**Symptoms:**
```
Error: Request timeout after 30 seconds
Failed to connect to remote service
```

**Solutions:**

**Increase timeout:**
```bash
# Increase connection timeout
export ATG_TIMEOUT=300

# For slow networks
export ATG_TIMEOUT=600
```

**Check network latency:**
```bash
# Measure latency to service
ping -c 5 atg-dev.azurecontainerinstances.net

# If latency > 500ms, increase timeout significantly
```

## Authentication Issues

### Problem: "Invalid API key" or "Authentication failed"

**Symptoms:**
```
Error: HTTP 401 Unauthorized
Invalid API key provided
Authentication failed: API key not recognized
```

**Solutions:**

**Verify API key format:**
```bash
# Check API key be set
echo $ATG_API_KEY

# Should start with "atg_dev_" or "atg_integration_"
echo $ATG_API_KEY | cut -c1-8

# Key should be 72 characters total
echo $ATG_API_KEY | wc -c
```

**Test API key:**
```bash
# Test authentication directly
curl -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-dev.azurecontainerinstances.net/api/v1/status

# Should return JSON, not 401 error
```

**Request new API key:**
```bash
# Contact administrator or regenerate
# Keys stored in Azure Key Vault

# Retrieve from Key Vault (if ye have access)
az keyvault secret show \
  --vault-name atg-vault-dev \
  --name atg-api-key \
  --query value -o tsv
```

**Check environment:**
```bash
# Verify ye're using correct environment
echo $ATG_ENVIRONMENT

# Dev keys don't work with integration environment
# Integration keys don't work with dev environment
```

### Problem: "Azure authentication failed"

**Symptoms:**
```
Error: Azure authentication failed
DefaultAzureCredential failed to retrieve token
No access to tenant <TENANT_ID>
```

**Solutions:**

**Re-authenticate with Azure CLI:**
```bash
# Check current authentication
az account show

# Re-login if needed
az login --tenant <YOUR_TENANT_ID>

# Verify access to tenant
az account list --all -o table
```

**Use service principal:**
```bash
# Set service principal credentials
export AZURE_CLIENT_ID=<APP_ID>
export AZURE_CLIENT_SECRET=<SECRET>
export AZURE_TENANT_ID=<TENANT_ID>

# Test authentication
az login --service-principal \
  --username $AZURE_CLIENT_ID \
  --password $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID
```

**Check tenant access:**
```bash
# Verify ye have access to target tenant
az account tenant list

# Should include yer target tenant
```

## Performance Issues

### Problem: "Operations running very slow"

**Symptoms:**
- Scan taking > 1 hour for medium tenant
- Progress updates delayed or frozen
- Timeouts during large operations

**Solutions:**

**Check service resources:**
```bash
# Check container resource usage
az container show \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --query "containers[0].resources" -o table

# Should show: 8 CPU, 64 GB memory
```

**Check active operations:**
```bash
# List all active operations
atg remote operations

# If many operations running, wait or cancel old ones
atg remote operation cancel <operation-id>
```

**Check Neo4j performance:**
```bash
# Connect to Neo4j browser
# Open: http://<NEO4J_FQDN>:7474

# Run performance query
CALL dbms.queryJmx("org.neo4j:*")
YIELD name, attributes
WHERE name CONTAINS "memory"
RETURN name, attributes.HeapMemoryUsage
```

**Increase timeouts:**
```bash
# For large operations
export ATG_TIMEOUT=3600              # 1 hour
export ATG_OPERATION_TIMEOUT=7200    # 2 hours

# Retry operation
atg scan --tenant-id <ID>
```

### Problem: "Out of memory errors"

**Symptoms:**
```
Error: Container out of memory
Neo4j heap memory exhausted
Operation failed: insufficient memory
```

**Solutions:**

**Check container size:**
```bash
# Verify container has 64GB RAM
az container show \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --query "containers[0].resources.requests.memoryInGB" -o tsv

# Should output: 64.0
```

**Increase Neo4j heap:**
```bash
# Update Neo4j container with more heap memory
az container create \
  --resource-group atg-remote-dev \
  --name atg-neo4j-dev \
  --image neo4j:5.12.0 \
  --memory 32 \
  --environment-variables \
    NEO4J_server_memory_heap_max__size=24G \
    NEO4J_server_memory_pagecache_size=8G
```

**Break operation into smaller chunks:**
```bash
# Scan subscriptions separately
atg scan --tenant-id <ID> --filter-by-subscriptions sub1

atg scan --tenant-id <ID> --filter-by-subscriptions sub2
```

## WebSocket Issues

### Problem: "WebSocket connection failed" or "Progress updates not showing"

**Symptoms:**
```
Error: WebSocket connection failed
Progress updates not received
Connection dropped during operation
```

**Solutions:**

**Check WebSocket support:**
```bash
# Test WebSocket connection manually
npm install -g wscat

wscat -c wss://atg-dev.azurecontainerinstances.net/ws/progress \
  -H "Authorization: Bearer $ATG_API_KEY"

# Should connect without errors
```

**Disable WebSocket (use polling instead):**
```bash
# Fallback to HTTP polling for progress
export ATG_PROGRESS_ENABLED=false

atg scan --tenant-id <ID>

# Check progress with separate command
atg remote operation <operation-id>
```

**Check proxy/firewall:**
```bash
# Corporate proxies often block WebSocket
# Try from different network

# Or configure proxy
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1
```

**Increase reconnection attempts:**
```bash
# Configure more aggressive reconnection
export ATG_WS_RECONNECT_ATTEMPTS=10
export ATG_WS_RECONNECT_DELAY=3

atg scan --tenant-id <ID>
```

### Problem: "Progress stream disconnects randomly"

**Solutions:**

**Enable auto-reconnect:**
```bash
# Already enabled by default
# Increase attempts if needed
export ATG_WS_RECONNECT_ATTEMPTS=10
```

**Reduce message frequency:**
```bash
# Reduce verbosity to decrease message load
export ATG_PROGRESS_VERBOSE=false
```

**Reconnect manually:**
```bash
# If disconnected, reconnect to operation
atg remote attach <operation-id>
```

## Operation Issues

### Problem: "Operation stuck in 'running' state"

**Symptoms:**
- Operation shows "running" for hours
- No progress updates received
- Cannot cancel operation

**Solutions:**

**Check operation details:**
```bash
# Get detailed operation status
atg remote operation <operation-id> --verbose

# Check for error messages or last activity
```

**Force cancel operation:**
```bash
# Cancel stuck operation
atg remote operation cancel <operation-id> --force

# Wait 30 seconds and verify
atg remote operation <operation-id>
```

**Check container logs:**
```bash
# View service logs for errors
az container logs \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --follow

# Look for exceptions or error messages
```

**Restart service (last resort):**
```bash
# Restart container
az container restart \
  --resource-group atg-remote-dev \
  --name atg-service-dev

# Wait 60 seconds for restart
sleep 60

# Verify service running
atg remote status
```

### Problem: "Operation failed with no error message"

**Solutions:**

**Enable debug logging:**
```bash
# Run with debug output
export ATG_DEBUG=true
export ATG_LOG_LEVEL=DEBUG

atg scan --tenant-id <ID> --debug
```

**Check container logs:**
```bash
# View full service logs
az container logs \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --tail 1000

# Look for stack traces or error details
```

**Check Azure activity log:**
```bash
# Check Azure activity for failures
az monitor activity-log list \
  --resource-group atg-remote-dev \
  --start-time 2025-12-09T00:00:00Z \
  --query "[?level=='Error']" -o table
```

## Environment Issues

### Problem: "Wrong environment - data not found"

**Symptoms:**
```
Error: Graph not found for tenant <ID>
No data available in environment 'integration'
```

**Solutions:**

**Verify environment:**
```bash
# Check current environment
atg config show | grep Environment

# List available environments
atg remote environments
```

**Switch environment:**
```bash
# Switch to correct environment
export ATG_ENVIRONMENT=dev

# Or specify in command
atg scan --environment dev --tenant-id <ID>
```

**Check data location:**
```bash
# Check which environment has yer data
atg remote operation-history --all-environments

# Look for yer tenant ID across environments
```

### Problem: "Environment quota exceeded"

**Symptoms:**
```
Error: Environment quota exceeded
Cannot start operation: maximum concurrent operations reached
Resource limit: 64GB memory exhausted
```

**Solutions:**

**Check environment usage:**
```bash
# View environment resource usage
atg remote status --verbose

# Output shows:
# Active operations: 5 / 10
# Memory usage: 60.2 GB / 64.0 GB
# CPU usage: 85%
```

**Wait for operations to complete:**
```bash
# List active operations
atg remote operations

# Wait for completions or cancel old operations
atg remote operation cancel <old-operation-id>
```

**Use different environment:**
```bash
# Switch to less busy environment
export ATG_ENVIRONMENT=dev

# Or request additional capacity from administrator
```

## Data and Results Issues

### Problem: "Cannot download results"

**Symptoms:**
```
Error: Failed to download IaC templates
Timeout downloading visualization data
Results not available
```

**Solutions:**

**Check operation status:**
```bash
# Verify operation completed successfully
atg remote operation <operation-id>

# Should show status: completed
```

**Download results explicitly:**
```bash
# Download with explicit command
atg remote download <operation-id> --output ./results

# Or download specific artifact
atg remote download <operation-id> --artifact iac-templates
```

**Check network bandwidth:**
```bash
# For large results, increase timeout
export ATG_DOWNLOAD_TIMEOUT=600

atg remote download <operation-id> --output ./results
```

### Problem: "Results missing or incomplete"

**Solutions:**

**Verify operation success:**
```bash
# Check operation details
atg remote operation <operation-id> --verbose

# Look for errors or warnings
```

**Re-run operation:**
```bash
# Retry operation
atg scan --tenant-id <ID>

# Use --force to override cache
atg scan --tenant-id <ID> --force
```

**Check Neo4j data:**
```bash
# Verify data in Neo4j
atg remote query "MATCH (n) RETURN count(n) as total"

# Should return total node count
```

## Common Error Messages

### "HTTP 429: Too Many Requests"

**Cause:** Rate limit exceeded

**Solution:**
```bash
# Wait and retry with exponential backoff (automatic)
# Or reduce concurrent requests
export ATG_MAX_RETRIES=5
export ATG_RETRY_BACKOFF=3
```

### "HTTP 500: Internal Server Error"

**Cause:** Service error or bug

**Solution:**
```bash
# Check service logs
az container logs --resource-group atg-remote-dev --name atg-service-dev

# Report to administrator with operation ID
# Retry operation after service restart
```

### "HTTP 503: Service Unavailable"

**Cause:** Service overloaded or restarting

**Solution:**
```bash
# Wait 2-5 minutes and retry
sleep 120
atg remote status

# If still unavailable, check with administrator
```

## Getting Help

If ye can't resolve yer issue:

1. **Collect diagnostic information:**
```bash
# Run full diagnostics
atg doctor --remote --verbose > diagnostics.txt

# Collect logs
az container logs \
  --resource-group atg-remote-dev \
  --name atg-service-dev \
  --tail 1000 > service-logs.txt

# Include operation ID if applicable
atg remote operation <operation-id> > operation-details.txt
```

2. **Contact support with:**
   - Diagnostic output
   - Service logs
   - Operation ID
   - Error messages
   - Steps to reproduce

3. **Check documentation:**
   - [User Guide](./USER_GUIDE.md)
   - [Configuration Guide](./CONFIGURATION.md)
   - [API Reference](./API_REFERENCE.md)
   - [GitHub Issues](https://github.com/<ORG>/azure-tenant-grapher/issues)

## Prevention Tips

**Avoid future issues:**

1. **Always verify configuration:**
   ```bash
   atg config show
   atg remote status
   ```

2. **Test before large operations:**
   ```bash
   atg scan --tenant-id <ID> --dry-run
   ```

3. **Monitor operation progress:**
   ```bash
   atg remote operations
   ```

4. **Keep ATG updated:**
   ```bash
   pip install --upgrade azure-tenant-grapher
   ```

5. **Use appropriate environment:**
   - Dev for testing
   - Integration for production

6. **Set reasonable timeouts:**
   - Small tenants: 300s
   - Large tenants: 1800s+
