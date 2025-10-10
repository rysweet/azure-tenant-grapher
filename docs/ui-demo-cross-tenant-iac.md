# Cross-Tenant IaC Demo - UI Workflow

This guide demonstrates the complete cross-tenant Infrastructure-as-Code (IaC) workflow using the Azure Tenant Grapher SPA/Electron UI.

## Overview

This demo replicates resources from one Azure tenant (DefenderATEVET17) to another tenant (Simuland) using a graphical workflow:

1. **Scan** - Discover Azure resources and build Neo4j graph
2. **Generate IaC** - Create Terraform/Bicep/ARM templates from graph
3. **Deploy** - Deploy IaC to target tenant
4. **Validate** - Compare source and target graphs for accuracy
5. **Undeploy** - Clean up (if needed)

## Prerequisites

- Azure Tenant Grapher installed (`uv run atg --version`)
- Neo4j database running and populated with source tenant data
- Service principal credentials configured in `.env` file:
  ```bash
  # Source tenant (DefenderATEVET17)
  AZURE_TENANT_ID=3cd87a41-1f61-4aef-a212-cefdecd9a2d1
  AZURE_CLIENT_ID=c331f235-8306-4227-aef1-9d7e79d11c2b
  AZURE_CLIENT_SECRET=<secret>

  # Target tenant (Simuland)
  AZURE_TENANT_2_ID=506f82b2-e2e7-40a2-b0be-ea6f8cb908f8
  AZURE_TENANT_2_CLIENT_ID=af0628c3-fdf8-488a-a466-e5d64032ab36
  AZURE_TENANT_2_CLIENT_SECRET=<secret>
  AZURE_TENANT_2_NAME=Simuland
  ```

## Step 1: Start the SPA

Launch the Electron GUI:

```bash
cd azure-tenant-grapher
uv run atg start
```

The SPA will:
- Build the Electron app (if needed)
- Start the MCP server
- Open the GUI application

**Expected Output:**
```
🔨 Building Electron app with latest code...
✅ Electron app built successfully
🤖 Starting MCP server...
✅ MCP server started (PID: 28144)
🚀 SPA started. The Electron app should open shortly.
```

## Step 2: Navigate to Status Tab

The **Status** tab shows:
- Neo4j connection status
- Database population status
- Available tenants in graph
- System information

**Actions:**
- Verify Neo4j is connected (green status)
- Confirm DefenderATEVET17 tenant data is loaded

## Step 3: Generate IaC from Source Tenant

Navigate to the **Generate IaC** tab:

### Configuration:
1. **Tenant ID**: Select DefenderATEVET17 (or enter manually: `3cd87a41-1f61-4aef-a212-cefdecd9a2d1`)
2. **Output Format**: Select `Terraform` (or Bicep/ARM)
3. **Target Tenant**: Select "Tenant 2 (Simuland)"
4. **Resource Filters**: Add filter `resourceGroup=SimuLand` to generate only SimuLand RG resources
   - Click "Add Filter" button to add the filter
5. **Dry Run**: Leave unchecked (we want actual files)

### Generate:
1. Click **Generate IaC** button
2. Monitor terminal output for progress
3. Look for success message: "Generated X files in: output/iac"
4. Click **Open Output Folder** to view generated files

**Expected Files:**
- `main.tf.json` - Terraform configuration with all resources
- `.terraform.lock.hcl` - Provider lock file
- Provider configurations for azurerm, random, tls

**Example Terminal Output:**
```
Filtering resources by resourceGroup: SimuLand
Processing 90 resources...
Generated 56 valid resources (34 skipped):
  - 15 VMs (azurerm_linux_virtual_machine)
  - 18 NICs (azurerm_network_interface)
  - 2 Subnets (azurerm_subnet)
  - 3 VNets (azurerm_virtual_network)
  - 16 NSGs (azurerm_network_security_group)
  - 3 Public IPs (azurerm_public_ip)
  - 1 Key Vault (azurerm_key_vault)

Files generated in: output/iac
```

## Step 4: Deploy IaC to Target Tenant

Navigate to the **Deploy** tab (⚠️ **NEW TAB** implemented in this PR):

### Configuration:
1. **IaC Directory**: `output/iac` (click Browse to select)
2. **Target Tenant**: Select "Tenant 2 (Simuland)"
3. **Target Tenant ID**: Auto-filled `506f82b2-e2e7-40a2-b0be-ea6f8cb908f8`
4. **Resource Group**: Enter `SimuLandReplica` (target RG name)
5. **Azure Region**: `eastus` (or your preferred region)
6. **Subscription ID**: Enter target subscription ID (for Bicep/ARM)
7. **IaC Format**: Select `Auto-detect` (or specify Terraform)
8. **Dry Run**: ✅ Check this box first to validate

