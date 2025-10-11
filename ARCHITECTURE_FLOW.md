# VNet Overlap Detection - Architecture Flow Diagram

## High-Level System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Azure Tenant Grapher CLI                           │
│                    atg generate-iac --format terraform                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 1: Graph Traversal (GraphTraverser)                               │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  • Queries Neo4j for all :Resource nodes                       │    │
│  │  • Extracts properties (type, name, address_space, etc.)       │    │
│  │  • Returns TenantGraph with resources list                     │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Output: TenantGraph { resources: [ {...}, {...}, ... ] }               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 2: Transformation Engine (engine.py)                              │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  2a. Apply Subset Filters (if --subset-* flags provided)      │    │
│  │  2b. Apply Transformation Rules (rename, region, etc.)         │    │
│  └────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 3: VNet Address Space Validation ← CURRENT FOCUS                  │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  File: src/iac/engine.py (lines 148-177)                      │    │
│  │                                                                 │    │
│  │  if validate_address_spaces:                                   │    │
│  │      validator = AddressSpaceValidator()                       │    │
│  │      result = validator.validate_resources(resources)          │    │
│  │                                                                 │    │
│  │      if not result.is_valid:                                   │    │
│  │          for conflict in result.conflicts:                     │    │
│  │              logger.warning(conflict.message) ← ENHANCE THIS   │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Delegate to: AddressSpaceValidator                                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 3a: AddressSpaceValidator (validation/address_space_validator.py) │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  Detection Algorithm:                                          │    │
│  │                                                                 │    │
│  │  1. Extract all VNet resources from resource list             │    │
│  │     filter(type == "Microsoft.Network/virtualNetworks")        │    │
│  │                                                                 │    │
│  │  2. Build address space mapping                                │    │
│  │     vnet_networks = [                                          │    │
│  │         ("vnet1", ipaddress.ip_network("10.0.0.0/16")),       │    │
│  │         ("vnet2", ipaddress.ip_network("10.0.0.0/16")),       │    │
│  │         ("vnet3", ipaddress.ip_network("10.1.0.0/16")),       │    │
│  │     ]                                                           │    │
│  │                                                                 │    │
│  │  3. Check all pairs for overlaps (O(n²))                       │    │
│  │     for i in range(len(vnet_networks)):                        │    │
│  │         for j in range(i+1, len(vnet_networks)):               │    │
│  │             if network_a.overlaps(network_b):  ← Python stdlib │    │
│  │                 conflicts.append(...)                          │    │
│  │                                                                 │    │
│  │  4. Return ValidationResult with conflicts list                │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Output: ValidationResult {                                             │
│      is_valid: False,                                                   │
│      conflicts: [AddressSpaceConflict {...}, ...],                      │
│      vnets_checked: 5                                                   │
│  }                                                                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 4: IaC Emitter (emitters/terraform_emitter.py)                    │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  • Convert resources to Terraform HCL/JSON                     │    │
│  │  • Generate resource blocks, providers, etc.                   │    │
│  │  • Write main.tf.json to output directory                      │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Note: Generation continues EVEN IF conflicts detected                  │
│        (warnings are non-blocking)                                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────┐
│  Output: Generated IaC Files                                            │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  output/                                                       │    │
│  │  ├── main.tf.json                                              │    │
│  │  ├── vnet_conflict_report.md  ← NEW (if flag set)             │    │
│  │  └── .terraform/                                               │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Detailed: VNet Overlap Detection Flow

