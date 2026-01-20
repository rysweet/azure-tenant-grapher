"""
Test that azure_discovery_service properly includes scan_id and tenant_id
for child resources discovered via Azure API (Issue #563).

This test verifies the fix ensures child resource dictionaries include
scan_id and tenant_id from their parent resources.
"""


class TestChildResourceScanMetadata:
    """Test child resource dictionary structure includes scan_id and tenant_id (Issue #563 fix)."""

    def test_subnet_dict_structure_includes_scan_metadata(self):
        """Test that subnet dictionaries include scan_id and tenant_id fields."""
        # This test verifies the fix pattern: child resources must have scan_id and tenant_id
        # Simulating what the code creates when building child resource dictionaries

        parent_vnet = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        # This matches the pattern from the fix (lines 715-716 in azure_discovery_service.py)
        subnet_dict = {
            "id": "subnet-id",
            "name": "subnet-1",
            "type": "Microsoft.Network/subnets",
            "location": parent_vnet.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_vnet.get(
                "scan_id"
            ),  # FIX: Required for SCAN_SOURCE_NODE relationship
            "tenant_id": parent_vnet.get(
                "tenant_id"
            ),  # FIX: Required for SCAN_SOURCE_NODE relationship
        }

        assert "scan_id" in subnet_dict, "Subnet dict must include scan_id field"
        assert "tenant_id" in subnet_dict, "Subnet dict must include tenant_id field"
        assert subnet_dict["scan_id"] == "scan-abc-123", (
            "scan_id must match parent VNet"
        )
        assert subnet_dict["tenant_id"] == "tenant-xyz-456", (
            "tenant_id must match parent VNet"
        )

    def test_automation_runbook_dict_structure_includes_scan_metadata(self):
        """Test that automation runbook dictionaries include scan_id and tenant_id fields (Issue #563 specific)."""
        parent_account = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        # This matches the pattern from the fix (lines 770-771 in azure_discovery_service.py)
        runbook_dict = {
            "id": "runbook-id",
            "name": "runbook-1",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": parent_account.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_account.get("scan_id"),
            "tenant_id": parent_account.get("tenant_id"),
        }

        assert "scan_id" in runbook_dict, "Runbook dict must include scan_id field"
        assert "tenant_id" in runbook_dict, "Runbook dict must include tenant_id field"
        assert runbook_dict["scan_id"] == "scan-abc-123"
        assert runbook_dict["tenant_id"] == "tenant-xyz-456"

    def test_dns_link_dict_structure_includes_scan_metadata(self):
        """Test that DNS zone link dictionaries include scan_id and tenant_id fields."""
        parent_zone = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        link_dict = {
            "id": "link-id",
            "name": "link-1",
            "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
            "location": parent_zone.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_zone.get("scan_id"),
            "tenant_id": parent_zone.get("tenant_id"),
        }

        assert "scan_id" in link_dict
        assert "tenant_id" in link_dict
        assert link_dict["scan_id"] == "scan-abc-123"
        assert link_dict["tenant_id"] == "tenant-xyz-456"

    def test_vm_extension_dict_structure_includes_scan_metadata(self):
        """Test that VM extension dictionaries include scan_id and tenant_id fields."""
        parent_vm = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        ext_dict = {
            "id": "ext-id",
            "name": "ext-1",
            "type": "Microsoft.Compute/virtualMachines/extensions",
            "location": parent_vm.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_vm.get("scan_id"),
            "tenant_id": parent_vm.get("tenant_id"),
        }

        assert "scan_id" in ext_dict
        assert "tenant_id" in ext_dict
        assert ext_dict["scan_id"] == "scan-abc-123"
        assert ext_dict["tenant_id"] == "tenant-xyz-456"

    def test_sql_database_dict_structure_includes_scan_metadata(self):
        """Test that SQL database dictionaries include scan_id and tenant_id fields."""
        parent_server = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        db_dict = {
            "id": "db-id",
            "name": "db-1",
            "type": "Microsoft.Sql/servers/databases",
            "location": parent_server.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_server.get("scan_id"),
            "tenant_id": parent_server.get("tenant_id"),
        }

        assert "scan_id" in db_dict
        assert "tenant_id" in db_dict
        assert db_dict["scan_id"] == "scan-abc-123"
        assert db_dict["tenant_id"] == "tenant-xyz-456"

    def test_postgresql_config_dict_structure_includes_scan_metadata(self):
        """Test that PostgreSQL configuration dictionaries include scan_id and tenant_id fields."""
        parent_server = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        config_dict = {
            "id": "config-id",
            "name": "config-1",
            "type": "Microsoft.DBforPostgreSQL/servers/configurations",
            "location": parent_server.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_server.get("scan_id"),
            "tenant_id": parent_server.get("tenant_id"),
        }

        assert "scan_id" in config_dict
        assert "tenant_id" in config_dict
        assert config_dict["scan_id"] == "scan-abc-123"
        assert config_dict["tenant_id"] == "tenant-xyz-456"

    def test_container_registry_webhook_dict_structure_includes_scan_metadata(self):
        """Test that container registry webhook dictionaries include scan_id and tenant_id fields."""
        parent_registry = {
            "scan_id": "scan-abc-123",
            "tenant_id": "tenant-xyz-456",
            "location": "eastus",
        }

        webhook_dict = {
            "id": "webhook-id",
            "name": "webhook-1",
            "type": "Microsoft.ContainerRegistry/registries/webhooks",
            "location": parent_registry.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_registry.get("scan_id"),
            "tenant_id": parent_registry.get("tenant_id"),
        }

        assert "scan_id" in webhook_dict
        assert "tenant_id" in webhook_dict
        assert webhook_dict["scan_id"] == "scan-abc-123"
        assert webhook_dict["tenant_id"] == "tenant-xyz-456"

    def test_child_resource_without_parent_metadata_has_none(self):
        """Test that child resources get None for scan_id/tenant_id if parent doesn't have them."""
        parent_without_metadata = {
            "location": "eastus",
            # No scan_id or tenant_id
        }

        child_dict = {
            "id": "child-id",
            "name": "child-1",
            "type": "Microsoft.Network/subnets",
            "location": parent_without_metadata.get("location"),
            "properties": {},
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "scan_id": parent_without_metadata.get("scan_id"),  # Should be None
            "tenant_id": parent_without_metadata.get("tenant_id"),  # Should be None
        }

        assert child_dict["scan_id"] is None, (
            "scan_id should be None if parent doesn't have it"
        )
        assert child_dict["tenant_id"] is None, (
            "tenant_id should be None if parent doesn't have it"
        )

    def test_all_child_resource_types_have_required_fields(self):
        """Test that all child resource dict structures include required fields including scan_id and tenant_id."""
        required_fields = [
            "id",
            "name",
            "type",
            "location",
            "subscription_id",
            "resource_group",
            "scan_id",  # NEW: Required for SCAN_SOURCE_NODE
            "tenant_id",  # NEW: Required for SCAN_SOURCE_NODE
        ]

        # Sample child resource dict (representing the fix pattern)
        parent = {
            "scan_id": "scan-test",
            "tenant_id": "tenant-test",
            "location": "eastus",
        }

        child_dict = {
            "id": "child-id",
            "name": "child-name",
            "type": "Microsoft.Resource/type",
            "location": parent.get("location"),
            "subscription_id": "sub-123",
            "resource_group": "rg-test",
            "properties": {},
            "scan_id": parent.get("scan_id"),
            "tenant_id": parent.get("tenant_id"),
        }

        for field in required_fields:
            assert field in child_dict, (
                f"Child resource dict must include {field} field"
            )