### Dry Run (Validation):
1. Check "Dry Run" checkbox
2. Click **Validate Deployment** button
3. Monitor terminal output for Terraform plan
4. Verify no errors in the plan output
5. Review resources to be created

**Expected Output (Dry Run):**
```
Deploying terraform to tenant 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8, RG SimuLandReplica
Running terraform init...
Initializing provider plugins...
- Installing hashicorp/azurerm v4.47.0...
✅ Terraform initialized successfully

Running terraform plan (dry-run mode)...
Terraform will perform the following actions:
  # 56 resources to add
  # 0 to change
  # 0 to destroy

Plan: 56 to add, 0 to change, 0 to destroy.
```

### Actual Deployment:
1. Uncheck "Dry Run" checkbox
2. Click **Deploy to Azure** button
3. Monitor terminal output for Terraform apply progress
4. Wait for completion (may take 10-30 minutes depending on resources)

**Expected Output (Deployment):**
```
Running terraform apply...
azurerm_resource_group.SimuLandReplica: Creating...
azurerm_resource_group.SimuLandReplica: Creation complete after 3s

azurerm_virtual_network.vnet1: Creating...
azurerm_virtual_network.vnet1: Creation complete after 12s

... (56 resources created)

Apply complete! Resources: 56 added, 0 changed, 0 destroyed.
```

## Step 5: Validate Deployment

Navigate to the **Validate** tab (⚠️ **NEW TAB** implemented in this PR):

### Configuration:
1. **Source Tenant**: Select "Tenant 1 (DefenderATEVET17)"
2. **Source Tenant ID**: Auto-filled `3cd87a41-1f61-4aef-a212-cefdecd9a2d1`
3. **Target Tenant**: Select "Tenant 2 (Simuland)"
4. **Target Tenant ID**: Auto-filled `506f82b2-e2e7-40a2-b0be-ea6f8cb908f8`
5. **Source Filter**: Enter `resourceGroup=SimuLand`
6. **Target Filter**: Enter `resourceGroup=SimuLandReplica`
7. **Output Format**: Select `Markdown` (or JSON)
8. **Verbose**: Check for detailed logging

### Validate:
1. Click **Validate Deployment** button
2. Monitor terminal output for comparison results
3. Review validation report
4. Click **Download Report** to save the results

**Expected Output:**
```
Comparing source tenant 3cd87a41... with target tenant 506f82b2...
Source filter: resourceGroup=SimuLand
Target filter: resourceGroup=SimuLandReplica

📊 Resource Count Comparison:
  Virtual Machines: 15 → 15 ✅
  Network Interfaces: 18 → 18 ✅
  Virtual Networks: 3 → 3 ✅
  Subnets: 2 → 2 ✅
  NSGs: 16 → 16 ✅
  Public IPs: 3 → 3 ✅
  Key Vaults: 1 → 1 ✅

🎯 Similarity Score: 98.5%

✅ VALIDATION PASSED
Deployment successfully replicated source configuration.

ℹ️  Minor differences:
  - Resource IDs differ (expected for cross-tenant)
  - Creation timestamps differ (expected)
  - Some tags may vary
```

## Step 6: Review Deployment (Optional)

Navigate to the **Undeploy** tab to view active deployments:

### View Deployments:
1. Click **Refresh** to load deployment list
2. Review deployment details:
   - Deployment ID
   - Status (active/destroyed/failed)
   - Tenant
   - Resource count
   - Deployment timestamp
   - Directory path

### Undeploy (Cleanup):
If you want to clean up the deployed resources:

1. Select the deployment from the table
2. Click **Undeploy** button
3. Select target tenant
4. Check "Dry run" to preview destruction
5. Type the deployment ID to confirm
6. Click **Destroy Resources**

**⚠️ WARNING:** Undeploying permanently destroys Azure resources. This cannot be undone.

## Troubleshooting

### Neo4j Connection Issues
- **Error**: "Neo4j connection failed"
- **Solution**: Verify Neo4j container is running (`docker ps | grep neo4j`)
- **Solution**: Check `NEO4J_URI` and `NEO4J_PASSWORD` in `.env`

### Authentication Errors
- **Error**: "AADSTS5000224: We are sorry, this resource is not available"
- **Cause**: Target tenant is inaccessible or service principal lacks permissions
- **Solution**: Verify service principal has Contributor role on target subscription
- **Solution**: Use `az login --tenant <TENANT_ID>` to test authentication manually

### Terraform Errors
- **Error**: "Missing required argument: network_interface_ids"
- **Cause**: VM resources missing NIC references
- **Solution**: This was fixed in PR #284 - ensure you're on latest code

