# IAC Future Work Specifications

This document specifies the remaining TODO items from Issue #738 that require more complex implementation. Each item includes clear requirements and implementation guidance for future development.

## Completed TODOs

The following TODOs have been implemented in this PR:

- **TODO #4**: Subscription ID Resolution (`cli_handler.py:1314`) ✅
- **TODO #2**: Threshold Checking (`property_validation/cli.py:301`) ✅
- **TODO #5**: PR Checker Real Analysis (`property_validation/ci/pr_checker.py:122`) ✅

## Remaining Future Work

### TODO #1: Property Validation HTML Report Generation

**File**: `src/iac/property_validation/cli.py:214`
**Status**: Stub implementation with basic HTML template
**Complexity**: Medium

**Current State**:
- Basic HTML structure exists
- Shows placeholder "Report generation in progress..."
- No actual metrics or visualizations

**Requirements**:
1. Handler-level coverage metrics display
2. Visual charts/graphs for coverage trends
3. Detailed gap analysis tables with criticality highlighting
4. Color-coded status indicators (green=passed, red=failed, yellow=warning)
5. Drill-down capability to see specific gaps per handler
6. Export-friendly format for CI/CD integration

**Implementation Approach**:
```python
def generate_report(output_path: str = "coverage_report.html") -> int:
    """Generate comprehensive HTML coverage report."""
    # 1. Run validate_handler() for all handlers to get metrics
    # 2. Generate HTML with:
    #    - Summary section (overall coverage, total gaps)
    #    - Handler breakdown table
    #    - Gap details (grouped by criticality)
    #    - Charts using Chart.js or similar
    # 3. Use templates for consistent styling
    # 4. Write to output_path
```

**Dependencies**:
- Reuse validation logic from `validate_handler()`
- Consider lightweight charting library (Chart.js, Plotly)
- Template engine (Jinja2) for clean HTML generation

**Estimated Effort**: 2-4 hours

---

### TODO #3: KeyVault Soft-Delete Handler

**File**: `src/iac/keyvault_handler.py`
**Status**: Stub returning no conflicts
**Complexity**: High

**Current State**:
- Class structure exists with method signature
- Returns empty dict (no conflicts detected)
- Warning logged about stub implementation

**Requirements**:
1. Query Azure for soft-deleted Key Vaults in target subscription
2. Detect naming conflicts with soft-deleted vaults
3. Optionally purge soft-deleted vaults if `auto_purge=True`
4. Return name mapping for conflicts (old_name -> new_name)
5. Handle Azure API authentication and rate limiting
6. Support location filtering to reduce API calls

**Implementation Approach**:
```python
class KeyVaultHandler:
    def handle_vault_conflicts(
        self,
        vault_names: List[str],
        subscription_id: str,
        location: Optional[str] = None,
        auto_purge: bool = False,
    ) -> Dict[str, str]:
        """Check for Key Vault conflicts and optionally resolve them."""
        # 1. Create KeyVaultManagementClient with credential
        # 2. List soft-deleted vaults: client.vaults.list_deleted()
        # 3. Filter by location if specified
        # 4. Check each vault_name against soft-deleted list
        # 5. If auto_purge:
        #    - Purge conflicting vaults: client.vaults.begin_purge_deleted_vault()
        #    - Wait for purge to complete (async operation)
        # 6. If not auto_purge:
        #    - Generate unique name with suffix
        #    - Add to name_mappings dict
        # 7. Return name_mappings
```

**Azure SDK Reference**:
```python
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = KeyVaultManagementClient(credential, subscription_id)

# List soft-deleted vaults
deleted_vaults = client.vaults.list_deleted()
for vault in deleted_vaults:
    print(f"Soft-deleted: {vault.name} in {vault.properties.location}")

# Purge soft-deleted vault
client.vaults.begin_purge_deleted_vault(
    vault_name="my-vault",
    location="eastus"
).result()  # Wait for completion
```

**Dependencies**:
- `azure-mgmt-keyvault` package
- Credential with permissions: `Microsoft.KeyVault/vaults/write`, `Microsoft.KeyVault/locations/deletedVaults/purge/action`
- Async operation handling (purge takes 10-30 seconds)

**Edge Cases**:
- Vault soft-deleted in different location
- Multiple vaults with same name across locations
- Purge operation timeout/failure
- Insufficient permissions for purge

**Estimated Effort**: 4-6 hours
**Risk**: Azure API integration, requires testing with real Azure subscription

---

### ~~TODO #6: Dependency Extraction Enhancement~~ ✅ COMPLETED

