"""Handler analyzer for property extraction.

Philosophy:
- Orchestrate AST parsing and property extraction
- Standard library only
- Self-contained and regeneratable

Public API:
    HandlerAnalyzer: Main analyzer class
    analyze_handler: Convenience function
"""

from pathlib import Path
from typing import Optional

from ..models import HandlerPropertyUsage
from .ast_parser import HandlerASTParser
from .property_extractor import PropertyExtractor


class HandlerAnalyzer:
    """Analyze handler files to extract property usage.

    This is the main entry point for analyzing handler files.
    It orchestrates AST parsing and property extraction.

    Usage:
        analyzer = HandlerAnalyzer(Path("handler.py"))
        result = analyzer.analyze()
        print(f"Found {len(result.properties)} property usages")
    """

    def __init__(self, handler_file: Path):
        """Initialize analyzer with handler file.

        Args:
            handler_file: Path to handler Python file
        """
        self.handler_file = handler_file
        self.parser = HandlerASTParser(handler_file)
        self.extractor = PropertyExtractor()

    def analyze(self) -> HandlerPropertyUsage:
        """Analyze handler file and extract property usage.

        Returns:
            HandlerPropertyUsage with complete analysis results

        Raises:
            SyntaxError: If handler file has syntax errors
            FileNotFoundError: If handler file doesn't exist
        """
        # Parse the file
        self.parser.parse()

        # Extract metadata
        handler_class = self.parser.extract_handler_class()
        if not handler_class:
            return HandlerPropertyUsage(
                handler_file=str(self.handler_file),
                handler_class="",
            )

        handled_types = self.parser.extract_class_variable(
            handler_class, "HANDLED_TYPES"
        )
        terraform_types = self.parser.extract_class_variable(
            handler_class, "TERRAFORM_TYPES"
        )

        # Extract property patterns
        self._extract_property_patterns()

        # Get results from extractor
        (
            properties,
            terraform_writes,
            azure_reads,
            bidirectional_mappings,
        ) = self.extractor.get_results()

        return HandlerPropertyUsage(
            handler_file=str(self.handler_file),
            handler_class=handler_class,
            handled_types=handled_types,
            terraform_types=terraform_types,
            properties=properties,
            terraform_writes=terraform_writes,
            azure_reads=azure_reads,
            bidirectional_mappings=bidirectional_mappings,
        )

    def _extract_property_patterns(self) -> None:
        """Extract all property usage patterns from AST."""
        # Pattern 1: Subscript accesses (config["key"], properties["key"])
        subscript_accesses = self.parser.find_subscript_accesses(
            var_names=["config", "properties", "resource"]
        )
        self.extractor.process_subscript_accesses(subscript_accesses)

        # Pattern 2: Method calls (properties.get(), config.update())
        method_calls = self.parser.find_method_calls(
            var_names=["config", "properties", "resource"],
            method_names=["get", "update"],
        )
        self.extractor.process_method_calls(method_calls)

        # Pattern 3: Dict literals in config.update({...})
        dict_literals = self.parser.find_dict_literals(context_var="config")
        self.extractor.process_dict_literals(dict_literals)

        # Pattern 4: Assignment patterns (bidirectional mappings)
        self.extractor.process_assignment_patterns(subscript_accesses)


def analyze_handler(handler_file: Path) -> Optional[HandlerPropertyUsage]:
    """Convenience function to analyze a handler file.

    Args:
        handler_file: Path to handler Python file

    Returns:
        HandlerPropertyUsage or None if analysis fails

    Example:
        >>> from pathlib import Path
        >>> result = analyze_handler(Path("storage_account.py"))
        >>> if result:
        ...     print(f"Handler: {result.handler_class}")
        ...     print(f"Properties: {len(result.properties)}")
    """
    try:
        analyzer = HandlerAnalyzer(handler_file)
        return analyzer.analyze()
    except (SyntaxError, FileNotFoundError) as e:
        print(f"Error analyzing {handler_file}: {e}")
        return None


__all__ = ["HandlerAnalyzer", "analyze_handler"]
