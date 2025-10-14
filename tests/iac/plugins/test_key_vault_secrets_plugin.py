"""Tests for Key Vault Secrets replication plugin.

Tests cover:
- Plugin metadata and configuration
- Vault analysis (secrets, certificates, keys, policies)
- Data extraction with encryption
- Replication step generation
- Target application
- Security features
- Error handling
"""

import base64
import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from src.iac.plugins.key_vault_secrets_plugin import KeyVaultSecretsReplicationPlugin
from src.iac.plugins.models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    ExtractionFormat,
    ExtractionResult,
    PluginMetadata,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepResult,
    StepType,
)


@pytest.fixture
def plugin():
    """Create plugin instance with default config."""
    return KeyVaultSecretsReplicationPlugin()


@pytest.fixture
def plugin_with_config():
    """Create plugin instance with custom config."""
    config = {
        "export_certificate_private_keys": False,
        "include_disabled_secrets": True,
        "include_deleted_secrets": False,
        "max_versions_per_secret": 1,
        "output_dir": "./test_output",
        "dry_run": False,
    }
    return KeyVaultSecretsReplicationPlugin(config=config)


@pytest.fixture
def sample_vault_resource() -> Dict[str, Any]:
    """Create sample Key Vault resource."""
    return {
        "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/testvault",
        "name": "testvault",
        "type": "Microsoft.KeyVault/vaults",
        "location": "eastus",
        "properties": {
            "tenantId": "tenant-123",
            "sku": {"name": "standard"},
            "vaultUri": "https://testvault.vault.azure.net/",
            "enabledForDeployment": True,
            "enabledForDiskEncryption": False,
            "enabledForTemplateDeployment": True,
            "enableSoftDelete": True,
            "softDeleteRetentionInDays": 90,
            "enablePurgeProtection": True,
            "enableRbacAuthorization": False,
            "accessPolicies": [
                {
                    "tenantId": "tenant-123",
                    "objectId": "object-456",
                    "permissions": {
                        "secrets": ["get", "list", "set"],
                        "keys": ["get", "list", "create"],
                        "certificates": ["get", "list", "import"],
                    },
                },
                {
                    "tenantId": "tenant-123",
                    "objectId": "object-789",
                    "permissions": {
                        "secrets": ["get", "list"],
                        "keys": [],
                        "certificates": [],
                    },
                },
            ],
            "networkAcls": {
                "defaultAction": "Allow",
                "bypass": "AzureServices",
                "ipRules": [],
                "virtualNetworkRules": [],
            },
        },
    }


@pytest.fixture
def sample_analysis() -> DataPlaneAnalysis:
    """Create sample analysis result."""
    from src.iac.plugins.models import DataPlaneElement

    return DataPlaneAnalysis(
        resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/testvault",
        resource_type="Microsoft.KeyVault/vaults",
        status=AnalysisStatus.SUCCESS,
        elements=[
            DataPlaneElement(
                name="secrets",
                element_type="Secrets",
                description="25 secrets",
                complexity="HIGH",
                estimated_size_mb=0.25,
                is_sensitive=True,
                metadata={"count": 25},
            ),
            DataPlaneElement(
                name="certificates",
                element_type="Certificates",
                description="8 certificates",
                complexity="MEDIUM",
                estimated_size_mb=0.4,
                metadata={"count": 8},
            ),
            DataPlaneElement(
                name="keys",
                element_type="Keys",
                description="5 keys",
                complexity="MEDIUM",
                estimated_size_mb=0.05,
                metadata={"count": 5},
            ),
            DataPlaneElement(
                name="access_policies",
                element_type="Access Policies",
                description="2 access policies",
                complexity="LOW",
                estimated_size_mb=0.01,
                metadata={"count": 2},
            ),
            DataPlaneElement(
                name="vault_configuration",
                element_type="Vault Config",
                description="Vault settings",
                complexity="LOW",
                estimated_size_mb=0.01,
            ),
        ],
        total_estimated_size_mb=0.72,
        complexity_score=8,
        requires_credentials=True,
        requires_network_access=True,
        connection_methods=["Azure Key Vault SDK", "REST API"],
        estimated_extraction_time_minutes=25,
        warnings=["SECURITY: Sensitive data will be encrypted before storage"],
        errors=[],
        metadata={
            "vault_name": "testvault",
            "vault_uri": "https://testvault.vault.azure.net/",
        },
    )


