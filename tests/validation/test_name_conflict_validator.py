"""Tests for name conflict validator module."""

import json
from unittest.mock import patch

from src.validation import NameConflict, NameConflictValidator, NameValidationResult


class TestNameConflict:
    """Tests for NameConflict dataclass."""

    def test_name_conflict_creation(self):
        """Test NameConflict dataclass creation."""
        conflict = NameConflict(
            resource_type="Microsoft.Storage/storageAccounts",
            original_name="teststorage",
            conflict_reason="Already exists",
            suggested_name="teststorage-copy",
        )

        assert conflict.resource_type == "Microsoft.Storage/storageAccounts"
        assert conflict.original_name == "teststorage"
        assert conflict.conflict_reason == "Already exists"
        assert conflict.suggested_name == "teststorage-copy"

    def test_name_conflict_str(self):
        """Test NameConflict string representation."""
        conflict = NameConflict(
            resource_type="Microsoft.Storage/storageAccounts",
            original_name="teststorage",
            conflict_reason="Already exists",
            suggested_name="teststorage-copy",
        )

        result = str(conflict)
        assert "Microsoft.Storage/storageAccounts" in result
        assert "teststorage" in result
        assert "teststorage-copy" in result


class TestNameValidationResult:
    """Tests for NameValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test NameValidationResult creation."""
        result = NameValidationResult()

        assert result.conflicts == []
        assert result.name_mappings == {}
        assert result.warnings == []
        assert result.resources_checked == 0
        assert result.conflicts_fixed == 0

    def test_has_conflicts_property(self):
        """Test has_conflicts property."""
        result = NameValidationResult()
        assert not result.has_conflicts

        conflict = NameConflict(
            resource_type="Microsoft.Storage/storageAccounts",
            original_name="test",
            conflict_reason="Test",
        )
        result.conflicts.append(conflict)
        assert result.has_conflicts

    def test_has_fixes_property(self):
        """Test has_fixes property."""
        result = NameValidationResult()
        assert not result.has_fixes

        result.name_mappings["old"] = "new"
        assert result.has_fixes


