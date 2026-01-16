# Azure Sentinel Multi-Tenant Automation Examples

This directory contains working code examples for implementing Azure Sentinel multi-tenant telemetry aggregation using the distributed hub-and-spoke architecture with Azure Lighthouse.

## Directory Structure

```
examples/
├── bicep/               # Infrastructure-as-Code templates
│   ├── lighthouse-delegation.bicep      # Lighthouse delegation template
│   ├── lighthouse-parameters.json       # Parameter file
│   └── deploy.sh                        # Deployment script
├── powershell/          # Operational automation scripts
│   └── Deploy-SentinelConnectors.ps1    # Multi-tenant connector deployment
├── python/              # Query and analysis tools
│   └── sentinel_multi_tenant_query.py   # Cross-tenant query aggregation
└── README.md            # This file
```

## Prerequisites

### General Requirements
- Azure CLI installed and configured
- Appropriate permissions in managing tenant and customer tenants
- Service principal with necessary RBAC roles

### Bicep Examples
- Azure CLI with Bicep support (`az bicep version`)
- Owner or User Access Administrator role in customer tenants

### PowerShell Examples
- PowerShell 7.0 or later
- Az PowerShell module (`Install-Module -Name Az`)
- Service principal credentials

### Python Examples
- Python 3.8 or later
- Required packages: `pip install azure-identity azure-mgmt-loganalytics azure-monitor-query pandas`

## Usage Guides

### 1. Deploy Azure Lighthouse Delegation (Bicep)

**Purpose:** Establish cross-tenant access from your managing tenant to customer tenants.

**Steps:**

1. **Edit parameters file** (`bicep/lighthouse-parameters.json`):
   ```json
   {
     "managingTenantId": { "value": "your-managing-tenant-id" },
     "authorizations": {
       "value": [
         {
           "principalId": "service-principal-object-id",
           "roleDefinitionId": "ab8e14d6-4a74-4a29-9ba8-549422addade",
           "principalIdDisplayName": "Sentinel Management SP"
         }
       ]
     }
   }
   ```

2. **Deploy to customer subscription:**
   ```bash
   # Login to customer tenant
   az login --tenant customer-tenant-id

   # Deploy at subscription level
   az deployment sub create \
     --location eastus \
     --template-file bicep/lighthouse-delegation.bicep \
     --parameters bicep/lighthouse-parameters.json \
     --name sentinel-lighthouse-deployment
   ```

3. **Verify delegation:**
   ```bash
   # Check delegation status
   az managedservices definition list
   az managedservices assignment list
   ```

**Alternative:** Use the provided `deploy.sh` script:
```bash
cd bicep/
chmod +x deploy.sh
./deploy.sh
```

### 2. Deploy Data Connectors (PowerShell)

**Purpose:** Automate deployment of Sentinel data connectors across all delegated customer tenants.

**Steps:**

1. **Set environment variables:**
   ```powershell
   $managingTenantId = "your-managing-tenant-id"
   $servicePrincipalId = "your-service-principal-client-id"
   $secret = ConvertTo-SecureString "your-client-secret" -AsPlainText -Force
   ```

2. **Run deployment script:**
   ```powershell
   .\powershell\Deploy-SentinelConnectors.ps1 `
     -ManagingTenantId $managingTenantId `
     -ServicePrincipalId $servicePrincipalId `
     -ServicePrincipalSecret $secret `
     -ConnectorTypes @("AzureActiveDirectory", "Office365", "AzureSecurityCenter")
   ```

3. **Review results:**
   - Check console output for deployment status
   - Review CSV report: `connector-deployment-<timestamp>.csv`

**Supported Connector Types:**
- `AzureActiveDirectory` - Azure AD sign-in and audit logs
- `Office365` - Exchange, SharePoint, Teams activity logs
- `AzureSecurityCenter` - Azure Security Center alerts
- `AzureActivityLog` - Azure Activity logs
- `SecurityEvents` - Windows security events (requires agent)

### 3. Query Across Tenants (Python)

**Purpose:** Execute KQL queries across multiple Sentinel workspaces and aggregate results.

**Steps:**

1. **Set authentication environment variables:**
   ```bash
   export AZURE_CLIENT_ID="your-service-principal-client-id"
   export AZURE_CLIENT_SECRET="your-service-principal-secret"  # pragma: allowlist secret
   export AZURE_TENANT_ID="your-managing-tenant-id"
   ```