# Test metadata and configuration


def test_plugin_metadata(plugin):
    """Test plugin metadata."""
    metadata = plugin.metadata

    assert isinstance(metadata, PluginMetadata)
    assert metadata.name == "key_vault_secrets"
    assert metadata.version == "1.0.0"
    assert metadata.resource_types == ["Microsoft.KeyVault/vaults"]
    assert metadata.requires_credentials is True
    assert metadata.requires_network_access is True
    assert metadata.complexity == "HIGH"
    assert ExtractionFormat.JSON in metadata.supported_formats
    assert ExtractionFormat.POWERSHELL_DSC in metadata.supported_formats


def test_can_handle_key_vault(plugin, sample_vault_resource):
    """Test that plugin can handle Key Vault resources."""
    assert plugin.can_handle(sample_vault_resource) is True


def test_cannot_handle_non_vault_resource(plugin):
    """Test that plugin rejects non-Key Vault resources."""
    vm_resource = {
        "id": "/subscriptions/sub-123/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        "type": "Microsoft.Compute/virtualMachines",
        "name": "vm1",
    }
    assert plugin.can_handle(vm_resource) is False


def test_get_config_value(plugin_with_config):
    """Test configuration value retrieval."""
    assert plugin_with_config.get_config_value("dry_run") is False
    assert plugin_with_config.get_config_value("max_versions_per_secret") == 1
    assert plugin_with_config.get_config_value("nonexistent", "default") == "default"


# Test analysis


@pytest.mark.asyncio
async def test_analyze_source_success(plugin, sample_vault_resource):
    """Test successful vault analysis."""
    with patch.object(
        plugin, "_check_vault_accessibility", return_value=True
    ), patch.object(plugin, "_count_secrets", return_value=25), patch.object(
        plugin, "_count_certificates", return_value=8
    ), patch.object(plugin, "_count_keys", return_value=5), patch.object(
        plugin, "_count_access_policies", return_value=2
    ):
        analysis = await plugin.analyze_source(sample_vault_resource)

    assert isinstance(analysis, DataPlaneAnalysis)
    assert analysis.status == AnalysisStatus.SUCCESS
    assert len(analysis.elements) == 5  # secrets, certs, keys, policies, config
    assert analysis.total_estimated_size_mb > 0
    assert analysis.complexity_score >= 6  # High due to security
    assert any("SECURITY" in w for w in analysis.warnings)


@pytest.mark.asyncio
async def test_analyze_source_no_access(plugin, sample_vault_resource):
    """Test analysis with no vault access."""
    with patch.object(plugin, "_check_vault_accessibility", return_value=False):
        analysis = await plugin.analyze_source(sample_vault_resource)
        # Should return FAILED status when no access
        assert analysis.status == AnalysisStatus.FAILED
        assert len(analysis.errors) > 0


@pytest.mark.asyncio
async def test_analyze_source_partial_failure(plugin, sample_vault_resource):
    """Test analysis with partial errors."""
    with patch.object(
        plugin, "_check_vault_accessibility", return_value=True
    ), patch.object(
        plugin, "_count_secrets", side_effect=Exception("Connection timeout")
    ), patch.object(plugin, "_count_certificates", return_value=8), patch.object(
        plugin, "_count_keys", return_value=5
    ), patch.object(plugin, "_count_access_policies", return_value=2):
        # Should return FAILED status with errors
        analysis = await plugin.analyze_source(sample_vault_resource)
        assert analysis.status == AnalysisStatus.FAILED
        assert len(analysis.errors) > 0


@pytest.mark.asyncio
async def test_count_access_policies(plugin, sample_vault_resource):
    """Test counting access policies from resource properties."""
    count = await plugin._count_access_policies(sample_vault_resource)
    assert count == 2


@pytest.mark.asyncio
async def test_get_vault_uri(plugin, sample_vault_resource):
    """Test getting vault URI from resource."""
    uri = plugin._get_vault_uri(sample_vault_resource)
    assert uri == "https://testvault.vault.azure.net/"


