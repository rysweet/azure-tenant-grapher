"""
Key Vault Translator for Cross-Tenant Translation

Translates Azure Key Vault cross-tenant references including:
- Resource IDs in Key Vault properties
- Access policies (tenant_id, object_id, application_id)
- Vault URIs (e.g., https://{name}.vault.azure.net/)
- Key/Secret/Certificate resource IDs

This translator handles the critical security-sensitive area of Key Vault access
policies, which contain Entra ID (Azure AD) object IDs that are tenant-specific.

Example Translations:
    Resource ID:
        /subscriptions/SOURCE/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv1
        -> /subscriptions/TARGET/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv1

    Access Policy:
        {
          "tenant_id": "source-tenant-id",
          "object_id": "source-object-id",
          "permissions": {...}
        }
        -> {
          "tenant_id": "target-tenant-id",
          "object_id": "target-object-id",  # If identity mapping available
          "permissions": {...}
        }

    Vault URI:
        https://sourcekv.vault.azure.net/
        -> https://sourcekv.vault.azure.net/  # Typically no change needed

Design Philosophy:
    - CONSERVATIVE: Key Vault access is security-critical - be very cautious
    - INFORMATIVE: Provide clear warnings when identity mapping is missing
    - DEFENSIVE: Validate all inputs and handle errors gracefully
    - TRACEABLE: Record all translations for audit purposes
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .base_translator import BaseTranslator
from .registry import register_translator

logger = logging.getLogger(__name__)

# Key Vault URI pattern: https://{vault-name}.vault.azure.net/
VAULT_URI_PATTERN = re.compile(
    r"https?://([a-z0-9\-]+)\.vault\.azure\.net/?",
    re.IGNORECASE,
)

# Key Vault resource ID pattern
KEYVAULT_ID_PATTERN = re.compile(
    r"/subscriptions/([^/]+)/resourceGroups/([^/]+)/providers/Microsoft\.KeyVault/vaults/([^/]+)",
    re.IGNORECASE,
)

# Key/Secret/Certificate resource ID pattern (hierarchical under vault)
KEYVAULT_ITEM_ID_PATTERN = re.compile(
    r"/subscriptions/([^/]+)/resourceGroups/([^/]+)/providers/Microsoft\.KeyVault/vaults/([^/]+)/(keys|secrets|certificates)/([^/]+)",
    re.IGNORECASE,
)


@register_translator
class KeyVaultTranslator(BaseTranslator):
    """
    Translates Azure Key Vault cross-tenant references.

    Handles translation of:
    - Key Vault resource IDs
    - Access policies (tenant_id, object_id, application_id)
    - Vault URIs
    - Key/Secret/Certificate resource IDs

    This translator is CRITICAL for security as it handles identity-based
    access control. It operates in two modes:

    1. WITH identity mapping (Phase 3): Fully translates object IDs
    2. WITHOUT identity mapping (Phase 2): Translates tenant_id only, warns about object IDs

    Design Philosophy:
    - Conservative: Only translate when necessary and safe
    - Defensive: Validate all inputs, gracefully handle errors
    - Informative: Provide warnings for security-critical issues
    - Traceable: Record all translations for reporting
    """

    @property
    def supported_resource_types(self) -> List[str]:
        """
        Get list of resource types this translator handles.

        Supports both Azure and Terraform resource type formats.

        Returns:
            List containing Key Vault-related resource types
        """
        return [
            # Key Vault
            "azurerm_key_vault",
            "Microsoft.KeyVault/vaults",
            # Keys
            "azurerm_key_vault_key",
            "Microsoft.KeyVault/vaults/keys",
            # Secrets
            "azurerm_key_vault_secret",
            "Microsoft.KeyVault/vaults/secrets",
            # Certificates
            "azurerm_key_vault_certificate",
            "Microsoft.KeyVault/vaults/certificates",
        ]

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this resource needs Key Vault translation.

        A resource needs translation if:
        1. It's a Key Vault resource type
        2. It has properties that might contain cross-subscription/tenant references

        Args:
            resource: Resource dictionary from Neo4j graph

        Returns:
            True if translation is needed
        """
        resource_type = resource.get("type", "")

        # Check if this is a Key Vault resource
        if resource_type not in self.supported_resource_types:
            return False

        # For Key Vaults, check if there are access policies or cross-subscription refs
        if resource_type == "azurerm_key_vault":
            # Check for access policies (always need tenant_id translation)
            if "access_policy" in resource:
                logger.debug(
                    f"Key Vault {resource.get('name', 'unknown')} has access policies"
                )
                return True

            # Check for resource ID that might need translation
            if "id" in resource:
                return True

            # Check for vault_uri
            if "vault_uri" in resource:
                return True

        # For Key/Secret/Certificate resources, check for hierarchical IDs
        if resource_type in [
            "azurerm_key_vault_key",
            "azurerm_key_vault_secret",
            "azurerm_key_vault_certificate",
        ]:
            if "id" in resource or "key_vault_id" in resource:
                logger.debug(
                    f"Key Vault item {resource.get('name', 'unknown')} has resource IDs"
                )
                return True

        return False

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate Key Vault cross-tenant references.

        Args:
            resource: Key Vault resource to translate

        Returns:
            Translated resource dictionary

        Note:
            This method creates a copy to avoid modifying the original resource.
        """
        # Create a copy to avoid modifying original
        translated = resource.copy()
        resource_name = resource.get("name", "unknown")
        resource_type = resource.get("type", "unknown")

        logger.info(
            f"Translating Key Vault resource: {resource_name} ({resource_type})"
        )

        # Translate resource ID
        if "id" in translated:
            original_id = translated["id"]
            translated_id, warnings = self._translate_resource_id(original_id, "id")
            translated["id"] = translated_id
            self._add_result("id", original_id, translated_id, warnings)

        # Translate key_vault_id (for Key/Secret/Certificate resources)
        if "key_vault_id" in translated:
            original_kv_id = translated["key_vault_id"]
            translated_kv_id, warnings = self._translate_resource_id(
                original_kv_id, "key_vault_id"
            )
            translated["key_vault_id"] = translated_kv_id
            self._add_result("key_vault_id", original_kv_id, translated_kv_id, warnings)

        # Translate access policies (Key Vault only)
        if resource_type == "azurerm_key_vault" and "access_policy" in translated:
            original_policies = translated["access_policy"]
            translated_policies, warnings = self._translate_access_policies(
                original_policies
            )
            translated["access_policy"] = translated_policies

            # Record result for access policies block
            self._add_result(
                "access_policy",
                original_policies,
                translated_policies,
                warnings,
                resource_type="Microsoft.KeyVault/vaults",
                resource_name=resource_name,
            )

        # Translate vault_uri (typically no change, but validate)
        if "vault_uri" in translated:
            original_uri = translated["vault_uri"]
            translated_uri, warnings = self._translate_vault_uri(
                original_uri, resource_name
            )
            translated["vault_uri"] = translated_uri
            self._add_result(
                "vault_uri",
                original_uri,
                translated_uri,
                warnings,
                resource_type="Microsoft.KeyVault/vaults",
                resource_name=resource_name,
            )

        logger.info(f"Completed translation for Key Vault resource: {resource_name}")
        return translated

    def _translate_access_policies(
        self, policies: Any
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Translate Key Vault access policies.

        Access policies contain:
        - tenant_id: ALWAYS translate from source to target tenant
        - object_id: CONDITIONALLY translate if identity mapping available
        - application_id: CONDITIONALLY translate if identity mapping available
        - permissions: PRESERVE unchanged

        Args:
            policies: List of access policy dictionaries (or invalid type)

        Returns:
            Tuple of (translated_policies, warnings)

        Note:
            This is CRITICAL for security. Be conservative and provide clear warnings.
        """
        warnings: List[str] = []

        # Defensive type check: ensure policies is a list
        if not isinstance(policies, list):
            warnings.append(
                f"Access policies is not a list (got {type(policies).__name__}), skipping translation"
            )
            return [] if policies is None else policies, warnings

        if not policies:
            warnings.append("Access policies is empty")
            return policies, warnings

        translated_policies = []

        for i, policy in enumerate(policies):
            if not isinstance(policy, dict):
                warnings.append(f"Access policy at index {i} is not a dictionary")
                translated_policies.append(policy)
                continue

            # Create a copy of the policy
            translated_policy = policy.copy()

            # ALWAYS translate tenant_id
            if "tenant_id" in translated_policy:
                original_tenant_id = translated_policy["tenant_id"]

                # Get target tenant ID from context
                target_tenant_id = self.context.target_tenant_id

                if target_tenant_id:
                    translated_policy["tenant_id"] = target_tenant_id
                    logger.debug(
                        f"Translated access policy tenant_id: {original_tenant_id} -> {target_tenant_id}"
                    )
                else:
                    warnings.append(
                        f"Access policy {i}: No target tenant ID available for translation"
                    )

            # CONDITIONALLY translate object_id (if identity mapping available)
            if "object_id" in translated_policy:
                original_object_id = translated_policy["object_id"]

                # Check if we have identity mapping in context
                identity_mapping = self._get_identity_mapping()

                if identity_mapping:
                    # Try to find mapping for this object ID
                    target_object_id = self._lookup_identity_mapping(original_object_id)

                    if target_object_id:
                        translated_policy["object_id"] = target_object_id
                        logger.info(
                            f"Translated access policy object_id: {original_object_id} -> {target_object_id}"
                        )
                    else:
                        warnings.append(
                            f"Access policy {i}: No identity mapping found for object_id '{original_object_id}'. "
                            f"This access policy will likely fail in the target tenant. "
                            f"Please provide an identity mapping file or manually update this after deployment."
                        )
                else:
                    # No identity mapping available - this is expected in Phase 2
                    warnings.append(
                        f"Access policy {i}: Identity mapping not available. "
                        f"Object ID '{original_object_id}' cannot be translated. "
                        f"This access policy will need manual update after deployment."
                    )

            # CONDITIONALLY translate application_id
            if "application_id" in translated_policy:
                original_app_id = translated_policy["application_id"]

                identity_mapping = self._get_identity_mapping()

                if identity_mapping:
                    # Application IDs are typically service principal app IDs
                    target_app_id = self._lookup_application_mapping(original_app_id)

                    if target_app_id:
                        translated_policy["application_id"] = target_app_id
                        logger.info(
                            f"Translated access policy application_id: {original_app_id} -> {target_app_id}"
                        )
                    else:
                        warnings.append(
                            f"Access policy {i}: No application mapping found for application_id '{original_app_id}'. "
                            f"This access policy may fail if the application doesn't exist in target tenant."
                        )
                else:
                    warnings.append(
                        f"Access policy {i}: Identity mapping not available. "
                        f"Application ID '{original_app_id}' cannot be translated."
                    )

            # Permissions are preserved as-is (they're not tenant-specific)
            # Certificate/Key/Secret permissions arrays remain unchanged

            translated_policies.append(translated_policy)

        # Summary warning if any object IDs couldn't be translated
        untranslated_count = sum(
            1 for w in warnings if "cannot be translated" in w.lower()
        )
        if untranslated_count > 0:
            warnings.append(
                f"SECURITY WARNING: {untranslated_count} access policy object IDs could not be translated. "
                f"These access policies will need manual configuration in the target tenant after deployment."
            )

        return translated_policies, warnings

    def _translate_vault_uri(self, uri: str, vault_name: str) -> Tuple[str, List[str]]:
        """
        Translate Key Vault URI.

        Vault URIs typically have the format:
            https://{vault-name}.vault.azure.net/

        Key Vault names are globally unique, so typically no translation is needed.
        However, we validate the URI format and warn about potential name collisions.

        Args:
            uri: Original vault URI
            vault_name: Name of the Key Vault

        Returns:
            Tuple of (translated_uri, warnings)

        Note:
            Vault URIs rarely need translation unless there's a name collision.
        """
        warnings: List[str] = []

        if not uri or not isinstance(uri, str):
            warnings.append("Vault URI is empty or invalid")
            return uri, warnings

        # Skip Terraform variables
        if "${" in uri or "var." in uri:
            return uri, warnings

        # Try to parse the URI
        match = VAULT_URI_PATTERN.match(uri)
        if not match:
            warnings.append(
                f"Vault URI does not match expected format: {uri}. "
                f"Expected format: https://{{name}}.vault.azure.net/"
            )
            return uri, warnings

        vault_name_in_uri = match.group(1)

        # Check if the vault name in URI matches the resource name
        if vault_name_in_uri != vault_name:
            warnings.append(
                f"Vault URI name mismatch: URI has '{vault_name_in_uri}', "
                f"resource name is '{vault_name}'. This may need manual review."
            )

        # Check if a Key Vault with this name exists in the target IaC
        target_exists = self._check_target_exists(
            "Microsoft.KeyVault/vaults", vault_name_in_uri
        )

        if not target_exists:
            warnings.append(
                f"Key Vault '{vault_name_in_uri}' referenced in URI not found in generated IaC. "
                f"This may indicate a cross-subscription reference that needs attention."
            )

        # Warn about potential name collisions (Key Vault names are global)
        # This is informational - we don't change the URI
        logger.debug(
            f"Vault URI validation: {vault_name_in_uri}, target_exists={target_exists}"
        )

        # Vault URIs typically don't need translation (names are globally unique)
        # Return as-is unless there's a specific name remapping scenario
        return uri, warnings

    def _get_identity_mapping(self) -> Optional[Dict[str, Any]]:
        """
        Get identity mapping from translation context.

        This will be used in Phase 3 when identity mapping is available.
        For Phase 2, this returns None.

        Returns:
            Identity mapping dictionary or None if not available
        """
        # Phase 2: No identity mapping yet
        # Phase 3: Will load from context.identity_mapping_file
        identity_mapping_file = self.context.identity_mapping_file

        if not identity_mapping_file:
            logger.debug("No identity mapping file provided in context")
            return None

        # TODO Phase 3: Load and parse identity mapping file
        # For now, return None (Phase 2 implementation)
        logger.debug(
            f"Identity mapping file specified but not yet implemented: {identity_mapping_file}"
        )
        return None

    def _lookup_identity_mapping(self, object_id: str) -> Optional[str]:
        """
        Look up target object ID for a source object ID.

        This will be implemented in Phase 3 when identity mapping is available.

        Args:
            object_id: Source tenant object ID

        Returns:
            Target tenant object ID or None if not found
        """
        # Phase 2: No mapping available
        # Phase 3: Will query identity mapping
        logger.debug(f"Identity mapping lookup not yet implemented for: {object_id}")
        return None

    def _lookup_application_mapping(self, app_id: str) -> Optional[str]:
        """
        Look up target application ID for a source application ID.

        This will be implemented in Phase 3 when identity mapping is available.

        Args:
            app_id: Source tenant application ID

        Returns:
            Target tenant application ID or None if not found
        """
        # Phase 2: No mapping available
        # Phase 3: Will query identity mapping
        logger.debug(f"Application mapping lookup not yet implemented for: {app_id}")
        return None
