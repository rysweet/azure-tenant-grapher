"""Gap identification for property validation.

Identifies missing properties by comparing schema definitions with actual IaC.

Philosophy:
- Direct set comparison for clarity
- No fuzzy matching - exact names only
- Return structured gap information
"""

from typing import Dict, List, Set

from ..models import Criticality, PropertyDefinition, PropertyGap


class GapFinder:
    """Find missing properties in generated IaC."""

    def __init__(self, critical_classifier: "CriticalClassifier"):
        """Initialize with criticality classifier.

        Args:
            critical_classifier: Classifier to determine property criticality
        """
        self.classifier = critical_classifier

    def find_gaps(
        self,
        schema_properties: Dict[str, PropertyDefinition],
        actual_properties: Set[str],
    ) -> List[PropertyGap]:
        """Identify missing properties and classify by criticality.

        Args:
            schema_properties: Property definitions from Terraform schema
            actual_properties: Properties present in generated IaC

        Returns:
            List of PropertyGap objects sorted by criticality (CRITICAL first)
        """
        gaps: List[PropertyGap] = []

        for prop_name, prop_def in schema_properties.items():
            if prop_name not in actual_properties:
                # Property is missing - determine criticality
                criticality = self.classifier.classify_property(prop_def)

                # Generate helpful reason message
                reason = self._generate_reason(prop_def, criticality)

                # Suggest default value if available
                suggested = self._suggest_value(prop_def)

                gap = PropertyGap(
                    property_name=prop_name,
                    criticality=criticality,
                    reason=reason,
                    suggested_value=suggested,
                )
                gaps.append(gap)

        # Sort by criticality (CRITICAL first, LOW last)
        criticality_order = {
            Criticality.CRITICAL: 0,
            Criticality.HIGH: 1,
            Criticality.MEDIUM: 2,
            Criticality.LOW: 3,
        }
        gaps.sort(key=lambda g: criticality_order[g.criticality])

        return gaps

    def _generate_reason(
        self, prop_def: PropertyDefinition, criticality: Criticality
    ) -> str:
        """Generate human-readable reason for gap.

        Args:
            prop_def: Property definition
            criticality: Classified criticality level

        Returns:
            Descriptive reason string
        """
        if criticality == Criticality.CRITICAL:
            return "Required property with no default - blocks deployment"
        elif criticality == Criticality.HIGH:
            return "Security or compliance property - significant risk if missing"
        elif criticality == Criticality.MEDIUM:
            return "Operational property - impacts functionality"
        else:
            return "Optional feature - nice to have"

    def _suggest_value(self, prop_def: PropertyDefinition) -> str | None:
        """Suggest a reasonable default value for missing property.

        Args:
            prop_def: Property definition

        Returns:
            Suggested value string or None if no suggestion available
        """
        # Common property patterns with sensible defaults
        suggestions = {
            "account_tier": "Standard",
            "replication_type": "LRS",
            "tls_version": "TLS1_2",
            "https_only": "true",
            "public_network_access": "Disabled",
            "location": "eastus",
            "min_tls_version": "TLS1_2",
        }

        # Check if this is a known property with a good default
        return suggestions.get(prop_def.name)


__all__ = ["GapFinder"]
