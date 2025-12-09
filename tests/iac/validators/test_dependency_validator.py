"""
Tests for DependencyValidator - Terraform resource reference validation.

Tests cover:
- Terraform CLI availability checking
- Terraform init and validate execution
- Dependency error parsing from JSON output
- Integration tests with actual Terraform validation
- Missing reference detection
"""

import json
import shutil
import subprocess
from unittest.mock import Mock, patch

import pytest

from src.iac.validators.dependency_validator import (
    DependencyError,
    DependencyValidationResult,
    DependencyValidator,
)


class TestDependencyValidatorUnit:
    """Unit tests for DependencyValidator methods."""

    def test_undeclared_pattern_matches_resource(self):
        """Test UNDECLARED_PATTERN regex matches undeclared resource errors."""
        validator = DependencyValidator()

        test_cases = [
            (
                'A managed resource "azurerm_network_interface" "missing_nic" has not been declared',
                "azurerm_network_interface",
                "missing_nic",
            ),
            (
                'A managed resource "azuread_user" "test_user" has not been declared',
                "azuread_user",
                "test_user",
            ),
            (
                'A managed resource "azurerm_virtual_machine" "vm1" has not been declared',
                "azurerm_virtual_machine",
                "vm1",
            ),
            (
                'A managed resource "azurerm_subnet" "subnet_1" has not been declared',
                "azurerm_subnet",
                "subnet_1",
            ),
        ]

        for message, expected_type, expected_name in test_cases:
            match = validator.UNDECLARED_PATTERN.search(message)
            assert match is not None, f"Pattern should match: {message}"
            assert match.group(1) == expected_type
            assert match.group(2) == expected_name

    def test_undeclared_pattern_ignores_non_azure_resources(self):
        """Test UNDECLARED_PATTERN ignores non-Azure resource references."""
        validator = DependencyValidator()

        non_matching_cases = [
            'A managed resource "aws_instance" "ec2" has not been declared',
            'A managed resource "google_compute_instance" "vm" has not been declared',
            'A managed resource "random_string" "test" has not been declared',
            "Some other error message",
            'A managed resource "invalid_format" has not been declared',
        ]

        for message in non_matching_cases:
            match = validator.UNDECLARED_PATTERN.search(message)
            assert match is None, f"Pattern should NOT match: {message}"

    @patch("shutil.which")
    def test_check_terraform_available_when_installed(self, mock_which):
        """Test _check_terraform_available returns True when terraform is installed."""
        mock_which.return_value = "/usr/local/bin/terraform"

        validator = DependencyValidator()

        assert validator._terraform_available is True
        mock_which.assert_called_once_with("terraform")

    @patch("shutil.which")
    def test_check_terraform_available_when_not_installed(self, mock_which):
        """Test _check_terraform_available returns False when terraform not installed."""
        mock_which.return_value = None

        validator = DependencyValidator()

        assert validator._terraform_available is False
        mock_which.assert_called_once_with("terraform")

    def test_parse_dependency_errors_with_valid_json(self):
        """Test _parse_dependency_errors parses terraform validate JSON correctly."""
        validator = DependencyValidator()

        validate_output = json.dumps(
            {
                "valid": False,
                "diagnostics": [
                    {
                        "severity": "error",
                        "summary": "Reference to undeclared resource",
                        "detail": 'A managed resource "azurerm_network_interface" "missing_nic" has not been declared in the root module.',
                        "address": "azurerm_virtual_machine.vm1",
                    },
                    {
                        "severity": "error",
                        "summary": "Reference to undeclared resource",
                        "detail": 'A managed resource "azurerm_storage_account" "missing_storage" has not been declared in the root module.',
                        "address": "azurerm_virtual_machine.vm1",
                    },
                    {
                        "severity": "warning",
                        "summary": "Deprecated resource",
                        "detail": "This resource type is deprecated",
                        "address": "azurerm_old_resource.test",
                    },
                ],
            }
        )

        errors = validator._parse_dependency_errors(validate_output)

        assert len(errors) == 2  # Only errors, not warnings

        # Check first error
        assert errors[0].resource_type == "azurerm_virtual_machine"
        assert errors[0].resource_name == "vm1"
        assert errors[0].missing_reference == "azurerm_network_interface.missing_nic"
        assert "azurerm_network_interface" in errors[0].error_message
        assert "missing_nic" in errors[0].error_message

        # Check second error
        assert errors[1].resource_type == "azurerm_virtual_machine"
        assert errors[1].resource_name == "vm1"
        assert errors[1].missing_reference == "azurerm_storage_account.missing_storage"

    def test_parse_dependency_errors_with_no_errors(self):
        """Test _parse_dependency_errors returns empty list when validation passes."""
        validator = DependencyValidator()

        validate_output = json.dumps(
            {
                "valid": True,
                "diagnostics": [],
            }
        )

        errors = validator._parse_dependency_errors(validate_output)

        assert len(errors) == 0

    def test_parse_dependency_errors_with_invalid_json(self):
        """Test _parse_dependency_errors handles invalid JSON gracefully."""
        validator = DependencyValidator()

        invalid_json = "not valid json{"

        errors = validator._parse_dependency_errors(invalid_json)

        assert len(errors) == 0

    def test_parse_dependency_errors_with_none(self):
        """Test _parse_dependency_errors handles None input."""
        validator = DependencyValidator()

        errors = validator._parse_dependency_errors(None)

        assert len(errors) == 0

    def test_parse_dependency_errors_without_address(self):
        """Test _parse_dependency_errors handles diagnostics without address field."""
        validator = DependencyValidator()

        validate_output = json.dumps(
            {
                "valid": False,
                "diagnostics": [
                    {
                        "severity": "error",
                        "summary": "Reference to undeclared resource",
                        "detail": 'A managed resource "azurerm_subnet" "test" has not been declared in the root module.',
                        # No "address" field
                    },
                ],
            }
        )

        errors = validator._parse_dependency_errors(validate_output)

        assert len(errors) == 1
        assert errors[0].resource_type == "unknown"
        assert errors[0].resource_name == "unknown"
        assert errors[0].missing_reference == "azurerm_subnet.test"