### Validation Errors
- **Error**: "Source tenant not found in graph"
- **Cause**: Source tenant hasn't been scanned yet
- **Solution**: Run scan on source tenant first (Scan tab)

## UI Implementation Details

### New Tabs Implemented

This PR adds two critical UI tabs that were missing from the SPA:

#### **DeployTab** (`spa/renderer/src/components/tabs/DeployTab.tsx`)
- Wraps `atg deploy` CLI command
- Features:
  - Browse for IaC directory
  - Select target tenant (Tenant 1/Tenant 2)
  - Configure deployment parameters (RG, location, subscription)
  - Auto-detect or specify IaC format
  - Dry-run validation mode
  - Real-time terminal output
  - Success/error notifications

#### **ValidateDeploymentTab** (`spa/renderer/src/components/tabs/ValidateDeploymentTab.tsx`)
- Wraps `atg validate-deployment` CLI command
- Features:
  - Select source and target tenants
  - Apply resource filters to both sides
  - Choose output format (Markdown/JSON)
  - Save validation report to file
  - Download report from UI
  - Real-time terminal output
  - Verbose logging option

### Integration Points

**App.tsx Updates:**
- Added lazy imports for DeployTab and ValidateDeploymentTab
- Added routes `/deploy` and `/validate-deployment`
- Wrapped in error boundaries for fault tolerance

**TabNavigation.tsx Updates:**
- Added "Deploy" tab with CloudUpload icon
- Added "Validate" tab with CheckCircle icon
- Positioned after "Generate IaC" and before "Undeploy"

### UI/UX Considerations

1. **Tenant Selection**: Dropdowns pre-populate tenant IDs to avoid typos
2. **Dry Run First**: Dry-run checkbox defaults to true for safety
3. **Terminal Output**: Real-time streaming shows progress
4. **Error Handling**: Clear error messages with actionable guidance
5. **Success Indicators**: Green alerts confirm successful operations
6. **File Paths**: Browse button for easy directory selection
7. **Responsive Layout**: Works on various screen sizes

## Next Steps

After completing the UI demo:

1. **Documentation**: Update screenshots once tabs are merged
2. **Testing**: Run full e2e tests in SPA environment
3. **CI/CD**: Ensure SPA builds successfully in GitHub Actions
4. **User Feedback**: Collect feedback on UI workflow
5. **Iteration**: Address any UX issues discovered during testing

## Related Issues and PRs

- **PR #284**: Fixed Terraform IaC generation bugs (VMs, NICs, subnets)
- **PR #285**: Added subnet generation from vnet properties
- **PR #286**: Implemented multi-tenant authentication
- **Issue #291**: UI missing Deploy and Validate tabs (this work)

## Demo Video Script

For creating a video walkthrough:

1. **Introduction** (30s)
   - "Today I'll show you cross-tenant Azure resource replication using ATG"
   - Show both Azure portals side by side (source and target)

2. **Start SPA** (15s)
   - Run `uv run atg start`
   - Show Electron app opening

3. **Check Status** (15s)
   - Navigate to Status tab
   - Point out Neo4j connection and tenant data

4. **Generate IaC** (60s)
   - Navigate to Generate IaC tab
   - Select DefenderATEVET17 tenant
   - Add resourceGroup=SimuLand filter
   - Click Generate IaC
   - Show terminal output
   - Open output folder to show main.tf.json

5. **Deploy (Dry Run)** (60s)
   - Navigate to Deploy tab
   - Configure target tenant (Simuland)
   - Enter resource group name
   - Check dry-run checkbox
   - Click Validate Deployment
   - Review Terraform plan output

6. **Deploy (Actual)** (90s)
   - Uncheck dry-run
   - Click Deploy to Azure
   - Show progress in terminal
   - Highlight resource creation
   - Show success message

7. **Validate** (60s)
   - Navigate to Validate tab
   - Configure source and target filters
   - Click Validate Deployment
   - Show validation report
   - Download report

8. **Review in Azure Portal** (30s)
   - Switch to Azure Portal
   - Show replicated resources in target tenant
   - Compare with source

9. **Cleanup** (30s)
   - Navigate to Undeploy tab
   - Show deployment list
   - Demonstrate undeploy workflow (can dry-run)

10. **Conclusion** (15s)
    - "Cross-tenant replication complete!"
    - Show final validation score

**Total Duration**: ~6 minutes

## Conclusion

This UI demo provides a comprehensive graphical workflow for cross-tenant Azure resource replication. The new Deploy and Validate tabs complete the end-to-end IaC workflow that was previously only available via CLI.

Key improvements:
- ✅ No manual CLI commands required
- ✅ Visual feedback throughout the process
- ✅ Safety features (dry-run, confirmations)
- ✅ Integrated validation and reporting
- ✅ Accessible to non-CLI users
