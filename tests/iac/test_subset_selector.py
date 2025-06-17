from src.iac.subset import SubsetFilter, SubsetSelector
from src.iac.traverser import TenantGraph


def make_graph():
    # Simple graph: A depends on B, B depends on C, D is isolated
    resources = [
        {
            "id": "A",
            "name": "resA",
            "type": "Microsoft.Storage/storageAccounts",
            "dependsOn": ["B"],
        },
        {
            "id": "B",
            "name": "resB",
            "type": "Microsoft.Storage/storageAccounts",
            "dependsOn": ["C"],
        },
        {"id": "C", "name": "resC", "type": "Microsoft.Storage/storageAccounts"},
        {"id": "D", "name": "resD", "type": "Microsoft.Storage/storageAccounts"},
    ]
    relationships = [
        {"source": "A", "target": "B", "type": "dependsOn"},
        {"source": "B", "target": "C", "type": "dependsOn"},
    ]
    return TenantGraph(resources=resources, relationships=relationships)


def test_subset_by_node_id_closure():
    graph = make_graph()
    selector = SubsetSelector()
    # Select only A, should pull in B and C due to dependsOn closure
    filt = SubsetFilter(node_ids=["A"])
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    assert ids == {"A", "B", "C"}


def test_subset_by_type():
    graph = make_graph()
    selector = SubsetSelector()
    # Select by type, should get all storage accounts
    filt = SubsetFilter(resource_types=["Microsoft.Storage/storageAccounts"])
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    assert ids == {"A", "B", "C", "D"}


def test_subset_by_label():
    graph = make_graph()
    # Add labels to resources
    for r in graph.resources:
        if r["id"] == "A":
            r["labels"] = ["prod"]
        if r["id"] == "D":
            r["labels"] = ["test"]
    selector = SubsetSelector()
    filt = SubsetFilter(labels=["prod"])
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Only A, plus closure (B, C)
    assert ids == {"A", "B", "C"}


def test_empty_filter_returns_all():
    graph = make_graph()
    selector = SubsetSelector()
    filt = SubsetFilter()
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    assert ids == {"A", "B", "C", "D"}
