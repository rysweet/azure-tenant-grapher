"""Unit tests for DevTestLab Policy handler (GAP-019).

Tests policy emission for various policy types and configurations.
"""

from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.devtest.devtest_policy import (
    DevTestPolicyHandler,
)


class TestDevTestPolicyHandler:
    """Tests for DevTestLab Policy handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return DevTestPolicyHandler()

    @pytest.fixture
    def context(self):
        """Create mock emitter context."""
        ctx = Mock(spec=EmitterContext)
        ctx.get_effective_subscription_id.return_value = "sub-12345"
        return ctx

    @pytest.fixture
    def base_policy_resource(self):
        """Base DevTestLab policy resource structure."""
        return {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.DevTestLab/labs/testlab/policysets/default/policies/LabVmCount",
            "name": "testlab/default/LabVmCount",
            "type": "Microsoft.DevTestLab/labs/policysets/policies",
            "location": "eastus",
            "resource_group": "rg-test",
            "tags": {},
            "properties": {
                "description": "Maximum VMs allowed in lab",
                "status": "Enabled",
                "factName": "LabVmCount",
                "factData": "",
                "threshold": "10",
                "evaluatorType": "MaxValuePolicy",
            },
        }

    # ========== Basic Emission Tests ==========

    def test_emit_basic_policy(self, handler, context, base_policy_resource):
        """Test basic policy emission with all properties."""
        tf_type, safe_name, config = handler.emit(base_policy_resource, context)

        assert tf_type == "azurerm_dev_test_policy"
        assert (
            safe_name == "LabVmCount"
        )  # sanitize_name only replaces invalid chars, not camelCase
        assert config["name"] == "LabVmCount"
        assert config["lab_name"] == "testlab"
        assert config["policy_set_name"] == "default"
        assert config["threshold"] == "10"
        assert config["evaluator_type"] == "MaxValuePolicy"
        assert config["fact_data"] == ""
        assert config["location"] == "eastus"

    def test_handler_registration(self, handler):
        """Test handler is registered for correct resource type."""
        assert handler.can_handle("Microsoft.DevTestLab/labs/policysets/policies")
        assert handler.can_handle("microsoft.devtestlab/labs/policysets/policies")

    # ========== Name Parsing Tests ==========

    def test_parse_hierarchical_name(self, handler, context, base_policy_resource):
        """Test parsing of lab/policyset/policy name."""
        base_policy_resource["name"] = "mylab/default/LabVmSize"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["lab_name"] == "mylab"
        assert config["policy_set_name"] == "default"
        assert config["name"] == "LabVmSize"

    def test_parse_name_with_unusual_characters(
        self, handler, context, base_policy_resource
    ):
        """Test name parsing with hyphens and underscores."""
        base_policy_resource["name"] = (
            "my-lab_01/default/UserOwnedLabVmCount"  # pragma: allowlist secret
        )

        _, safe_name, config = handler.emit(base_policy_resource, context)

        assert config["lab_name"] == "my-lab_01"
        assert (
            safe_name == "UserOwnedLabVmCount"
        )  # sanitize_name preserves alphanumeric and underscore

    def test_malformed_name_fallback(self, handler, context, base_policy_resource):
        """Test fallback for malformed policy names."""
        base_policy_resource["name"] = "SingleName"

        _, _, config = handler.emit(base_policy_resource, context)

        # Should handle gracefully with defaults
        assert config["lab_name"] is not None
        assert config["policy_set_name"] == "default"

    # ========== Policy Type Tests ==========

    def test_emit_lab_vm_count_policy(self, handler, context, base_policy_resource):
        """Test LabVmCount policy type."""
        base_policy_resource["name"] = "testlab/default/LabVmCount"
        base_policy_resource["properties"]["factName"] = "LabVmCount"
        base_policy_resource["properties"]["threshold"] = "50"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["name"] == "LabVmCount"
        assert config["threshold"] == "50"

    def test_emit_lab_vm_size_policy(self, handler, context, base_policy_resource):
        """Test LabVmSize policy type."""
        base_policy_resource["name"] = "testlab/default/LabVmSize"
        base_policy_resource["properties"]["factName"] = "LabVmSize"
        base_policy_resource["properties"]["factData"] = "Standard_DS2_v2"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["name"] == "LabVmSize"
        assert config["fact_data"] == "Standard_DS2_v2"

    def test_emit_gallery_image_policy(self, handler, context, base_policy_resource):
        """Test GalleryImage policy type."""
        base_policy_resource["name"] = "testlab/default/GalleryImage"
        base_policy_resource["properties"]["factName"] = "GalleryImage"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["name"] == "GalleryImage"

    def test_emit_user_owned_lab_vm_count(self, handler, context, base_policy_resource):
        """Test UserOwnedLabVmCount policy type."""
        base_policy_resource["name"] = "testlab/default/UserOwnedLabVmCount"
        base_policy_resource["properties"]["factName"] = "UserOwnedLabVmCount"
        base_policy_resource["properties"]["threshold"] = "5"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["name"] == "UserOwnedLabVmCount"
        assert config["threshold"] == "5"

    # ========== Evaluator Type Tests ==========

    def test_max_value_policy_evaluator(self, handler, context, base_policy_resource):
        """Test MaxValuePolicy evaluator type."""
        base_policy_resource["properties"]["evaluatorType"] = "MaxValuePolicy"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["evaluator_type"] == "MaxValuePolicy"

    def test_allowed_values_policy_evaluator(
        self, handler, context, base_policy_resource
    ):
        """Test AllowedValuesPolicy evaluator type."""
        base_policy_resource["properties"]["evaluatorType"] = "AllowedValuesPolicy"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["evaluator_type"] == "AllowedValuesPolicy"

    # ========== Edge Cases Tests ==========

    def test_missing_description(self, handler, context, base_policy_resource):
        """Test handling of missing description property."""
        del base_policy_resource["properties"]["description"]

        _, _, config = handler.emit(base_policy_resource, context)

        # Should still emit successfully
        assert config["name"] == "LabVmCount"

    def test_empty_fact_data(self, handler, context, base_policy_resource):
        """Test handling of empty factData."""
        base_policy_resource["properties"]["factData"] = ""

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["fact_data"] == ""

    def test_disabled_policy_status(self, handler, context, base_policy_resource):
        """Test handling of Disabled policy status."""
        base_policy_resource["properties"]["status"] = "Disabled"

        _, _, config = handler.emit(base_policy_resource, context)

        # Should emit successfully regardless of status
        assert config["name"] == "LabVmCount"

    def test_threshold_as_string(self, handler, context, base_policy_resource):
        """Test threshold is preserved as string (Terraform requirement)."""
        base_policy_resource["properties"]["threshold"] = "999"

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["threshold"] == "999"
        assert isinstance(config["threshold"], str)

    def test_tags_preservation(self, handler, context, base_policy_resource):
        """Test tags are preserved in config."""
        base_policy_resource["tags"] = {
            "Environment": "Test",
            "Owner": "TeamA",
        }

        _, _, config = handler.emit(base_policy_resource, context)

        assert config["tags"]["Environment"] == "Test"
        assert config["tags"]["Owner"] == "TeamA"

    def test_resource_group_extraction(self, handler, context, base_policy_resource):
        """Test resource group is correctly extracted."""
        _, _, config = handler.emit(base_policy_resource, context)

        assert "resource_group_name" in config
        assert config["resource_group_name"] is not None
