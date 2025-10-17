"""
Unit tests for resource group filtering in SubsetFilter.

Tests the new resource_group predicate functionality added in Issue #277.
"""

from src.iac.subset import SubsetFilter, SubsetSelector
from src.iac.traverser import TenantGraph


def test_parse_resource_group_single():
    """Test parsing single resource group."""
    filter_obj = SubsetFilter.parse("resourceGroup=SimuLand")
    assert filter_obj.resource_group == ["SimuLand"]


def test_parse_resource_group_multiple():
    """Test parsing multiple resource groups."""
    filter_obj = SubsetFilter.parse("resourceGroup=RG1,RG2")
    assert filter_obj.resource_group == ["RG1", "RG2"]


def test_parse_resource_group_case_insensitive():
    """Test that parsing is case-insensitive for the predicate name."""
    filter_obj = SubsetFilter.parse("RESOURCEGROUP=TestRG")
    assert filter_obj.resource_group == ["TestRG"]


def test_parse_resource_group_with_spaces():
    """Test parsing resource groups with spaces in names."""
    filter_obj = SubsetFilter.parse("resourceGroup=RG1, RG2 , RG3")
    assert filter_obj.resource_group == ["RG1", "RG2", "RG3"]


def test_selector_resource_group_filter():
    """Test resource group filtering in selector."""
    # Create test graph with resources in different RGs
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/OtherRG/providers/Microsoft.Compute/virtualMachines/VM2",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM2",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
        },
    ]
    graph = TenantGraph(resources=resources, relationships=[])

    filter_obj = SubsetFilter(resource_group=["SimuLand"])
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    assert len(result.resources) == 2
    assert all("SimuLand" in r["id"] for r in result.resources)
    # Verify the correct resources are included
    result_ids = {r["id"] for r in result.resources}
    assert (
        "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1"
        in result_ids
    )
    assert (
        "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Network/virtualNetworks/vnet1"
        in result_ids
    )


def test_selector_multiple_resource_groups():
    """Test filtering with multiple resource groups."""
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/RG1/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/RG2/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/RG3/providers/Microsoft.Storage/storageAccounts/sa1",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sa1",
        },
    ]
    graph = TenantGraph(resources=resources, relationships=[])

    filter_obj = SubsetFilter(resource_group=["RG1", "RG2"])
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    assert len(result.resources) == 2
    # Verify the correct resources are included
    result_ids = {r["id"] for r in result.resources}
    assert (
        "/subscriptions/sub1/resourceGroups/RG1/providers/Microsoft.Compute/virtualMachines/VM1"
        in result_ids
    )
    assert (
        "/subscriptions/sub1/resourceGroups/RG2/providers/Microsoft.Network/virtualNetworks/vnet1"
        in result_ids
    )


def test_selector_no_matching_resource_groups():
    """Test filtering with no matching resource groups."""
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/RG1/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
    ]
    graph = TenantGraph(resources=resources, relationships=[])

    filter_obj = SubsetFilter(resource_group=["NonExistentRG"])
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    assert len(result.resources) == 0


def test_selector_resource_group_excludes_non_rg_resources():
    """Test that resource group filter excludes resources without resourceGroups in ID."""
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
        {
            "id": "/subscriptions/sub1",
            "type": "Microsoft.Resources/subscriptions",
            "name": "sub1",
        },
        {
            "id": "/tenants/tenant1",
            "type": "Microsoft.Directory/tenants",
            "name": "tenant1",
        },
    ]
    graph = TenantGraph(resources=resources, relationships=[])

    filter_obj = SubsetFilter(resource_group=["SimuLand"])
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    assert len(result.resources) == 1
    assert (
        result.resources[0]["id"]
        == "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1"
    )


def test_selector_resource_group_no_dependency_closure():
    """Test that resource group filter does NOT perform dependency closure."""
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/OtherRG/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
        },
    ]
    # VM1 depends on vnet1
    relationships = [
        {
            "source": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "target": "/subscriptions/sub1/resourceGroups/OtherRG/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "DEPENDS_ON",
        }
    ]
    graph = TenantGraph(resources=resources, relationships=relationships)

    filter_obj = SubsetFilter(resource_group=["SimuLand"])
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    # Should only include resources in SimuLand, not dependencies
    assert len(result.resources) == 1
    assert (
        result.resources[0]["id"]
        == "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1"
    )


def test_selector_resource_group_with_relationships():
    """Test that relationships within the same resource group are preserved."""
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/OtherRG/providers/Microsoft.Storage/storageAccounts/sa1",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sa1",
        },
    ]
    relationships = [
        {
            "source": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "target": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "USES",
        },
        {
            "source": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "target": "/subscriptions/sub1/resourceGroups/OtherRG/providers/Microsoft.Storage/storageAccounts/sa1",
            "type": "USES",
        },
    ]
    graph = TenantGraph(resources=resources, relationships=relationships)

    filter_obj = SubsetFilter(resource_group=["SimuLand"])
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    # Should include both SimuLand resources
    assert len(result.resources) == 2
    # Should only include the relationship between SimuLand resources
    assert len(result.relationships) == 1
    assert (
        result.relationships[0]["target"]
        == "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Network/virtualNetworks/vnet1"
    )


def test_has_filters_with_resource_group():
    """Test that has_filters returns True when resource_group is set."""
    filter_obj = SubsetFilter(resource_group=["SimuLand"])
    selector = SubsetSelector()
    assert selector.has_filters(filter_obj) is True


def test_parse_and_apply_integration():
    """Integration test: parse filter string and apply to graph."""
    resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/SimuLand/providers/Microsoft.Compute/virtualMachines/VM1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "VM1",
        },
        {
            "id": "/subscriptions/sub1/resourceGroups/Production/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
        },
    ]
    graph = TenantGraph(resources=resources, relationships=[])

    # Parse filter string
    filter_obj = SubsetFilter.parse("resourceGroup=SimuLand")

    # Apply filter
    selector = SubsetSelector()
    result = selector.apply(graph, filter_obj)

    assert len(result.resources) == 1
    assert "SimuLand" in result.resources[0]["id"]
