from src.relationship_rules.network_rule import (
    CONNECTED_TO_PE,
    DNS_ZONE,
    PRIVATE_ENDPOINT,
    RESOLVES_TO,
    NetworkRule,
)


class DummyDbOps:
    def __init__(self):
        self.calls = []

    def create_generic_rel(self, src, rel, tgt, tgt_label, tgt_key):
        self.calls.append(("rel", src, rel, tgt, tgt_label, tgt_key))

    def upsert_generic(self, label, key, value, props):
        self.calls.append(("upsert", label, key, value, props))


def test_private_endpoint_node_and_edges():
    rule = NetworkRule()
    db = DummyDbOps()
    resource = {
        "id": "pe1",
        "type": "Microsoft.Network/privateEndpoints",
        "properties": {
            "privateLinkServiceConnections": [
                {"privateLinkServiceId": "resA"},
                {"privateLinkServiceId": "resB"},
            ]
        },
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    # Node upsert
    assert (
        "upsert",
        PRIVATE_ENDPOINT,
        "id",
        "pe1",
        {"id": "pe1", "properties": resource["properties"]},
    ) in db.calls
    # Edges (bidirectional)
    assert ("rel", "pe1", CONNECTED_TO_PE, "resA", "Resource", "id") in db.calls
    assert ("rel", "resA", CONNECTED_TO_PE, "pe1", PRIVATE_ENDPOINT, "id") in db.calls
    assert ("rel", "pe1", CONNECTED_TO_PE, "resB", "Resource", "id") in db.calls
    assert ("rel", "resB", CONNECTED_TO_PE, "pe1", PRIVATE_ENDPOINT, "id") in db.calls


def test_dnszone_node_and_resolves_to_edge():
    rule = NetworkRule()
    db = DummyDbOps()
    resource = {
        "id": "zone1",
        "type": "Microsoft.Network/dnszones",
        "resolves_to": ["resX", "resY"],
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    # Node upsert
    assert (
        "upsert",
        DNS_ZONE,
        "id",
        "zone1",
        {"id": "zone1", "resolves_to": ["resX", "resY"]},
    ) in db.calls
    # Edges
    assert ("rel", "zone1", RESOLVES_TO, "resX", "Resource", "id") in db.calls
    assert ("rel", "zone1", RESOLVES_TO, "resY", "Resource", "id") in db.calls


def test_resource_with_dnszoneid_creates_resolves_to_edge():
    rule = NetworkRule()
    db = DummyDbOps()
    resource = {
        "id": "resZ",
        "type": "Microsoft.Storage/storageAccounts",
        "dnsZoneId": "zone2",
    }
    assert (
        rule.applies(resource) is False
    )  # Not a DNSZone/PE, but emit() should still work
    rule.emit(resource, db)
    assert ("rel", "zone2", RESOLVES_TO, "resZ", "Resource", "id") in db.calls


def test_idempotency_private_endpoint():
    rule = NetworkRule()
    db = DummyDbOps()
    resource = {
        "id": "pe2",
        "type": "Microsoft.Network/privateEndpoints",
        "properties": {
            "privateLinkServiceConnections": [{"privateLinkServiceId": "resC"}]
        },
    }
    # Run twice
    rule.emit(resource, db)
    rule.emit(resource, db)
    # Only one upsert per node, one edge per direction per run (db_ops should be idempotent in real impl)
    upserts = [c for c in db.calls if c[0] == "upsert"]
    rels = [c for c in db.calls if c[0] == "rel"]
    assert (
        upserts.count(
            (
                "upsert",
                PRIVATE_ENDPOINT,
                "id",
                "pe2",
                {"id": "pe2", "properties": resource["properties"]},
            )
        )
        == 2
    )
    assert rels.count(("rel", "pe2", CONNECTED_TO_PE, "resC", "Resource", "id")) == 2
    assert (
        rels.count(("rel", "resC", CONNECTED_TO_PE, "pe2", PRIVATE_ENDPOINT, "id")) == 2
    )


def test_idempotency_dnszone_resolves_to():
    rule = NetworkRule()
    db = DummyDbOps()
    resource = {
        "id": "zone3",
        "type": "Microsoft.Network/dnszones",
        "resolves_to": ["resD"],
    }
    rule.emit(resource, db)
    rule.emit(resource, db)
    upserts = [c for c in db.calls if c[0] == "upsert"]
    rels = [c for c in db.calls if c[0] == "rel"]
    assert (
        upserts.count(
            (
                "upsert",
                DNS_ZONE,
                "id",
                "zone3",
                {"id": "zone3", "resolves_to": ["resD"]},
            )
        )
        == 2
    )
    assert rels.count(("rel", "zone3", RESOLVES_TO, "resD", "Resource", "id")) == 2
