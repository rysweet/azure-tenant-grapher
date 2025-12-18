"""Tests for IaC format detection."""

import json

from src.deployment.format_detector import detect_iac_format


class TestDetectIaCFormat:
    """Tests for IaC format detection."""

    def test_detect_terraform_format(self, tmp_path):
        """Test Terraform format detection."""
        (tmp_path / "main.tf").write_text(
            'resource "azurerm_resource_group" "example" {}'
        )
        assert detect_iac_format(tmp_path) == "terraform"

    def test_detect_terraform_with_multiple_files(self, tmp_path):
        """Test Terraform detection with multiple .tf files."""
        (tmp_path / "main.tf").write_text("# Main")
        (tmp_path / "variables.tf").write_text("# Variables")
        assert detect_iac_format(tmp_path) == "terraform"

    def test_detect_bicep_format(self, tmp_path):
        """Test Bicep format detection."""
        (tmp_path / "main.bicep").write_text(
            "resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )
        assert detect_iac_format(tmp_path) == "bicep"

    def test_detect_arm_format(self, tmp_path):
        """Test ARM template format detection."""
        arm_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [],
        }
        (tmp_path / "template.json").write_text(json.dumps(arm_template))
        assert detect_iac_format(tmp_path) == "arm"

    def test_detect_unknown_format(self, tmp_path):
        """Test unknown format detection."""
        (tmp_path / "readme.txt").write_text("Not IaC")
        assert detect_iac_format(tmp_path) is None

    def test_detect_nonexistent_directory(self, tmp_path):
        """Test detection with non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        assert detect_iac_format(nonexistent) is None

    def test_detect_file_instead_of_directory(self, tmp_path):
        """Test detection when path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        assert detect_iac_format(file_path) is None

    def test_detect_arm_with_invalid_json(self, tmp_path):
        """Test ARM detection with invalid JSON file."""
        (tmp_path / "invalid.json").write_text("{invalid json")
        assert detect_iac_format(tmp_path) is None

    def test_detect_arm_with_non_template_json(self, tmp_path):
        """Test ARM detection with JSON that's not a template."""
        (tmp_path / "data.json").write_text('{"key": "value"}')
        assert detect_iac_format(tmp_path) is None