@pytest.mark.asyncio
async def test_get_vault_uri_fallback(plugin):
    """Test vault URI construction when not in properties."""
    resource = {
        "name": "myvault",
        "properties": {},
    }
    uri = plugin._get_vault_uri(resource)
    assert uri == "https://myvault.vault.azure.net/"


# Test extraction


@pytest.mark.asyncio
async def test_extract_data_success(
    plugin, sample_vault_resource, sample_analysis, tmp_path
):
    """Test successful data extraction."""
    plugin.config["output_dir"] = str(tmp_path)

    with patch.object(plugin, "_has_element", return_value=True):
        result = await plugin.extract_data(sample_vault_resource, sample_analysis)

    assert isinstance(result, ExtractionResult)
    assert result.status == AnalysisStatus.SUCCESS
    assert result.items_extracted == 5  # secrets, certs, keys, policies, config
    assert result.items_failed == 0
    assert len(result.extracted_data) == 5
    assert result.total_size_mb > 0
    assert any("encrypted" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_extract_secrets_with_encryption(plugin, sample_vault_resource, tmp_path):
    """Test secret extraction with encryption."""
    encryption_key = plugin._derive_encryption_key(sample_vault_resource)

    secrets_data = await plugin._extract_secrets(
        sample_vault_resource, tmp_path, encryption_key
    )

    assert secrets_data.name == "secrets"
    assert secrets_data.format == ExtractionFormat.JSON
    assert secrets_data.metadata["encrypted"] is True

    # Verify file was created
    file_path = Path(secrets_data.file_path)
    assert file_path.exists()

    # Verify content structure
    content = json.loads(secrets_data.content)
    assert "secrets" in content
    assert "metadata" in content
    assert content["metadata"]["encryption"] == "AES-256-GCM"
    assert len(content["secrets"]) > 0

    # Verify secrets are encrypted (base64 encoded in mock)
    for secret in content["secrets"]:
        assert "value" in secret
        # Mock encryption uses base64 encoding
        try:
            decoded = base64.b64decode(secret["value"])
            assert b"ENCRYPTED:" in decoded  # Mock prefix
        except Exception:
            pytest.fail("Secret value should be base64 encoded")


@pytest.mark.asyncio
async def test_extract_certificates(plugin, sample_vault_resource, tmp_path):
    """Test certificate extraction."""
    certs_data = await plugin._extract_certificates(sample_vault_resource, tmp_path)

    assert certs_data.name == "certificates"
    assert certs_data.format == ExtractionFormat.JSON

    content = json.loads(certs_data.content)
    assert "certificates" in content
    assert len(content["certificates"]) > 0

    # Verify private keys not included by default
    for cert in content["certificates"]:
        assert cert["has_private_key"] is False


@pytest.mark.asyncio
async def test_extract_certificates_with_private_keys(sample_vault_resource, tmp_path):
    """Test certificate extraction with private keys enabled."""
    plugin = KeyVaultSecretsReplicationPlugin(
        config={"export_certificate_private_keys": True}
    )

    certs_data = await plugin._extract_certificates(sample_vault_resource, tmp_path)

    content = json.loads(certs_data.content)
    for cert in content["certificates"]:
        assert cert["has_private_key"] is True


@pytest.mark.asyncio
async def test_extract_keys(plugin, sample_vault_resource, tmp_path):
    """Test key metadata extraction."""
    keys_data = await plugin._extract_keys(sample_vault_resource, tmp_path)

    assert keys_data.name == "keys"
    assert keys_data.format == ExtractionFormat.JSON

    content = json.loads(keys_data.content)
    assert "keys" in content
    assert "metadata" in content
    assert "NOT exported" in content["metadata"]["note"]


@pytest.mark.asyncio
async def test_extract_access_policies(plugin, sample_vault_resource, tmp_path):
    """Test access policy extraction."""
    policies_data = await plugin._extract_access_policies(
        sample_vault_resource, tmp_path
    )

    assert policies_data.name == "access_policies"
    content = json.loads(policies_data.content)

    assert len(content["access_policies"]) == 2
    assert all("object_id" in p for p in content["access_policies"])
    assert all("permissions" in p for p in content["access_policies"])


@pytest.mark.asyncio
async def test_extract_vault_config(plugin, sample_vault_resource, tmp_path):
    """Test vault configuration extraction."""
    config_data = await plugin._extract_vault_config(sample_vault_resource, tmp_path)

    assert config_data.name == "vault_config"
    content = json.loads(config_data.content)

    assert content["vault_name"] == "testvault"
    assert content["enable_soft_delete"] is True
    assert content["soft_delete_retention_days"] == 90
    assert content["enable_purge_protection"] is True


@pytest.mark.asyncio
async def test_extraction_partial_failure(
    plugin, sample_vault_resource, sample_analysis, tmp_path
):
    """Test extraction with partial failures."""
    plugin.config["output_dir"] = str(tmp_path)

    # Mock one extraction to fail
    with patch.object(
        plugin, "_extract_secrets", side_effect=Exception("Network error")
    ), patch.object(plugin, "_has_element", return_value=True):
        result = await plugin.extract_data(sample_vault_resource, sample_analysis)

    assert result.status == AnalysisStatus.PARTIAL
    assert result.items_failed > 0
    assert len(result.errors) > 0


# Test encryption


def test_derive_encryption_key(plugin, sample_vault_resource):
    """Test encryption key derivation."""
    key1 = plugin._derive_encryption_key(sample_vault_resource)
    key2 = plugin._derive_encryption_key(sample_vault_resource)

    assert len(key1) == 32  # 256 bits
    assert key1 == key2  # Deterministic


def test_derive_encryption_key_custom(sample_vault_resource):
    """Test encryption key derivation with custom key."""
    plugin = KeyVaultSecretsReplicationPlugin(
        config={"encryption_key": "my-custom-key-123"}
    )

    key = plugin._derive_encryption_key(sample_vault_resource)
    assert len(key) == 32


def test_encrypt_secret_value(plugin, sample_vault_resource):
    """Test secret value encryption."""
    key = plugin._derive_encryption_key(sample_vault_resource)

    plaintext = "SuperSecretPassword123!"
    encrypted = plugin._encrypt_secret_value(plaintext, key)

    # Should be base64 encoded
    assert isinstance(encrypted, str)
    try:
        decoded = base64.b64decode(encrypted)
        assert b"ENCRYPTED:" in decoded  # Mock implementation
    except Exception:
        pytest.fail("Encrypted value should be valid base64")


# Test replication steps generation


@pytest.mark.asyncio
async def test_generate_replication_steps(plugin, tmp_path):
    """Test replication steps generation."""
    from src.iac.plugins.models import ExtractedData

    # Create mock extraction result
    extraction = ExtractionResult(
        resource_id="/subscriptions/sub-123/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/vault1",
        status=AnalysisStatus.SUCCESS,
        extracted_data=[
            ExtractedData(
                name="secrets",
                format=ExtractionFormat.JSON,
                content='{"secrets": []}',
                file_path=str(tmp_path / "secrets.json"),
            ),
            ExtractedData(
                name="certificates",
                format=ExtractionFormat.JSON,
                content='{"certificates": []}',
                file_path=str(tmp_path / "certs.json"),
            ),
            ExtractedData(
                name="keys",
                format=ExtractionFormat.JSON,
                content='{"keys": []}',
                file_path=str(tmp_path / "keys.json"),
            ),
            ExtractedData(
                name="access_policies",
                format=ExtractionFormat.JSON,
                content='{"policies": []}',
                file_path=str(tmp_path / "policies.json"),
            ),
            ExtractedData(
                name="vault_config",
                format=ExtractionFormat.JSON,
                content='{"config": {}}',
                file_path=str(tmp_path / "config.json"),
            ),
        ],
    )

    steps = await plugin.generate_replication_steps(extraction)

    assert len(steps) > 0
    assert isinstance(steps[0], ReplicationStep)

    # Check for key steps
    step_ids = [s.step_id for s in steps]
    assert "prereq_verify_vault" in step_ids
    assert "configure_vault" in step_ids
    assert "import_secrets" in step_ids
    assert "import_certificates" in step_ids
    assert "validate_vault" in step_ids

    # Verify step order
    prereq_step = next(s for s in steps if s.step_id == "prereq_verify_vault")
    assert prereq_step.step_type == StepType.PREREQUISITE
    assert prereq_step.depends_on == []

    # Verify secret import is critical and has security metadata
    secret_step = next(s for s in steps if s.step_id == "import_secrets")
    assert secret_step.is_critical is True
    assert secret_step.metadata.get("security_level") == "CRITICAL"


@pytest.mark.asyncio
async def test_generate_prereq_script(plugin):
    """Test prerequisite check script generation."""
    script = plugin._generate_prereq_check_script()

    assert "VaultName" in script
    assert "Get-AzKeyVault" in script
    assert "permissions" in script.lower()


@pytest.mark.asyncio
async def test_generate_secrets_import_script(plugin):
    """Test secrets import script generation."""
    from src.iac.plugins.models import ExtractedData

    secrets_data = ExtractedData(
        name="secrets",
        format=ExtractionFormat.JSON,
        content='{"secrets": []}',
    )

    script = plugin._generate_secrets_import_script(secrets_data)

    assert "Set-AzKeyVaultSecret" in script
    assert "SECURITY AUDIT" in script or "AUDIT" in script
    assert "encrypted" in script.lower() or "decrypt" in script.lower()


# Test application to target


@pytest.mark.asyncio
async def test_apply_to_target_success(plugin):
    """Test successful application to target vault."""
    steps = [
        ReplicationStep(
            step_id="prereq_verify_vault",
            step_type=StepType.PREREQUISITE,
            description="Verify vault",
            script_content="# Check vault",
        ),
        ReplicationStep(
            step_id="import_secrets",
            step_type=StepType.DATA_IMPORT,
            description="Import secrets",
            script_content="# Import",
            depends_on=["prereq_verify_vault"],
            metadata={"security_level": "CRITICAL"},
        ),
    ]

    result = await plugin.apply_to_target(
        steps,
        "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/target",
    )

    assert isinstance(result, ReplicationResult)
    assert result.status == ReplicationStatus.SUCCESS
    assert result.steps_succeeded == 2
    assert result.steps_failed == 0
    assert result.fidelity_score > 0


@pytest.mark.asyncio
async def test_apply_to_target_dry_run(plugin):
    """Test dry run mode."""
    plugin.config["dry_run"] = True

    steps = [
        ReplicationStep(
            step_id="test_step",
            step_type=StepType.CONFIGURATION,
            description="Test",
            script_content="# Test",
        ),
    ]

    result = await plugin.apply_to_target(steps, "target-vault-id")

    assert result.status == ReplicationStatus.SUCCESS
    assert any("dry run" in w.lower() for w in result.warnings)
    assert result.metadata["dry_run"] is True


@pytest.mark.asyncio
async def test_apply_to_target_with_failures(plugin):
    """Test application with step failures."""
    steps = [
        ReplicationStep(
            step_id="critical_step",
            step_type=StepType.PREREQUISITE,
            description="Critical",
            script_content="# Fail",
            is_critical=True,
        ),
        ReplicationStep(
            step_id="next_step",
            step_type=StepType.CONFIGURATION,
            description="Next",
            script_content="# Never runs",
            depends_on=["critical_step"],
        ),
    ]

    # Mock execution to fail
    with patch.object(
        plugin,
        "_execute_step_on_target",
        return_value=StepResult(
            step_id="critical_step",
            status=ReplicationStatus.FAILED,
            duration_seconds=1.0,
            error_message="Mock failure",
        ),
    ):
        result = await plugin.apply_to_target(steps, "target-vault-id")

    assert result.status == ReplicationStatus.FAILED
    assert result.steps_failed > 0
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_dependencies_met(plugin):
    """Test dependency checking."""
    step = ReplicationStep(
        step_id="step2",
        step_type=StepType.CONFIGURATION,
        description="Depends on step1",
        script_content="# Script",
        depends_on=["step1"],
    )

    # No results yet
    assert plugin._dependencies_met(step, []) is False

    # Step1 succeeded
    results = [
        StepResult(
            step_id="step1",
            status=ReplicationStatus.SUCCESS,
            duration_seconds=1.0,
        )
    ]
    assert plugin._dependencies_met(step, results) is True

    # Step1 failed
    results = [
        StepResult(
            step_id="step1",
            status=ReplicationStatus.FAILED,
            duration_seconds=1.0,
        )
    ]
    assert plugin._dependencies_met(step, results) is False


@pytest.mark.asyncio
async def test_execute_step_on_target(plugin):
    """Test step execution (mock)."""
    step = ReplicationStep(
        step_id="test_step",
        step_type=StepType.CONFIGURATION,
        description="Test",
        script_content="# Test",
    )

    result = await plugin._execute_step_on_target(step, "target-vault-id")

    assert isinstance(result, StepResult)
    assert result.step_id == "test_step"
    assert result.status == ReplicationStatus.SUCCESS


def test_calculate_fidelity_score(plugin):
    """Test fidelity score calculation."""
    # Perfect score
    score = plugin._calculate_fidelity_score(10, 0, 0, 10)
    assert score == 1.0

    # Partial success
    score = plugin._calculate_fidelity_score(5, 3, 2, 10)
    assert 0.5 < score < 0.7  # 5 + (2 * 0.5) = 6 / 10 = 0.6

    # Complete failure
    score = plugin._calculate_fidelity_score(0, 10, 0, 10)
    assert score == 0.0

    # Empty
    score = plugin._calculate_fidelity_score(0, 0, 0, 0)
    assert score == 0.0


# Test helper methods


def test_has_element(plugin, sample_analysis):
    """Test element existence check."""
    assert plugin._has_element(sample_analysis, "secrets") is True
    assert plugin._has_element(sample_analysis, "certificates") is True
    assert plugin._has_element(sample_analysis, "nonexistent") is False


def test_find_extracted_data(plugin):
    """Test finding extracted data by name pattern."""
    from src.iac.plugins.models import ExtractedData

    extraction = ExtractionResult(
        resource_id="vault1",
        extracted_data=[
            ExtractedData(name="secrets", format=ExtractionFormat.JSON, content="{}"),
            ExtractedData(
                name="certificates", format=ExtractionFormat.JSON, content="{}"
            ),
        ],
    )

    found = plugin._find_extracted_data(extraction, "secret")
    assert found is not None
    assert found.name == "secrets"

    not_found = plugin._find_extracted_data(extraction, "keys")
    assert not_found is None


# Test error handling


@pytest.mark.asyncio
async def test_analyze_with_exception(plugin, sample_vault_resource):
    """Test analysis handles exceptions gracefully."""
    with patch.object(
        plugin, "_check_vault_accessibility", side_effect=Exception("Network error")
    ):
        analysis = await plugin.analyze_source(sample_vault_resource)

    assert analysis.status == AnalysisStatus.FAILED
    assert len(analysis.errors) > 0
    assert "Network error" in analysis.errors[0]


@pytest.mark.asyncio
async def test_extract_with_exception(plugin, sample_vault_resource, sample_analysis):
    """Test extraction handles exceptions gracefully."""
    with patch.object(
        plugin, "_has_element", side_effect=Exception("Unexpected error")
    ):
        result = await plugin.extract_data(sample_vault_resource, sample_analysis)

    assert result.status == AnalysisStatus.FAILED
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_apply_with_exception(plugin):
    """Test application handles exceptions gracefully."""
    steps = [
        ReplicationStep(
            step_id="test",
            step_type=StepType.CONFIGURATION,
            description="Test",
            script_content="# Test",
        ),
    ]

    with patch.object(
        plugin, "_execute_step_on_target", side_effect=Exception("Execution error")
    ):
        result = await plugin.apply_to_target(steps, "target-vault-id")

    assert result.status == ReplicationStatus.FAILED


# Test security features


def test_security_warnings_in_analysis(plugin, sample_vault_resource):
    """Test that security warnings are included in analysis."""

    async def run_test():
        with patch.object(
            plugin, "_check_vault_accessibility", return_value=True
        ), patch.object(plugin, "_count_secrets", return_value=10), patch.object(
            plugin, "_count_certificates", return_value=2
        ), patch.object(plugin, "_count_keys", return_value=1), patch.object(
            plugin, "_count_access_policies", return_value=1
        ):
            analysis = await plugin.analyze_source(sample_vault_resource)

        # Should have security warnings
        assert any("SECURITY" in w for w in analysis.warnings)
        assert any("encrypted" in w.lower() for w in analysis.warnings)

    import asyncio

    asyncio.run(run_test())


def test_complexity_score_with_sensitive_data(plugin):
    """Test that complexity score increases with sensitive data."""
    from src.iac.plugins.models import DataPlaneElement

    # No sensitive elements
    elements_normal = [
        DataPlaneElement(
            name="config",
            element_type="Config",
            description="Config",
            is_sensitive=False,
        )
    ]
    score_normal = plugin._calculate_complexity_score(elements_normal)

    # With sensitive elements
    elements_sensitive = [
        DataPlaneElement(
            name="secrets",
            element_type="Secrets",
            description="Secrets",
            is_sensitive=True,
            metadata={"count": 100},
        )
    ]
    score_sensitive = plugin._calculate_complexity_score(elements_sensitive)

    assert score_sensitive > score_normal


@pytest.mark.asyncio
async def test_audit_logging_on_secret_extraction(
    plugin, sample_vault_resource, tmp_path, caplog
):
    """Test that secret extraction is audit logged."""
    import logging

    caplog.set_level(logging.INFO)

    encryption_key = plugin._derive_encryption_key(sample_vault_resource)
    await plugin._extract_secrets(sample_vault_resource, tmp_path, encryption_key)

    # Check for audit log
    assert any("SECURITY AUDIT" in record.message for record in caplog.records)


# Test integration


@pytest.mark.asyncio
async def test_full_replication_workflow(plugin, sample_vault_resource, tmp_path):
    """Test complete replication workflow."""
    plugin.config["output_dir"] = str(tmp_path)
    plugin.config["dry_run"] = True

    # 1. Analyze
    with patch.object(
        plugin, "_check_vault_accessibility", return_value=True
    ), patch.object(plugin, "_count_secrets", return_value=5), patch.object(
        plugin, "_count_certificates", return_value=2
    ), patch.object(plugin, "_count_keys", return_value=1), patch.object(
        plugin, "_count_access_policies", return_value=1
    ):
        analysis = await plugin.analyze_source(sample_vault_resource)

    assert analysis.status == AnalysisStatus.SUCCESS

    # 2. Extract
    extraction = await plugin.extract_data(sample_vault_resource, analysis)
    assert extraction.status == AnalysisStatus.SUCCESS
    assert len(extraction.extracted_data) > 0

    # 3. Generate steps
    steps = await plugin.generate_replication_steps(extraction)
    assert len(steps) > 0

    # 4. Apply (dry run)
    result = await plugin.apply_to_target(steps, "target-vault-id")
    assert result.status == ReplicationStatus.SUCCESS
    assert result.metadata["dry_run"] is True


# Test edge cases


@pytest.mark.asyncio
async def test_empty_vault(plugin):
    """Test handling of empty vault with no secrets."""
    empty_vault = {
        "id": "vault-id",
        "name": "empty-vault",
        "type": "Microsoft.KeyVault/vaults",
        "properties": {"vaultUri": "https://empty-vault.vault.azure.net/"},
    }

    with patch.object(
        plugin, "_check_vault_accessibility", return_value=True
    ), patch.object(plugin, "_count_secrets", return_value=0), patch.object(
        plugin, "_count_certificates", return_value=0
    ), patch.object(plugin, "_count_keys", return_value=0), patch.object(
        plugin, "_count_access_policies", return_value=0
    ):
        analysis = await plugin.analyze_source(empty_vault)

    # Should still succeed with vault_configuration element
    assert analysis.status == AnalysisStatus.SUCCESS
    assert len(analysis.elements) >= 1  # At least config


@pytest.mark.asyncio
async def test_large_vault(plugin):
    """Test handling of vault with many secrets."""
    large_vault = {
        "id": "vault-id",
        "name": "large-vault",
        "type": "Microsoft.KeyVault/vaults",
        "properties": {},
    }

    with patch.object(
        plugin, "_check_vault_accessibility", return_value=True
    ), patch.object(plugin, "_count_secrets", return_value=250), patch.object(
        plugin, "_count_certificates", return_value=0
    ), patch.object(plugin, "_count_keys", return_value=0), patch.object(
        plugin, "_count_access_policies", return_value=0
    ):
        analysis = await plugin.analyze_source(large_vault)

    # Complexity should be high for many secrets
    assert analysis.complexity_score >= 8
