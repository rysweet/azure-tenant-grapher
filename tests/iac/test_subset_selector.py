from datetime import datetime, timedelta

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


def make_graph_with_policy_and_tags():
    # Graph: E (noncompliant, prod), F (compliant, prod), G (noncompliant, test), H (created recently)
    now = datetime.utcnow()
    resources = [
        {
            "id": "E",
            "name": "resE",
            "type": "Microsoft.Compute/virtualMachines",
            "policyState": "noncompliant",
            "tags": {"env": "prod"},
            "createdAt": (now - timedelta(days=10)).isoformat(),
        },
        {
            "id": "F",
            "name": "resF",
            "type": "Microsoft.Compute/virtualMachines",
            "policyState": "compliant",
            "tags": {"env": "prod"},
            "createdAt": (now - timedelta(days=20)).isoformat(),
        },
        {
            "id": "G",
            "name": "resG",
            "type": "Microsoft.Compute/virtualMachines",
            "policyState": "noncompliant",
            "tags": {"env": "test"},
            "createdAt": (now - timedelta(days=30)).isoformat(),
        },
        {
            "id": "H",
            "name": "resH",
            "type": "Microsoft.Compute/virtualMachines",
            "createdAt": now.isoformat(),
        },
    ]
    relationships = []
    return TenantGraph(resources=resources, relationships=relationships)


def make_graph_with_closure():
    # I is a child of J (parent scope), I has diagnostics K, I has role assignment L
    resources = [
        {
            "id": "I",
            "name": "resI",
            "type": "Microsoft.Storage/storageAccounts",
            "parent_id": "J",
        },
        {"id": "J", "name": "resJ", "type": "Microsoft.Resources/resourceGroups"},
        {
            "id": "K",
            "name": "diagK",
            "type": "Microsoft.Insights/diagnosticSettings",
            "target_id": "I",
        },
        {
            "id": "L",
            "name": "roleL",
            "type": "Microsoft.Authorization/roleAssignments",
            "target_id": "I",
        },
    ]
    relationships = [
        {"source": "I", "target": "J", "type": "parent"},
        {"source": "K", "target": "I", "type": "diagnosticFor"},
        {"source": "L", "target": "I", "type": "roleAssignmentFor"},
    ]
    return TenantGraph(resources=resources, relationships=relationships)


def test_subset_policy_state_noncompliant():
    graph = make_graph_with_policy_and_tags()
    selector = SubsetSelector()
    filt = SubsetFilter()
    filt.policy_state = "noncompliant"
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Should select E and G (noncompliant)
    assert ids == {"E", "G"}


def test_subset_created_after():
    graph = make_graph_with_policy_and_tags()
    selector = SubsetSelector()
    recent_date = (datetime.utcnow() - timedelta(days=5)).isoformat()
    filt = SubsetFilter()
    filt.created_after = recent_date
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Should select H (created now)
    assert ids == {"H"}


def test_subset_tag_selector_env_prod():
    graph = make_graph_with_policy_and_tags()
    selector = SubsetSelector()
    filt = SubsetFilter()
    filt.tag_selector = {"env": "prod"}
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Should select E and F (env:prod)
    assert ids == {"E", "F"}


def test_subset_depth_limit():
    # A depends on B, B depends on C, D is isolated (from make_graph)
    graph = make_graph()
    selector = SubsetSelector()
    filt = SubsetFilter(node_ids=["A"])
    filt.depth = 1
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # With depth=1, should only include A and B (not C)
    assert ids == {"A", "B"}


def test_subset_includes_parent_scope():
    graph = make_graph_with_closure()
    selector = SubsetSelector()
    filt = SubsetFilter(node_ids=["I"])
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Should include I and its parent J
    assert "I" in ids and "J" in ids


def test_subset_includes_diagnostics():
    graph = make_graph_with_closure()
    selector = SubsetSelector()
    filt = SubsetFilter(node_ids=["I"])
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Should include I and its diagnostic K
    assert "I" in ids and "K" in ids


def test_subset_includes_role_assignments():
    graph = make_graph_with_closure()
    selector = SubsetSelector()
    filt = SubsetFilter(node_ids=["I"])
    filtered = selector.apply(graph, filt)
    ids = {r["id"] for r in filtered.resources}
    # Should include I and its role assignment L
    assert "I" in ids and "L" in ids