class TestNameConflictValidator:
    """Tests for NameConflictValidator class."""

    def test_validator_initialization(self):
        """Test validator initialization with default parameters."""
        validator = NameConflictValidator()

        assert validator.subscription_id is None
        assert validator.naming_suffix == "-copy"
        assert validator.preserve_names is False
        assert validator.auto_purge_soft_deleted is False

    def test_validator_initialization_custom(self):
        """Test validator initialization with custom parameters."""
        validator = NameConflictValidator(
            subscription_id="test-sub-id",
            naming_suffix="-test",
            preserve_names=True,
            auto_purge_soft_deleted=True,
        )

        assert validator.subscription_id == "test-sub-id"
        assert validator.naming_suffix == "-test"
        assert validator.preserve_names is True
        assert validator.auto_purge_soft_deleted is True

    def test_validate_and_fix_terraform_no_subscription(self):
        """Test validation without subscription ID (no conflict detection)."""
        validator = NameConflictValidator()
        config = {"resources": []}

        updated_config, result = validator.validate_and_fix_terraform(config)

        assert result.resources_checked == 0
        assert len(result.warnings) > 0
        assert "Subscription ID not provided" in result.warnings[0]

    def test_validate_and_fix_terraform_empty_config(self):
        """Test validation with empty config."""
        validator = NameConflictValidator(subscription_id="fake-sub-id")
        config = {"resources": []}

        with patch.object(validator, "_detect_conflicts", return_value=[]):
            updated_config, result = validator.validate_and_fix_terraform(config)

        assert result.resources_checked == 0
        assert not result.has_conflicts

    def test_extract_terraform_resources(self):
        """Test extracting resources from Terraform config."""
        validator = NameConflictValidator()
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "teststorage",
                    "resource_group": "test-rg",
                    "location": "eastus",
                }
            ]
        }

        resources = validator._extract_terraform_resources(config)

        assert len(resources) == 1
        assert resources[0]["type"] == "Microsoft.Storage/storageAccounts"
        assert resources[0]["name"] == "teststorage"

    def test_extract_terraform_resources_list_format(self):
        """Test extracting resources from list-format Terraform config."""
        validator = NameConflictValidator()
        config = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
            }
        ]

        resources = validator._extract_terraform_resources(config)

        assert len(resources) == 1
        assert resources[0]["type"] == "Microsoft.Storage/storageAccounts"

    def test_check_naming_rules_valid_storage(self):
        """Test naming rules validation for valid storage account."""
        validator = NameConflictValidator()

        result = validator._check_naming_rules(
            "validname123", "Microsoft.Storage/storageAccounts"
        )

        assert result is None

    def test_check_naming_rules_invalid_storage_too_long(self):
        """Test naming rules validation for storage account name too long."""
        validator = NameConflictValidator()
        long_name = "a" * 25  # Max is 24

        result = validator._check_naming_rules(
            long_name, "Microsoft.Storage/storageAccounts"
        )

        assert result is not None
        assert "max length" in result.lower()

    def test_check_naming_rules_invalid_storage_pattern(self):
        """Test naming rules validation for invalid storage account pattern."""
        validator = NameConflictValidator()

        result = validator._check_naming_rules(
            "Invalid-Name", "Microsoft.Storage/storageAccounts"
        )

        assert result is not None
        assert "pattern" in result.lower()

    def test_check_naming_rules_no_rules(self):
        """Test naming rules validation for resource type with no rules."""
        validator = NameConflictValidator()

        result = validator._check_naming_rules(
            "any-name", "Microsoft.Unknown/resourceType"
        )

        assert result is None

    def test_generate_fixed_name(self):
        """Test generating fixed name with suffix."""
        validator = NameConflictValidator(naming_suffix="-test")

        new_name = validator._generate_fixed_name(
            "original", "Microsoft.Storage/storageAccounts"
        )

        # Storage accounts need lowercase, no hyphens
        assert "test" in new_name

    def test_generate_fixed_name_with_truncation(self):
        """Test generating fixed name with truncation for max length."""
        validator = NameConflictValidator(naming_suffix="-suffix")
        long_name = "a" * 24  # Already at max

        new_name = validator._generate_fixed_name(
            long_name, "Microsoft.Storage/storageAccounts"
        )

        # Should be truncated to fit within 24 chars
        assert len(new_name) <= 24

    def test_apply_fixes(self):
        """Test applying fixes to Terraform config."""
        validator = NameConflictValidator(naming_suffix="-copy")
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "conflictname",
                }
            ]
        }
        conflicts = [
            NameConflict(
                resource_type="Microsoft.Storage/storageAccounts",
                original_name="conflictname",
                conflict_reason="Test",
            )
        ]
        result = NameValidationResult()

        _ = validator._apply_fixes(config, conflicts, result)

        assert "conflictname" in result.name_mappings
        assert len(result.name_mappings) == 1

    def test_update_resource_name(self):
        """Test updating resource name in config."""
        validator = NameConflictValidator()
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "oldname",
                }
            ]
        }

        validator._update_resource_name(
            config, "Microsoft.Storage/storageAccounts", "oldname", "newname"
        )

        assert config["resources"][0]["name"] == "newname"

    def test_update_resource_name_with_values(self):
        """Test updating resource name in config with values dict."""
        validator = NameConflictValidator()
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "oldname",
                    "values": {"name": "oldname"},
                }
            ]
        }

        validator._update_resource_name(
            config, "Microsoft.Storage/storageAccounts", "oldname", "newname"
        )

        assert config["resources"][0]["name"] == "newname"
        assert config["resources"][0]["values"]["name"] == "newname"

    def test_save_name_mappings(self, tmp_path):
        """Test saving name mappings to JSON file."""
        validator = NameConflictValidator(naming_suffix="-copy")
        mappings = {"oldname": "newname"}
        conflicts = [
            NameConflict(
                resource_type="Microsoft.Storage/storageAccounts",
                original_name="oldname",
                conflict_reason="Test conflict",
            )
        ]

        validator.save_name_mappings(mappings, tmp_path, conflicts)

        mappings_file = tmp_path / "name_mappings.json"
        assert mappings_file.exists()

        with open(mappings_file) as f:
            data = json.load(f)

        assert "mappings" in data
        assert len(data["mappings"]) == 1
        assert data["mappings"][0]["original_name"] == "oldname"
        assert data["mappings"][0]["new_name"] == "newname"
        assert data["naming_suffix"] == "-copy"

    def test_extract_resource_info(self):
        """Test extracting resource info from resource dict."""
        validator = NameConflictValidator()
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "testname",
            "resource_group": "test-rg",
            "location": "eastus",
        }

        result = validator._extract_resource_info(resource)

        assert result is not None
        assert result["type"] == "Microsoft.Storage/storageAccounts"
        assert result["name"] == "testname"
        assert result["resource_group"] == "test-rg"
        assert result["location"] == "eastus"

    def test_extract_resource_info_with_values(self):
        """Test extracting resource info from resource with values dict."""
        validator = NameConflictValidator()
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "values": {
                "name": "testname",
                "resource_group_name": "test-rg",
                "location": "eastus",
            },
        }

        result = validator._extract_resource_info(resource)

        assert result is not None
        assert result["name"] == "testname"
        assert result["resource_group"] == "test-rg"
        assert result["location"] == "eastus"

    def test_extract_resource_info_missing_required_fields(self):
        """Test extracting resource info with missing required fields."""
        validator = NameConflictValidator()
        resource = {"type": "Microsoft.Storage/storageAccounts"}  # No name

        result = validator._extract_resource_info(resource)

        assert result is None