class TestDependencyValidatorValidateMethod:
    """Tests for the main validate() method."""

    @patch("shutil.which")
    def test_validate_returns_success_when_terraform_not_available(
        self, mock_which, tmp_path
    ):
        """Test validate returns success (skip) when terraform not installed."""
        mock_which.return_value = None

        validator = DependencyValidator()
        result = validator.validate(tmp_path)

        assert result.valid is True  # Don't fail if terraform not available
        assert result.terraform_available is False
        assert len(result.errors) == 0

    @patch("shutil.which")
    def test_validate_returns_error_when_path_not_exists(self, mock_which, tmp_path):
        """Test validate returns error when output path doesn't exist."""
        mock_which.return_value = "/usr/local/bin/terraform"

        validator = DependencyValidator()
        non_existent_path = tmp_path / "does_not_exist"
        result = validator.validate(non_existent_path)

        assert result.valid is False
        assert result.terraform_available is True
        assert len(result.errors) == 0

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_runs_terraform_init_by_default(
        self, mock_run, mock_which, tmp_path
    ):
        """Test validate runs terraform init unless skip_init=True."""
        mock_which.return_value = "/usr/local/bin/terraform"

        # Mock terraform init success
        init_result = Mock()
        init_result.returncode = 0

        # Mock terraform validate success
        validate_result = Mock()
        validate_result.returncode = 0
        validate_result.stdout = json.dumps({"valid": True, "diagnostics": []})

        mock_run.side_effect = [init_result, validate_result]

        validator = DependencyValidator()
        result = validator.validate(tmp_path, skip_init=False)

        assert result.valid is True
        assert mock_run.call_count == 2  # init + validate

        # Verify terraform init was called
        init_call = mock_run.call_args_list[0]
        assert init_call[0][0][0] == "terraform"
        assert "init" in init_call[0][0]

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_skips_init_when_requested(self, mock_run, mock_which, tmp_path):
        """Test validate skips terraform init when skip_init=True."""
        mock_which.return_value = "/usr/local/bin/terraform"

        # Mock terraform validate success
        validate_result = Mock()
        validate_result.returncode = 0
        validate_result.stdout = json.dumps({"valid": True, "diagnostics": []})

        mock_run.return_value = validate_result

        validator = DependencyValidator()
        result = validator.validate(tmp_path, skip_init=True)

        assert result.valid is True
        assert mock_run.call_count == 1  # Only validate, no init

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_returns_error_when_init_fails(
        self, mock_run, mock_which, tmp_path
    ):
        """Test validate returns error when terraform init fails."""
        mock_which.return_value = "/usr/local/bin/terraform"

        # Mock terraform init failure
        init_result = Mock()
        init_result.returncode = 1

        mock_run.return_value = init_result

        validator = DependencyValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert result.terraform_available is True

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_validate_handles_subprocess_timeout(self, mock_run, mock_which, tmp_path):
        """Test validate handles subprocess timeout gracefully."""
        mock_which.return_value = "/usr/local/bin/terraform"

        # Mock terraform init timeout
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="terraform", timeout=60)

        validator = DependencyValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False