**File**: `src/iac/dependency_analyzer.py:217-267`
**Status**: ✅ Implemented - All dependency types now extracted
**Complexity**: Medium
**Completed**: 2026-01-26 (Issue #324)

**Current State**:
- Resource group dependencies work correctly
- Placeholder comment for additional dependency types
- Method `_extract_dependencies()` returns Set[str]

**Requirements**:
1. Extract VNet dependencies for subnets
2. Extract subnet dependencies for NICs
3. Extract NIC dependencies for VMs
4. Extract storage account dependencies for VM diagnostics
5. Maintain existing RG dependency logic

**Implementation Approach**:
```python
def _extract_dependencies(self, resource: Dict[str, Any]) -> Set[str]:
    """Extract explicit dependencies for a resource."""
    dependencies = set()
    resource_type = resource.get("type", "")
    properties = resource.get("properties", {})

    # Existing RG dependency logic (keep)
    if resource_type != "Microsoft.Resources/resourceGroups":
        # ... RG logic ...

    # NEW: VNet -> Subnet dependency
    if resource_type == "Microsoft.Network/subnets":
        vnet_name = self._extract_vnet_name_from_subnet(resource)
        if vnet_name:
            safe_vnet = self._sanitize_terraform_name(vnet_name)
            dependencies.add(f"azurerm_virtual_network.{safe_vnet}")

    # NEW: Subnet -> NIC dependency
    if resource_type == "Microsoft.Network/networkInterfaces":
        subnet_id = properties.get("ipConfigurations", [{}])[0].get("subnet", {}).get("id", "")
        if subnet_id:
            subnet_name = self._extract_resource_name_from_id(subnet_id)
            safe_subnet = self._sanitize_terraform_name(subnet_name)
            dependencies.add(f"azurerm_subnet.{safe_subnet}")

    # NEW: NIC -> VM dependency
    if resource_type == "Microsoft.Compute/virtualMachines":
        nic_ids = properties.get("networkProfile", {}).get("networkInterfaces", [])
        for nic_ref in nic_ids:
            nic_id = nic_ref.get("id", "")
            if nic_id:
                nic_name = self._extract_resource_name_from_id(nic_id)
                safe_nic = self._sanitize_terraform_name(nic_name)
                dependencies.add(f"azurerm_network_interface.{safe_nic}")

    # NEW: Storage Account -> VM diagnostics dependency
    if resource_type == "Microsoft.Compute/virtualMachines":
        diagnostics = properties.get("diagnosticsProfile", {})
        storage_uri = diagnostics.get("bootDiagnostics", {}).get("storageUri", "")
        if storage_uri:
            # Extract storage account name from URI: https://<name>.blob.core.windows.net/
            storage_name = storage_uri.split("//")[1].split(".")[0]
            safe_storage = self._sanitize_terraform_name(storage_name)
            dependencies.add(f"azurerm_storage_account.{safe_storage}")

    return dependencies

def _extract_resource_name_from_id(self, resource_id: str) -> str:
    """Extract resource name from Azure resource ID."""
    # Azure ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
    parts = resource_id.split("/")
    return parts[-1] if parts else ""
```

**Dependencies**:
- No new packages required
- Must handle malformed resource IDs gracefully
- Existing `_sanitize_terraform_name()` method works correctly

**Edge Cases**:
- Missing properties in resource dictionary
- Malformed Azure resource IDs
- Cross-resource-group references
- Optional dependencies (NIC can exist without VM)

**Estimated Effort**: 3-4 hours

**Implementation Summary**:
✅ Added 4 new dependency extraction methods:
1. `_extract_vnet_name_from_subnet()` - Extracts VNet from subnet resource ID
2. `_extract_subnet_ids_from_nic()` - Extracts subnets from NIC IP configurations
3. `_extract_nic_ids_from_vm()` - Extracts NICs from VM network profile
4. `_extract_storage_from_diagnostics()` - Extracts storage account from VM diagnostics URI

✅ Updated `_extract_dependencies()` to add 4 new dependency types:
- VNet → Subnet (line 217)
- Subnet → NIC (line 228)
- NIC → VM (line 242)
- Storage Account → VM diagnostics (line 256)

✅ Comprehensive test coverage: 24 tests in `tests/iac/test_dependency_analyzer_resource_deps.py`
- VNet/Subnet: 5 tests (valid ID, hyphenated names, missing ID, malformed ID, fallback)
- Subnet/NIC: 5 tests (single IP config, multiple configs, no configs, empty ID, hyphenated)
- NIC/VM: 5 tests (single NIC, multiple NICs, no profile, empty ID, hyphenated)
- Storage/VM: 5 tests (valid URI, hyphenated, no profile, empty URI, malformed URI)
- Combined: 2 tests (VM with all deps, full dependency chain)
- Helper methods: 2 tests (resource name extraction, storage extraction)

✅ All tests passing, no existing functionality broken.

---

### TODO #7: Load Balancer Enhancement

**File**: `src/iac/emitters/terraform/handlers/network/load_balancer.py:66`
**Status**: Basic LB emission only
**Complexity**: High

**Current State**:
- Emits `azurerm_lb` resource with SKU
- Does NOT emit: frontend IPs, backend pools, probes, rules
- TODO comment lists missing components

**Requirements**:
1. Extract and emit frontend_ip_configuration blocks
2. Emit backend_address_pool as separate resources
3. Emit probe blocks as separate resources
4. Emit lb_rule blocks as separate resources
5. Maintain existing basic LB functionality
6. Handle dependencies between LB components

**Implementation Approach**:
```python
class LoadBalancerHandler(ResourceHandler):
    def emit(self, resource, context):
        # Existing: Emit azurerm_lb base resource
        lb_config = self._build_base_lb_config(resource)

        # NEW: Extract frontend IP configurations
        frontend_ips = self._extract_frontend_ips(resource)
        lb_config["frontend_ip_configuration"] = frontend_ips

        yield ("azurerm_lb", safe_name, lb_config)

        # NEW: Emit backend address pools
        backend_pools = self._extract_backend_pools(resource)
        for pool in backend_pools:
            pool_name = self.sanitize_name(pool["name"])
            pool_config = {
                "name": pool["name"],
                "loadbalancer_id": f"${{azurerm_lb.{safe_name}.id}}",
            }
            yield ("azurerm_lb_backend_address_pool", pool_name, pool_config)

        # NEW: Emit health probes
        probes = self._extract_probes(resource)
        for probe in probes:
            probe_name = self.sanitize_name(probe["name"])
            probe_config = {
                "name": probe["name"],
                "loadbalancer_id": f"${{azurerm_lb.{safe_name}.id}}",
                "protocol": probe.get("protocol", "Tcp"),
                "port": probe.get("port"),
                "interval_in_seconds": probe.get("intervalInSeconds", 15),
                "number_of_probes": probe.get("numberOfProbes", 2),
            }
            yield ("azurerm_lb_probe", probe_name, probe_config)

        # NEW: Emit load balancing rules
        rules = self._extract_rules(resource)
        for rule in rules:
            rule_name = self.sanitize_name(rule["name"])
            rule_config = {
                "name": rule["name"],
                "loadbalancer_id": f"${{azurerm_lb.{safe_name}.id}}",
                "frontend_ip_configuration_name": rule.get("frontendIPConfiguration"),
                "backend_address_pool_id": f"${{azurerm_lb_backend_address_pool.{pool_name}.id}}",
                "probe_id": f"${{azurerm_lb_probe.{probe_name}.id}}",
                "protocol": rule.get("protocol", "Tcp"),
                "frontend_port": rule.get("frontendPort"),
                "backend_port": rule.get("backendPort"),
            }
            yield ("azurerm_lb_rule", rule_name, rule_config)
```

**Terraform Resource Structure**:
```hcl
resource "azurerm_lb" "example" {
  name                = "example-lb"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.example.name
  sku                 = "Standard"

  frontend_ip_configuration {
    name                 = "public-ip"
    public_ip_address_id = azurerm_public_ip.example.id
  }
}

resource "azurerm_lb_backend_address_pool" "example" {
  name            = "backend-pool"
  loadbalancer_id = azurerm_lb.example.id
}

resource "azurerm_lb_probe" "example" {
  name            = "http-probe"
  loadbalancer_id = azurerm_lb.example.id
  protocol        = "Http"
  port            = 80
  request_path    = "/health"
}

resource "azurerm_lb_rule" "example" {
  name                           = "http-rule"
  loadbalancer_id                = azurerm_lb.example.id
  frontend_ip_configuration_name = "public-ip"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.example.id]
  probe_id                       = azurerm_lb_probe.example.id
  protocol                       = "Tcp"
  frontend_port                  = 80
  backend_port                   = 80
}
```

**Dependencies**:
- Must emit multiple resources from single handler (change handler return type or use generator)
- Dependency ordering: LB → Backend Pools → Probes → Rules
- Handle missing properties gracefully (not all LBs have all components)

**Edge Cases**:
- LB without backend pools (valid for some scenarios)
- Multiple frontend IPs
- NAT rules vs load balancing rules
- Internal vs external load balancers

**Estimated Effort**: 6-8 hours
**Risk**: Complex nested Azure properties, Terraform resource interdependencies

---

### TODO #8: KeyVault Identity Mapping

**File**: `src/iac/translators/keyvault_translator.py`
**Status**: Phase 3 TODO comment
**Complexity**: Medium-High

**Current State**:
- Phase 1-2 complete (basic translation working)
- Comment indicates Phase 3 needed: load and parse identity mapping file
- Related to cross-tenant deployment feature

**Requirements**:
1. Load identity mapping JSON file (if provided)
2. Parse mappings for users, groups, service principals
3. Translate source tenant identities to target tenant identities
4. Handle missing mappings gracefully (warn or error based on strict_mode)
5. Integrate with existing KeyVault access policy translation

**Implementation Approach**:
```python
class KeyVaultTranslator:
    def translate_access_policies(
        self,
        access_policies: List[Dict],
        identity_mapping_file: Optional[Path] = None,
        strict_mode: bool = False
    ) -> List[Dict]:
        """Translate access policies for cross-tenant deployment."""
        # Phase 3: Load identity mapping
        identity_map = {}
        if identity_mapping_file and identity_mapping_file.exists():
            with open(identity_mapping_file) as f:
                mapping_data = json.load(f)
                identity_map = self._build_identity_lookup(mapping_data)

        translated_policies = []
        for policy in access_policies:
            source_object_id = policy.get("objectId")

            # Translate object ID using mapping
            if source_object_id in identity_map:
                target_object_id = identity_map[source_object_id]
                policy["objectId"] = target_object_id
                translated_policies.append(policy)
            elif strict_mode:
                raise ValueError(f"Missing identity mapping for {source_object_id}")
            else:
                logger.warning(f"No mapping for {source_object_id}, using original")
                translated_policies.append(policy)

        return translated_policies

    def _build_identity_lookup(self, mapping_data: Dict) -> Dict[str, str]:
        """Build source_id -> target_id lookup from mapping file."""
        lookup = {}

        # Map users
        for user_mapping in mapping_data.get("users", []):
            lookup[user_mapping["source_id"]] = user_mapping["target_id"]

        # Map groups
        for group_mapping in mapping_data.get("groups", []):
            lookup[group_mapping["source_id"]] = group_mapping["target_id"]

        # Map service principals
        for sp_mapping in mapping_data.get("service_principals", []):
            lookup[sp_mapping["source_id"]] = sp_mapping["target_id"]

        return lookup
```

**Identity Mapping File Format** (JSON):
```json
{
  "users": [
    {
      "source_id": "aaaa-bbbb-cccc-dddd",
      "source_upn": "user@source.com",
      "target_id": "1111-2222-3333-4444",
      "target_upn": "user@target.com"
    }
  ],
  "groups": [
    {
      "source_id": "eeee-ffff-gggg-hhhh",
      "source_name": "DevOps Team",
      "target_id": "5555-6666-7777-8888",
      "target_name": "DevOps Team"
    }
  ],
  "service_principals": [
    {
      "source_id": "iiii-jjjj-kkkk-llll",
      "source_name": "App Registration",
      "target_id": "9999-aaaa-bbbb-cccc",
      "target_name": "App Registration"
    }
  ]
}
```

**Dependencies**:
- JSON parsing (standard library)
- Integration with existing KeyVault translator
- Cross-tenant deployment feature (already exists)

**Edge Cases**:
- Missing mapping file (graceful fallback)
- Partial mappings (some identities mapped, others not)
- Invalid object IDs in mapping file
- Circular or duplicate mappings

**Estimated Effort**: 3-4 hours

---

## Implementation Priority

Based on complexity and value, recommended implementation order:

1. **TODO #6** (Dependency Extraction) - Medium complexity, high value
2. **TODO #1** (HTML Report) - Medium complexity, good UX improvement
3. **TODO #8** (Identity Mapping) - Medium-high complexity, completes cross-tenant feature
4. **TODO #3** (KeyVault Soft-Delete) - High complexity, Azure API integration
5. **TODO #7** (Load Balancer) - Highest complexity, complex Terraform structure

## Testing Recommendations

For each TODO implementation:

1. **Unit Tests**: Test extraction/parsing logic in isolation
2. **Integration Tests**: Test with real Azure resources (where applicable)
3. **End-to-End Tests**: Validate complete workflows (e.g., scan → analyze → report)
4. **Manual Testing**: Use `uvx --from git+<branch>` syntax per USER_PREFERENCES.md

## Related Documentation

- Azure SDK Documentation: https://docs.microsoft.com/en-us/python/api/overview/azure/
- Terraform Azure Provider: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs
- Property Validation System: `src/iac/property_validation/README.md`
- Cross-Tenant Deployment: See Issue #406

---

**Last Updated**: 2026-01-18
**Related Issue**: #738
**PR**: (to be added)