class TestNameConflictValidatorIntegration:
    """Integration tests for NameConflictValidator (no Azure calls)."""

    def test_full_validation_workflow_no_conflicts(self):
        """Test full validation workflow with no conflicts."""
        validator = NameConflictValidator(subscription_id="fake-sub-id")
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "validname123",
                }
            ]
        }

        # Mock the async conflict detection to return no conflicts
        with patch.object(validator, "_detect_conflicts", return_value=[]):
            updated_config, result = validator.validate_and_fix_terraform(
                config, auto_fix=True
            )

        assert result.resources_checked == 1
        assert not result.has_conflicts
        assert not result.has_fixes

    def test_full_validation_workflow_with_auto_fix(self):
        """Test full validation workflow with conflicts and auto-fix."""
        validator = NameConflictValidator(
            subscription_id="fake-sub-id", naming_suffix="-copy"
        )
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "conflictname",
                }
            ]
        }

        # Mock conflict detection
        mock_conflicts = [
            NameConflict(
                resource_type="Microsoft.Storage/storageAccounts",
                original_name="conflictname",
                conflict_reason="Already exists",
            )
        ]

        with patch.object(validator, "_detect_conflicts", return_value=mock_conflicts):
            updated_config, result = validator.validate_and_fix_terraform(
                config, auto_fix=True
            )

        assert result.has_conflicts
        assert result.has_fixes
        assert "conflictname" in result.name_mappings

    def test_full_validation_workflow_preserve_names(self):
        """Test validation workflow with preserve_names mode."""
        validator = NameConflictValidator(
            subscription_id="fake-sub-id", preserve_names=True
        )
        config = {
            "resources": [
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": "conflictname",
                }
            ]
        }

        # Mock conflict detection
        mock_conflicts = [
            NameConflict(
                resource_type="Microsoft.Storage/storageAccounts",
                original_name="conflictname",
                conflict_reason="Already exists",
            )
        ]

        with patch.object(validator, "_detect_conflicts", return_value=mock_conflicts):
            updated_config, result = validator.validate_and_fix_terraform(
                config, auto_fix=False
            )

        # Should report conflicts but not fix them
        assert result.has_conflicts
        assert not result.has_fixes
