"""Property extractor for handler analysis.

Philosophy:
- Extract property mappings from AST parse results
- Detect read/write patterns for Terraform and Azure properties
- Standard library only

Public API:
    PropertyExtractor: Extract and classify property usage
"""

from typing import Dict, List, Set, Tuple

from ..models import PropertyUsage


class PropertyExtractor:
    """Extract and classify property usage patterns from AST results.

    Patterns detected:
        1. config["key"] = value          -> Terraform write
        2. config.update({"key": value})  -> Terraform write
        3. properties.get("azureKey")     -> Azure read
        4. resource.get("key")            -> Azure read
    """

    def __init__(self):
        """Initialize property extractor."""
        self.properties: List[PropertyUsage] = []
        self.terraform_writes: Set[str] = set()
        self.azure_reads: Set[str] = set()
        self.bidirectional_mappings: Dict[str, str] = {}

    def process_subscript_accesses(
        self, accesses: List[Tuple[int, str, str, str]]
    ) -> None:
        """Process subscript accesses (dict["key"]).

        Args:
            accesses: List of (line_number, var_name, key, code_snippet)
        """
        for line_num, var_name, key, snippet in accesses:
            if var_name == "config":
                # Pattern: config["key"] = value (Terraform write)
                self._add_terraform_write(key, line_num, snippet)
            elif var_name in ["properties", "resource"]:
                # Pattern: properties["key"] (Azure read)
                self._add_azure_read(key, line_num, snippet)

    def process_method_calls(
        self, calls: List[Tuple[int, str, str, str, str]]
    ) -> None:
        """Process method calls (var.method()).

        Args:
            calls: List of (line_number, var_name, method_name, first_arg, code_snippet)
        """
        for line_num, var_name, method_name, first_arg, snippet in calls:
            if var_name == "config" and method_name == "update":
                # Pattern: config.update({...})
                # These will be handled separately in process_dict_literals
                continue
            elif var_name in ["properties", "resource"] and method_name == "get":
                # Pattern: properties.get("azureKey")
                if first_arg:
                    self._add_azure_read(first_arg, line_num, snippet)

    def process_dict_literals(
        self, dicts: List[Tuple[int, Dict[str, str], str]]
    ) -> None:
        """Process dict literals in config.update().

        Args:
            dicts: List of (line_number, dict_content, code_snippet)
        """
        for line_num, dict_content, snippet in dicts:
            # All keys in config.update({...}) are Terraform writes
            for key in dict_content.keys():
                self._add_terraform_write(key, line_num, snippet)

    def process_assignment_patterns(
        self, accesses: List[Tuple[int, str, str, str]]
    ) -> None:
        """Process assignment patterns to detect bidirectional mappings.

        Pattern: config["terraformKey"] = properties.get("azureKey")

        Args:
            accesses: List of (line_number, var_name, key, code_snippet)
        """
        # Look for lines that read from properties/resource and write to config
        for line_num, var_name, key, snippet in accesses:
            if var_name == "config" and "properties.get(" in snippet:
                # Extract Azure key from snippet
                azure_key = self._extract_azure_key_from_snippet(snippet)
                if azure_key:
                    self._add_bidirectional_mapping(key, azure_key, line_num, snippet)

    def _add_terraform_write(self, key: str, line_num: int, snippet: str) -> None:
        """Add Terraform config write.

        Args:
            key: Terraform config key
            line_num: Line number
            snippet: Code snippet
        """
        self.terraform_writes.add(key)
        self.properties.append(
            PropertyUsage(
                property_name=key,
                usage_type="write",
                terraform_key=key,
                azure_key="",
                line_number=line_num,
                code_snippet=snippet,
            )
        )

    def _add_azure_read(self, key: str, line_num: int, snippet: str) -> None:
        """Add Azure property read.

        Args:
            key: Azure property key
            line_num: Line number
            snippet: Code snippet
        """
        self.azure_reads.add(key)
        self.properties.append(
            PropertyUsage(
                property_name=key,
                usage_type="read",
                terraform_key="",
                azure_key=key,
                line_number=line_num,
                code_snippet=snippet,
            )
        )

    def _add_bidirectional_mapping(
        self, terraform_key: str, azure_key: str, line_num: int, snippet: str
    ) -> None:
        """Add bidirectional property mapping.

        Args:
            terraform_key: Terraform config key
            azure_key: Azure property key
            line_num: Line number
            snippet: Code snippet
        """
        self.bidirectional_mappings[terraform_key] = azure_key
        self.terraform_writes.add(terraform_key)
        self.azure_reads.add(azure_key)

        self.properties.append(
            PropertyUsage(
                property_name=f"{terraform_key} <- {azure_key}",
                usage_type="both",
                terraform_key=terraform_key,
                azure_key=azure_key,
                line_number=line_num,
                code_snippet=snippet,
            )
        )

    def _extract_azure_key_from_snippet(self, snippet: str) -> str:
        """Extract Azure property key from code snippet.

        Pattern: properties.get("azureKey")

        Args:
            snippet: Code snippet

        Returns:
            Azure key or empty string
        """
        import re

        # Match properties.get("key") or properties.get('key')
        pattern = r'properties\.get\(["\']([^"\']+)["\']\)'
        match = re.search(pattern, snippet)
        if match:
            return match.group(1)

        # Also check resource.get()
        pattern = r'resource\.get\(["\']([^"\']+)["\']\)'
        match = re.search(pattern, snippet)
        if match:
            return match.group(1)

        return ""

    def get_results(
        self,
    ) -> Tuple[List[PropertyUsage], Set[str], Set[str], Dict[str, str]]:
        """Get extraction results.

        Returns:
            Tuple of (properties, terraform_writes, azure_reads, bidirectional_mappings)
        """
        return (
            self.properties,
            self.terraform_writes,
            self.azure_reads,
            self.bidirectional_mappings,
        )


__all__ = ["PropertyExtractor"]
