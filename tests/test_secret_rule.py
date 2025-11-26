"""
Tests for SecretRule - KeyVault secret relationship handling.

These tests verify that SecretRule correctly:
1. Applies to KeyVault resources with secrets
2. Creates KeyVaultSecret nodes via upsert_generic
3. Creates STORES_SECRET relationships via dual-graph API
4. Supports dual-graph architecture

Issue #478: Fix broken SecretRule API
"""

from src.relationship_rules.secret_rule import SecretRule


class DummyDbOps:
    """Mock database operations for testing.

    Uses the same mock pattern as test_relationship_rules.py to test
    rule behavior with legacy-mode fallback (session_manager=None).
    """

    def __init__(self):
        self.calls = []
        # Mock session manager for batching support
        # None triggers legacy mode fallback in base class
        self.session_manager = None

    def create_generic_rel(self, src, rel, tgt, tgt_label, tgt_key):
        """Record relationship creation calls."""
        self.calls.append(("rel", src, rel, tgt, tgt_label, tgt_key))

    def upsert_generic(self, label, key, value, props):
        """Record node upsert calls."""
        self.calls.append(("upsert", label, key, value, props))


def test_secret_rule_applies_to_keyvault_with_secrets():
    """SecretRule should apply to KeyVault resources that have secrets."""
    # Note: Using legacy mode (no dual_graph) for unit tests with mock db_ops
    # Matches pattern from test_relationship_rules.py
    rule = SecretRule()

    # Should apply: KeyVault with secrets
    resource_with_secrets = {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv1",
        "secrets": [{"name": "secret1", "contentType": "application/json"}],
    }
    assert rule.applies(resource_with_secrets) is True

    # Should NOT apply: KeyVault without secrets
    resource_no_secrets = {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv2",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv2",
    }
    assert rule.applies(resource_no_secrets) is False

    # Should NOT apply: Non-KeyVault resource with "secrets" key
    non_keyvault = {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
        "type": "Microsoft.Storage/storageAccounts",
        "secrets": [{"name": "secret1"}],
    }
    assert rule.applies(non_keyvault) is False


def test_secret_rule_creates_keyvaultsecret_nodes():
    """SecretRule should create KeyVaultSecret nodes for each secret."""
    rule = SecretRule()
    db = DummyDbOps()

    resource = {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv1",
        "secrets": [
            {"name": "db-password", "contentType": "text/plain"},
            {"name": "api-key", "contentType": "application/json"},
        ],
    }

    rule.emit(resource, db)

    # Verify KeyVaultSecret nodes are created via upsert_generic
    secret1_call = (
        "upsert",
        "KeyVaultSecret",
        "name",
        "db-password",
        {
            "name": "db-password",
            "contentType": "text/plain",
            "keyVaultId": resource["id"],
        },
    )
    secret2_call = (
        "upsert",
        "KeyVaultSecret",
        "name",
        "api-key",
        {
            "name": "api-key",
            "contentType": "application/json",
            "keyVaultId": resource["id"],
        },
    )

    assert secret1_call in db.calls, f"Expected {secret1_call} in {db.calls}"
    assert secret2_call in db.calls, f"Expected {secret2_call} in {db.calls}"


def test_secret_rule_creates_stores_secret_relationships():
    """SecretRule should create STORES_SECRET relationships from KeyVault to secrets."""
    rule = SecretRule()
    db = DummyDbOps()

    keyvault_id = (
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
    )
    resource = {
        "id": keyvault_id,
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv1",
        "secrets": [
            {"name": "connection-string", "contentType": "text/plain"},
        ],
    }

    rule.emit(resource, db)

    # Verify STORES_SECRET relationship is created
    expected_rel = (
        "rel",
        keyvault_id,
        "STORES_SECRET",
        "connection-string",
        "KeyVaultSecret",
        "name",
    )
    assert expected_rel in db.calls, f"Expected {expected_rel} in {db.calls}"


def test_secret_rule_handles_empty_secrets_list():
    """SecretRule should handle empty secrets list gracefully."""
    rule = SecretRule()

    resource = {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv1",
        "secrets": [],
    }

    # Should not apply if secrets list is empty
    assert rule.applies(resource) is False


def test_secret_rule_handles_secrets_without_content_type():
    """SecretRule should handle secrets without contentType property."""
    rule = SecretRule()
    db = DummyDbOps()

    resource = {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv1",
        "secrets": [
            {"name": "secret-no-content-type"},
        ],
    }

    rule.emit(resource, db)

    # Should create node with None contentType
    expected_upsert = (
        "upsert",
        "KeyVaultSecret",
        "name",
        "secret-no-content-type",
        {
            "name": "secret-no-content-type",
            "contentType": None,
            "keyVaultId": resource["id"],
        },
    )
    assert expected_upsert in db.calls


def test_secret_rule_is_registered():
    """SecretRule should be registered in create_relationship_rules."""
    from src.relationship_rules import create_relationship_rules

    rules = create_relationship_rules()
    rule_types = [type(r).__name__ for r in rules]

    assert "SecretRule" in rule_types, f"SecretRule not found in {rule_types}"


def test_secret_rule_supports_dual_graph():
    """SecretRule should support dual-graph architecture."""
    rule = SecretRule(enable_dual_graph=True)
    assert rule.enable_dual_graph is True

    rule_no_dual = SecretRule(enable_dual_graph=False)
    assert rule_no_dual.enable_dual_graph is False
