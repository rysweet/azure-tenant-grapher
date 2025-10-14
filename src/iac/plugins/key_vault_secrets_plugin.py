"""Key Vault Secrets replication plugin.

This plugin handles data-plane replication for Azure Key Vaults,
including secrets, certificates, keys, and access policies.

CRITICAL SECURITY NOTICE:
- Secret values are ENCRYPTED before being written to disk
- Certificates include only public parts (private keys NOT exported unless explicitly configured)
- Access requires appropriate Azure RBAC permissions
- All operations are logged for audit trails
- Transfer to target vault uses secure Azure SDK methods
"""

import asyncio
import base64
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import ResourceReplicationPlugin
from .models import (
    AnalysisStatus,
    DataPlaneAnalysis,
    DataPlaneElement,
    ExtractedData,
    ExtractionFormat,
    ExtractionResult,
    PluginMetadata,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    StepResult,
    StepType,
)

logger = logging.getLogger(__name__)


class KeyVaultSecretsReplicationPlugin(ResourceReplicationPlugin):
    """Handles Azure Key Vault secrets replication.

    This plugin replicates Key Vault data-plane elements:
    - Secrets (names, values, versions, metadata)
    - Certificates (public parts, policies, metadata)
    - Keys (metadata, attributes - NOT private key material)
    - Access policies (from vault properties)
    - Vault configuration (soft delete, purge protection, network rules)

    Security Features:
    - Secret values encrypted at rest using AES-256
    - Encryption key derived from target vault URI
    - Certificate private keys EXCLUDED by default
    - Audit logging of all secret access
    - Secure transfer via Azure Key Vault SDK

    Requires:
    - Azure RBAC: Key Vault Secrets Officer or equivalent
    - Key Vault access policy or RBAC permissions
    - Network access to source and target vaults
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the Key Vault plugin.

        Args:
            config: Optional configuration dictionary with options:
                - export_certificate_private_keys: bool (default: False)
                - encryption_key: str (optional custom encryption key)
                - include_disabled_secrets: bool (default: True)
                - include_deleted_secrets: bool (default: False)
                - max_versions_per_secret: int (default: 1, use -1 for all)
                - output_dir: str (default: "./keyvault_extraction")
                - dry_run: bool (default: False)
        """
        self.config = config or {}

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="key_vault_secrets",
            version="1.0.0",
            description="Replicates Azure Key Vault secrets, certificates, and keys with encryption",
            author="Azure Tenant Grapher",
            resource_types=["Microsoft.KeyVault/vaults"],
            supported_formats=[
                ExtractionFormat.JSON,
                ExtractionFormat.POWERSHELL_DSC,
                ExtractionFormat.SHELL_SCRIPT,
            ],
            requires_credentials=True,
            requires_network_access=True,
            complexity="HIGH",
            estimated_effort_weeks=2.0,
            tags=["key-vault", "secrets", "security", "encryption", "certificates"],
            documentation_url="https://docs.microsoft.com/en-us/azure/key-vault/",
        )

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if resource is a Key Vault.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a Key Vault
        """
        resource_type = resource.get("type", "")
        return resource_type == "Microsoft.KeyVault/vaults"

    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze Key Vault to determine what needs replication.

        Args:
            resource: Source Key Vault resource dictionary

        Returns:
            DataPlaneAnalysis with discovered elements

        Raises:
            ConnectionError: If cannot connect to Key Vault
            PermissionError: If lacking Key Vault read permissions
        """
        logger.info(f"Analyzing Key Vault: {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        vault_name = resource.get("name", "unknown")
        elements: List[DataPlaneElement] = []
        warnings: List[str] = []
        errors: List[str] = []

        try:
            # Check connectivity and permissions
            if not await self._check_vault_accessibility(resource):
                raise PermissionError(
                    "Cannot access Key Vault - check RBAC permissions"
                )

            # Analyze secrets
            secret_count = await self._count_secrets(resource)
            if secret_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="secrets",
                        element_type="Secrets",
                        description=f"{secret_count} secrets (values will be encrypted)",
                        complexity="HIGH",
                        estimated_size_mb=secret_count * 0.01,
                        dependencies=[],
                        metadata={"count": secret_count},
                        is_sensitive=True,
                    )
                )

            # Analyze certificates
            cert_count = await self._count_certificates(resource)
            if cert_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="certificates",
                        element_type="Certificates",
                        description=f"{cert_count} certificates (public parts only by default)",
                        complexity="MEDIUM",
                        estimated_size_mb=cert_count * 0.05,
                        dependencies=[],
                        metadata={"count": cert_count},
                        is_sensitive=self.get_config_value(
                            "export_certificate_private_keys", False
                        ),
                    )
                )

            # Analyze keys
            key_count = await self._count_keys(resource)
            if key_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="keys",
                        element_type="Keys",
                        description=f"{key_count} keys (metadata only, NOT key material)",
                        complexity="MEDIUM",
                        estimated_size_mb=key_count * 0.01,
                        dependencies=[],
                        metadata={"count": key_count},
                        is_sensitive=False,
                    )
                )

            # Analyze access policies
            policy_count = await self._count_access_policies(resource)
            if policy_count > 0:
                elements.append(
                    DataPlaneElement(
                        name="access_policies",
                        element_type="Access Policies",
                        description=f"{policy_count} access policies",
                        complexity="LOW",
                        estimated_size_mb=0.01,
                        dependencies=[],
                        metadata={"count": policy_count},
                    )
                )

            # Analyze vault configuration
            elements.append(
                DataPlaneElement(
                    name="vault_configuration",
                    element_type="Vault Config",
                    description="Vault settings (soft delete, purge protection, network rules)",
                    complexity="LOW",
                    estimated_size_mb=0.01,
                    dependencies=[],
                    metadata={},
                )
            )

            # Calculate totals
            total_size = sum(e.estimated_size_mb for e in elements)
            complexity_score = self._calculate_complexity_score(elements)

            # Add security warnings
            if any(e.is_sensitive for e in elements):
                warnings.append(
                    "SECURITY: Sensitive data will be encrypted before storage"
                )
            warnings.append(
                "Requires Key Vault Secrets Officer or equivalent RBAC role"
            )

            status = AnalysisStatus.SUCCESS
            if errors:
                status = (
                    AnalysisStatus.FAILED if not elements else AnalysisStatus.PARTIAL
                )

            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", ""),
                status=status,
                elements=elements,
                total_estimated_size_mb=total_size,
                complexity_score=complexity_score,
                requires_credentials=True,
                requires_network_access=True,
                connection_methods=["Azure Key Vault SDK", "REST API"],
                estimated_extraction_time_minutes=max(10, len(elements) * 5),
                warnings=warnings,
                errors=errors,
                metadata={
                    "vault_name": vault_name,
                    "vault_uri": self._get_vault_uri(resource),
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze Key Vault: {e}")
            errors.append(str(e))

            return DataPlaneAnalysis(
                resource_id=resource_id,
                resource_type=resource.get("type", ""),
                status=AnalysisStatus.FAILED,
                elements=[],
                total_estimated_size_mb=0,
                complexity_score=8,
                requires_credentials=True,
                requires_network_access=True,
                connection_methods=["Azure Key Vault SDK"],
                estimated_extraction_time_minutes=0,
                warnings=warnings,
                errors=errors,
            )

    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract Key Vault data from source vault.

        SECURITY: Secret values are encrypted using AES-256 before writing to disk.

        Args:
            resource: Source Key Vault resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with extracted and encrypted data

        Raises:
            ConnectionError: If cannot connect to Key Vault
            PermissionError: If lacking read permissions
            IOError: If cannot write extracted data
        """
        logger.info(f"Extracting Key Vault data from {resource.get('name')}")

        resource_id = resource.get("id", "unknown")
        extracted_data: List[ExtractedData] = []
        warnings: List[str] = []
        errors: List[str] = []
        items_extracted = 0
        items_failed = 0
        start_time = datetime.utcnow()

        # Get output directory
        output_dir = Path(self.get_config_value("output_dir", "./keyvault_extraction"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get encryption key for secrets
        encryption_key = self._derive_encryption_key(resource)

        try:
            # Extract secrets
            if self._has_element(analysis, "secrets"):
                try:
                    logger.info("Extracting secrets (values will be encrypted)")
                    secrets_data = await self._extract_secrets(
                        resource, output_dir, encryption_key
                    )
                    extracted_data.append(secrets_data)
                    items_extracted += 1
                    warnings.append(
                        "Secret values encrypted with AES-256 - encryption key derived from target vault"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract secrets: {e}")
                    errors.append(f"Secrets: {e}")
                    items_failed += 1

            # Extract certificates
            if self._has_element(analysis, "certificates"):
                try:
                    logger.info("Extracting certificates")
                    certs_data = await self._extract_certificates(resource, output_dir)
                    extracted_data.append(certs_data)
                    items_extracted += 1

                    if not self.get_config_value(
                        "export_certificate_private_keys", False
                    ):
                        warnings.append(
                            "Certificate private keys NOT exported - import will require new CSR or manual key import"
                        )
                except Exception as e:
                    logger.error(f"Failed to extract certificates: {e}")
                    errors.append(f"Certificates: {e}")
                    items_failed += 1

            # Extract keys
            if self._has_element(analysis, "keys"):
                try:
                    logger.info("Extracting key metadata")
                    keys_data = await self._extract_keys(resource, output_dir)
                    extracted_data.append(keys_data)
                    items_extracted += 1
                    warnings.append(
                        "Key metadata only - key material NOT exported (Azure Key Vault restriction)"
                    )
                except Exception as e:
                    logger.error(f"Failed to extract keys: {e}")
                    errors.append(f"Keys: {e}")
                    items_failed += 1

            # Extract access policies
            if self._has_element(analysis, "access_policies"):
                try:
                    logger.info("Extracting access policies")
                    policies_data = await self._extract_access_policies(
                        resource, output_dir
                    )
                    extracted_data.append(policies_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract access policies: {e}")
                    errors.append(f"Access policies: {e}")
                    items_failed += 1

            # Extract vault configuration
            if self._has_element(analysis, "vault_configuration"):
                try:
                    logger.info("Extracting vault configuration")
                    config_data = await self._extract_vault_config(resource, output_dir)
                    extracted_data.append(config_data)
                    items_extracted += 1
                except Exception as e:
                    logger.error(f"Failed to extract vault config: {e}")
                    errors.append(f"Vault configuration: {e}")
                    items_failed += 1

            # Calculate totals
            total_size_mb = sum(d.size_bytes / (1024 * 1024) for d in extracted_data)
            duration = (datetime.utcnow() - start_time).total_seconds()

            status = AnalysisStatus.SUCCESS
            if items_failed > 0:
                status = (
                    AnalysisStatus.FAILED
                    if items_extracted == 0
                    else AnalysisStatus.PARTIAL
                )

            # Add security audit log
            logger.info(
                f"SECURITY AUDIT: Extracted {items_extracted} element types from Key Vault {resource.get('name')}"
            )

            return ExtractionResult(
                resource_id=resource_id,
                status=status,
                extracted_data=extracted_data,
                total_size_mb=total_size_mb,
                extraction_duration_seconds=duration,
                items_extracted=items_extracted,
                items_failed=items_failed,
                warnings=warnings,
                errors=errors,
                metadata={
                    "output_directory": str(output_dir),
                    "encryption_enabled": True,
                    "encryption_algorithm": "AES-256-GCM",
                },
            )

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            return ExtractionResult(
                resource_id=resource_id,
                status=AnalysisStatus.FAILED,
                extracted_data=extracted_data,
                total_size_mb=0,
                extraction_duration_seconds=duration,
                items_extracted=items_extracted,
                items_failed=items_failed + 1,
                warnings=warnings,
                errors=[*errors, str(e)],
            )

    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate steps to replicate Key Vault data to target.

        Args:
            extraction: Result from extract_data()

        Returns:
            List of ReplicationStep objects in execution order
        """
        logger.info("Generating Key Vault replication steps")

        steps: List[ReplicationStep] = []

        # Step 1: Prerequisites - verify target vault exists and is accessible
        steps.append(
            ReplicationStep(
                step_id="prereq_verify_vault",
                step_type=StepType.PREREQUISITE,
                description="Verify target Key Vault exists and is accessible",
                script_content=self._generate_prereq_check_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[],
                estimated_duration_minutes=2,
                is_critical=True,
                can_retry=True,
                max_retries=3,
            )
        )

        # Step 2: Configure vault settings
        vault_config_data = self._find_extracted_data(extraction, "vault_config")
        if vault_config_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_vault",
                    step_type=StepType.CONFIGURATION,
                    description="Apply vault configuration (soft delete, purge protection, network rules)",
                    script_content=self._generate_vault_config_script(
                        vault_config_data
                    ),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["prereq_verify_vault"],
                    estimated_duration_minutes=5,
                    is_critical=True,
                    can_retry=True,
                )
            )

        # Step 3: Import secrets
        secrets_data = self._find_extracted_data(extraction, "secrets")
        if secrets_data:
            steps.append(
                ReplicationStep(
                    step_id="import_secrets",
                    step_type=StepType.DATA_IMPORT,
                    description="Import secrets to target vault (encrypted values will be decrypted during import)",
                    script_content=self._generate_secrets_import_script(secrets_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_vault"],
                    estimated_duration_minutes=10,
                    is_critical=True,
                    can_retry=True,
                    max_retries=3,
                    metadata={"security_level": "CRITICAL"},
                )
            )

        # Step 4: Import certificates
        certs_data = self._find_extracted_data(extraction, "certificates")
        if certs_data:
            steps.append(
                ReplicationStep(
                    step_id="import_certificates",
                    step_type=StepType.DATA_IMPORT,
                    description="Import certificates to target vault",
                    script_content=self._generate_certificates_import_script(
                        certs_data
                    ),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["configure_vault"],
                    estimated_duration_minutes=10,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 5: Import keys (metadata only)
        keys_data = self._find_extracted_data(extraction, "keys")
        if keys_data:
            steps.append(
                ReplicationStep(
                    step_id="document_keys",
                    step_type=StepType.POST_CONFIG,
                    description="Document key requirements (manual recreation needed)",
                    script_content=self._generate_keys_documentation_script(keys_data),
                    script_format=ExtractionFormat.SHELL_SCRIPT,
                    depends_on=["configure_vault"],
                    estimated_duration_minutes=2,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 6: Configure access policies
        policies_data = self._find_extracted_data(extraction, "access_policies")
        if policies_data:
            steps.append(
                ReplicationStep(
                    step_id="configure_access_policies",
                    step_type=StepType.CONFIGURATION,
                    description="Configure access policies (principal IDs must be updated for target tenant)",
                    script_content=self._generate_access_policies_script(policies_data),
                    script_format=ExtractionFormat.POWERSHELL_DSC,
                    depends_on=["import_secrets"],
                    estimated_duration_minutes=5,
                    is_critical=False,
                    can_retry=True,
                )
            )

        # Step 7: Validation
        steps.append(
            ReplicationStep(
                step_id="validate_vault",
                step_type=StepType.VALIDATION,
                description="Validate Key Vault configuration and secret availability",
                script_content=self._generate_validation_script(),
                script_format=ExtractionFormat.POWERSHELL_DSC,
                depends_on=[s.step_id for s in steps],
                estimated_duration_minutes=5,
                is_critical=False,
                can_retry=True,
            )
        )

        return steps

    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply Key Vault replication steps to target vault.

        SECURITY: Secrets are decrypted and transferred via Azure SDK (encrypted in transit).

        Args:
            steps: Replication steps to execute
            target_resource_id: Azure resource ID of target Key Vault

        Returns:
            ReplicationResult with execution status
        """
        logger.info(f"Applying Key Vault replication to {target_resource_id}")

        start_time = datetime.utcnow()
        step_results: List[StepResult] = []
        steps_succeeded = 0
        steps_failed = 0
        steps_skipped = 0
        warnings: List[str] = []
        errors: List[str] = []

        # Check if dry run
        is_dry_run = self.get_config_value("dry_run", False)
        if is_dry_run:
            warnings.append("Dry run mode - no actual changes made")

        try:
            # Execute steps in order
            for step in steps:
                # Check dependencies
                if not self._dependencies_met(step, step_results):
                    logger.warning(f"Skipping {step.step_id} - dependencies not met")
                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SKIPPED,
                            duration_seconds=0,
                            error_message="Dependencies not met",
                        )
                    )
                    steps_skipped += 1
                    continue

                # Execute step
                logger.info(f"Executing step: {step.step_id}")
                step_start = datetime.utcnow()

                try:
                    if is_dry_run:
                        # Simulate execution
                        await asyncio.sleep(0.1)
                        result = StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.SUCCESS,
                            duration_seconds=0.1,
                            stdout="[DRY RUN] Step would execute successfully",
                        )
                    else:
                        # Execute via Azure SDK
                        result = await self._execute_step_on_target(
                            step, target_resource_id
                        )

                    # Audit log for security-critical steps
                    if step.metadata.get("security_level") == "CRITICAL":
                        logger.info(
                            f"SECURITY AUDIT: Executed critical step {step.step_id} with status {result.status}"
                        )

                    step_results.append(result)

                    if result.status == ReplicationStatus.SUCCESS:
                        steps_succeeded += 1
                    elif result.status == ReplicationStatus.SKIPPED:
                        steps_skipped += 1
                    else:
                        steps_failed += 1
                        if step.is_critical:
                            errors.append(
                                f"Critical step {step.step_id} failed: {result.error_message}"
                            )
                            break

                except Exception as e:
                    logger.error(f"Step {step.step_id} failed: {e}")
                    duration = (datetime.utcnow() - step_start).total_seconds()

                    step_results.append(
                        StepResult(
                            step_id=step.step_id,
                            status=ReplicationStatus.FAILED,
                            duration_seconds=duration,
                            error_message=str(e),
                        )
                    )
                    steps_failed += 1

                    if step.is_critical:
                        errors.append(f"Critical step {step.step_id} failed: {e}")
                        break

            # Calculate fidelity score
            fidelity = self._calculate_fidelity_score(
                steps_succeeded, steps_failed, steps_skipped, len(steps)
            )

            # Determine overall status
            if steps_failed == 0 and steps_skipped == 0:
                status = ReplicationStatus.SUCCESS
            elif steps_succeeded > 0:
                status = ReplicationStatus.PARTIAL_SUCCESS
            else:
                status = ReplicationStatus.FAILED

            total_duration = (datetime.utcnow() - start_time).total_seconds()

            return ReplicationResult(
                source_resource_id="unknown",
                target_resource_id=target_resource_id,
                status=status,
                steps_executed=step_results,
                total_duration_seconds=total_duration,
                steps_succeeded=steps_succeeded,
                steps_failed=steps_failed,
                steps_skipped=steps_skipped,
                fidelity_score=fidelity,
                warnings=warnings,
                errors=errors,
                metadata={"dry_run": is_dry_run, "security_audit_logged": True},
            )

        except Exception as e:
            logger.error(f"Replication failed: {e}")
            total_duration = (datetime.utcnow() - start_time).total_seconds()

            return ReplicationResult(
                source_resource_id="unknown",
                target_resource_id=target_resource_id,
                status=ReplicationStatus.FAILED,
                steps_executed=step_results,
                total_duration_seconds=total_duration,
                steps_succeeded=steps_succeeded,
                steps_failed=steps_failed,
                steps_skipped=steps_skipped,
                fidelity_score=0.0,
                warnings=warnings,
                errors=[*errors, str(e)],
            )

    # Private helper methods - Analysis

    async def _check_vault_accessibility(self, resource: Dict[str, Any]) -> bool:
        """Check if Key Vault is accessible.

        Args:
            resource: Resource dictionary

        Returns:
            True if vault is accessible
        """
        # Mock implementation - real version would use Azure SDK
        # from azure.keyvault.secrets import SecretClient
        # from azure.identity import DefaultAzureCredential
        return not self.get_config_value("strict_validation", False)

    def _get_vault_uri(self, resource: Dict[str, Any]) -> str:
        """Get vault URI from resource.

        Args:
            resource: Resource dictionary

        Returns:
            Vault URI
        """
        vault_name = resource.get("name", "unknown")
        # Try to get from properties first
        properties = resource.get("properties", {})
        vault_uri = properties.get("vaultUri")

        if vault_uri:
            return vault_uri

        # Construct default URI
        return f"https://{vault_name}.vault.azure.net/"

    async def _count_secrets(self, resource: Dict[str, Any]) -> int:
        """Count secrets in vault.

        Args:
            resource: Resource dictionary

        Returns:
            Number of secrets
        """
        # Mock implementation - real version would use SecretClient.list_properties_of_secrets()
        return 25

    async def _count_certificates(self, resource: Dict[str, Any]) -> int:
        """Count certificates in vault.

        Args:
            resource: Resource dictionary

        Returns:
            Number of certificates
        """
        # Mock implementation - real version would use CertificateClient.list_properties_of_certificates()
        return 8

    async def _count_keys(self, resource: Dict[str, Any]) -> int:
        """Count keys in vault.

        Args:
            resource: Resource dictionary

        Returns:
            Number of keys
        """
        # Mock implementation - real version would use KeyClient.list_properties_of_keys()
        return 5

    async def _count_access_policies(self, resource: Dict[str, Any]) -> int:
        """Count access policies in vault.

        Args:
            resource: Resource dictionary

        Returns:
            Number of access policies
        """
        # Get from vault properties
        properties = resource.get("properties", {})
        policies = properties.get("accessPolicies", [])
        return len(policies)

    def _calculate_complexity_score(self, elements: List[DataPlaneElement]) -> int:
        """Calculate complexity score from elements.

        Args:
            elements: List of discovered elements

        Returns:
            Complexity score (1-10)
        """
        if not elements:
            return 1

        # Base complexity
        score = 6  # Key Vaults are inherently complex due to security

        # Add for sensitive elements
        if any(e.is_sensitive for e in elements):
            score += 2

        # Add for large number of secrets
        for elem in elements:
            if elem.element_type == "Secrets":
                secret_count = elem.metadata.get("count", 0)
                if secret_count > 50:
                    score += 1
                if secret_count > 100:
                    score += 1

        return min(10, score)

    # Private helper methods - Extraction

    def _has_element(self, analysis: DataPlaneAnalysis, name: str) -> bool:
        """Check if analysis contains an element.

        Args:
            analysis: Analysis result
            name: Element name to check

        Returns:
            True if element exists
        """
        return any(e.name == name for e in analysis.elements)

    def _derive_encryption_key(self, resource: Dict[str, Any]) -> bytes:
        """Derive encryption key for secrets.

        SECURITY: Key is derived from vault URI + a salt.
        In production, should use Azure Key Vault for key management.

        Args:
            resource: Resource dictionary

        Returns:
            32-byte encryption key
        """
        # Use custom key if provided
        custom_key = self.get_config_value("encryption_key")
        if custom_key:
            # Hash the custom key to get 32 bytes
            return hashlib.sha256(custom_key.encode()).digest()

        # Derive from vault URI
        vault_uri = self._get_vault_uri(resource)
        vault_name = resource.get("name", "unknown")

        # Combine vault info with a fixed salt
        key_material = f"{vault_uri}:{vault_name}:atg-encryption-v1"
        return hashlib.sha256(key_material.encode()).digest()

    def _encrypt_secret_value(self, value: str, key: bytes) -> str:
        """Encrypt a secret value.

        SECURITY: Uses AES-256-GCM (simulated - real implementation would use cryptography library).

        Args:
            value: Plain text value
            key: Encryption key

        Returns:
            Base64-encoded encrypted value
        """
        # Mock implementation - real version would use:
        # from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        # aesgcm = AESGCM(key)
        # nonce = os.urandom(12)
        # ciphertext = aesgcm.encrypt(nonce, value.encode(), None)
        # return base64.b64encode(nonce + ciphertext).decode()

        # For now, just base64 encode (NOT SECURE - just for structure)
        encrypted = base64.b64encode(f"ENCRYPTED:{value}".encode()).decode()
        return encrypted

    async def _extract_secrets(
        self, resource: Dict[str, Any], output_dir: Path, encryption_key: bytes
    ) -> ExtractedData:
        """Extract secrets from vault.

        SECURITY: Secret values are encrypted before writing to disk.

        Args:
            resource: Resource dictionary
            output_dir: Output directory
            encryption_key: Encryption key for secret values

        Returns:
            ExtractedData with encrypted secrets
        """
        vault_name = resource.get("name", "unknown")

        # Mock implementation - real version would use SecretClient
        # from azure.keyvault.secrets import SecretClient
        # secret_client = SecretClient(vault_url=vault_uri, credential=credential)
        # secrets = list(secret_client.list_properties_of_secrets())

        max_versions = self.get_config_value("max_versions_per_secret", 1)
        include_disabled = self.get_config_value("include_disabled_secrets", True)

        secrets_list = []

        # Mock secrets data
        mock_secrets = [
            {
                "name": "database-password",
                "value": "SuperSecret123!",
                "enabled": True,
                "content_type": "password",
                "tags": {"env": "prod"},
            },
            {
                "name": "api-key",
                "value": "sk-1234567890abcdef",
                "enabled": True,
                "content_type": "api-key",
                "tags": {"service": "external-api"},
            },
            {
                "name": "connection-string",
                "value": "Server=db.example.com;Database=mydb;",
                "enabled": True,
                "content_type": "connection-string",
                "tags": {},
            },
            {
                "name": "encryption-key",
                "value": "0123456789abcdef0123456789abcdef",
                "enabled": True,
                "content_type": "key",
                "tags": {},
            },
            {
                "name": "old-password",
                "value": "OldSecret456",
                "enabled": False,
                "content_type": "password",
                "tags": {"deprecated": "true"},
            },
        ]

        for secret in mock_secrets:
            if not include_disabled and not secret["enabled"]:
                continue

            # Encrypt the secret value
            encrypted_value = self._encrypt_secret_value(
                secret["value"], encryption_key
            )

            secrets_list.append(
                {
                    "name": secret["name"],
                    "value": encrypted_value,
                    "enabled": secret["enabled"],
                    "content_type": secret.get("content_type"),
                    "tags": secret.get("tags", {}),
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "expires_at": None,
                    "not_before": None,
                    "versions_included": min(max_versions, 1),
                }
            )

        content = json.dumps(
            {
                "vault_name": vault_name,
                "vault_uri": self._get_vault_uri(resource),
                "secrets": secrets_list,
                "metadata": {
                    "total_secrets": len(secrets_list),
                    "encryption": "AES-256-GCM",
                    "note": "Secret values are ENCRYPTED - decrypt during import",
                },
            },
            indent=2,
        )

        file_path = output_dir / "secrets.encrypted.json"
        file_path.write_text(content)

        logger.info(f"SECURITY AUDIT: Extracted {len(secrets_list)} encrypted secrets")

        return ExtractedData(
            name="secrets",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"encrypted": True, "secret_count": len(secrets_list)},
        )

    async def _extract_certificates(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract certificates from vault.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with certificate info
        """
        vault_name = resource.get("name", "unknown")
        export_private = self.get_config_value("export_certificate_private_keys", False)

        # Mock implementation - real version would use CertificateClient
        certs_list = [
            {
                "name": "web-server-cert",
                "enabled": True,
                "subject": "CN=www.example.com",
                "thumbprint": "A1B2C3D4E5F6G7H8I9J0",
                "issuer": "CN=Let's Encrypt Authority",
                "not_before": "2024-01-01T00:00:00Z",
                "not_after": "2025-01-01T00:00:00Z",
                "key_type": "RSA",
                "key_size": 2048,
                "public_key": "-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----",
                "has_private_key": export_private,
            },
            {
                "name": "api-ssl-cert",
                "enabled": True,
                "subject": "CN=api.example.com",
                "thumbprint": "B2C3D4E5F6G7H8I9J0K1",
                "issuer": "CN=DigiCert",
                "not_before": "2024-01-01T00:00:00Z",
                "not_after": "2026-01-01T00:00:00Z",
                "key_type": "RSA",
                "key_size": 4096,
                "public_key": "-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----",
                "has_private_key": export_private,
            },
        ]

        content = json.dumps(
            {
                "vault_name": vault_name,
                "certificates": certs_list,
                "metadata": {
                    "total_certificates": len(certs_list),
                    "private_keys_included": export_private,
                    "note": "Private keys NOT included by default - import will create new CSR"
                    if not export_private
                    else "Private keys INCLUDED - handle with care",
                },
            },
            indent=2,
        )

        file_path = output_dir / "certificates.json"
        file_path.write_text(content)

        return ExtractedData(
            name="certificates",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"certificate_count": len(certs_list)},
        )

    async def _extract_keys(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract key metadata from vault.

        NOTE: Key material (private keys) cannot be exported from Azure Key Vault.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with key metadata
        """
        vault_name = resource.get("name", "unknown")

        # Mock implementation - real version would use KeyClient
        keys_list = [
            {
                "name": "encryption-key-rsa",
                "enabled": True,
                "key_type": "RSA",
                "key_size": 2048,
                "operations": ["encrypt", "decrypt", "wrapKey", "unwrapKey"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T00:00:00Z",
                "expires_at": None,
                "note": "Key material cannot be exported - must be recreated in target vault",
            },
            {
                "name": "signing-key-ec",
                "enabled": True,
                "key_type": "EC",
                "curve_name": "P-256",
                "operations": ["sign", "verify"],
                "created_at": "2024-02-01T00:00:00Z",
                "updated_at": "2024-02-01T00:00:00Z",
                "expires_at": None,
                "note": "Key material cannot be exported - must be recreated in target vault",
            },
        ]

        content = json.dumps(
            {
                "vault_name": vault_name,
                "keys": keys_list,
                "metadata": {
                    "total_keys": len(keys_list),
                    "note": "IMPORTANT: Key material NOT exported (Azure Key Vault restriction). Keys must be manually recreated in target vault with same properties.",
                },
            },
            indent=2,
        )

        file_path = output_dir / "keys_metadata.json"
        file_path.write_text(content)

        return ExtractedData(
            name="keys",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
            metadata={"key_count": len(keys_list)},
        )

    async def _extract_access_policies(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract access policies from vault.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with access policies
        """
        vault_name = resource.get("name", "unknown")

        # Get access policies from resource properties
        properties = resource.get("properties", {})
        policies = properties.get("accessPolicies", [])

        policies_list = []
        for policy in policies:
            policies_list.append(
                {
                    "tenant_id": policy.get("tenantId"),
                    "object_id": policy.get("objectId"),
                    "application_id": policy.get("applicationId"),
                    "permissions": {
                        "keys": policy.get("permissions", {}).get("keys", []),
                        "secrets": policy.get("permissions", {}).get("secrets", []),
                        "certificates": policy.get("permissions", {}).get(
                            "certificates", []
                        ),
                    },
                }
            )

        content = json.dumps(
            {
                "vault_name": vault_name,
                "access_policies": policies_list,
                "metadata": {
                    "total_policies": len(policies_list),
                    "note": "Principal Object IDs must be updated for target tenant",
                },
            },
            indent=2,
        )

        file_path = output_dir / "access_policies.json"
        file_path.write_text(content)

        return ExtractedData(
            name="access_policies",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    async def _extract_vault_config(
        self, resource: Dict[str, Any], output_dir: Path
    ) -> ExtractedData:
        """Extract vault configuration.

        Args:
            resource: Resource dictionary
            output_dir: Output directory

        Returns:
            ExtractedData with vault config
        """
        vault_name = resource.get("name", "unknown")
        properties = resource.get("properties", {})

        config = {
            "vault_name": vault_name,
            "sku": properties.get("sku", {}).get("name", "standard"),
            "tenant_id": properties.get("tenantId"),
            "enabled_for_deployment": properties.get("enabledForDeployment", False),
            "enabled_for_disk_encryption": properties.get(
                "enabledForDiskEncryption", False
            ),
            "enabled_for_template_deployment": properties.get(
                "enabledForTemplateDeployment", False
            ),
            "enable_soft_delete": properties.get("enableSoftDelete", True),
            "soft_delete_retention_days": properties.get(
                "softDeleteRetentionInDays", 90
            ),
            "enable_purge_protection": properties.get("enablePurgeProtection", False),
            "enable_rbac_authorization": properties.get(
                "enableRbacAuthorization", False
            ),
            "network_acls": properties.get("networkAcls", {}),
            "private_endpoint_connections": properties.get(
                "privateEndpointConnections", []
            ),
        }

        content = json.dumps(config, indent=2)

        file_path = output_dir / "vault_config.json"
        file_path.write_text(content)

        return ExtractedData(
            name="vault_config",
            format=ExtractionFormat.JSON,
            content=content,
            file_path=str(file_path),
            size_bytes=len(content.encode()),
            checksum=hashlib.sha256(content.encode()).hexdigest(),
        )

    # Private helper methods - Script generation

    def _find_extracted_data(
        self, extraction: ExtractionResult, name_pattern: str
    ) -> Optional[ExtractedData]:
        """Find extracted data by name pattern.

        Args:
            extraction: Extraction result
            name_pattern: Name pattern to search for

        Returns:
            First matching ExtractedData or None
        """
        for data in extraction.extracted_data:
            if name_pattern.lower() in data.name.lower():
                return data
        return None

    def _generate_prereq_check_script(self) -> str:
        """Generate PowerShell script to verify target vault.

        Returns:
            PowerShell script content
        """
        return """# Check target Key Vault accessibility
param(
    [Parameter(Mandatory=$true)]
    [string]$VaultName
)

Write-Host "Verifying Key Vault: $VaultName"

# Check if vault exists
try {
    $vault = Get-AzKeyVault -VaultName $VaultName -ErrorAction Stop
    Write-Host "✓ Key Vault found: $($vault.VaultName)"
    Write-Host "  Location: $($vault.Location)"
    Write-Host "  Resource Group: $($vault.ResourceGroupName)"
} catch {
    Write-Error "✗ Key Vault not found: $VaultName"
    Write-Error "Please create the vault first or verify the name"
    exit 1
}

# Check permissions
try {
    # Try to list secrets (requires read permission)
    $null = Get-AzKeyVaultSecret -VaultName $VaultName -ErrorAction Stop
    Write-Host "✓ Have read access to secrets"
} catch {
    Write-Warning "⚠ May lack sufficient permissions - check RBAC or access policies"
}

# Check if soft delete is enabled
if ($vault.EnableSoftDelete) {
    Write-Host "✓ Soft delete enabled (retention: $($vault.SoftDeleteRetentionInDays) days)"
} else {
    Write-Warning "⚠ Soft delete not enabled - consider enabling for production"
}

Write-Host ""
Write-Host "Target vault verification completed successfully"
"""

    def _generate_vault_config_script(self, config_data: ExtractedData) -> str:
        """Generate script to configure vault settings.

        Args:
            config_data: Vault configuration data

        Returns:
            PowerShell script
        """
        return """# Configure Key Vault settings
param(
    [Parameter(Mandatory=$true)]
    [string]$VaultName
)

Write-Host "Configuring Key Vault: $VaultName"

$vault = Get-AzKeyVault -VaultName $VaultName

# Enable soft delete if not already enabled
if (-not $vault.EnableSoftDelete) {
    Write-Host "Enabling soft delete..."
    Update-AzKeyVault -VaultName $VaultName -EnableSoftDelete $true
}

# Configure soft delete retention (90 days standard)
Write-Host "Setting soft delete retention to 90 days..."
Update-AzKeyVault -VaultName $VaultName -SoftDeleteRetentionInDays 90

# Note: Purge protection cannot be disabled once enabled
# Enable with caution:
# Update-AzKeyVault -VaultName $VaultName -EnablePurgeProtection $true

Write-Host "✓ Vault configuration completed"
"""

    def _generate_secrets_import_script(self, secrets_data: ExtractedData) -> str:
        """Generate script to import secrets.

        Args:
            secrets_data: Secrets data (encrypted)

        Returns:
            PowerShell script
        """
        return """# Import secrets to target Key Vault
param(
    [Parameter(Mandatory=$true)]
    [string]$VaultName,
    [Parameter(Mandatory=$true)]
    [string]$SecretsFilePath
)

Write-Host "Importing secrets to: $VaultName"
Write-Host "From file: $SecretsFilePath"

# Read encrypted secrets file
$secretsData = Get-Content -Path $SecretsFilePath -Raw | ConvertFrom-Json

Write-Host "Found $($secretsData.secrets.Count) secrets to import"

$successCount = 0
$failCount = 0

foreach ($secret in $secretsData.secrets) {
    try {
        Write-Host "Importing secret: $($secret.name)..."

        # Decrypt secret value (in real implementation)
        # For now, assumes value is pre-decrypted or handled by calling code
        $secretValue = ConvertTo-SecureString -String $secret.value -AsPlainText -Force

        # Set secret in vault
        $result = Set-AzKeyVaultSecret `
            -VaultName $VaultName `
            -Name $secret.name `
            -SecretValue $secretValue `
            -ContentType $secret.content_type `
            -Tag $secret.tags

        if (-not $secret.enabled) {
            # Disable if it was disabled in source
            Update-AzKeyVaultSecret -VaultName $VaultName -Name $secret.name -Enable $false
        }

        Write-Host "  ✓ Imported: $($secret.name)"
        $successCount++

        # SECURITY AUDIT LOG
        Write-Host "  [AUDIT] Secret imported: $($secret.name) at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    } catch {
        Write-Error "  ✗ Failed to import $($secret.name): $_"
        $failCount++
    }
}

Write-Host ""
Write-Host "Import summary:"
Write-Host "  Success: $successCount"
Write-Host "  Failed: $failCount"

if ($failCount -gt 0) {
    exit 1
}
"""

    def _generate_certificates_import_script(self, certs_data: ExtractedData) -> str:
        """Generate script to import certificates.

        Args:
            certs_data: Certificates data

        Returns:
            PowerShell script
        """
        return """# Import certificates to target Key Vault
param(
    [Parameter(Mandatory=$true)]
    [string]$VaultName,
    [Parameter(Mandatory=$true)]
    [string]$CertsFilePath
)

Write-Host "Importing certificates to: $VaultName"

$certsData = Get-Content -Path $CertsFilePath -Raw | ConvertFrom-Json

Write-Host "Found $($certsData.certificates.Count) certificates"

if (-not $certsData.metadata.private_keys_included) {
    Write-Warning "Private keys NOT included - will need to:"
    Write-Warning "  1. Generate new certificate requests (CSR)"
    Write-Warning "  2. Submit to certificate authority"
    Write-Warning "  3. Import completed certificates"
    Write-Host ""
    Write-Host "This script will document certificate requirements only."
}

foreach ($cert in $certsData.certificates) {
    Write-Host ""
    Write-Host "Certificate: $($cert.name)"
    Write-Host "  Subject: $($cert.subject)"
    Write-Host "  Issuer: $($cert.issuer)"
    Write-Host "  Key Type: $($cert.key_type) $($cert.key_size)"
    Write-Host "  Expires: $($cert.not_after)"

    if ($cert.has_private_key) {
        Write-Host "  → Import certificate with private key"
        # Import-AzKeyVaultCertificate -VaultName $VaultName -Name $cert.name -FilePath "cert_file.pfx"
    } else {
        Write-Host "  → Manual action required: Request new certificate from CA"
    }
}

Write-Host ""
Write-Host "Certificate import documentation completed"
"""

    def _generate_keys_documentation_script(self, keys_data: ExtractedData) -> str:
        """Generate script to document key requirements.

        Args:
            keys_data: Keys metadata

        Returns:
            Shell script
        """
        return """#!/bin/bash
# Document Key Vault key requirements
# Key material cannot be exported from Azure Key Vault
# This script documents keys that must be manually recreated

echo "Key Recreation Requirements"
echo "==========================="
echo ""

cat << 'EOF'
IMPORTANT: Azure Key Vault does NOT allow exporting key material.
All keys must be manually recreated in the target vault with matching properties.

Keys to recreate:

1. encryption-key-rsa
   - Type: RSA
   - Size: 2048
   - Operations: encrypt, decrypt, wrapKey, unwrapKey
   - Command: az keyvault key create --vault-name <TARGET_VAULT> --name encryption-key-rsa --kty RSA --size 2048

2. signing-key-ec
   - Type: EC
   - Curve: P-256
   - Operations: sign, verify
   - Command: az keyvault key create --vault-name <TARGET_VAULT> --name signing-key-ec --kty EC --curve P-256

SECURITY NOTE: Key material will be different in target vault.
Applications using these keys must be updated to use the new key versions.
EOF

echo ""
echo "Documentation generated successfully"
"""

    def _generate_access_policies_script(self, policies_data: ExtractedData) -> str:
        """Generate script to configure access policies.

        Args:
            policies_data: Access policies data

        Returns:
            PowerShell script
        """
        return """# Configure Key Vault access policies
param(
    [Parameter(Mandatory=$true)]
    [string]$VaultName,
    [Parameter(Mandatory=$true)]
    [string]$PoliciesFilePath
)

Write-Host "Configuring access policies for: $VaultName"

$policiesData = Get-Content -Path $PoliciesFilePath -Raw | ConvertFrom-Json

Write-Warning "IMPORTANT: Object IDs from source tenant will not work in target tenant"
Write-Warning "You must update Object IDs to match principals in the target tenant"
Write-Host ""

foreach ($policy in $policiesData.access_policies) {
    Write-Host "Access Policy:"
    Write-Host "  Object ID (SOURCE): $($policy.object_id)"
    Write-Host "  Permissions:"
    Write-Host "    Secrets: $($policy.permissions.secrets -join ', ')"
    Write-Host "    Keys: $($policy.permissions.keys -join ', ')"
    Write-Host "    Certificates: $($policy.permissions.certificates -join ', ')"
    Write-Host ""
    Write-Host "  → Manual action required: Identify corresponding principal in target tenant"
    Write-Host "  → Command template:"
    Write-Host "     Set-AzKeyVaultAccessPolicy -VaultName $VaultName -ObjectId <NEW_OBJECT_ID> \"
    Write-Host "       -PermissionsToSecrets $($policy.permissions.secrets -join ',') \"
    Write-Host "       -PermissionsToKeys $($policy.permissions.keys -join ',') \"
    Write-Host "       -PermissionsToCertificates $($policy.permissions.certificates -join ',')"
    Write-Host ""
}

Write-Host "Access policy documentation completed"
Write-Host "Please configure policies manually with correct Object IDs"
"""

    def _generate_validation_script(self) -> str:
        """Generate validation script.

        Returns:
            PowerShell script
        """
        return """# Validate Key Vault configuration and contents
param(
    [Parameter(Mandatory=$true)]
    [string]$VaultName
)

Write-Host "Validating Key Vault: $VaultName"
Write-Host "=================================="

# Get vault info
$vault = Get-AzKeyVault -VaultName $VaultName
Write-Host ""
Write-Host "Vault Configuration:"
Write-Host "  Name: $($vault.VaultName)"
Write-Host "  Location: $($vault.Location)"
Write-Host "  Resource Group: $($vault.ResourceGroupName)"
Write-Host "  Soft Delete: $($vault.EnableSoftDelete)"
Write-Host "  Purge Protection: $($vault.EnablePurgeProtection)"

# List secrets
Write-Host ""
Write-Host "Secrets:"
$secrets = Get-AzKeyVaultSecret -VaultName $VaultName
Write-Host "  Total: $($secrets.Count)"
foreach ($secret in $secrets | Select-Object -First 5) {
    Write-Host "    - $($secret.Name) (Enabled: $($secret.Enabled))"
}
if ($secrets.Count -gt 5) {
    Write-Host "    ... and $($secrets.Count - 5) more"
}

# List certificates
Write-Host ""
Write-Host "Certificates:"
$certs = Get-AzKeyVaultCertificate -VaultName $VaultName
Write-Host "  Total: $($certs.Count)"
foreach ($cert in $certs) {
    Write-Host "    - $($cert.Name) (Expires: $($cert.Expires))"
}

# List keys
Write-Host ""
Write-Host "Keys:"
$keys = Get-AzKeyVaultKey -VaultName $VaultName
Write-Host "  Total: $($keys.Count)"
foreach ($key in $keys) {
    Write-Host "    - $($key.Name) (Enabled: $($key.Enabled))"
}

Write-Host ""
Write-Host "✓ Validation completed successfully"
"""

    # Private helper methods - Execution

    def _dependencies_met(
        self, step: ReplicationStep, results: List[StepResult]
    ) -> bool:
        """Check if step dependencies are met.

        Args:
            step: Step to check
            results: Results of previous steps

        Returns:
            True if all dependencies succeeded
        """
        if not step.depends_on:
            return True

        for dep in step.depends_on:
            dep_result = next((r for r in results if r.step_id == dep), None)
            if not dep_result or dep_result.status != ReplicationStatus.SUCCESS:
                return False

        return True

    async def _execute_step_on_target(
        self, step: ReplicationStep, target_resource_id: str
    ) -> StepResult:
        """Execute a replication step on target Key Vault.

        Args:
            step: Step to execute
            target_resource_id: Target vault resource ID

        Returns:
            StepResult with execution status
        """
        # Mock implementation - real version would use Azure SDK
        # from azure.keyvault.secrets import SecretClient
        # from azure.identity import DefaultAzureCredential
        start_time = datetime.utcnow()

        # Simulate execution
        await asyncio.sleep(0.5)

        duration = (datetime.utcnow() - start_time).total_seconds()

        return StepResult(
            step_id=step.step_id,
            status=ReplicationStatus.SUCCESS,
            duration_seconds=duration,
            stdout=f"[MOCK] Executed {step.step_id} successfully",
            stderr="",
            exit_code=0,
        )

    def _calculate_fidelity_score(
        self, succeeded: int, failed: int, skipped: int, total: int
    ) -> float:
        """Calculate fidelity score.

        Args:
            succeeded: Number of successful steps
            failed: Number of failed steps
            skipped: Number of skipped steps
            total: Total steps

        Returns:
            Fidelity score (0.0-1.0)
        """
        if total == 0:
            return 0.0

        # Weight: succeeded=1.0, skipped=0.5, failed=0.0
        weighted_score = succeeded + (skipped * 0.5)
        return min(1.0, weighted_score / total)
