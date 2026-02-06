"""Resource-Level Fidelity Calculator.

This module provides resource-level fidelity validation comparing source and
replicated Azure resources. It validates configurations at the property level
and generates detailed fidelity reports with security redaction.

Philosophy:
- Ruthless simplicity: Reuse ResourceComparator for property comparison
- Zero-BS: No stubs, fully functional implementation
- Modular design: Clean separation between calculator, security, and formatters
- Regeneratable: Self-contained module with clear public API

Public API:
    ResourceFidelityCalculator: Main calculator class
    ResourceFidelityMetrics: Metrics dataclass
    ResourceClassification: Resource-level classification
    ResourceStatus: Resource state enum
    RedactionLevel: Security redaction levels
    PropertyComparison: Property-level comparison result
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.iac.resource_comparator import ResourceComparator
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


def _sanitize_error_message(error: Exception, debug_mode: bool = False) -> str:
    """Sanitize error message to prevent sensitive data leakage.

    Args:
        error: Exception to sanitize
        debug_mode: If True, include full details (use only in secure environments)

    Returns:
        Sanitized error message safe for logging
    """
    if debug_mode:
        # In debug mode, log full traceback (secure environments only)
        import traceback
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    # Production mode - sanitize sensitive patterns
    error_msg = str(error)

    # Patterns to redact from error messages
    sensitive_patterns = [
        (r"password[=:][\w\-]+", "password=[REDACTED]"),
        (r"key[=:][\w\-]+", "key=[REDACTED]"),
        (r"secret[=:][\w\-]+", "secret=[REDACTED]"),
        (r"token[=:][\w\-]+", "token=[REDACTED]"),
        (r"connection[_\-]?string[=:][\w\-;=]+", "connection_string=[REDACTED]"),
        # Redact subscription IDs and resource IDs (UUIDs and Azure resource paths)
        (r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "[SUBSCRIPTION-ID]"),
        (r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/[^/\s]+", "[RESOURCE-PATH]"),
    ]

    for pattern, replacement in sensitive_patterns:
        error_msg = re.sub(pattern, replacement, error_msg, flags=re.IGNORECASE)

    return f"Operation failed: {error_msg}"


class ResourceStatus(Enum):
    """Resource status classification."""

    EXACT_MATCH = "exact_match"  # All properties match
    DRIFTED = "drifted"  # Some properties differ
    MISSING_TARGET = "missing_target"  # Source exists, target doesn't
    MISSING_SOURCE = "missing_source"  # Target exists, source doesn't


class RedactionLevel(Enum):
    """Security redaction levels for sensitive properties."""

    FULL = "full"  # Redact all sensitive values completely
    MINIMAL = "minimal"  # Redact passwords/keys, show connection info
    NONE = "none"  # No redaction (dangerous!)


@dataclass
class PropertyComparison:
    """Property-level comparison result."""

    property_path: str  # Dot-notation path (e.g., "sku.name")
    source_value: Any  # Value from source resource
    target_value: Any  # Value from target resource
    match: bool  # True if values match
    redacted: bool  # True if values were redacted


@dataclass
class ResourceClassification:
    """Resource-level fidelity classification."""

    resource_id: str  # Resource ID
    resource_name: str  # Resource name
    resource_type: str  # Azure resource type
    status: ResourceStatus  # Classification status
    source_exists: bool  # True if resource exists in source
    target_exists: bool  # True if resource exists in target
    property_comparisons: List[PropertyComparison]  # Property-level comparisons
    mismatch_count: int  # Number of mismatched properties
    match_count: int  # Number of matching properties


@dataclass
class ResourceFidelityMetrics:
    """Aggregate fidelity metrics."""

    total_resources: int
    exact_match: int
    drifted: int
    missing_target: int
    missing_source: int
    match_percentage: float
    top_mismatched_properties: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FidelityResult:
    """Complete fidelity validation result."""

    classifications: List[ResourceClassification]
    metrics: ResourceFidelityMetrics
    validation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_subscription: str = ""
    target_subscription: str = ""
    redaction_level: RedactionLevel = RedactionLevel.FULL
    security_warnings: List[str] = field(default_factory=list)


class ResourceFidelityCalculator:
    """Calculate resource-level fidelity between source and target subscriptions."""

    # Sensitive property patterns for redaction
    SENSITIVE_PATTERNS = [
        r"password",
        r"key",
        r"secret",
        r"token",
        r"connection[_\-]?string",
        r"certificate",
        r"private[_\-]?key",
    ]

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        source_subscription_id: str,
        target_subscription_id: str,
    ):
        """Initialize calculator with Neo4j session manager.

        Args:
            session_manager: Neo4j session manager for graph queries
            source_subscription_id: Source subscription ID
            target_subscription_id: Target subscription ID
        """
        self.session_manager = session_manager
        self.source_subscription_id = source_subscription_id
        self.target_subscription_id = target_subscription_id
        self.comparator = ResourceComparator(
            session_manager=session_manager,
            source_subscription_id=source_subscription_id,
            target_subscription_id=target_subscription_id,
        )

    def _validate_resource_type(self, resource_type: str) -> None:
        """Validate resource type format.

        Args:
            resource_type: Azure resource type string

        Raises:
            ValueError: If resource type format is invalid

        Note:
            Azure resource types must follow the pattern:
            Provider/resourceType (e.g., Microsoft.Storage/storageAccounts)
        """
        # Azure resource type pattern: Provider/resourceType
        # Provider: Must start with capital letter, may contain periods
        # ResourceType: alphanumeric and periods
        pattern = r"^[A-Z][a-zA-Z0-9]*(\.[A-Z][a-zA-Z0-9]*)+\/[a-zA-Z0-9]+(\/[a-zA-Z0-9]+)*$"

        if not re.match(pattern, resource_type):
            raise ValueError(
                f"Invalid resource type format: '{resource_type}'. "
                "Expected format: Provider/resourceType (e.g., Microsoft.Storage/storageAccounts)"
            )

        # Log warning for non-standard providers (not Microsoft.*)
        if not resource_type.startswith("Microsoft."):
            logger.warning(
                f"Resource type '{resource_type}' does not start with 'Microsoft.'. "
                "Ensure this is a valid Azure resource provider."
            )

    def calculate_fidelity(
        self,
        resource_type: Optional[str] = None,
        redaction_level: RedactionLevel = RedactionLevel.FULL,
    ) -> FidelityResult:
        """Calculate resource-level fidelity.

        Args:
            resource_type: Optional filter by resource type
            redaction_level: Security redaction level

        Returns:
            FidelityResult with classifications and metrics

        Raises:
            ValueError: If resource_type format is invalid
            RuntimeError: If Neo4j queries fail (with sanitized error message)
        """
        # Validate resource_type format if provided
        if resource_type:
            self._validate_resource_type(resource_type)

        # Check if debug mode is enabled via environment variable
        debug_mode = os.environ.get("ATG_DEBUG", "").lower() in ("1", "true", "yes")

        try:
            # Query source and target resources
            source_resources = self._query_resources(self.source_subscription_id, resource_type)
            target_resources = self._query_resources(self.target_subscription_id, resource_type)
        except Exception as e:
            # Sanitize error message and log full details to file
            sanitized_msg = _sanitize_error_message(e, debug_mode=debug_mode)
            logger.error(f"Neo4j query failed: {sanitized_msg}")

            # Log full traceback to file (not console) for debugging
            if not debug_mode:
                logger.debug("Full error details:", exc_info=True)

            raise RuntimeError(sanitized_msg) from e

        # Build resource lookup by name
        target_lookup = {r["name"]: r for r in target_resources}

        # Classify resources
        classifications = []

        # Process source resources
        for source in source_resources:
            resource_name = source.get("name", "")
            target = target_lookup.get(resource_name)

            if target is None:
                # Missing in target
                classification = ResourceClassification(
                    resource_id=source.get("id", ""),
                    resource_name=resource_name,
                    resource_type=source.get("type", ""),
                    status=ResourceStatus.MISSING_TARGET,
                    source_exists=True,
                    target_exists=False,
                    property_comparisons=[],
                    mismatch_count=0,
                    match_count=0,
                )
            else:
                # Compare properties
                comparisons = self._compare_properties(
                    source.get("properties", {}), target.get("properties", {}), redaction_level
                )

                mismatch_count = sum(1 for c in comparisons if not c.match and not c.redacted)
                match_count = sum(1 for c in comparisons if c.match)

                status = ResourceStatus.EXACT_MATCH if mismatch_count == 0 else ResourceStatus.DRIFTED

                classification = ResourceClassification(
                    resource_id=source.get("id", ""),
                    resource_name=resource_name,
                    resource_type=source.get("type", ""),
                    status=status,
                    source_exists=True,
                    target_exists=True,
                    property_comparisons=comparisons,
                    mismatch_count=mismatch_count,
                    match_count=match_count,
                )

                # Remove from lookup
                target_lookup.pop(resource_name)

            classifications.append(classification)

        # Remaining target resources are orphaned (missing in source)
        for target in target_lookup.values():
            classification = ResourceClassification(
                resource_id=target.get("id", ""),
                resource_name=target.get("name", ""),
                resource_type=target.get("type", ""),
                status=ResourceStatus.MISSING_SOURCE,
                source_exists=False,
                target_exists=True,
                property_comparisons=[],
                mismatch_count=0,
                match_count=0,
            )
            classifications.append(classification)

        # Calculate metrics
        metrics = self._calculate_metrics(classifications)

        # Generate security warnings
        security_warnings = self._generate_security_warnings(redaction_level)

        return FidelityResult(
            classifications=classifications,
            metrics=metrics,
            source_subscription=self.source_subscription_id,
            target_subscription=self.target_subscription_id,
            redaction_level=redaction_level,
            security_warnings=security_warnings,
        )

    def _query_resources(self, subscription_id: str, resource_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query subscription resources from Neo4j.

        Args:
            subscription_id: Subscription ID to query
            resource_type: Optional filter by resource type

        Returns:
            List of resources
        """
        query = """
        MATCH (r:AzureResource)
        WHERE r.subscription_id = $subscription_id
        """

        params = {"subscription_id": subscription_id}

        if resource_type:
            query += " AND r.type = $resource_type"
            params["resource_type"] = resource_type

        query += """
        RETURN r.id AS id, r.name AS name, r.type AS type, r.properties AS properties
        """

        result = self.session_manager.execute_read(query, params)
        return [dict(record) for record in result]

    def _compare_properties(
        self,
        source_props: Dict[str, Any],
        target_props: Dict[str, Any],
        redaction_level: RedactionLevel,
        prefix: str = "",
    ) -> List[PropertyComparison]:
        """Compare properties recursively.

        Args:
            source_props: Source resource properties
            target_props: Target resource properties
            redaction_level: Security redaction level
            prefix: Property path prefix for recursion

        Returns:
            List of PropertyComparison objects
        """
        comparisons = []

        # Get all property keys
        all_keys = set(source_props.keys()) | set(target_props.keys())

        for key in all_keys:
            property_path = f"{prefix}.{key}" if prefix else key
            source_val = source_props.get(key)
            target_val = target_props.get(key)

            # Handle nested objects
            if isinstance(source_val, dict) and isinstance(target_val, dict):
                comparisons.extend(self._compare_properties(source_val, target_val, redaction_level, property_path))
            elif isinstance(source_val, list) and isinstance(target_val, list):
                # Compare lists
                for idx, (s_item, t_item) in enumerate(zip(source_val, target_val)):
                    item_path = f"{property_path}[{idx}]"
                    if isinstance(s_item, dict) and isinstance(t_item, dict):
                        comparisons.extend(self._compare_properties(s_item, t_item, redaction_level, item_path))
                    else:
                        comparison = PropertyComparison(
                            property_path=item_path,
                            source_value=s_item,
                            target_value=t_item,
                            match=(s_item == t_item),
                            redacted=False,
                        )
                        comparison = self._redact_if_sensitive(comparison, redaction_level)
                        comparisons.append(comparison)
            else:
                # Leaf property comparison
                comparison = PropertyComparison(
                    property_path=property_path,
                    source_value=source_val,
                    target_value=target_val,
                    match=(source_val == target_val),
                    redacted=False,
                )
                comparison = self._redact_if_sensitive(comparison, redaction_level)
                comparisons.append(comparison)

        return comparisons

    def _is_sensitive_property(self, property_path: str) -> bool:
        """Check if property is sensitive and should be redacted.

        Args:
            property_path: Property path in dot notation

        Returns:
            True if property is sensitive
        """
        property_lower = property_path.lower()

        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, property_lower):
                return True

        return False

    def _redact_if_sensitive(self, comparison: PropertyComparison, redaction_level: RedactionLevel) -> PropertyComparison:
        """Redact sensitive property values based on redaction level.

        Args:
            comparison: Property comparison to potentially redact
            redaction_level: Security redaction level

        Returns:
            PropertyComparison with redacted values if sensitive
        """
        if redaction_level == RedactionLevel.NONE:
            return comparison

        if not self._is_sensitive_property(comparison.property_path):
            return comparison

        # Apply redaction
        if redaction_level == RedactionLevel.FULL:
            # Full redaction - hide everything
            return PropertyComparison(
                property_path=comparison.property_path,
                source_value="[REDACTED]",
                target_value="[REDACTED]",
                match=True,  # Redacted values always match
                redacted=True,
            )
        elif redaction_level == RedactionLevel.MINIMAL:
            # Minimal redaction - show structure, hide secrets
            if "connection" in comparison.property_path.lower():
                # For connection strings, preserve server info
                source_redacted = self._minimal_redact_connection_string(comparison.source_value)
                target_redacted = self._minimal_redact_connection_string(comparison.target_value)
                return PropertyComparison(
                    property_path=comparison.property_path,
                    source_value=source_redacted,
                    target_value=target_redacted,
                    match=(source_redacted == target_redacted),
                    redacted=True,
                )
            else:
                # For other sensitive properties, full redaction
                return PropertyComparison(
                    property_path=comparison.property_path,
                    source_value="[REDACTED]",
                    target_value="[REDACTED]",
                    match=True,
                    redacted=True,
                )

        return comparison

    def _minimal_redact_connection_string(self, value: Any) -> str:
        """Minimally redact connection string preserving server info.

        Args:
            value: Connection string value

        Returns:
            Partially redacted string
        """
        if not isinstance(value, str):
            return "[REDACTED]"

        # Preserve server/hostname, redact password/key
        result = value

        # Redact password values
        result = re.sub(r"Password=[^;]+", "Password=[REDACTED]", result, flags=re.IGNORECASE)
        result = re.sub(r"AccountKey=[^;]+", "AccountKey=[REDACTED]", result, flags=re.IGNORECASE)
        result = re.sub(r"SharedAccessKey=[^;]+", "SharedAccessKey=[REDACTED]", result, flags=re.IGNORECASE)

        return result

    def _calculate_metrics(self, classifications: List[ResourceClassification]) -> ResourceFidelityMetrics:
        """Calculate aggregate fidelity metrics.

        Args:
            classifications: List of resource classifications

        Returns:
            ResourceFidelityMetrics with summary statistics
        """
        total = len(classifications)
        exact_match = sum(1 for c in classifications if c.status == ResourceStatus.EXACT_MATCH)
        drifted = sum(1 for c in classifications if c.status == ResourceStatus.DRIFTED)
        missing_target = sum(1 for c in classifications if c.status == ResourceStatus.MISSING_TARGET)
        missing_source = sum(1 for c in classifications if c.status == ResourceStatus.MISSING_SOURCE)

        match_percentage = (exact_match / total * 100) if total > 0 else 0.0

        # Calculate top mismatched properties
        property_mismatches: Dict[str, int] = {}
        for classification in classifications:
            if classification.status == ResourceStatus.DRIFTED:
                for comparison in classification.property_comparisons:
                    if not comparison.match and not comparison.redacted:
                        property_mismatches[comparison.property_path] = property_mismatches.get(comparison.property_path, 0) + 1

        # Sort by count descending
        top_mismatched = [
            {"property": prop, "count": count} for prop, count in sorted(property_mismatches.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return ResourceFidelityMetrics(
            total_resources=total,
            exact_match=exact_match,
            drifted=drifted,
            missing_target=missing_target,
            missing_source=missing_source,
            match_percentage=match_percentage,
            top_mismatched_properties=top_mismatched,
        )

    def _generate_security_warnings(self, redaction_level: RedactionLevel) -> List[str]:
        """Generate security warnings based on redaction level.

        Args:
            redaction_level: Security redaction level

        Returns:
            List of security warning messages
        """
        warnings = []

        if redaction_level == RedactionLevel.FULL:
            warnings.append("Security: FULL redaction enabled. All sensitive properties are completely redacted.")
            warnings.append("Sensitive property values are hidden to protect credentials and secrets.")
        elif redaction_level == RedactionLevel.MINIMAL:
            warnings.append("Security: MINIMAL redaction enabled. Some sensitive information may be visible.")
            warnings.append("Connection strings show server information but passwords are redacted.")
            warnings.append("Use FULL redaction for maximum security.")
        elif redaction_level == RedactionLevel.NONE:
            warnings.append("WARNING: NO REDACTION enabled. All sensitive data is VISIBLE!")
            warnings.append("Passwords, keys, secrets, and connection strings are NOT protected.")
            warnings.append("Only use this mode in secure environments for debugging.")
            warnings.append("Never share reports with NONE redaction level.")

        return warnings


__all__ = [
    "ResourceFidelityCalculator",
    "ResourceFidelityMetrics",
    "ResourceClassification",
    "ResourceStatus",
    "RedactionLevel",
    "PropertyComparison",
    "FidelityResult",
]