class TestDependencyValidatorIntegration:
    """Integration tests with actual terraform (if available)."""

    @pytest.fixture
    def terraform_available(self):
        """Check if terraform CLI is available."""
        return shutil.which("terraform") is not None

    @pytest.fixture
    def valid_terraform_config(self, tmp_path):
        """Create a valid Terraform configuration."""
        (tmp_path / "main.tf").write_text("""
resource "azurerm_resource_group" "rg" {
  name     = "test-rg"
  location = "East US"
}

resource "azurerm_storage_account" "storage" {
  name                     = "teststorage"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
""")
        return tmp_path

    @pytest.fixture
    def invalid_terraform_config(self, tmp_path):
        """Create a Terraform configuration with missing dependencies."""
        (tmp_path / "main.tf").write_text("""
# This references a network interface that doesn't exist
resource "azurerm_linux_virtual_machine" "vm" {
  name                  = "test-vm"
  location              = "East US"
  resource_group_name   = "test-rg"
  size                  = "Standard_DS1_v2"
  admin_username        = "adminuser"

  network_interface_ids = [
    azurerm_network_interface.missing_nic.id
  ]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  admin_ssh_key {
    username   = "adminuser"
    public_key = "ssh-rsa AAAAB3..."
  }
}

# This references a subnet that doesn't exist
resource "azurerm_network_interface" "nic2" {
  name                = "test-nic2"
  location            = "East US"
  resource_group_name = "test-rg"

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.missing_subnet.id
    private_ip_address_allocation = "Dynamic"
  }
}
""")
        return tmp_path

    @pytest.mark.skipif(
        shutil.which("terraform") is None,
        reason="Terraform CLI not found - install from https://www.terraform.io/downloads",
    )
    def test_validate_passes_with_valid_config(self, valid_terraform_config):
        """Test validation passes with valid Terraform configuration."""
        validator = DependencyValidator()
        result = validator.validate(valid_terraform_config)

        assert result.terraform_available is True
        assert result.valid is True
        assert len(result.errors) == 0

    @pytest.mark.skipif(
        shutil.which("terraform") is None,
        reason="Terraform CLI not found - install from https://www.terraform.io/downloads",
    )
    def test_validate_detects_missing_dependencies(self, invalid_terraform_config):
        """Test validation detects missing resource dependencies."""
        validator = DependencyValidator()
        result = validator.validate(invalid_terraform_config)

        assert result.terraform_available is True
        assert result.valid is False
        assert len(result.errors) >= 2  # At least the two missing references

        # Check that missing references are detected
        missing_refs = [error.missing_reference for error in result.errors]
        assert any("missing_nic" in ref for ref in missing_refs)
        assert any("missing_subnet" in ref for ref in missing_refs)

    @pytest.mark.skipif(
        shutil.which("terraform") is None,
        reason="Terraform CLI not found - install from https://www.terraform.io/downloads",
    )
    def test_validate_provides_detailed_error_info(self, invalid_terraform_config):
        """Test validation provides detailed information about errors."""
        validator = DependencyValidator()
        result = validator.validate(invalid_terraform_config)

        assert result.terraform_available is True
        assert result.valid is False

        # Check error details
        for error in result.errors:
            assert error.resource_type != ""
            assert error.resource_name != ""
            assert error.missing_reference != ""
            assert error.error_message != ""
            assert error.missing_reference.startswith("azurerm_")


class TestDependencyValidationResult:
    """Tests for DependencyValidationResult dataclass."""

    def test_result_default_values(self):
        """Test DependencyValidationResult has correct default values."""
        result = DependencyValidationResult(
            valid=True,
            terraform_available=True,
        )

        assert result.valid is True
        assert result.terraform_available is True
        assert result.errors == []
        assert result.total_errors == 0
        assert result.validation_output is None

    def test_result_with_errors(self):
        """Test DependencyValidationResult with errors."""
        errors = [
            DependencyError(
                resource_type="azurerm_virtual_machine",
                resource_name="vm1",
                missing_reference="azurerm_network_interface.nic1",
                error_message="Reference to undeclared resource",
            ),
            DependencyError(
                resource_type="azurerm_virtual_machine",
                resource_name="vm2",
                missing_reference="azurerm_subnet.subnet1",
                error_message="Reference to undeclared resource",
            ),
        ]

        result = DependencyValidationResult(
            valid=False,
            terraform_available=True,
            errors=errors,
            total_errors=2,
        )

        assert result.valid is False
        assert len(result.errors) == 2
        assert result.total_errors == 2


class TestDependencyError:
    """Tests for DependencyError dataclass."""

    def test_dependency_error_creation(self):
        """Test DependencyError can be created with all fields."""
        error = DependencyError(
            resource_type="azurerm_virtual_machine",
            resource_name="test_vm",
            missing_reference="azurerm_network_interface.test_nic",
            error_message="Reference to undeclared resource: azurerm_network_interface.test_nic",
        )

        assert error.resource_type == "azurerm_virtual_machine"
        assert error.resource_name == "test_vm"
        assert error.missing_reference == "azurerm_network_interface.test_nic"
        assert "test_nic" in error.error_message
