# Cross-Resource Group Dependency Handling

## Overview

The Azure Tenant Grapher IaC generation system now supports cross-Resource Group (cross-RG) dependency detection and handling. This feature ensures that when generating Terraform configurations for multi-RG deployments, resources that reference resources in other Resource Groups are properly ordered for successful deployment.

## Problem Statement

When generating Terraform IaC for Azure resources across multiple Resource Groups, dependencies can cross RG boundaries. For example:
- A VM in `RG-Compute` might reference a VNet in `RG-Network`
- A Storage Account in `RG-Data` might be connected to a Private Endpoint in `RG-Network`
- An Application in `RG-Apps` might reference a Key Vault in `RG-Shared`

Without tracking these cross-RG dependencies, Terraform deployments can fail if:
1. Resource Groups are deployed in the wrong order
2. Referenced resources don't exist yet when a resource tries to reference them
3. RG structure changes break existing references

## Features

### 1. Cross-RG Dependency Detection

The system automatically detects when a resource in one Resource Group references a resource in a different Resource Group.

**Example**:
```python
from src.iac.dependency_analyzer import DependencyAnalyzer

analyzer = DependencyAnalyzer()

# Analyze resources from multiple RGs
resources = [
    {"name": "vm1", "type": "Microsoft.Compute/virtualMachines",
     "resource_group": "rg-compute", "vnet_id": "/subscriptions/.../rg-network/..."},
    {"name": "vnet1", "type": "Microsoft.Network/virtualNetworks",
     "resource_group": "rg-network"}
]

# Get cross-RG dependencies
cross_rg_deps = analyzer.get_cross_rg_dependencies(resources)

# Output: [ResourceGroupDependency(source_rg='rg-compute',
#                                   target_rg='rg-network',
#                                   dependency_count=1,
#                                   resources=['vm1'])]
```

### 2. Deployment Ordering

The system provides recommended deployment order that respects cross-RG dependencies.

**Example**:
```python
# Get deployment order for Resource Groups
deployment_order = analyzer.get_rg_deployment_order(resources)

# Output: ['rg-network', 'rg-compute']
# Network RG must be deployed before Compute RG
```

**Use Case**:
When deploying via Terraform, you can use this ordering to:
1. Generate separate Terraform configurations per RG
2. Deploy RGs in the correct order
3. Use Terraform remote state to reference resources across RGs

### 3. Broken Reference Warnings

The system warns when RG structure changes might break existing references.

**Example**:
```python
# Check if proposed RG changes would break dependencies
warnings = analyzer.check_broken_references(current_resources, proposed_rg_structure)

# Output: [
#   "Warning: Moving vm1 from rg-compute to rg-apps would break reference to vnet1 in rg-network"
# ]
```

### 4. Resource Grouping by Dependencies

The system can group resources by their cross-RG dependency relationships to help visualize and understand coupling.

**Example**:
```python
# Group resources by cross-RG dependencies
groups = analyzer.group_by_cross_rg_deps(resources)

# Output: {
#   'rg-network': {'dependencies': [], 'dependents': ['rg-compute', 'rg-apps']},
#   'rg-compute': {'dependencies': ['rg-network'], 'dependents': []},
#   'rg-apps': {'dependencies': ['rg-network'], 'dependents': []}
# }
```

## Implementation Details

### Data Structures

**ResourceGroupDependency**:
```python
@dataclass
class ResourceGroupDependency:
    """Represents a dependency relationship between two Resource Groups."""

    source_rg: str  # RG that has the dependency
    target_rg: str  # RG being depended upon
    dependency_count: int  # Number of dependencies from source to target
    resources: List[str]  # List of resource names with dependencies
```

### Detection Algorithm

1. **Extract Resource RG**: For each resource, identify its Resource Group
2. **Find References**: Scan resource properties for references to other resources (via Azure Resource IDs)
3. **Cross-RG Check**: Compare resource's RG with referenced resource's RG
4. **Track Dependencies**: Record cross-RG dependency relationship

### Deployment Ordering Algorithm

1. **Build Dependency Graph**: Create graph of RG → RG dependencies
2. **Topological Sort**: Sort RGs topologically (dependencies first)
3. **Cycle Detection**: Detect and report circular dependencies
4. **Return Order**: Return ordered list of RGs for deployment

## Usage in Terraform Generation

When generating Terraform IaC:

### Single Configuration File

```python
# Generate single Terraform config with proper depends_on
analyzer.analyze(resources)  # Automatically handles cross-RG dependencies
```

### Separate Configurations Per RG

```python
# Generate separate configs for each RG
deployment_order = analyzer.get_rg_deployment_order(resources)

for rg in deployment_order:
    rg_resources = [r for r in resources if r['resource_group'] == rg]
    generate_terraform_for_rg(rg, rg_resources)
```

### Terraform Remote State References

```python
# For cross-RG references, use remote state data sources
# Example: VM in rg-compute referencing VNet in rg-network

# rg-network/outputs.tf
output "vnet_id" {
  value = azurerm_virtual_network.vnet1.id
}

# rg-compute/main.tf
data "terraform_remote_state" "network" {
  backend = "azurerm"
  config = {
    resource_group_name  = "terraform-state-rg"
    storage_account_name = "tfstate"
    container_name      = "rg-network"
    key                 = "terraform.tfstate"
  }
}

resource "azurerm_linux_virtual_machine" "vm1" {
  # Reference VNet from remote state
  network_interface_ids = [azurerm_network_interface.nic1.id]
}

resource "azurerm_network_interface" "nic1" {
  subnet_id = data.terraform_remote_state.network.outputs.vnet_id
}
```

## Configuration

No additional configuration required - cross-RG dependency handling is automatically enabled in the `DependencyAnalyzer`.

## Testing

Comprehensive tests cover:
- Cross-RG dependency detection for common Azure resource types
- Deployment ordering with simple and complex dependency graphs
- Cycle detection in cross-RG dependencies
- Broken reference warnings
- Edge cases (single RG, no dependencies, circular dependencies)

Run tests:
```bash
pytest tests/iac/test_dependency_analyzer_cross_rg.py
```

## Limitations

1. **Detection Scope**: Only detects explicit references (via Azure Resource IDs) - doesn't detect implicit dependencies
2. **Terraform Backend**: Assumes user configures Terraform remote state backend for cross-RG references
3. **Manual Deployment**: User must manually deploy RGs in recommended order when using separate configs

## Future Enhancements

1. **Automatic Terraform Backend Config**: Generate Terraform backend configuration automatically
2. **Implicit Dependency Detection**: Detect implicit dependencies (e.g., via tags, naming conventions)
3. **Multi-Subscription Support**: Extend to track cross-subscription dependencies
4. **Dependency Visualization**: Generate visual dependency graph for RGs

## References

- Issue #314: GAP-018 - Cross-RG Dependency Handling
- Gap Catalog: `demo_run/GAP_ANALYSIS_CATALOG.md`
- Related: `src/iac/dependency_analyzer.py` (tier-based ordering)
- Related: `src/iac/validators/dependency_validator.py` (Terraform validation)