```
┌────────────────────────────────────────────────────────────────────┐
│  Input: TenantGraph.resources (from Neo4j)                         │
│  [                                                                  │
│    {                                                                │
│      "type": "Microsoft.Network/virtualNetworks",                  │
│      "name": "dtlatevet12_attack_vnet",                            │
│      "address_space": ["10.0.0.0/16"],                             │
│      "resourceGroup": "atevet12-Working",                          │
│      "location": "eastus"                                           │
│    },                                                               │
│    {                                                                │
│      "type": "Microsoft.Network/virtualNetworks",                  │
│      "name": "dtlatevet12_infra_vnet",                             │
│      "address_space": ["10.0.0.0/16"],  ← SAME AS ATTACK!          │
│      "resourceGroup": "atevet12-Working",                          │
│      "location": "eastus"                                           │
│    },                                                               │
│    { "type": "Microsoft.Storage/storageAccounts", ... },           │
│    { "type": "Microsoft.Compute/virtualMachines", ... }            │
│  ]                                                                  │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         v
┌────────────────────────────────────────────────────────────────────┐
│  AddressSpaceValidator.validate_resources()                        │
│                                                                     │
│  Step 1: Extract VNets                                             │
│  ──────────────────────                                            │
│  vnets = [r for r in resources                                     │
│            if r["type"] == "Microsoft.Network/virtualNetworks"]    │
│                                                                     │
│  Result: 2 VNets found                                             │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         v
┌────────────────────────────────────────────────────────────────────┐
│  Step 2: Parse Address Spaces                                      │
│  ────────────────────────────                                      │
│  vnet_networks = []                                                │
│  for vnet in vnets:                                                │
│      for address_space in vnet["address_space"]:                   │
│          network = ipaddress.ip_network(address_space)             │
│          vnet_networks.append((vnet["name"], network))             │
│                                                                     │
│  Result:                                                            │
│  [                                                                  │
│    ("dtlatevet12_attack_vnet", IPv4Network('10.0.0.0/16')),        │
│    ("dtlatevet12_infra_vnet", IPv4Network('10.0.0.0/16'))          │
│  ]                                                                  │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         v
┌────────────────────────────────────────────────────────────────────┐
│  Step 3: Check for Overlaps (Pairwise Comparison)                  │
│  ─────────────────────────────────────────────                     │
│  conflicts = []                                                     │
│  for i in range(len(vnet_networks)):              # i = 0          │
│      vnet_a, net_a = vnet_networks[i]             # attack_vnet    │
│      for j in range(i+1, len(vnet_networks)):     # j = 1          │
│          vnet_b, net_b = vnet_networks[j]         # infra_vnet     │
│                                                                     │
│          # Python ipaddress library method                          │
│          if net_a.overlaps(net_b):  ← TRUE!                        │
│              conflict = AddressSpaceConflict(                       │
│                  vnet_names=[vnet_a, vnet_b],                       │
│                  address_space=f"{net_a} overlaps {net_b}",        │
│                  severity="warning",                                │
│                  message="VNets 'attack_vnet' and 'infra_vnet'     │
│                           have overlapping address spaces"          │
│              )                                                       │
│              conflicts.append(conflict)                             │
│                                                                     │
│  Result: 1 conflict detected                                        │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         v
┌────────────────────────────────────────────────────────────────────┐
│  Step 4: Return ValidationResult                                    │
│  ───────────────────────────────                                   │
│  return ValidationResult(                                           │
│      is_valid=False,          ← Conflicts found!                   │
│      conflicts=[conflict],                                          │
│      warnings=[],                                                   │
│      vnets_checked=2,                                               │
│      auto_renumbered=[]       ← Empty unless auto-renumber enabled  │
│  )                                                                  │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         v
┌────────────────────────────────────────────────────────────────────┐
│  Back to engine.py: Log Warnings                                    │
│  ───────────────────────────────                                   │
│  if not validation_result.is_valid:                                │
│      logger.warning(                                                │
│          f"Address space validation found "                         │
│          f"{len(validation_result.conflicts)} conflicts"            │
│      )                                                               │
│      for conflict in validation_result.conflicts:                  │
│          # CURRENT (simple):                                        │
│          logger.warning(f"  - {conflict.message}")                 │
│                                                                     │
│          # PROPOSED (rich):                                         │
│          rich_msg = validator.format_conflict_warning(conflict)    │
│          logger.warning(rich_msg)                                   │
│                                                                     │
│  Continue with IaC generation... (non-blocking)                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Structures

### TenantGraph
```python
@dataclass
class TenantGraph:
    resources: List[Dict[str, Any]]        # From Neo4j
    relationships: List[Dict[str, Any]]    # From Neo4j
