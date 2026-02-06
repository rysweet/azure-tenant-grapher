"""
Unit tests for Resource Fidelity Security Controls.

Tests security redaction, sensitive property detection, and data protection
in resource-level fidelity validation.

Testing pyramid distribution: Part of 60% unit tests
"""

from unittest.mock import Mock, patch

import pytest

# These imports will fail initially - that's expected for TDD
try:
    from src.validation.resource_fidelity_calculator import (
        PropertyComparison,
        RedactionLevel,
        ResourceFidelityCalculator,
    )
except ImportError:
    # TDD: Module doesn't exist yet
    pass


class TestSensitivePropertyDetection:
    """Test detection of sensitive properties requiring redaction."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_detects_password_properties(self, calculator):
        """Test detection of password-related properties."""
        sensitive_passwords = [
            "password",
            "adminPassword",
            "properties.password",
            "properties.osProfile.adminPassword",
            "properties.linuxConfiguration.ssh.publicKeys[0].password",
        ]

        for prop_path in sensitive_passwords:
            assert calculator._is_sensitive_property(prop_path) is True, f"Failed to detect: {prop_path}"

    def test_detects_key_properties(self, calculator):
        """Test detection of key-related properties."""
        sensitive_keys = [
            "key",
            "apiKey",
            "secretKey",
            "properties.storageAccountKeys",
            "properties.primaryKey",
            "properties.secondaryKey",
            "properties.keys[0].value",
        ]

        for prop_path in sensitive_keys:
            assert calculator._is_sensitive_property(prop_path) is True, f"Failed to detect: {prop_path}"

    def test_detects_secret_properties(self, calculator):
        """Test detection of secret-related properties."""
        sensitive_secrets = [
            "secret",
            "clientSecret",
            "properties.secretUri",
            "properties.secrets[0].value",
            "properties.vaultSecrets",
        ]

        for prop_path in sensitive_secrets:
            assert calculator._is_sensitive_property(prop_path) is True, f"Failed to detect: {prop_path}"

    def test_detects_token_properties(self, calculator):
        """Test detection of token-related properties."""
        sensitive_tokens = [
            "token",
            "accessToken",
            "refreshToken",
            "properties.bearerToken",
            "properties.sasToken",
        ]

        for prop_path in sensitive_tokens:
            assert calculator._is_sensitive_property(prop_path) is True, f"Failed to detect: {prop_path}"

    def test_detects_connection_string_properties(self, calculator):
        """Test detection of connection string properties."""
        sensitive_connections = [
            "connectionString",
            "properties.connectionStrings[0].connectionString",
            "properties.defaultPrimaryConnectionString",
            "properties.defaultSecondaryConnectionString",
        ]

        for prop_path in sensitive_connections:
            assert calculator._is_sensitive_property(prop_path) is True, f"Failed to detect: {prop_path}"

    def test_does_not_detect_non_sensitive_properties(self, calculator):
        """Test that non-sensitive properties are not flagged."""
        non_sensitive = [
            "sku.name",
            "location",
            "tags.environment",
            "properties.accessTier",
            "properties.publicIPAllocationMethod",
            "name",
            "type",
            "id",
        ]

        for prop_path in non_sensitive:
            assert calculator._is_sensitive_property(prop_path) is False, f"Incorrectly detected as sensitive: {prop_path}"


class TestRedactionLevelFull:
    """Test FULL redaction level (default, most secure)."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_full_redaction_redacts_passwords(self, calculator):
        """Test FULL redaction completely hides passwords."""
        comparison = PropertyComparison(
            property_path="properties.adminPassword",
            source_value="MySecretPassword123!",
            target_value="MySecretPassword456!",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is True
        assert redacted.source_value == "[REDACTED]"
        assert redacted.target_value == "[REDACTED]"
        assert redacted.match is True  # Redacted values always match

    def test_full_redaction_redacts_connection_strings(self, calculator):
        """Test FULL redaction completely hides connection strings."""
        comparison = PropertyComparison(
            property_path="properties.connectionStrings[0].connectionString",
            source_value="Server=tcp:myserver.database.windows.net;Password=Secret123;",
            target_value="Server=tcp:myserver-dr.database.windows.net;Password=Secret456;",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is True
        assert redacted.source_value == "[REDACTED]"
        assert redacted.target_value == "[REDACTED]"

    def test_full_redaction_redacts_api_keys(self, calculator):
        """Test FULL redaction hides API keys."""
        comparison = PropertyComparison(
            property_path="properties.apiKey",
            source_value="sk-1234567890abcdefghij",
            target_value="sk-0987654321zyxwvutsr",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is True
        assert "sk-" not in redacted.source_value
        assert "sk-" not in redacted.target_value

    def test_full_redaction_preserves_non_sensitive(self, calculator):
        """Test FULL redaction preserves non-sensitive properties."""
        comparison = PropertyComparison(
            property_path="sku.name",
            source_value="Standard_LRS",
            target_value="Premium_LRS",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is False
        assert redacted.source_value == "Standard_LRS"
        assert redacted.target_value == "Premium_LRS"


class TestRedactionLevelMinimal:
    """Test MINIMAL redaction level (balances security and visibility)."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_minimal_redaction_preserves_server_info(self, calculator):
        """Test MINIMAL redaction keeps server information visible."""
        comparison = PropertyComparison(
            property_path="properties.connectionStrings[0].connectionString",
            source_value="Server=tcp:myserver.database.windows.net,1433;Initial Catalog=mydb;User ID=admin;Password=Secret123;",
            target_value="Server=tcp:myserver-dr.database.windows.net,1433;Initial Catalog=mydb;User ID=admin;Password=Secret456;",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.MINIMAL)

        # Should preserve server hostname
        assert "myserver.database.windows.net" in redacted.source_value
        assert "myserver-dr.database.windows.net" in redacted.target_value
        # But redact password
        assert "Secret123" not in redacted.source_value
        assert "Secret456" not in redacted.target_value

    def test_minimal_redaction_redacts_passwords(self, calculator):
        """Test MINIMAL redaction still redacts password values."""
        comparison = PropertyComparison(
            property_path="properties.adminPassword",
            source_value="MySecretPassword123!",
            target_value="MySecretPassword456!",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.MINIMAL)

        assert redacted.redacted is True
        assert redacted.source_value == "[REDACTED]"
        assert redacted.target_value == "[REDACTED]"

    def test_minimal_redaction_shows_key_length(self, calculator):
        """Test MINIMAL redaction shows key length but not value."""
        comparison = PropertyComparison(
            property_path="properties.apiKey",
            source_value="sk-1234567890abcdefghij",
            target_value="sk-0987654321zyxwvutsr",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.MINIMAL)

        # Should show length or format hint
        assert redacted.redacted is True
        assert "[REDACTED:" in redacted.source_value or "[REDACTED]" in redacted.source_value


class TestRedactionLevelNone:
    """Test NONE redaction level (no redaction, for debugging only)."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_none_redaction_preserves_passwords(self, calculator):
        """Test NONE redaction shows passwords (dangerous!)."""
        comparison = PropertyComparison(
            property_path="properties.adminPassword",
            source_value="MySecretPassword123!",
            target_value="MySecretPassword456!",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.NONE)

        assert redacted.redacted is False
        assert redacted.source_value == "MySecretPassword123!"
        assert redacted.target_value == "MySecretPassword456!"

    def test_none_redaction_preserves_connection_strings(self, calculator):
        """Test NONE redaction shows full connection strings."""
        comparison = PropertyComparison(
            property_path="properties.connectionStrings[0].connectionString",
            source_value="Server=tcp:myserver.database.windows.net;Password=Secret123;",
            target_value="Server=tcp:myserver-dr.database.windows.net;Password=Secret456;",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.NONE)

        assert redacted.redacted is False
        assert "Password=Secret123" in redacted.source_value
        assert "Password=Secret456" in redacted.target_value


class TestSecurityWarnings:
    """Test security warning generation in validation reports."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_full_redaction_includes_security_warnings(self, calculator):
        """Test FULL redaction level includes appropriate warnings."""
        warnings = calculator._generate_security_warnings(RedactionLevel.FULL)

        assert len(warnings) > 0
        assert any("FULL" in w for w in warnings)
        assert any("redacted" in w.lower() for w in warnings)

    def test_minimal_redaction_includes_security_warnings(self, calculator):
        """Test MINIMAL redaction level includes warnings about partial visibility."""
        warnings = calculator._generate_security_warnings(RedactionLevel.MINIMAL)

        assert len(warnings) > 0
        assert any("MINIMAL" in w for w in warnings)
        assert any("visible" in w.lower() or "partial" in w.lower() for w in warnings)

    def test_none_redaction_includes_strong_warnings(self, calculator):
        """Test NONE redaction level includes strong security warnings."""
        warnings = calculator._generate_security_warnings(RedactionLevel.NONE)

        assert len(warnings) > 0
        assert any("NONE" in w or "no redaction" in w.lower() for w in warnings)
        assert any("sensitive" in w.lower() for w in warnings)


class TestRedactionInPropertyComparisons:
    """Test redaction integration in property comparison workflow."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_compare_properties_applies_redaction(self, calculator):
        """Test that property comparison automatically applies redaction."""
        source_props = {
            "adminPassword": "SecretPass123!",
            "sku": {"name": "Standard_LRS"},
        }
        target_props = {
            "adminPassword": "SecretPass456!",
            "sku": {"name": "Premium_LRS"},
        }

        comparisons = calculator._compare_properties(source_props, target_props, RedactionLevel.FULL)

        # Find password comparison
        password_comps = [c for c in comparisons if "password" in c.property_path.lower()]
        assert len(password_comps) > 0
        # Password should be redacted
        assert password_comps[0].redacted is True
        assert password_comps[0].source_value == "[REDACTED]"

        # Find SKU comparison
        sku_comps = [c for c in comparisons if "sku" in c.property_path]
        assert len(sku_comps) > 0
        # SKU should NOT be redacted
        assert sku_comps[0].redacted is False

    def test_redacted_properties_always_match(self, calculator):
        """Test that redacted properties are marked as matching."""
        comparison = PropertyComparison(
            property_path="properties.password",
            source_value="DifferentPassword1!",
            target_value="DifferentPassword2!",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        # After redaction, values should match (both [REDACTED])
        assert redacted.match is True


class TestCertificateAndPrivateKeyRedaction:
    """Test redaction of certificates and private keys."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_detects_certificate_properties(self, calculator):
        """Test detection of certificate-related properties."""
        cert_properties = [
            "properties.certificate",
            "properties.sslCertificate",
            "properties.certificates[0].data",
            "properties.tlsCertificate",
        ]

        for prop_path in cert_properties:
            assert calculator._is_sensitive_property(prop_path) is True

    def test_detects_private_key_properties(self, calculator):
        """Test detection of private key properties."""
        key_properties = [
            "properties.privateKey",
            "properties.sshPrivateKey",
            "properties.keys[0].privateKeyData",
        ]

        for prop_path in key_properties:
            assert calculator._is_sensitive_property(prop_path) is True

    def test_full_redaction_redacts_certificates(self, calculator):
        """Test FULL redaction hides certificate data."""
        comparison = PropertyComparison(
            property_path="properties.certificate",
            source_value="-----BEGIN CERTIFICATE-----\nMIIE...\n-----END CERTIFICATE-----",
            target_value="-----BEGIN CERTIFICATE-----\nMIIE...\n-----END CERTIFICATE-----",
            match=True,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is True
        assert "BEGIN CERTIFICATE" not in redacted.source_value


class TestStorageAccountKeyRedaction:
    """Test redaction of Azure Storage Account keys."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

    def test_detects_storage_account_keys(self, calculator):
        """Test detection of storage account key properties."""
        storage_key_props = [
            "properties.storageAccountKeys",
            "properties.keys[0].value",
            "properties.primaryKey",
            "properties.secondaryKey",
        ]

        for prop_path in storage_key_props:
            assert calculator._is_sensitive_property(prop_path) is True

    def test_full_redaction_redacts_storage_keys(self, calculator):
        """Test FULL redaction hides storage account keys."""
        comparison = PropertyComparison(
            property_path="properties.primaryKey",
            source_value="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=abc123XYZ==;EndpointSuffix=core.windows.net",
            target_value="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=def456ABC==;EndpointSuffix=core.windows.net",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is True
        assert "AccountKey" not in redacted.source_value or "REDACTED" in redacted.source_value
