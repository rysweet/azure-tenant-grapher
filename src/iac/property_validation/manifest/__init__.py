"""Property Manifest brick - YAML-based property mapping definitions.

Philosophy:
- Self-contained module for manifest operations
- Standard library + PyYAML only
- Regeneratable from specification
- Clear separation: schema, generator, validator

Public API (the "studs"):
    PropertyMapping: Individual property mapping definition
    ResourceManifest: Complete resource type manifest
    ManifestGenerator: Generate manifests from Azure/Terraform schemas
    ManifestValidator: Validate manifest correctness
    CriticalityLevel: Property criticality enumeration
    PropertyType: Property type enumeration
"""

from .generator import ManifestGenerator
from .schema import (
    CriticalityLevel,
    PropertyMapping,
    PropertyType,
    ProviderVersion,
    ResourceManifest,
)
from .validator import ManifestValidator

__all__ = [
    "CriticalityLevel",
    "ManifestGenerator",
    "ManifestValidator",
    "PropertyMapping",
    "PropertyType",
    "ProviderVersion",
    "ResourceManifest",
]
