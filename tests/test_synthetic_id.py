"""Tests for Synthetic ID Generator.

This test suite validates synthetic ID generation for scale operations,
ensuring collision-free IDs with proper formatting and type prefixes.
"""

from src.utils.synthetic_id import (
    extract_type_from_synthetic_id,
    generate_synthetic_id,
    get_resource_type_from_prefix,
    is_synthetic_id,
)


class TestSyntheticIDGenerator:
    """Test suite for synthetic ID generation."""

    def test_generate_synthetic_id_format(self):
        """Test that synthetic IDs have the correct format."""
        synthetic_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")

        # Format: synthetic-{type}-{uuid8}
        assert synthetic_id.startswith("synthetic-")
        parts = synthetic_id.split("-")
        assert len(parts) == 3
        assert parts[0] == "synthetic"
        assert parts[1] == "vm"
        assert len(parts[2]) == 8  # UUID truncated to 8 chars

    def test_generate_synthetic_id_type_prefixes(self):
        """Test correct type prefixes for different resource types."""
        test_cases = [
            ("Microsoft.Compute/virtualMachines", "vm"),
            ("Microsoft.Network/virtualNetworks", "vnet"),
            ("Microsoft.Storage/storageAccounts", "storage"),
            ("Microsoft.Sql/servers", "sql"),
            ("Microsoft.KeyVault/vaults", "kv"),
            ("Microsoft.Web/sites", "app"),
            ("Microsoft.ContainerService/managedClusters", "aks"),
        ]

        for resource_type, expected_prefix in test_cases:
            synthetic_id = generate_synthetic_id(resource_type)
            parts = synthetic_id.split("-")
            assert parts[1] == expected_prefix, (
                f"Expected prefix '{expected_prefix}' for {resource_type}, "
                f"got '{parts[1]}'"
            )

    def test_generate_synthetic_id_unknown_type(self):
        """Test that unknown types get default prefix."""
        synthetic_id = generate_synthetic_id("Unknown.Type/resource")
        parts = synthetic_id.split("-")
        assert parts[1] == "resource"  # Default prefix

    def test_generate_synthetic_id_uniqueness(self):
        """Test that 1000 generated IDs have no collisions."""
        resource_type = "Microsoft.Compute/virtualMachines"
        synthetic_ids = set()

        # Generate 1000 IDs
        for _ in range(1000):
            synthetic_id = generate_synthetic_id(resource_type)
            synthetic_ids.add(synthetic_id)

        # All should be unique
        assert len(synthetic_ids) == 1000

    def test_generate_synthetic_id_cross_type_uniqueness(self):
        """Test uniqueness across different resource types."""
        types = [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Sql/servers",
        ]

        all_ids = set()
        for resource_type in types:
            for _ in range(100):
                synthetic_id = generate_synthetic_id(resource_type)
                all_ids.add(synthetic_id)

        # 4 types * 100 IDs = 400 unique IDs
        assert len(all_ids) == 400

    def test_is_synthetic_id_true(self):
        """Test identification of synthetic IDs."""
        synthetic_ids = [
            "synthetic-vm-a1b2c3d4",
            "synthetic-vnet-e5f6g7h8",
            "synthetic-storage-12345678",
        ]

        for synthetic_id in synthetic_ids:
            assert is_synthetic_id(synthetic_id) is True

    def test_is_synthetic_id_false(self):
        """Test rejection of non-synthetic IDs."""
        non_synthetic_ids = [
            "vm-a1b2c3d4",  # Abstracted ID (no 'synthetic-' prefix)
            "/subscriptions/abc/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",  # Azure ID
            "my-vm-name",  # Regular name
            "",
            "syntheticvm-12345678",  # Missing dash
        ]

        for non_synthetic_id in non_synthetic_ids:
            assert is_synthetic_id(non_synthetic_id) is False

    def test_extract_type_from_synthetic_id(self):
        """Test extraction of type prefix from synthetic ID."""
        test_cases = [
            ("synthetic-vm-a1b2c3d4", "vm"),
            ("synthetic-vnet-e5f6g7h8", "vnet"),
            ("synthetic-storage-12345678", "storage"),
            ("synthetic-sql-abcd1234", "sql"),
        ]

        for synthetic_id, expected_type in test_cases:
            extracted_type = extract_type_from_synthetic_id(synthetic_id)
            assert extracted_type == expected_type

    def test_extract_type_from_non_synthetic_id(self):
        """Test extraction returns 'unknown' for non-synthetic IDs."""
        non_synthetic_ids = [
            "vm-a1b2c3d4",
            "/subscriptions/abc/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "my-vm-name",
        ]

        for non_synthetic_id in non_synthetic_ids:
            extracted_type = extract_type_from_synthetic_id(non_synthetic_id)
            assert extracted_type == "unknown"

    def test_get_resource_type_from_prefix(self):
        """Test reverse lookup of resource type from prefix."""
        test_cases = [
            ("vm", "Microsoft.Compute/virtualMachines"),
            ("vnet", "Microsoft.Network/virtualNetworks"),
            ("storage", "Microsoft.Storage/storageAccounts"),
            ("sql", "Microsoft.Sql/servers"),
            ("kv", "Microsoft.KeyVault/vaults"),
        ]

        for prefix, expected_resource_type in test_cases:
            resource_type = get_resource_type_from_prefix(prefix)
            assert resource_type == expected_resource_type

    def test_get_resource_type_from_unknown_prefix(self):
        """Test reverse lookup returns 'Unknown' for unknown prefixes."""
        unknown_prefixes = ["xyz", "unknown", ""]

        for prefix in unknown_prefixes:
            resource_type = get_resource_type_from_prefix(prefix)
            assert resource_type == "Unknown"

    def test_synthetic_id_roundtrip(self):
        """Test that we can generate, identify, and extract type from synthetic IDs."""
        test_types = [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Storage/storageAccounts",
        ]

        for resource_type in test_types:
            # Generate synthetic ID
            synthetic_id = generate_synthetic_id(resource_type)

            # Verify it's identified as synthetic
            assert is_synthetic_id(synthetic_id)

            # Extract type prefix
            type_prefix = extract_type_from_synthetic_id(synthetic_id)

            # Reverse lookup to get resource type
            roundtrip_type = get_resource_type_from_prefix(type_prefix)

            # Should match original resource type
            assert roundtrip_type == resource_type

    def test_synthetic_id_distinct_from_abstracted_id(self):
        """Test that synthetic IDs are clearly distinct from abstracted IDs."""
        synthetic_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
        abstracted_id_example = "vm-a1b2c3d4e5f6g7h8"  # Abstracted ID format

        # Synthetic ID should have 'synthetic-' prefix
        assert synthetic_id.startswith("synthetic-")

        # Abstracted ID should NOT have 'synthetic-' prefix
        assert not abstracted_id_example.startswith("synthetic-")

        # is_synthetic_id should distinguish them
        assert is_synthetic_id(synthetic_id) is True
        assert is_synthetic_id(abstracted_id_example) is False

    def test_synthetic_id_no_collisions_with_batch_generation(self):
        """Test batch generation doesn't produce collisions."""
        batch_size = 500
        resource_type = "Microsoft.Compute/virtualMachines"

        # Generate first batch
        batch1 = {generate_synthetic_id(resource_type) for _ in range(batch_size)}

        # Generate second batch
        batch2 = {generate_synthetic_id(resource_type) for _ in range(batch_size)}

        # All IDs in batch1 should be unique
        assert len(batch1) == batch_size

        # All IDs in batch2 should be unique
        assert len(batch2) == batch_size

        # No overlap between batches (very high probability)
        # In theory there's a tiny chance of collision with UUID, but extremely unlikely
        overlap = batch1 & batch2
        assert len(overlap) == 0, f"Unexpected collisions between batches: {overlap}"

    def test_synthetic_id_subnet_type(self):
        """Test subnet type handling with multiple possible paths."""
        # Both subnet paths should map to same prefix
        subnet_type_1 = "Microsoft.Network/subnets"
        subnet_type_2 = "Microsoft.Network/virtualNetworks/subnets"

        id1 = generate_synthetic_id(subnet_type_1)
        id2 = generate_synthetic_id(subnet_type_2)

        # Both should use 'subnet' prefix
        assert id1.split("-")[1] == "subnet"
        assert id2.split("-")[1] == "subnet"

    def test_synthetic_id_comprehensive_type_coverage(self):
        """Test that all major Azure resource types have prefixes."""
        major_types = [
            # Compute
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Compute/disks",
            "Microsoft.Compute/virtualMachineScaleSets",
            # Network
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.Network/publicIPAddresses",
            "Microsoft.Network/loadBalancers",
            # Storage
            "Microsoft.Storage/storageAccounts",
            # Database
            "Microsoft.Sql/servers",
            "Microsoft.DBforMySQL/servers",
            "Microsoft.DocumentDB/databaseAccounts",
            # Containers
            "Microsoft.ContainerService/managedClusters",
            "Microsoft.ContainerRegistry/registries",
            # Web
            "Microsoft.Web/sites",
            "Microsoft.Web/serverfarms",
            # Monitoring
            "Microsoft.Insights/components",
            "Microsoft.OperationalInsights/workspaces",
        ]

        for resource_type in major_types:
            synthetic_id = generate_synthetic_id(resource_type)
            # Should have a specific prefix, not the default 'resource'
            parts = synthetic_id.split("-")
            assert parts[1] != "resource", (
                f"Resource type {resource_type} is using default prefix. "
                f"It should have a specific prefix."
            )
