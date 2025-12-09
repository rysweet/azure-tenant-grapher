# ITERATION 13 - Implementation Details

**Date:** 2025-01-15
**Objective:** Fix GAP-024 by generating explicit Resource Group resources with proper depends_on
**Status:** ✅ Deployed - awaiting fidelity measurement

## Problem Summary

ITERATION 12 achieved only 19.1% fidelity because:
- Resource Groups were not generated as Terraform resources
- Dependency tier system sorted resources in JSON but didn't control Terraform execution
- Terraform executed resources in parallel, causing ResourceGroupNotFound errors
- Cannot use `depends_on` to reference non-existent RG resources

## Solution Implemented

Generate Resource Groups as explicit `azurerm_resource_group` Terraform resources with proper dependency chains.

## Code Changes

### 1. terraform_emitter.py

**Added `_extract_resource_groups()` method** (lines 70-99):
```python
def _extract_resource_groups(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract unique resource groups from all resources.

    Returns list of RG resource dictionaries with properties:
    - id: RG azure resource ID
    - name: RG name
    - location: Azure region
    - type: "Microsoft.Resources/resourceGroups"
    """
    rg_map = {}
    for resource in resources:
        # Try both field names (resource_group and resourceGroup)
        rg_name = resource.get("resource_group") or resource.get("resourceGroup")
        if rg_name and rg_name not in rg_map:
            # Extract location from first resource in this RG
            location = resource.get("location", "westus2")
            subscription = resource.get("subscription_id") or resource.get("subscriptionId", "")

            rg_map[rg_name] = {
                "id": f"/subscriptions/{subscription}/resourceGroups/{rg_name}",
                "name": rg_name,
                "location": location,
                "type": "Microsoft.Resources/resourceGroups",
                "subscriptionId": subscription,
                "subscription_id": subscription,
                "resourceGroup": rg_name,  # For compatibility
                "resource_group": rg_name,  # Self-reference
            }

    return list(rg_map.values())
```

**Modified `emit()` method** (lines 185-203):
```python
# Extract and generate resource group resources
logger.info("Extracting resource groups from discovered resources")
rg_resources = self._extract_resource_groups(graph.resources)
logger.info(f"Found {len(rg_resources)} unique resource groups")

# Add RG resources to the available resources index
for rg_resource in rg_resources:
    rg_name_sanitized = self._sanitize_terraform_name(rg_resource["name"])
    if "azurerm_resource_group" not in self._available_resources:
        self._available_resources["azurerm_resource_group"] = set()
    self._available_resources["azurerm_resource_group"].add(rg_name_sanitized)

# Prepend RG resources to the resource list for dependency analysis
all_resources = rg_resources + graph.resources

# Analyze dependencies and sort resources by tier
logger.info("Analyzing resource dependencies and calculating tiers")
analyzer = DependencyAnalyzer()
resource_dependencies = analyzer.analyze(all_resources)
```

**Modified `_convert_resource()` method** (lines 387-398):
```python
# Resource groups don't have a resource_group_name field
if azure_type == "Microsoft.Resources/resourceGroups":
    resource_config = {
        "name": resource_name,
        "location": location,
    }
else:
    resource_config = {
        "name": resource_name,
        "location": location,
        "resource_group_name": resource.get("resource_group", "default-rg"),
    }
```

### 2. dependency_analyzer.py

**Modified `_extract_dependencies()` method** (lines 145-197):
```python
def _extract_dependencies(self, resource: Dict[str, Any]) -> Set[str]:
    """Extract explicit dependencies for a resource.

    This identifies resources that must exist before this one can be created.

    Args:
        resource: Resource dictionary

    Returns:
        Set of Terraform resource references
    """
    dependencies = set()

    # Add resource group dependency for all non-RG resources
    resource_type = resource.get("type", "")

    # Normalize type names for Azure AD resources
    if resource_type.lower() in ("user", "aaduser"):
        resource_type = "Microsoft.Graph/users"
    elif resource_type.lower() in ("group", "aadgroup", "identitygroup"):
        resource_type = "Microsoft.Graph/groups"
    elif resource_type.lower() == "serviceprincipal":
        resource_type = "Microsoft.Graph/servicePrincipals"
    elif resource_type.lower() == "managedidentity":
        resource_type = "Microsoft.ManagedIdentity/managedIdentities"

    # Azure AD resources don't have resource groups
    azure_ad_types = {
        "Microsoft.AAD/User",
        "Microsoft.AAD/Group",
        "Microsoft.AAD/ServicePrincipal",
        "Microsoft.Graph/users",
        "Microsoft.Graph/groups",
        "Microsoft.Graph/servicePrincipals",
    }

    if resource_type != "Microsoft.Resources/resourceGroups" and resource_type not in azure_ad_types:
        # Try both field names (resource_group and resourceGroup)
        rg_name = resource.get("resource_group") or resource.get("resourceGroup")
        if rg_name:
            # Sanitize RG name for Terraform reference
            rg_name_sanitized = self._sanitize_terraform_name(rg_name)
            terraform_ref = f"azurerm_resource_group.{rg_name_sanitized}"
            dependencies.add(terraform_ref)
            logger.debug(f"Added RG dependency for {resource.get('name', 'unknown')}: {terraform_ref}")

    # TODO: Extract additional explicit dependencies from properties
    # - VNets for subnets
    # - Subnets for NICs
    # - NICs for VMs
    # - Storage accounts for VM diagnostics

    return dependencies
```

