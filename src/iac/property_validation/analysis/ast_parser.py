"""AST parser for Python handler files.

Philosophy:
- Pure AST walking with no external dependencies
- Standard library only (ast module)
- Extract metadata and property access patterns

Public API:
    HandlerASTParser: Parse handler files and extract metadata
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class HandlerASTParser:
    """Parse Python handler files using AST.

    Extracts:
        - Handler class name
        - HANDLED_TYPES class variable
        - TERRAFORM_TYPES class variable
        - All property access patterns
    """

    def __init__(self, file_path: Path):
        """Initialize parser with file path.

        Args:
            file_path: Path to handler Python file
        """
        self.file_path = file_path
        self.tree: Optional[ast.Module] = None
        self.source_lines: List[str] = []

    def parse(self) -> ast.Module:
        """Parse the file and return AST.

        Returns:
            Parsed AST module

        Raises:
            SyntaxError: If file has syntax errors
            FileNotFoundError: If file doesn't exist
        """
        source_code = self.file_path.read_text()
        self.source_lines = source_code.splitlines()
        self.tree = ast.parse(source_code, filename=str(self.file_path))
        return self.tree

    def extract_handler_class(self) -> Optional[str]:
        """Extract handler class name.

        Returns:
            Handler class name or None if not found
        """
        if not self.tree:
            return None

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                # Look for classes that inherit from ResourceHandler
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "ResourceHandler":
                        return node.name
        return None

    def extract_class_variable(self, class_name: str, var_name: str) -> Set[str]:
        """Extract set literal from class variable.

        Args:
            class_name: Name of the class
            var_name: Name of the variable (e.g., "HANDLED_TYPES")

        Returns:
            Set of string values from the variable
        """
        if not self.tree:
            return set()

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Look for class variable assignments
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        # Annotated assignment: HANDLED_TYPES: ClassVar[Set[str]] = {...}
                        if (
                            isinstance(item.target, ast.Name)
                            and item.target.id == var_name
                        ):
                            return self._extract_set_values(item.value)
                    elif isinstance(item, ast.Assign):
                        # Simple assignment: HANDLED_TYPES = {...}
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == var_name:
                                return self._extract_set_values(item.value)
        return set()

    def _extract_set_values(self, node: Optional[ast.expr]) -> Set[str]:
        """Extract string values from set literal.

        Args:
            node: AST node representing a set

        Returns:
            Set of string values
        """
        if not node:
            return set()

        values = set()
        if isinstance(node, ast.Set):
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    values.add(elt.value)
        return values

    def find_subscript_accesses(
        self, var_names: Optional[List[str]] = None
    ) -> List[Tuple[int, str, str, str]]:
        """Find all subscript accesses (dict["key"]).

        Args:
            var_names: List of variable names to track (e.g., ["config", "properties"])
                      If None, tracks all subscript accesses

        Returns:
            List of (line_number, var_name, key, code_snippet) tuples
        """
        if not self.tree:
            return []

        accesses = []
        for node in ast.walk(self.tree):
            # Pattern: config["key"] or properties.get("key")
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name):
                    var_name = node.value.id
                    if var_names is None or var_name in var_names:
                        key = self._extract_subscript_key(node.slice)
                        if key:
                            line_num = getattr(node, "lineno", 0)
                            snippet = self._get_code_snippet(line_num)
                            accesses.append((line_num, var_name, key, snippet))
        return accesses

    def find_method_calls(
        self, var_names: List[str], method_names: List[str]
    ) -> List[Tuple[int, str, str, str, str]]:
        """Find method calls on variables.

        Args:
            var_names: Variable names to track (e.g., ["config", "properties"])
            method_names: Method names to track (e.g., ["get", "update"])

        Returns:
            List of (line_number, var_name, method_name, first_arg, code_snippet) tuples
        """
        if not self.tree:
            return []

        calls = []
        for node in ast.walk(self.tree):
            # Pattern: config.update({...}) or properties.get("key")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        var_name = node.func.value.id
                        method_name = node.func.attr

                        if var_name in var_names and method_name in method_names:
                            # Extract first argument
                            first_arg = ""
                            if node.args:
                                first_arg = self._extract_call_arg(node.args[0])

                            line_num = getattr(node, "lineno", 0)
                            snippet = self._get_code_snippet(line_num)
                            calls.append(
                                (line_num, var_name, method_name, first_arg, snippet)
                            )
        return calls

    def find_dict_literals(
        self, context_var: str
    ) -> List[Tuple[int, Dict[str, str], str]]:
        """Find dict literals passed to update() or used in assignments.

        Args:
            context_var: Variable name to track (e.g., "config")

        Returns:
            List of (line_number, dict_content, code_snippet) tuples
        """
        if not self.tree:
            return []

        dicts = []
        for node in ast.walk(self.tree):
            # Pattern: config.update({"key": value})
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == context_var
                        and node.func.attr == "update"
                    ):
                        if node.args and isinstance(node.args[0], ast.Dict):
                            dict_content = self._extract_dict_keys(node.args[0])
                            line_num = getattr(node, "lineno", 0)
                            snippet = self._get_code_snippet(line_num)
                            dicts.append((line_num, dict_content, snippet))
        return dicts

    def _extract_subscript_key(self, slice_node: ast.expr) -> Optional[str]:
        """Extract string key from subscript slice.

        Args:
            slice_node: AST slice node

        Returns:
            String key or None
        """
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return slice_node.value
        return None

    def _extract_call_arg(self, arg_node: ast.expr) -> str:
        """Extract first argument from method call.

        Args:
            arg_node: AST argument node

        Returns:
            String representation of argument
        """
        if isinstance(arg_node, ast.Constant) and isinstance(arg_node.value, str):
            return arg_node.value
        elif isinstance(arg_node, ast.Dict):
            # Return placeholder for dict literals
            return "{...}"
        return ""

    def _extract_dict_keys(self, dict_node: ast.Dict) -> Dict[str, str]:
        """Extract key-value pairs from dict literal.

        Args:
            dict_node: AST Dict node

        Returns:
            Dict of string keys to placeholder values
        """
        result = {}
        for key, value in zip(dict_node.keys, dict_node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                # Store key with value type as placeholder
                result[key.value] = self._get_value_type(value)
        return result

    def _get_value_type(self, value_node: ast.expr) -> str:
        """Get type description of value node.

        Args:
            value_node: AST value node

        Returns:
            String describing value type
        """
        if isinstance(value_node, ast.Constant):
            return type(value_node.value).__name__
        elif isinstance(value_node, ast.Name):
            return f"var:{value_node.id}"
        elif isinstance(value_node, ast.Call):
            return "call"
        return "unknown"

    def _get_code_snippet(self, line_num: int) -> str:
        """Get code snippet for line number.

        Args:
            line_num: Line number (1-indexed)

        Returns:
            Code snippet (stripped)
        """
        if 1 <= line_num <= len(self.source_lines):
            return self.source_lines[line_num - 1].strip()
        return ""


__all__ = ["HandlerASTParser"]
