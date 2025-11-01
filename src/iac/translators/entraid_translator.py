"""
EntraId (Azure AD) Identity Translation for Cross-Tenant Deployment

Translates Entra ID (Azure Active Directory) object references when generating
IaC for a different target tenant. This is the most critical translator for
cross-tenant scenarios as object ID mismatches cause security failures.

Handles:
1. Tenant ID translation (source tenant -> target tenant)
2. Object ID translation for users, groups, service principals (via mapping file)
3. Principal ID translation in role assignments
4. Access policy object IDs in Key Vault
5. User Principal Name (UPN) domain translation (optional)

Translation Strategy:
- ALWAYS translate: tenant_id fields (source -> target tenant)
- CONDITIONALLY translate: object_id, principal_id, application_id (only if mapping available)
- WARN LOUDLY: When identity mapping missing for object IDs

Security Note:
    Object ID mismatches cause deployment failures and security vulnerabilities.
    This translator is conservative and thorough. When in doubt, it warns
    rather than failing silently.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base_translator import BaseTranslator, TranslationContext
from .registry import register_translator

logger = logging.getLogger(__name__)

# UUID pattern for validating object IDs and tenant IDs
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# UPN domain pattern (user@domain.onmicrosoft.com)
UPN_PATTERN = re.compile(r"^([^@]+)@(.+)$")


@dataclass
class IdentityMapping:
    """Mapping for a single identity from source to target tenant."""

    source_object_id: str
    """Source tenant object ID"""

    target_object_id: str
    """Target tenant object ID"""

    source_upn: Optional[str] = None
    """Source User Principal Name (for users)"""

    target_upn: Optional[str] = None
    """Target User Principal Name (for users)"""

    source_name: Optional[str] = None
    """Source display name (for groups/service principals)"""

    target_name: Optional[str] = None
    """Target display name (for groups/service principals)"""

    source_app_id: Optional[str] = None
    """Source application ID (for service principals)"""

    target_app_id: Optional[str] = None
    """Target application ID (for service principals)"""

    match_confidence: str = "manual"
    """Confidence level: high, medium, low, manual"""

    match_method: Optional[str] = None
    """How the mapping was created: email, upn, displayName, appId, manual"""

    notes: Optional[str] = None
    """Additional notes about this mapping"""


@dataclass
class TenantMapping:
    """Mapping between source and target tenants."""

    source_tenant_id: str
    """Source tenant ID (where resources were discovered)"""

    target_tenant_id: str
    """Target tenant ID (where resources will be deployed)"""

    source_subscription_id: Optional[str] = None
    """Source subscription ID (optional, for context)"""

    target_subscription_id: Optional[str] = None
    """Target subscription ID (optional, for context)"""

    source_domain: Optional[str] = None
    """Source domain (e.g., source.onmicrosoft.com)"""

    target_domain: Optional[str] = None
    """Target domain (e.g., target.onmicrosoft.com)"""


@dataclass
class IdentityMappingManifest:
    """Complete mapping manifest for cross-tenant identity translation."""

    tenant_mapping: TenantMapping
    """Tenant-level mapping information"""

    users: Dict[str, IdentityMapping] = field(default_factory=dict)
    """User object ID mappings: {source_object_id: IdentityMapping}"""

    groups: Dict[str, IdentityMapping] = field(default_factory=dict)
    """Group object ID mappings: {source_object_id: IdentityMapping}"""

    service_principals: Dict[str, IdentityMapping] = field(default_factory=dict)
    """Service principal object ID mappings: {source_object_id: IdentityMapping}"""

    def get_mapping(self, object_id: str) -> Optional[IdentityMapping]:
        """
        Get identity mapping for any object ID across all types.

        Args:
            object_id: Source object ID to look up

        Returns:
            IdentityMapping if found, None otherwise
        """
        # Try users first (most common)
        if object_id in self.users:
            return self.users[object_id]

        # Try groups
        if object_id in self.groups:
            return self.groups[object_id]

        # Try service principals
        if object_id in self.service_principals:
            return self.service_principals[object_id]

        return None


@register_translator
class EntraIdTranslator(BaseTranslator):
    """
    Translates Entra ID (Azure AD) object references for cross-tenant deployment.

    This translator handles identity translation which is critical for:
    - Role assignments (RBAC)
    - Key Vault access policies
    - Custom role definitions
    - Service principal references
    - User and group memberships

    The translator requires an identity mapping file (JSON) that maps source
    tenant object IDs to target tenant object IDs. Without this file, only
    tenant ID translation will be performed (object IDs will be preserved with warnings).

    Usage:
        # With identity mapping file in TranslationContext
        context = TranslationContext(
            source_tenant_id="aaaa-aaaa-aaaa",
            target_tenant_id="bbbb-bbbb-bbbb",
            identity_mapping={...}  # Loaded from JSON file
        )

        translator = EntraIdTranslator(context)
        result = translator.translate(resource, context)
    """

    @property
    def supported_resource_types(self) -> List[str]:
        """
        Resource types that contain Entra ID references.

        Supports both Azure and Terraform resource type formats.

        Returns:
            List of Azure resource types this translator handles
        """
        return [
            # Role assignments (RBAC)
            "azurerm_role_assignment",
            "Microsoft.Authorization/roleAssignments",
            "Microsoft.Authorization/roleDefinitions",
            # Key Vault (access policies contain object IDs)
            "azurerm_key_vault",
            "Microsoft.KeyVault/vaults",
            # Entra ID resources (if generating them)
            "azuread_user",
            "Microsoft.Graph/users",
            "Microsoft.AAD/User",
            "User",  # Neo4j label
            # Groups
            "azuread_group",
            "Microsoft.Graph/groups",
            "Microsoft.AAD/Group",
            "Group",  # Neo4j label
            # Service Principals
            "azuread_service_principal",
            "Microsoft.Graph/servicePrincipals",
            "Microsoft.AAD/ServicePrincipal",
            "ServicePrincipal",  # Neo4j label
            # Applications
            "azuread_application",
            "Microsoft.Graph/applications",
            "Microsoft.AAD/Application",
            "Application",  # Neo4j label
        ]

    def __init__(self, context: TranslationContext):
        """
        Initialize EntraIdTranslator.

        Args:
            context: Translation context with tenant info and optional identity mapping
        """
        super().__init__(context)

        # Load identity mapping manifest if provided
        self.manifest: Optional[IdentityMappingManifest] = None
        if context.identity_mapping:
            self.manifest = self._load_manifest_from_dict(context.identity_mapping)
            logger.info(
                f"Loaded identity mappings: "
                f"{len(self.manifest.users)} users, "
                f"{len(self.manifest.groups)} groups, "
                f"{len(self.manifest.service_principals)} service principals"
            )
        else:
            logger.warning(
                "No identity mapping provided. Only tenant ID translation will be performed. "
                "Object IDs will be preserved (may cause deployment failures)."
            )

        # Track missing mappings for reporting
        self.missing_mappings: List[Dict[str, str]] = []

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this resource needs Entra ID translation.

        Args:
            resource: Resource dictionary from Neo4j

        Returns:
            True if resource contains Entra ID references
        """
        resource_type = resource.get("type", "")
        properties = resource.get("properties", {})

        # Defensive type check: ensure properties is a dict
        if not isinstance(properties, dict):
            properties = {}

        # Check if resource type is supported
        type_supported = False
        for supported_type in self.supported_resource_types:
            if supported_type in resource_type:
                type_supported = True
                break

        if not type_supported:
            return False

        # Additional check: does this resource actually have identity fields?

        # Role assignments have principalId
        if "roleAssignment" in resource_type:
            return "principalId" in properties

        # Key Vaults have accessPolicies with objectId
        if "KeyVault" in resource_type:
            access_policies = properties.get("accessPolicies", [])
            return len(access_policies) > 0

        # Entra ID resources themselves (users, groups, service principals)
        if any(
            id_type in resource_type
            for id_type in ["users", "groups", "servicePrincipals", "applications"]
        ):
            return True

        # Check for tenant_id field anywhere in resource
        resource_json = json.dumps(resource)
        if (
            self.context.source_tenant_id
            and self.context.source_tenant_id in resource_json
        ):
            return True

        return False

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate Entra ID references in a resource.

        Translation happens in this order:
        1. Tenant ID replacement (always)
        2. Object ID translation in role assignments
        3. Object ID translation in Key Vault access policies
        4. UPN domain translation (if domain mapping available)

        Args:
            resource: Resource dictionary to translate

        Returns:
            Translated resource dictionary

        Raises:
            ValueError: In strict_mode when required mappings are missing
        """
        translated_resource = resource.copy()
        warnings: List[str] = []

        resource_type = resource.get("type", "")

        # Step 1: Translate tenant IDs (always performed)
        if self.context.source_tenant_id and self.context.target_tenant_id:
            translated_resource, tenant_warnings = self._translate_tenant_ids(
                translated_resource
            )
            warnings.extend(tenant_warnings)

        # Step 2: Translate role assignment principal IDs
        if "roleAssignment" in resource_type:
            translated_resource, role_warnings = self._translate_role_assignment(
                translated_resource
            )
            warnings.extend(role_warnings)

        # Step 3: Translate Key Vault access policies
        if "KeyVault" in resource_type:
            (
                translated_resource,
                kv_warnings,
            ) = self._translate_keyvault_access_policies(translated_resource)
            warnings.extend(kv_warnings)

        # Step 4: Translate UPNs (if domain mapping available)
        if self.manifest and self.manifest.tenant_mapping.source_domain:
            translated_resource, upn_warnings = self._translate_upns(
                translated_resource
            )
            warnings.extend(upn_warnings)

        return translated_resource

    def _translate_tenant_ids(
        self, resource: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Replace all occurrences of source tenant ID with target tenant ID.

        This is a global find-and-replace throughout the resource JSON.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (translated_resource, warnings)
        """
        if not self.context.source_tenant_id or not self.context.target_tenant_id:
            return resource, []

        warnings: List[str] = []

        # Convert to JSON string, replace all occurrences, convert back
        resource_json = json.dumps(resource)

        # Count occurrences for reporting
        occurrence_count = resource_json.count(self.context.source_tenant_id)

        if occurrence_count > 0:
            resource_json = resource_json.replace(
                self.context.source_tenant_id, self.context.target_tenant_id
            )
            logger.debug(
                f"Replaced {occurrence_count} tenant ID references: "
                f"{self.context.source_tenant_id} -> {self.context.target_tenant_id}"
            )

        return json.loads(resource_json), warnings

    def _translate_role_assignment(
        self, resource: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Translate principal_id in role assignments.

        Args:
            resource: Role assignment resource

        Returns:
            Tuple of (translated_resource, warnings)
        """
        warnings: List[str] = []
        properties = resource.get("properties", {})

        # Defensive type check: ensure properties is a dict
        if not isinstance(properties, dict):
            warnings.append("Role assignment properties is not a dict, skipping translation")
            return resource, warnings

        principal_id = properties.get("principalId")
        principal_type = properties.get("principalType", "Unknown")

        if not principal_id:
            return resource, warnings

        # Validate principal_id format
        if not self._is_valid_uuid(principal_id):
            warnings.append(
                f"Invalid principal ID format: {principal_id} (expected UUID)"
            )
            return resource, warnings

        # Attempt to translate using identity mapping
        translated_id, translate_warnings = self._translate_object_id(
            principal_id, principal_type
        )
        warnings.extend(translate_warnings)

        if translated_id != principal_id:
            properties["principalId"] = translated_id
            logger.info(
                f"Translated {principal_type} principal ID: {principal_id} -> {translated_id}"
            )

        return resource, warnings

    def _translate_keyvault_access_policies(
        self, resource: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Translate object_id in Key Vault access policies.

        Args:
            resource: Key Vault resource

        Returns:
            Tuple of (translated_resource, warnings)
        """
        warnings: List[str] = []
        properties = resource.get("properties", {})

        # Defensive type check: ensure properties is a dict
        if not isinstance(properties, dict):
            warnings.append("Key Vault properties is not a dict, skipping access policy translation")
            return resource, warnings

        access_policies = properties.get("accessPolicies", [])

        for policy in access_policies:
            object_id = policy.get("objectId")
            if not object_id:
                continue

            # Validate object_id format
            if not self._is_valid_uuid(object_id):
                warnings.append(
                    f"Invalid object ID format in access policy: {object_id} (expected UUID)"
                )
                continue

            # Try to translate (we don't know the type, so try all)
            translated_id, translate_warnings = self._translate_object_id(
                object_id, object_type="Unknown"
            )
            warnings.extend(translate_warnings)

            if translated_id != object_id:
                policy["objectId"] = translated_id
                logger.info(
                    f"Translated Key Vault access policy object ID: {object_id} -> {translated_id}"
                )

            # Always update tenant_id in access policy
            if self.context.target_tenant_id:
                policy["tenantId"] = self.context.target_tenant_id

        return resource, warnings

    def _translate_object_id(
        self, object_id: str, object_type: str
    ) -> Tuple[str, List[str]]:
        """
        Translate a single object ID using the identity mapping.

        Args:
            object_id: Source object ID
            object_type: Type hint (User, Group, ServicePrincipal, Unknown)

        Returns:
            Tuple of (translated_id, warnings)
        """
        warnings: List[str] = []

        # If no manifest, we can't translate
        if not self.manifest:
            warnings.append(
                f"No identity mapping available for {object_type} object ID: {object_id}. "
                "This resource may fail to deploy in the target tenant."
            )
            self._report_missing_mapping(object_type, object_id, "No manifest loaded")
            return object_id, warnings

        # Try to find mapping based on type hint
        mapping: Optional[IdentityMapping] = None

        if object_type == "User":
            mapping = self.manifest.users.get(object_id)
        elif object_type == "Group":
            mapping = self.manifest.groups.get(object_id)
        elif object_type == "ServicePrincipal":
            mapping = self.manifest.service_principals.get(object_id)
        elif object_type == "Unknown":
            # Try all types
            mapping = self.manifest.get_mapping(object_id)
        else:
            # Unknown type, try all
            mapping = self.manifest.get_mapping(object_id)

        if not mapping:
            warning_msg = (
                f"No mapping found for {object_type} object ID: {object_id}. "
                "Using original ID (may cause deployment failure)."
            )
            warnings.append(warning_msg)
            self._report_missing_mapping(
                object_type, object_id, "No mapping in manifest"
            )

            if self.context.strict_mode:
                raise ValueError(
                    f"Missing identity mapping for {object_type} {object_id} "
                    f"(strict mode enabled). Please add mapping to identity mapping file."
                )

            return object_id, warnings

        # Check if mapping requires manual input
        if mapping.target_object_id == "MANUAL_INPUT_REQUIRED":
            warning_msg = (
                f"Manual mapping required for {object_type} object ID: {object_id}. "
                "Please update identity mapping file with target object ID."
            )
            warnings.append(warning_msg)
            self._report_missing_mapping(
                object_type, object_id, "Manual input required"
            )

            if self.context.strict_mode:
                raise ValueError(
                    f"Manual mapping required for {object_type} {object_id} "
                    f"(strict mode enabled). Please update identity mapping file."
                )

            return object_id, warnings

        # Validate target object ID format
        if not self._is_valid_uuid(mapping.target_object_id):
            warnings.append(
                f"Invalid target object ID format: {mapping.target_object_id} (expected UUID)"
            )
            return object_id, warnings

        # Success - return translated ID
        logger.debug(
            f"Translated {object_type} object ID: {object_id} -> {mapping.target_object_id} "
            f"(confidence: {mapping.match_confidence}, method: {mapping.match_method})"
        )

        return mapping.target_object_id, warnings

    def _translate_upns(
        self, resource: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Translate User Principal Names (UPNs) by replacing domain.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (translated_resource, warnings)
        """
        warnings: List[str] = []

        if not self.manifest or not self.manifest.tenant_mapping.source_domain:
            return resource, warnings

        source_domain = self.manifest.tenant_mapping.source_domain
        target_domain = self.manifest.tenant_mapping.target_domain

        if not target_domain:
            return resource, warnings

        # Convert to JSON string for easier text replacement
        resource_json = json.dumps(resource)

        # Replace all UPNs with source domain
        # Pattern: anything@source.domain -> anything@target.domain
        upn_pattern = re.compile(rf"([^@\s\"]+)@{re.escape(source_domain)}")
        resource_json, count = upn_pattern.subn(rf"\1@{target_domain}", resource_json)

        if count > 0:
            logger.debug(
                f"Translated {count} UPN domain references: {source_domain} -> {target_domain}"
            )

        return json.loads(resource_json), warnings

    def _is_valid_uuid(self, value: str) -> bool:
        """
        Validate that a value is a valid UUID.

        Args:
            value: String to validate

        Returns:
            True if value is a valid UUID
        """
        return bool(UUID_PATTERN.match(value))

    def _report_missing_mapping(
        self, identity_type: str, source_id: str, context: str
    ) -> None:
        """
        Report a missing identity mapping for later analysis.

        Args:
            identity_type: Type of identity (User, Group, ServicePrincipal)
            source_id: Source object ID that's missing
            context: Context where this mapping was needed
        """
        missing = {
            "identity_type": identity_type,
            "source_id": source_id,
            "context": context,
        }
        self.missing_mappings.append(missing)

        logger.warning(
            f"Missing identity mapping: type={identity_type}, id={source_id}, context={context}"
        )

    def _load_manifest_from_dict(
        self, mapping_dict: Dict[str, Any]
    ) -> IdentityMappingManifest:
        """
        Load identity mapping manifest from dictionary.

        Expected format:
        {
            "tenant_mapping": {
                "source_tenant_id": "...",
                "target_tenant_id": "...",
                ...
            },
            "identity_mappings": {
                "users": {...},
                "groups": {...},
                "service_principals": {...}
            }
        }

        Args:
            mapping_dict: Dictionary loaded from JSON file

        Returns:
            Parsed IdentityMappingManifest

        Raises:
            ValueError: If mapping format is invalid
        """
        # Parse tenant mapping
        tenant_data = mapping_dict.get("tenant_mapping", {})
        if not tenant_data:
            raise ValueError(
                "Invalid identity mapping: missing 'tenant_mapping' section"
            )

        tenant_mapping = TenantMapping(
            source_tenant_id=tenant_data.get("source_tenant_id", ""),
            target_tenant_id=tenant_data.get("target_tenant_id", ""),
            source_subscription_id=tenant_data.get("source_subscription_id"),
            target_subscription_id=tenant_data.get("target_subscription_id"),
            source_domain=tenant_data.get("source_domain"),
            target_domain=tenant_data.get("target_domain"),
        )

        # Validate tenant IDs
        if not tenant_mapping.source_tenant_id or not tenant_mapping.target_tenant_id:
            raise ValueError(
                "Invalid identity mapping: source_tenant_id and target_tenant_id are required"
            )

        # Parse identity mappings
        identity_data = mapping_dict.get("identity_mappings", {})

        # Parse users
        users = {}
        for source_id, mapping in identity_data.get("users", {}).items():
            users[source_id] = IdentityMapping(
                source_object_id=source_id,
                target_object_id=mapping.get("target_object_id", ""),
                source_upn=mapping.get("source_upn"),
                target_upn=mapping.get("target_upn"),
                match_confidence=mapping.get("match_confidence", "manual"),
                match_method=mapping.get("match_method"),
                notes=mapping.get("notes"),
            )

        # Parse groups
        groups = {}
        for source_id, mapping in identity_data.get("groups", {}).items():
            groups[source_id] = IdentityMapping(
                source_object_id=source_id,
                target_object_id=mapping.get("target_object_id", ""),
                source_name=mapping.get("source_name"),
                target_name=mapping.get("target_name"),
                match_confidence=mapping.get("match_confidence", "manual"),
                match_method=mapping.get("match_method"),
                notes=mapping.get("notes"),
            )

        # Parse service principals
        service_principals = {}
        for source_id, mapping in identity_data.get("service_principals", {}).items():
            service_principals[source_id] = IdentityMapping(
                source_object_id=source_id,
                target_object_id=mapping.get("target_object_id", ""),
                source_name=mapping.get("source_name"),
                target_name=mapping.get("target_name"),
                source_app_id=mapping.get("source_app_id"),
                target_app_id=mapping.get("target_app_id"),
                match_confidence=mapping.get("match_confidence", "manual"),
                match_method=mapping.get("match_method"),
                notes=mapping.get("notes"),
            )

        return IdentityMappingManifest(
            tenant_mapping=tenant_mapping,
            users=users,
            groups=groups,
            service_principals=service_principals,
        )

    def get_missing_mappings_report(self) -> Dict[str, Any]:
        """
        Get detailed report of missing identity mappings.

        Returns:
            Dictionary with missing mapping details for programmatic use
        """
        return {
            "total_missing": len(self.missing_mappings),
            "by_type": self._group_missing_by_type(),
            "details": self.missing_mappings,
        }

    def _group_missing_by_type(self) -> Dict[str, int]:
        """
        Group missing mappings by identity type.

        Returns:
            Dictionary with counts per identity type
        """
        by_type: Dict[str, int] = {}
        for missing in self.missing_mappings:
            identity_type = missing["identity_type"]
            by_type[identity_type] = by_type.get(identity_type, 0) + 1
        return by_type
