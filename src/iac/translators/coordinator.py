"""
Coordinator for orchestrating all translators in the IaC generation pipeline.

The TranslationCoordinator manages the translation process by:
1. Discovering and instantiating all registered translators
2. Applying translators to resources in a single pass
3. Collecting translation results and statistics
4. Generating comprehensive reports

Design Pattern:
- Uses TranslatorRegistry for auto-discovery
- Single-pass orchestration for efficiency
- Graceful error handling with fallback
- Comprehensive result tracking

Usage:
    from src.iac.translators import TranslationCoordinator, TranslationContext

    context = TranslationContext(
        source_subscription_id=source_sub,
        target_subscription_id=target_sub,
        available_resources=resources,
    )

    coordinator = TranslationCoordinator(context)
    translated_resources = coordinator.translate_resources(resources)
    report = coordinator.format_translation_report()
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TranslationContext:
    """
    Context passed to all translators during initialization.

    This provides translators with all the information they need to perform
    cross-tenant translation, including subscription/tenant IDs, available
    resources, and configuration options.
    """

    source_subscription_id: Optional[str]
    """Source subscription ID (where resources were scanned)"""

    target_subscription_id: str
    """Target subscription ID (where resources will be deployed)"""

    source_tenant_id: Optional[str] = None
    """Source tenant ID (for Entra ID translation)"""

    target_tenant_id: Optional[str] = None
    """Target tenant ID (for Entra ID translation)"""

    available_resources: Dict[str, Any] = field(default_factory=dict)
    """Resources being generated in IaC (for existence validation)"""

    identity_mapping_file: Optional[str] = None
    """Path to identity mapping file (for EntraIdTranslator)"""

    strict_mode: bool = False
    """If True, fail on missing mappings. If False, warn."""


class TranslationCoordinator:
    """
    Orchestrates all translators in a single pass through resources.

    The coordinator is responsible for:
    - Initializing all registered translators with shared context
    - Applying translators to each resource
    - Collecting results from all translators
    - Generating comprehensive reports

    Design Philosophy:
    - Sequential application (simpler, easier to debug)
    - Graceful degradation (one translator failure doesn't stop others)
    - Comprehensive reporting (visibility into all translations)
    - Performance-conscious (single pass, minimal redundant work)

    Example:
        context = TranslationContext(
            source_subscription_id="source-sub-123",
            target_subscription_id="target-sub-456",
            available_resources={"azurerm_storage_account": {"storage1": {...}}}
        )

        coordinator = TranslationCoordinator(context)
        translated = coordinator.translate_resources(resources)
        print(coordinator.format_translation_report())
    """

    def __init__(self, context: TranslationContext):
        """
        Initialize coordinator with translation context.

        Args:
            context: Translation context with source/target info and resources

        Note:
            Translators are instantiated lazily during initialization.
            Any translators that fail to instantiate are logged and skipped.
        """
        self.context = context
        self.translators: List[Any] = []  # Will hold translator instances
        self._resources_processed = 0
        self._resources_translated = 0
        self._total_warnings = 0
        self._total_errors = 0

        # Initialize translators from registry
        self._initialize_translators()

    def _initialize_translators(self) -> None:
        """
        Initialize all registered translators from the registry.

        This method:
        1. Imports TranslatorRegistry to discover registered translators
        2. Instantiates each translator with the shared context
        3. Handles instantiation failures gracefully
        4. Logs which translators were successfully loaded

        Note:
            Import is done here (not at module level) to avoid circular dependencies
            and to support dynamic translator registration.
        """
        try:
            from .registry import TranslatorRegistry

            logger.debug("Discovering registered translators...")

            # Get list of registered translator names for logging
            registered_names = TranslatorRegistry.get_registered_translators()
            if not registered_names:
                logger.warning("No translators registered in TranslatorRegistry")
                return

            logger.info(
                f"Found {len(registered_names)} registered translators: {registered_names}"
            )

            # Instantiate all translators with the shared context
            self.translators = TranslatorRegistry.create_translators(self.context)

            if not self.translators:
                logger.warning(
                    "No translators were successfully instantiated. "
                    "Translation will be skipped."
                )
            else:
                translator_names = [t.__class__.__name__ for t in self.translators]
                logger.info(
                    f"Initialized {len(self.translators)} translators: {translator_names}"
                )

        except ImportError as e:
            logger.error(f"Failed to import TranslatorRegistry: {e}", exc_info=True)
        except Exception as e:
            logger.error(
                f"Unexpected error during translator initialization: {e}",
                exc_info=True,
            )

    def translate_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate a single resource through all applicable translators.

        Applies each translator sequentially if it can handle the resource.
        If multiple translators modify the same resource, the last one wins
        (though this should be avoided by proper translator design).

        Args:
            resource: Resource dictionary from Neo4j graph

        Returns:
            Translated resource dictionary

        Note:
            - Translators are applied sequentially (not in parallel)
            - Errors in one translator don't prevent others from running
            - Original resource is preserved if all translators fail
        """
        if not self.translators:
            # No translators available, return resource unchanged
            return resource

        translated_resource = resource.copy()

        for translator in self.translators:
            try:
                # Check if this translator can handle this resource
                if hasattr(translator, "can_translate"):
                    # New BaseTranslator pattern
                    if not translator.can_translate(translated_resource):
                        continue

                    translated_resource = translator.translate(translated_resource)
                    logger.debug(
                        f"Applied {translator.__class__.__name__} to "
                        f"{resource.get('type', 'Unknown')}"
                    )

                elif hasattr(translator, "should_translate"):
                    # Legacy PrivateEndpointTranslator pattern
                    # This translator works differently - it operates on resource IDs
                    # rather than full resources, so we skip it here
                    logger.debug(
                        f"Skipping legacy translator {translator.__class__.__name__} "
                        f"(not compatible with resource-level translation)"
                    )
                    continue

                else:
                    logger.warning(
                        f"Translator {translator.__class__.__name__} missing required methods"
                    )
                    continue

            except Exception as e:
                self._total_errors += 1
                logger.error(
                    f"Translator {translator.__class__.__name__} failed "
                    f"on resource {resource.get('id', resource.get('name', 'Unknown'))}: {e}",
                    exc_info=True,
                )
                # Continue with other translators

        return translated_resource

    def translate_resources(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Translate a list of resources through all translators.

        This is the main entry point for batch translation. It processes
        each resource sequentially and collects statistics.

        Args:
            resources: List of resource dictionaries from Neo4j

        Returns:
            List of translated resource dictionaries

        Note:
            - Resources are processed sequentially (not in parallel)
            - Progress is logged for large resource lists
            - Statistics are updated as resources are processed
        """
        if not resources:
            logger.info("No resources to translate")
            return []

        if not self.translators:
            logger.warning(
                "No translators available. Resources will not be translated."
            )
            return resources

        logger.info(
            f"Starting translation of {len(resources)} resources "
            f"using {len(self.translators)} translators"
        )

        translated = []

        for i, resource in enumerate(resources):
            # Log progress for large resource sets
            if i > 0 and i % 100 == 0:
                logger.info(f"Translated {i}/{len(resources)} resources...")

            translated_resource = self.translate_resource(resource)
            translated.append(translated_resource)

            self._resources_processed += 1
            if translated_resource != resource:
                self._resources_translated += 1

        logger.info(
            f"Translation complete: {self._resources_processed} processed, "
            f"{self._resources_translated} translated"
        )

        return translated

    def get_translation_statistics(self) -> Dict[str, Any]:
        """
        Get translation statistics from coordinator and all translators.

        Returns:
            Dictionary with statistics including:
            - Total translators initialized
            - Total resources processed
            - Total resources translated
            - Total warnings
            - Total errors
            - Per-translator statistics

        Example:
            {
                "total_translators": 3,
                "resources_processed": 150,
                "resources_translated": 42,
                "total_warnings": 5,
                "total_errors": 0,
                "translators": [
                    {
                        "name": "PrivateEndpointTranslator",
                        "translations": 12,
                        "warnings": 2
                    },
                    ...
                ]
            }
        """
        translator_stats = []

        for translator in self.translators:
            try:
                # Get report from translator if available
                if hasattr(translator, "get_report"):
                    report = translator.get_report()
                    translator_stats.append(report)
                elif hasattr(translator, "get_translation_results"):
                    # Fallback for translators with just results
                    results = translator.get_translation_results()
                    translator_stats.append(
                        {
                            "translator": translator.__class__.__name__,
                            "total_resources_processed": len(results),
                            "translations_performed": sum(
                                1
                                for r in results
                                if getattr(r, "was_translated", False)
                            ),
                            "warnings": sum(
                                len(getattr(r, "warnings", [])) for r in results
                            ),
                        }
                    )
            except Exception as e:
                logger.error(
                    f"Failed to get statistics from {translator.__class__.__name__}: {e}"
                )

        # Calculate totals
        total_translations = sum(
            stat.get("translations_performed", 0) for stat in translator_stats
        )
        total_warnings = sum(stat.get("warnings", 0) for stat in translator_stats)

        return {
            "total_translators": len(self.translators),
            "resources_processed": self._resources_processed,
            "resources_translated": total_translations,
            "total_warnings": total_warnings,
            "total_errors": self._total_errors,
            "translators": translator_stats,
        }

    def get_translation_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive translation report from all translators.

        Returns:
            Translation report with summary and per-translator details

        Format:
            {
                "summary": {
                    "total_translators": 5,
                    "total_translations": 47,
                    "total_warnings": 3,
                    "total_missing_targets": 0
                },
                "translators": [
                    {
                        "translator": "PrivateEndpointTranslator",
                        "translations_performed": 12,
                        ...
                    }
                ]
            }
        """
        stats = self.get_translation_statistics()

        # Calculate missing targets
        total_missing_targets = 0
        for stat in stats["translators"]:
            total_missing_targets += stat.get("missing_targets", 0)

        return {
            "summary": {
                "total_translators": stats["total_translators"],
                "total_translations": stats["resources_translated"],
                "total_warnings": stats["total_warnings"],
                "total_missing_targets": total_missing_targets,
                "total_errors": stats["total_errors"],
            },
            "translators": stats["translators"],
        }

    def format_translation_report(self) -> str:
        """
        Format translation report as human-readable text.

        Generates a comprehensive, formatted report suitable for:
        - Console output
        - Log files
        - Summary files

        Returns:
            Formatted report string with:
            - Summary statistics
            - Per-translator details
            - Sample translations
            - Warnings and errors

        Example Output:
            ======================================================================
            Cross-Tenant Translation Report
            ======================================================================

            Total Translators: 3
            Total Translations: 47
            Total Warnings: 2
            Total Errors: 0

            Translator Details:
            ----------------------------------------------------------------------

            PrivateEndpointTranslator:
              Processed: 12
              Translated: 8
              Warnings: 0
        """
        report = self.get_translation_report()
        summary = report["summary"]

        lines = [
            "",
            "=" * 70,
            "Cross-Tenant Translation Report",
            "=" * 70,
            "",
            f"Total Translators: {summary['total_translators']}",
            f"Total Translations: {summary['total_translations']}",
            f"Total Warnings: {summary['total_warnings']}",
            f"Total Errors: {summary['total_errors']}",
        ]

        if summary["total_missing_targets"] > 0:
            lines.append(f"Missing Targets: {summary['total_missing_targets']}")

        lines.append("")

        if summary["total_translations"] == 0:
            lines.append("No translations were performed.")
            lines.append("")
            return "\n".join(lines)

        lines.append("Translator Details:")
        lines.append("-" * 70)

        for translator_report in report["translators"]:
            if translator_report.get("translations_performed", 0) > 0:
                lines.append(f"\n{translator_report['translator']}:")
                lines.append(
                    f"  Processed: {translator_report.get('total_resources_processed', 0)}"
                )
                lines.append(
                    f"  Translated: {translator_report.get('translations_performed', 0)}"
                )
                lines.append(f"  Warnings: {translator_report.get('warnings', 0)}")

                # Include sample translations if available
                if translator_report.get("results"):
                    lines.append("  Sample Translations:")
                    for result in translator_report["results"][:3]:  # First 3 samples
                        if isinstance(result, dict):
                            lines.append(
                                f"    • {result.get('resource_type', 'Unknown')}"
                            )
                            if "property" in result:
                                lines.append(f"      Property: {result['property']}")
                            if "original" in result:
                                lines.append(
                                    f"      Original: {result['original'][:80]}..."
                                )
                            if "translated" in result:
                                lines.append(
                                    f"      Translated: {result['translated'][:80]}..."
                                )
                            if result.get("warnings"):
                                for warning in result["warnings"]:
                                    lines.append(f"      Warning: {warning}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    def save_translation_report(self, output_path: str, format: str = "text") -> None:
        """
        Save translation report to a file.

        Args:
            output_path: Path where report should be saved
            format: Output format - "text" (default) or "json"

        Raises:
            ValueError: If format is not supported
            IOError: If file cannot be written
        """
        import json
        from pathlib import Path

        if format not in ("text", "json"):
            raise ValueError(f"Unsupported format: {format}. Use 'text' or 'json'")

        output_file = Path(output_path)

        try:
            if format == "text":
                content = self.format_translation_report()
                output_file.write_text(content)
            else:  # json
                report = self.get_translation_report()
                content = json.dumps(report, indent=2)
                output_file.write_text(content)

            logger.info(f"Translation report saved to: {output_path}")

        except Exception as e:
            logger.error(f"Failed to save translation report: {e}", exc_info=True)
            raise
