"""Tests for global location mapper."""

import pytest

from src.iac.transformers.location_mapper import GlobalLocationMapper, LocationMapResult


class TestGlobalLocationMapper:
    """Test suite for GlobalLocationMapper."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance."""
        return GlobalLocationMapper()

    def test_initialization_default_region(self, mapper):
        """Test mapper initialization with default region."""
        assert mapper.default_region == "eastus"

    def test_initialization_custom_region(self):
        """Test mapper initialization with custom region."""
        mapper = GlobalLocationMapper(default_region="westus2")
        assert mapper.default_region == "westus2"

    def test_initialization_invalid_region_fallback(self):
        """Test mapper initialization with invalid region falls back to default."""
        mapper = GlobalLocationMapper(default_region="invalid-region")
        assert mapper.default_region == "eastus"

    def test_map_resource_group_global_location(self, mapper):
        """Test mapping Resource Group with global location."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg1",
                "location": "global",
            }
        ]

        result = mapper.transform_resources(resources)

        assert result.resources_processed == 1
        assert result.resources_mapped == 1
        assert resources[0]["location"] == "eastus"
        assert len(result.mappings) == 1

    def test_no_mapping_for_non_global_location(self, mapper):
        """Test no mapping for Resource Groups with valid location."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg1",
                "location": "westus",
            }
        ]

        result = mapper.transform_resources(resources)

        assert result.resources_processed == 1
        assert result.resources_mapped == 0
        assert resources[0]["location"] == "westus"

    def test_no_mapping_for_non_resource_group_types(self, mapper):
        """Test no mapping for non-Resource Group types."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm1",
                "location": "global",
            }
        ]

        result = mapper.transform_resources(resources)

        assert result.resources_processed == 1
        assert result.resources_mapped == 0
        assert resources[0]["location"] == "global"  # Unchanged

    def test_multiple_resource_groups(self, mapper):
        """Test mapping multiple Resource Groups."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg1",
                "location": "global",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg2",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg2",
                "location": "global",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg3",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg3",
                "location": "eastus",
            },
        ]

        result = mapper.transform_resources(resources)

        assert result.resources_processed == 3
        assert result.resources_mapped == 2
        assert resources[0]["location"] == "eastus"
        assert resources[1]["location"] == "eastus"
        assert resources[2]["location"] == "eastus"

    def test_case_insensitive_location(self, mapper):
        """Test case-insensitive location matching."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg1",
                "location": "GLOBAL",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg2",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg2",
                "location": "Global",
            },
        ]

        result = mapper.transform_resources(resources)

        assert result.resources_processed == 2
        assert result.resources_mapped == 2

    def test_get_mapping_summary(self, mapper):
        """Test mapping summary generation."""
        result = LocationMapResult(
            resources_processed=5,
            resources_mapped=2,
            mappings=[
                ("rg1", "global", "eastus"),
                ("rg2", "global", "eastus"),
            ],
        )

        summary = mapper.get_mapping_summary(result)

        assert "Resources processed: 5" in summary
        assert "Resources mapped: 2" in summary
        assert "rg1" in summary
        assert "rg2" in summary
        assert "global -> eastus" in summary

    def test_empty_resources_list(self, mapper):
        """Test handling empty resources list."""
        resources = []

        result = mapper.transform_resources(resources)

        assert result.resources_processed == 0
        assert result.resources_mapped == 0

    def test_custom_default_region(self):
        """Test mapping with custom default region."""
        mapper = GlobalLocationMapper(default_region="westeurope")

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "rg1",
                "location": "global",
            }
        ]

        result = mapper.transform_resources(resources)

        assert result.resources_mapped == 1
        assert resources[0]["location"] == "westeurope"