```

### VNet Resource (from Neo4j)
```python
{
    "id": "/subscriptions/.../virtualNetworks/vnet1",
    "type": "Microsoft.Network/virtualNetworks",
    "name": "dtlatevet12_attack_vnet",
    "address_space": ["10.0.0.0/16"],      # Key field for validation
    "resourceGroup": "atevet12-Working",
    "location": "eastus",
    "tags": {...},
    "properties": "{...}"
}
```

### AddressSpaceConflict
```python
@dataclass
class AddressSpaceConflict:
    vnet_names: List[str]           # ["vnet1", "vnet2"]
    address_space: str              # "10.0.0.0/16" or "10.0.0.0/16 overlaps 10.0.128.0/17"
    severity: str = "warning"       # Always "warning" for Phase 1
    message: str = ""               # Human-readable description
```

### ValidationResult
```python
@dataclass
class ValidationResult:
    is_valid: bool                          # False if conflicts found
    conflicts: List[AddressSpaceConflict]   # All detected conflicts
    warnings: List[str]                     # Additional warnings
    vnets_checked: int                      # Total VNets validated
    auto_renumbered: List[str]              # VNets that were auto-fixed (Phase 2)
```

## Enhancement Points (Issue #334)

### Point A: Rich Warning Formatter
```python
# Location: src/validation/address_space_validator.py

class AddressSpaceValidator:

    def format_conflict_warning(self, conflict: AddressSpaceConflict) -> str:
        """
        NEW METHOD - Issue #334

        Convert simple conflict object into rich multi-line warning
        with remediation guidance, impact explanation, and links.
        """
        lines = [
            "",
            "╔════════════════════════════════════════════╗",
            "║  VNet Address Space Conflict Detected     ║",
            "╚════════════════════════════════════════════╝",
            "",
            f"  VNets:     '{conflict.vnet_names[0]}' ↔ '{conflict.vnet_names[1]}'",
            f"  Conflict:  {conflict.address_space}",
            "",
            "  Impact:",
            "    • VNet peering will FAIL",
            "    • IP routing conflicts",
            "",
            "  Remediation:",
            "    1. Change to non-overlapping range",
            "    2. Use --auto-renumber-conflicts",
            "",
            "  Docs: https://learn.microsoft.com/.../virtual-network-peering",
            ""
        ]
        return "\n".join(lines)
```

### Point B: Conflict Report Generator
```python
# Location: src/validation/address_space_validator.py

class AddressSpaceValidator:

    def generate_conflict_report(
        self,
        validation_result: ValidationResult,
        output_path: Optional[Path] = None
    ) -> str:
        """
        NEW METHOD - Issue #334 Phase 2

        Generate detailed markdown report of all conflicts
        for documentation and debugging purposes.
        """
        markdown = [
            "# VNet Address Space Conflict Report",
            f"**Total VNets**: {validation_result.vnets_checked}",
            f"**Conflicts**: {len(validation_result.conflicts)}",
            "",
        ]

        for idx, conflict in enumerate(validation_result.conflicts, 1):
            markdown.extend([
                f"## Conflict {idx}",
                f"- VNets: {conflict.vnet_names}",
                f"- Address Space: {conflict.address_space}",
                f"- Impact: VNet peering will fail",
                "",
            ])

        report = "\n".join(markdown)

        if output_path:
            output_path.write_text(report)

        return report
```

### Point C: Engine Integration
```python
# Location: src/iac/engine.py (lines 148-177)

# CURRENT CODE:
if not validation_result.is_valid:
    logger.warning(f"Found {len(validation_result.conflicts)} conflicts")
    for conflict in validation_result.conflicts:
        logger.warning(f"  - {conflict.message}")  # Simple message

# PROPOSED CODE:
if not validation_result.is_valid:
    logger.warning(f"Found {len(validation_result.conflicts)} conflicts")
    for conflict in validation_result.conflicts:
        rich_message = validator.format_conflict_warning(conflict)  # Rich message
        logger.warning(rich_message)

    # Optional report generation
    if generate_conflict_report:
        report_path = out_dir / "vnet_conflict_report.md"
        validator.generate_conflict_report(validation_result, report_path)
