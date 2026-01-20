"""Criticality classification for property validation.

Classifies properties by impact level using rule-based logic.

Philosophy:
- Simple rule-based classification
- Domain-specific knowledge encoded explicitly
- No ML or complex algorithms
"""

from typing import Dict, Set

from ..models import Criticality, PropertyDefinition


class CriticalClassifier:
    """Classify property criticality using domain rules."""

    # Properties that block deployment if missing
    CRITICAL_PROPERTIES: Set[str] = {
        "account_tier",
        "replication_type",
        "sku_name",
        "sku_tier",
    }

    # Security and compliance properties
    HIGH_PRIORITY_PROPERTIES: Set[str] = {
        "tls_version",
        "min_tls_version",
        "https_only",
        "public_network_access",
        "network_acls",
        "enable_https_traffic_only",
        "encryption",
        "identity",
    }

    # Operational properties
    MEDIUM_PRIORITY_PROPERTIES: Set[str] = {
        "tags",
        "location",
        "resource_group_name",
        "zone_redundant",
        "backup_enabled",
    }

    # Keywords indicating security/compliance properties
    SECURITY_KEYWORDS: Set[str] = {
        "tls",
        "ssl",
        "https",
        "encryption",
        "security",
        "firewall",
        "network",
        "access",
        "authentication",
        "authorization",
    }

    def classify_property(self, prop_def: PropertyDefinition) -> Criticality:
        """Classify property criticality using domain rules.

        Classification rules:
        1. CRITICAL: Required properties with no defaults (blocks deployment)
        2. HIGH: Security/compliance properties (significant risk)
        3. MEDIUM: Operational properties (impacts functionality)
        4. LOW: Optional features (nice to have)

        Args:
            prop_def: Property definition from schema

        Returns:
            Criticality level
        """
        prop_name = prop_def.name.lower()

        # CRITICAL: Required with no default = deployment blocker
        if prop_def.required and not prop_def.has_default:
            return Criticality.CRITICAL

        # CRITICAL: Known deployment-blocking properties
        if prop_name in self.CRITICAL_PROPERTIES:
            return Criticality.CRITICAL

        # HIGH: Known security/compliance properties
        if prop_name in self.HIGH_PRIORITY_PROPERTIES:
            return Criticality.HIGH

        # HIGH: Property name contains security keywords
        if self._contains_security_keyword(prop_name):
            return Criticality.HIGH

        # MEDIUM: Known operational properties
        if prop_name in self.MEDIUM_PRIORITY_PROPERTIES:
            return Criticality.MEDIUM

        # MEDIUM: Required but has default
        if prop_def.required and prop_def.has_default:
            return Criticality.MEDIUM

        # LOW: Everything else (optional features)
        return Criticality.LOW

    def _contains_security_keyword(self, property_name: str) -> bool:
        """Check if property name indicates security/compliance concern.

        Args:
            property_name: Property name in lowercase

        Returns:
            True if name contains security keyword
        """
        return any(keyword in property_name for keyword in self.SECURITY_KEYWORDS)

    def add_critical_property(self, property_name: str) -> None:
        """Add a property to the CRITICAL classification.

        Allows extending classification rules dynamically.

        Args:
            property_name: Property name to classify as CRITICAL
        """
        self.CRITICAL_PROPERTIES.add(property_name.lower())

    def add_high_priority_property(self, property_name: str) -> None:
        """Add a property to the HIGH priority classification.

        Args:
            property_name: Property name to classify as HIGH
        """
        self.HIGH_PRIORITY_PROPERTIES.add(property_name.lower())

    def add_security_keyword(self, keyword: str) -> None:
        """Add a keyword that indicates security/compliance properties.

        Args:
            keyword: Keyword to add (e.g., "compliance", "audit")
        """
        self.SECURITY_KEYWORDS.add(keyword.lower())

    def get_classification_summary(self) -> Dict[str, int]:
        """Get summary of classification rules currently active.

        Returns:
            Dict with counts of properties in each category
        """
        return {
            "critical_properties": len(self.CRITICAL_PROPERTIES),
            "high_priority_properties": len(self.HIGH_PRIORITY_PROPERTIES),
            "medium_priority_properties": len(self.MEDIUM_PRIORITY_PROPERTIES),
            "security_keywords": len(self.SECURITY_KEYWORDS),
        }


__all__ = ["CriticalClassifier"]