## Generated Configuration

### Resource Groups at Tier 0
- **48 Resource Groups** extracted and generated
- All assigned to Tier 0 (highest priority)
- Example:
```json
{
  "azurerm_resource_group": {
    "atevet12_Lab": {
      "name": "atevet12-Lab",
      "location": "westus3"
    }
  }
}
```

### Depends_on Attributes
- **295 resources** have `depends_on` attributes
- All reference their parent Resource Group
- Example:
```json
{
  "azurerm_network_security_group": {
    "atevet12_bastion_nsg": {
      "name": "atevet12-bastion-nsg",
      "location": "westus3",
      "resource_group_name": "default-rg",
      "depends_on": ["azurerm_resource_group.default_rg"]
    }
  }
}
```

## Terraform Plan Results

- **Resources to add:** 347
  - 48 Resource Group resources
  - 299 other resources
- **Resources to change:** 0
- **Resources to destroy:** 0
- **Plan Status:** ✅ Success (no "undeclared resource" errors)

## Deployment Observations

### Initial Progress (first 30 seconds)
1. ✅ Resource Groups creating in parallel at Tier 0
   - AttackBotRG, RESEARCH1, MAIDAP, SimuLand, etc.
   - Completing in ~10-11 seconds each

2. ✅ Dependent resources starting AFTER RG completion
   - `azurerm_key_vault.AttackBotKV` started after AttackBotRG completed
   - `azurerm_key_vault.red_ai` started after rg_adapt_ai completed
   - `azurerm_storage_account.stadaptaieas670410800455` started after s003rgtest completed

3. ✅ No ResourceGroupNotFound errors observed

### Expected vs ITERATION 12
- **ITERATION 12:** 19.1% fidelity (57/299 resources)
  - Only SSH keys succeeded (no RG dependency)
  - 242 ResourceGroupNotFound errors

- **ITERATION 13 (expected):** 80-90% fidelity
  - RGs created first
  - Dependent resources can find their RGs
  - Only failures expected: already-exists conflicts, invalid configurations

## Technical Details

### Dependency Graph Behavior
- Terraform builds dependency graph from `depends_on` and resource references
- Resources with no dependencies (Tier 0 RGs) create in parallel
- Resources with dependencies wait for parent completion
- Proper dependency chains ensure correct ordering

### Resource Extraction Logic
- Scans all 557 discovered resources
- Extracts unique resource group names
- Deduplicates by RG name
- Assigns location from first resource in each RG
- Generates 48 unique RG resources

### Field Name Compatibility
- Handles both `resource_group` and `resourceGroup` field names
- Handles both `subscription_id` and `subscriptionId` field names
- Ensures compatibility with Neo4j graph property variations

## Next Steps

1. ✅ Deployment in progress (background task)
2. ⏸️ Wait for deployment completion
3. ⏸️ Measure deployment fidelity
4. ⏸️ Analyze any remaining errors
5. ⏸️ Document ITERATION 13 results
6. ⏸️ Plan ITERATION 14 if needed

## Success Criteria

- [ ] Deployment completes without ResourceGroupNotFound errors
- [ ] Fidelity > 80% (target: 80-90%)
- [ ] RG resources successfully created
- [ ] Dependent resources successfully created
- [ ] Terraform state reflects successful deployments

## Lessons Learned

1. **JSON key ordering is meaningless** - Terraform uses dependency graph, not file order
2. **Explicit resources required** - Can't use `depends_on` for implicit resources
3. **Dependency analysis must include RG extraction** - RGs must be part of the resource set
4. **Proper tier assignment** - RGs at Tier 0 ensures correct ordering
5. **Field name flexibility** - Must handle property name variations from Neo4j