2. **Edit subscription IDs** in `sentinel_multi_tenant_query.py`:
   ```python
   subscription_ids = [
       "customer-1-subscription-id",
       "customer-2-subscription-id",
       # ... add all delegated subscriptions
   ]
   ```

3. **Run query:**
   ```bash
   python python/sentinel_multi_tenant_query.py
   ```

4. **Customize KQL query:**
   Modify the `kql_query` variable in `main()` to run different queries:
   ```python
   kql_query = """
   SecurityAlert
   | where TimeGenerated > ago(24h)
   | where Severity == "High"
   | summarize count() by AlertName, CompromisedEntity
   | order by count_ desc
   """
   ```

**Example Queries:**

- **Failed sign-ins across all tenants:**
  ```kql
  SigninLogs
  | where TimeGenerated > ago(1h)
  | where ResultType != "0"
  | summarize FailedAttempts = count() by UserPrincipalName, IPAddress
  | where FailedAttempts > 5
  ```

- **High severity incidents by tenant:**
  ```kql
  SecurityIncident
  | where Severity == "High"
  | summarize count() by TenantId, Title
  ```

- **Top malware detections:**
  ```kql
  SecurityAlert
  | where AlertType contains "Malware"
  | summarize count() by AlertName, CompromisedEntity
  | top 10 by count_
  ```

## Common Workflows

### Workflow 1: Initial Setup (New Customer Onboarding)

1. **Deploy Lighthouse delegation** (Bicep)
2. **Deploy Log Analytics workspace + Sentinel** (manual or Bicep)
3. **Deploy data connectors** (PowerShell)
4. **Verify data ingestion** (Azure portal or Python queries)

### Workflow 2: Regular Operations (Multi-Tenant Monitoring)

1. **Run cross-workspace queries** (Python)
2. **Analyze security incidents** (KQL queries)
3. **Generate compliance reports** (export query results)
4. **Update analytics rules** (PowerShell or Azure portal)

### Workflow 3: Maintenance (Credential Rotation)

1. **Generate new service principal secret**
2. **Update Azure Key Vault** (or environment variables)
3. **Test authentication** with new credentials
4. **Delete old secret** after verification

## Troubleshooting

### Issue: "Authorization failed" when deploying Lighthouse
**Solution:** Ensure you have Owner or User Access Administrator role in the customer tenant.

### Issue: "Data connector already exists" error
**Solution:** Modify connector ID in PowerShell script or delete existing connector first.

### Issue: "Workspace not found" in Python script
**Solution:** Verify Sentinel solution is enabled on Log Analytics workspace.

### Issue: "Cross-tenant authentication failed"
**Solution:** Add `additionally_allowed_tenants=['*']` to `DefaultAzureCredential()`.

### Issue: Query times out with many workspaces
**Solution:** Limit to 5 workspaces per query or use dedicated Log Analytics cluster.

## Best Practices

1. **Security:**
   - Store service principal credentials in Azure Key Vault
   - Use Managed Identity when possible
   - Implement credential rotation every 60-90 days
   - Enable MFA for all user accounts

2. **Performance:**
   - Batch connector deployments (5-10 tenants concurrently)
   - Use workspace IDs instead of names in KQL queries
   - Limit cross-workspace queries to ≤5 workspaces
   - Implement exponential backoff for API rate limiting

3. **Cost Optimization:**
   - Use Data Collection Rules (DCR) to filter data at source
   - Enroll in commitment tier pricing (32-53% discount)
   - Archive old data to Azure Data Explorer
   - Monitor ingestion volume per tenant

4. **Operational Excellence:**
   - Document all Lighthouse delegations in a central registry
   - Automate connector deployment via CI/CD pipeline
   - Schedule regular cross-tenant security reports
   - Implement audit logging for all automation scripts

## Additional Resources

- [Main Documentation](../AZURE_SENTINEL_MULTI_TENANT_TELEMETRY_AGGREGATION.md)
- [Azure Lighthouse Documentation](https://learn.microsoft.com/en-us/azure/lighthouse/)
- [Microsoft Sentinel REST API Reference](https://learn.microsoft.com/en-us/rest/api/securityinsights/)
- [KQL Query Language](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/query/)

## Support

For issues or questions:
1. Review troubleshooting section above
2. Check main documentation for detailed explanations
3. Consult Microsoft documentation links
4. Open GitHub issue with error details

---

**Last Updated:** December 2025
**Maintained By:** Azure Tenant Grapher Project
