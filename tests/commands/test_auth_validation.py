"""Unit tests for auth.py input validation functions.

Issue #539: Add input validation for subprocess calls to prevent command injection
"""

import pytest

from src.commands.auth import (
    validate_app_id,
    validate_app_name,
    validate_redirect_uri,
    validate_tenant_id,
)


class TestValidateAppName:
    """Tests for app name validation."""

    def test_valid_app_name_simple(self):
        """Test validation with simple app name."""
        result = validate_app_name("MyApp")
        assert result == "MyApp"

    def test_valid_app_name_with_spaces(self):
        """Test validation with spaces in name."""
        result = validate_app_name("My App Name")
        assert result == "My App Name"

    def test_valid_app_name_with_hyphens(self):
        """Test validation with hyphens."""
        result = validate_app_name("My-App-Name")
        assert result == "My-App-Name"

    def test_valid_app_name_with_underscores(self):
        """Test validation with underscores."""
        result = validate_app_name("My_App_Name")
        assert result == "My_App_Name"

    def test_valid_app_name_with_numbers(self):
        """Test validation with numbers."""
        result = validate_app_name("MyApp123")
        assert result == "MyApp123"

    def test_valid_app_name_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = validate_app_name("  MyApp  ")
        assert result == "MyApp"

    def test_empty_name_raises_error(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="App name cannot be empty"):
            validate_app_name("")

    def test_whitespace_only_name_raises_error(self):
        """Test that whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="App name cannot be empty"):
            validate_app_name("   ")

    def test_invalid_characters_raises_error(self):
        """Test that special characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid app name format"):
            validate_app_name("My$App")

    def test_semicolon_injection_attempt_raises_error(self):
        """Test that semicolon injection attempt is blocked."""
        with pytest.raises(ValueError, match="Invalid app name format"):
            validate_app_name("MyApp; rm -rf /")

    def test_pipe_injection_attempt_raises_error(self):
        """Test that pipe injection attempt is blocked."""
        with pytest.raises(ValueError, match="Invalid app name format"):
            validate_app_name("MyApp | cat /etc/passwd")

    def test_backtick_injection_attempt_raises_error(self):
        """Test that backtick injection attempt is blocked."""
        with pytest.raises(ValueError, match="Invalid app name format"):
            validate_app_name("MyApp`whoami`")

    def test_dollar_sign_injection_attempt_raises_error(self):
        """Test that dollar sign command substitution is blocked."""
        with pytest.raises(ValueError, match="Invalid app name format"):
            validate_app_name("MyApp$(whoami)")


class TestValidateRedirectUri:
    """Tests for redirect URI validation."""

    def test_valid_http_uri(self):
        """Test validation with http URI."""
        result = validate_redirect_uri("http://localhost:3000")
        assert result == "http://localhost:3000"

    def test_valid_https_uri(self):
        """Test validation with https URI."""
        result = validate_redirect_uri("https://example.com/callback")
        assert result == "https://example.com/callback"

    def test_valid_uri_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = validate_redirect_uri("  http://localhost:3000  ")
        assert result == "http://localhost:3000"

    def test_empty_uri_raises_error(self):
        """Test that empty URI raises ValueError."""
        with pytest.raises(ValueError, match="Redirect URI cannot be empty"):
            validate_redirect_uri("")

    def test_whitespace_only_uri_raises_error(self):
        """Test that whitespace-only URI raises ValueError."""
        with pytest.raises(ValueError, match="Redirect URI cannot be empty"):
            validate_redirect_uri("   ")

    def test_invalid_protocol_raises_error(self):
        """Test that invalid protocol raises ValueError."""
        with pytest.raises(ValueError, match="Invalid redirect URI format"):
            validate_redirect_uri("ftp://example.com")

    def test_no_protocol_raises_error(self):
        """Test that missing protocol raises ValueError."""
        with pytest.raises(ValueError, match="Invalid redirect URI format"):
            validate_redirect_uri("example.com")


