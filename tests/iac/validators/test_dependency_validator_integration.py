"""
Integration test for DependencyValidator with TerraformEmitter.

Tests that the DependencyValidator is properly integrated into the
IaC generation pipeline and correctly validates generated Terraform configurations.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.iac.validators.dependency_validator import DependencyValidator


class TestDependencyValidatorIntegration:
    """Integration tests for DependencyValidator with TerraformEmitter."""

    def test_validator_called_during_emit(self):
        """Test that DependencyValidator is called during IaC generation."""
        emitter = TerraformEmitter()

        # Create test graph with a simple valid resource
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Patch the DependencyValidator to track if it was called
            with patch(
                "src.iac.emitters.terraform_emitter.DependencyValidator"
            ) as mock_validator_class:
                mock_validator = Mock()
                mock_result = Mock()
                mock_result.terraform_available = True
                mock_result.valid = True
                mock_result.errors = []
                mock_validator.validate.return_value = mock_result
                mock_validator_class.return_value = mock_validator

                # Generate IaC
                written_files = emitter.emit(graph, out_dir)

                # Verify DependencyValidator was instantiated
                mock_validator_class.assert_called_once()

                # Verify validate was called with correct parameters
                mock_validator.validate.assert_called_once()
                call_args = mock_validator.validate.call_args
                assert call_args[0][0] == out_dir  # First argument is out_dir
                assert call_args[1]["skip_init"] is True  # skip_init=True

    def test_validator_logs_errors_when_dependencies_invalid(self):
        """Test that validation errors are logged when dependencies are invalid."""
        emitter = TerraformEmitter()

        # Create test graph
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Patch DependencyValidator to return validation errors
            with patch(
                "src.iac.emitters.terraform_emitter.DependencyValidator"
            ) as mock_validator_class:
                from src.iac.validators.dependency_validator import DependencyError

                mock_validator = Mock()
                mock_result = Mock()
                mock_result.terraform_available = True
                mock_result.valid = False
                mock_result.errors = [
                    DependencyError(
                        resource_type="azurerm_virtual_machine",
                        resource_name="test_vm",
                        missing_reference="azurerm_network_interface.missing_nic",
                        error_message="Reference to undeclared resource",
                    )
                ]
                mock_validator.validate.return_value = mock_result
                mock_validator_class.return_value = mock_validator

                # Patch logger to capture error messages
                with patch("src.iac.emitters.terraform_emitter.logger") as mock_logger:
                    # Generate IaC
                    written_files = emitter.emit(graph, out_dir)

                    # Verify error was logged
                    error_calls = [
                        call for call in mock_logger.error.call_args_list if call
                    ]
                    assert len(error_calls) > 0

                    # Check for specific error message about dependency failure
                    error_messages = [str(call[0][0]) for call in error_calls]
                    assert any(
                        "Dependency validation failed" in msg for msg in error_messages
                    )
                    assert any("missing_nic" in msg for msg in error_messages)

    def test_validator_warns_when_terraform_not_available(self):
        """Test that a warning is logged when Terraform CLI is not available."""
        emitter = TerraformEmitter()

        # Create test graph
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Patch DependencyValidator to indicate Terraform not available
            with patch(
                "src.iac.emitters.terraform_emitter.DependencyValidator"
            ) as mock_validator_class:
                mock_validator = Mock()
                mock_result = Mock()
                mock_result.terraform_available = False
                mock_result.valid = True
                mock_result.errors = []
                mock_validator.validate.return_value = mock_result
                mock_validator_class.return_value = mock_validator

                # Patch logger to capture warning messages
                with patch("src.iac.emitters.terraform_emitter.logger") as mock_logger:
                    # Generate IaC
                    written_files = emitter.emit(graph, out_dir)

                    # Verify warning was logged
                    warning_calls = [
                        call for call in mock_logger.warning.call_args_list if call
                    ]
                    assert len(warning_calls) > 0

                    # Check for specific warning about Terraform not found
                    warning_messages = [str(call[0][0]) for call in warning_calls]
                    assert any(
                        "Terraform CLI not found" in msg for msg in warning_messages
                    )

    def test_validator_succeeds_with_valid_configuration(self):
        """Test that validation succeeds with a valid Terraform configuration."""
        emitter = TerraformEmitter()

        # Create test graph with valid resources
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Patch DependencyValidator to return success
            with patch(
                "src.iac.emitters.terraform_emitter.DependencyValidator"
            ) as mock_validator_class:
                mock_validator = Mock()
                mock_result = Mock()
                mock_result.terraform_available = True
                mock_result.valid = True
                mock_result.errors = []
                mock_validator.validate.return_value = mock_result
                mock_validator_class.return_value = mock_validator

                # Patch logger to capture info messages
                with patch("src.iac.emitters.terraform_emitter.logger") as mock_logger:
                    # Generate IaC
                    written_files = emitter.emit(graph, out_dir)

                    # Verify success message was logged
                    info_calls = [call for call in mock_logger.info.call_args_list if call]
                    info_messages = [str(call[0][0]) for call in info_calls]

                    # Check for validation success message
                    assert any(
                        "Dependency validation passed" in msg for msg in info_messages
                    )
