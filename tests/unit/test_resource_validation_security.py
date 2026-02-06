"""
Unit tests for resource validation security features (HIGH priority fixes).

This module tests the security enhancements added to resource fidelity validation:
- Input validation for resource_type parameter
- Error message sanitization
- Security metadata in exports
"""

from unittest.mock import Mock, patch

import pytest

from src.validation.resource_fidelity_calculator import (
    ResourceFidelityCalculator,
    _sanitize_error_message,
)


class TestResourceTypeValidation:
    """Test resource type input validation (Security Finding #3)."""

    @pytest.fixture
    def calculator(self):
        """Create calculator with mock dependencies."""
        manager = Mock()
        manager.execute_read = Mock(return_value=[])
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )

    def test_valid_resource_type_microsoft_storage(self, calculator):
        """Test validation accepts valid Microsoft.Storage resource type."""
        # Should not raise
        calculator._validate_resource_type("Microsoft.Storage/storageAccounts")

    def test_valid_resource_type_microsoft_compute(self, calculator):
        """Test validation accepts valid Microsoft.Compute resource type."""
        # Should not raise
        calculator._validate_resource_type("Microsoft.Compute/virtualMachines")

    def test_valid_resource_type_with_child(self, calculator):
        """Test validation accepts resource types with child types."""
        # Should not raise
        calculator._validate_resource_type(
            "Microsoft.Network/virtualNetworks/subnets"
        )

    def test_invalid_resource_type_no_provider(self, calculator):
        """Test validation rejects resource type without provider."""
        with pytest.raises(ValueError, match="Invalid resource type format"):
            calculator._validate_resource_type("storageAccounts")

    def test_invalid_resource_type_no_slash(self, calculator):
        """Test validation rejects resource type without slash separator."""
        with pytest.raises(ValueError, match="Invalid resource type format"):
            calculator._validate_resource_type("Microsoft.Storage")

    def test_invalid_resource_type_lowercase_provider(self, calculator):
        """Test validation rejects lowercase provider name."""
        with pytest.raises(ValueError, match="Invalid resource type format"):
            calculator._validate_resource_type("microsoft.storage/storageAccounts")

    def test_invalid_resource_type_special_chars(self, calculator):
        """Test validation rejects special characters in resource type."""
        with pytest.raises(ValueError, match="Invalid resource type format"):
            calculator._validate_resource_type("Microsoft.Storage/storage@Accounts")

    def test_valid_resource_type_non_microsoft_provider(self, calculator, caplog):
        """Test validation accepts non-Microsoft providers with warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            calculator._validate_resource_type("Contoso.Custom/resources")

        # Should log warning but not raise
        assert "does not start with 'Microsoft.'" in caplog.text

    def test_calculate_fidelity_with_valid_resource_type(self, calculator):
        """Test calculate_fidelity accepts valid resource type filter."""
        calculator.session_manager.execute_read.return_value = []

        # Should not raise
        result = calculator.calculate_fidelity(
            resource_type="Microsoft.Storage/storageAccounts"
        )

        assert result is not None

    def test_calculate_fidelity_with_invalid_resource_type(self, calculator):
        """Test calculate_fidelity rejects invalid resource type."""
        with pytest.raises(ValueError, match="Invalid resource type format"):
            calculator.calculate_fidelity(resource_type="invalid-type")


class TestErrorMessageSanitization:
    """Test error message sanitization (Security Finding #4)."""

    def test_sanitize_removes_passwords(self):
        """Test sanitization removes password values."""
        error = Exception("Connection failed: password=SecretPass123")  # #ggignore

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "SecretPass123" not in sanitized  # #ggignore
        assert "password=[REDACTED]" in sanitized

    def test_sanitize_removes_keys(self):
        """Test sanitization removes key values."""
        error = Exception("Authentication error: key=abc123xyz")

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "abc123xyz" not in sanitized
        assert "key=[REDACTED]" in sanitized

    def test_sanitize_removes_secrets(self):
        """Test sanitization removes secret values."""
        error = Exception("Config error: secret=mysecretvalue")

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "mysecretvalue" not in sanitized
        assert "secret=[REDACTED]" in sanitized

    def test_sanitize_removes_tokens(self):
        """Test sanitization removes token values."""
        error = Exception("Auth failed: token=bearer_token_xyz")

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "bearer_token_xyz" not in sanitized
        assert "token=[REDACTED]" in sanitized

    def test_sanitize_removes_connection_strings(self):
        """Test sanitization removes connection string values."""
        error = Exception("DB error: connection_string=Server=myserver;Password=pass123")

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "connection_string=[REDACTED]" in sanitized

    def test_sanitize_removes_subscription_ids(self):
        """Test sanitization removes subscription IDs (UUIDs)."""
        error = Exception(
            "Access denied to 12345678-1234-1234-1234-123456789abc"
        )

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "12345678-1234-1234-1234-123456789abc" not in sanitized
        assert "[SUBSCRIPTION-ID]" in sanitized

    def test_sanitize_removes_resource_paths(self):
        """Test sanitization removes Azure resource paths."""
        error = Exception(
            "Resource not found: /subscriptions/abc/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
        )

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "[RESOURCE-PATH]" in sanitized

    def test_sanitize_debug_mode_preserves_details(self):
        """Test debug mode preserves full error details."""
        error = Exception("password=secret123")  # #ggignore

        sanitized = _sanitize_error_message(error, debug_mode=True)

        # In debug mode, should preserve original error
        assert "password=secret123" in sanitized  # #ggignore

    def test_sanitize_multiple_sensitive_values(self):
        """Test sanitization handles multiple sensitive values."""
        error = Exception(
            "Error: password=pass123, key=key456, secret=secret789"  # #ggignore
        )

        sanitized = _sanitize_error_message(error, debug_mode=False)

        assert "pass123" not in sanitized  # #ggignore
        assert "key456" not in sanitized  # #ggignore
        assert "secret789" not in sanitized  # #ggignore
        assert "password=[REDACTED]" in sanitized
        assert "key=[REDACTED]" in sanitized
        assert "secret=[REDACTED]" in sanitized


class TestNeo4jErrorHandling:
    """Test Neo4j error handling with sanitization."""

    @pytest.fixture
    def calculator(self):
        """Create calculator with mock dependencies."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )

    def test_calculate_fidelity_sanitizes_neo4j_errors(self, calculator):
        """Test that Neo4j errors are sanitized before raising."""
        # Mock Neo4j query to fail with sensitive info
        calculator.session_manager.execute_read.side_effect = Exception(
            "Neo4j auth failed: password=dbpassword123"  # #ggignore
        )

        with pytest.raises(RuntimeError) as exc_info:
            calculator.calculate_fidelity()

        # Should not contain sensitive password
        assert "dbpassword123" not in str(exc_info.value)  # #ggignore
        assert "password=[REDACTED]" in str(exc_info.value)