class TestValidateTenantId:
    """Tests for tenant ID validation."""

    def test_valid_tenant_id(self):
        """Test validation with valid GUID."""
        tenant_id = "12345678-1234-1234-1234-123456789012"
        result = validate_tenant_id(tenant_id)
        assert result == tenant_id

    def test_valid_tenant_id_uppercase(self):
        """Test validation with uppercase GUID."""
        tenant_id = "12345678-1234-1234-1234-123456789ABC"
        result = validate_tenant_id(tenant_id)
        assert result == tenant_id

    def test_valid_tenant_id_mixed_case(self):
        """Test validation with mixed case GUID."""
        tenant_id = "12345678-1234-1234-1234-123456789AbC"
        result = validate_tenant_id(tenant_id)
        assert result == tenant_id

    def test_valid_tenant_id_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        tenant_id = "12345678-1234-1234-1234-123456789012"
        result = validate_tenant_id(f"  {tenant_id}  ")
        assert result == tenant_id

    def test_empty_tenant_id_raises_error(self):
        """Test that empty tenant ID raises ValueError."""
        with pytest.raises(ValueError, match="Tenant ID cannot be empty"):
            validate_tenant_id("")

    def test_whitespace_only_tenant_id_raises_error(self):
        """Test that whitespace-only tenant ID raises ValueError."""
        with pytest.raises(ValueError, match="Tenant ID cannot be empty"):
            validate_tenant_id("   ")

    def test_invalid_guid_format_raises_error(self):
        """Test that invalid GUID format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            validate_tenant_id("not-a-guid")

    def test_guid_without_hyphens_raises_error(self):
        """Test that GUID without hyphens raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            validate_tenant_id("12345678123412341234123456789012")

    def test_guid_wrong_length_raises_error(self):
        """Test that GUID with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            validate_tenant_id("12345678-1234-1234-1234-12345678901")

    def test_guid_with_invalid_characters_raises_error(self):
        """Test that GUID with invalid characters raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            validate_tenant_id("12345678-1234-1234-1234-12345678901Z")

    def test_injection_attempt_raises_error(self):
        """Test that injection attempt is blocked."""
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            validate_tenant_id("12345678-1234-1234-1234-123456789012; rm -rf /")


class TestValidateAppId:
    """Tests for application ID validation."""

    def test_valid_app_id(self):
        """Test validation with valid GUID."""
        app_id = "12345678-1234-1234-1234-123456789012"
        result = validate_app_id(app_id)
        assert result == app_id

    def test_valid_app_id_uppercase(self):
        """Test validation with uppercase GUID."""
        app_id = "12345678-1234-1234-1234-123456789ABC"
        result = validate_app_id(app_id)
        assert result == app_id

    def test_valid_app_id_mixed_case(self):
        """Test validation with mixed case GUID."""
        app_id = "12345678-1234-1234-1234-123456789AbC"
        result = validate_app_id(app_id)
        assert result == app_id

    def test_valid_app_id_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        app_id = "12345678-1234-1234-1234-123456789012"
        result = validate_app_id(f"  {app_id}  ")
        assert result == app_id

    def test_empty_app_id_raises_error(self):
        """Test that empty app ID raises ValueError."""
        with pytest.raises(ValueError, match="Application ID cannot be empty"):
            validate_app_id("")

    def test_whitespace_only_app_id_raises_error(self):
        """Test that whitespace-only app ID raises ValueError."""
        with pytest.raises(ValueError, match="Application ID cannot be empty"):
            validate_app_id("   ")

    def test_invalid_guid_format_raises_error(self):
        """Test that invalid GUID format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid application ID format"):
            validate_app_id("not-a-guid")

    def test_guid_without_hyphens_raises_error(self):
        """Test that GUID without hyphens raises ValueError."""
        with pytest.raises(ValueError, match="Invalid application ID format"):
            validate_app_id("12345678123412341234123456789012")

    def test_guid_wrong_length_raises_error(self):
        """Test that GUID with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid application ID format"):
            validate_app_id("12345678-1234-1234-1234-12345678901")

    def test_guid_with_invalid_characters_raises_error(self):
        """Test that GUID with invalid characters raises ValueError."""
        with pytest.raises(ValueError, match="Invalid application ID format"):
            validate_app_id("12345678-1234-1234-1234-12345678901Z")

    def test_injection_attempt_raises_error(self):
        """Test that injection attempt is blocked."""
        with pytest.raises(ValueError, match="Invalid application ID format"):
            validate_app_id("12345678-1234-1234-1234-123456789012; whoami")


class TestCommandInjectionPrevention:
    """Integration tests for command injection prevention."""

    def test_all_validators_block_semicolon_injection(self):
        """Test that all validators block semicolon-based injection."""
        with pytest.raises(ValueError):
            validate_app_name("test; rm -rf /")

        with pytest.raises(ValueError):
            validate_tenant_id("12345678-1234-1234-1234-123456789012; whoami")

        with pytest.raises(ValueError):
            validate_app_id("12345678-1234-1234-1234-123456789012; whoami")

    def test_all_validators_block_pipe_injection(self):
        """Test that all validators block pipe-based injection."""
        with pytest.raises(ValueError):
            validate_app_name("test | cat /etc/passwd")

    def test_all_validators_block_backtick_injection(self):
        """Test that all validators block backtick command substitution."""
        with pytest.raises(ValueError):
            validate_app_name("test`whoami`")

    def test_all_validators_block_dollar_injection(self):
        """Test that all validators block dollar command substitution."""
        with pytest.raises(ValueError):
            validate_app_name("test$(whoami)")