```

## Python ipaddress Library - How Overlaps Work

```python
import ipaddress

# Example 1: Exact Duplicate
net1 = ipaddress.ip_network("10.0.0.0/16")    # 10.0.0.0 - 10.0.255.255 (65,536 IPs)
net2 = ipaddress.ip_network("10.0.0.0/16")    # 10.0.0.0 - 10.0.255.255 (65,536 IPs)

net1.overlaps(net2)  # True - complete overlap

# Example 2: Partial Overlap (Subnet Contained)
net1 = ipaddress.ip_network("10.0.0.0/16")    # 10.0.0.0 - 10.0.255.255
net2 = ipaddress.ip_network("10.0.128.0/17")  # 10.0.128.0 - 10.0.255.255 (half of net1)

net1.overlaps(net2)  # True - net2 is fully contained in net1

# Example 3: Partial Overlap (Intersection)
net1 = ipaddress.ip_network("10.0.0.0/23")    # 10.0.0.0 - 10.0.1.255
net2 = ipaddress.ip_network("10.0.1.0/24")    # 10.0.1.0 - 10.0.1.255

net1.overlaps(net2)  # True - net2's range intersects net1

# Example 4: No Overlap (Adjacent Ranges)
net1 = ipaddress.ip_network("10.0.0.0/16")    # 10.0.0.0 - 10.0.255.255
net2 = ipaddress.ip_network("10.1.0.0/16")    # 10.1.0.0 - 10.1.255.255

net1.overlaps(net2)  # False - no shared IPs

# Example 5: No Overlap (Different Private Ranges)
net1 = ipaddress.ip_network("10.0.0.0/16")     # 10.x private range
net2 = ipaddress.ip_network("172.16.0.0/16")   # 172.x private range

net1.overlaps(net2)  # False - completely different ranges
```

## Performance Characteristics

### Time Complexity

```
VNets: n
Comparisons: n(n-1)/2 = O(n²)

Example scenarios:
- 10 VNets: 45 comparisons
- 50 VNets: 1,225 comparisons
- 100 VNets: 4,950 comparisons

Each comparison is O(1) using Python's ipaddress library.

Total time: O(n²) but n is typically small (< 100 VNets per tenant)
Expected validation time: < 1 second for typical tenants
```

### Space Complexity

```
O(n) for storing vnet_networks list
O(k) for storing conflicts list (where k = number of conflicts)

Typical memory usage: negligible (< 1 MB)
```

## Integration with Existing Systems

### Neo4j Graph Schema
```
(:Resource {
    id: string,
    type: "Microsoft.Network/virtualNetworks",
    name: string,
    address_space: [string, ...],    ← Used by validator
    resourceGroup: string,
    location: string
})
```

### Terraform Output (main.tf.json)
```json
{
  "resource": {
    "azurerm_virtual_network": {
      "dtlatevet12_attack_vnet": {
        "name": "dtlatevet12_attack_vnet",
        "location": "eastus",
        "resource_group_name": "atevet12-Working",
        "address_space": ["10.0.0.0/16"]   ← Conflicts here!
      },
      "dtlatevet12_infra_vnet": {
        "name": "dtlatevet12_infra_vnet",
        "location": "eastus",
        "resource_group_name": "atevet12-Working",
        "address_space": ["10.0.0.0/16"]   ← Conflicts here!
      }
    }
  }
}
```

Note: Both VNets are generated despite conflict (non-blocking behavior).

## Summary

This architecture diagram shows:

1. **Existing Implementation**: Detection is already integrated (GAP-012)
2. **Enhancement Points**: Two new methods + minor engine changes
3. **Data Flow**: Clear path from Neo4j → Validation → IaC
4. **Non-Blocking**: Warnings don't stop IaC generation
5. **Extensibility**: Phase 2 auto-renumber already implemented

The minimal changes required make this a low-risk, high-value enhancement.

---

**For Full Details**: See `DESIGN_VNET_OVERLAP_DETECTION.md`
