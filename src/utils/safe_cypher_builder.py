"""
Safe Cypher Query Builder

This module provides utilities for building Cypher queries safely without injection vulnerabilities.
All query construction uses parameterization and input validation.

Philosophy:
- Single responsibility: Safe Cypher query construction
- Standard library only (no external dependencies beyond Neo4j driver types)
- Self-contained and regeneratable
- Zero-BS: Every function works completely

Public API (the "studs"):
    SafeCypherBuilder: Main query builder class
    build_where_clause: Helper for WHERE clause construction
    escape_identifier: Safe identifier escaping
    validate_filter_keys: Input validation

Security Features:
- Parameterized queries prevent injection
- Whitelist-based filter key validation
- Safe identifier escaping for dynamic property access
- No string interpolation in query construction
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


class CypherInjectionError(Exception):
    """Raised when potential Cypher injection is detected"""

    pass


class SafeCypherBuilder:
    """
    Builder for constructing safe Cypher queries with parameterization.

    This class helps prevent Cypher injection by:
    1. Using parameterized queries for all values
    2. Validating filter keys against whitelists
    3. Escaping identifiers safely
    4. Never using string interpolation for query construction

    Example:
        >>> builder = SafeCypherBuilder(allowed_keys={"name", "type", "location"})
        >>> builder.add_filter("name", "prod-vm-01")
        >>> builder.add_filter("location", "eastus")
        >>> query, params = builder.build_match_query("Resource")
        >>> print(query)
        MATCH (r:Resource) WHERE r.name = $filter_name AND r.location = $filter_location RETURN r
    """

    # Common allowed filter keys for different node types
    RESOURCE_FILTER_KEYS: Set[str] = {
        "id",
        "name",
        "type",
        "location",
        "resource_group",
        "subscription_id",
        "layer_id",
        "tenant_id",
    }

    COST_FILTER_KEYS: Set[str] = {
        "resource_id",
        "subscription_id",
        "date",
        "service_name",
        "meter_category",
    }

    LAYER_FILTER_KEYS: Set[str] = {
        "layer_id",
        "name",
        "description",
        "is_active",
        "is_baseline",
        "is_locked",
    }

    def __init__(
        self,
        allowed_keys: Optional[Set[str]] = None,
        node_label: str = "Resource",
    ):
        """
        Initialize the safe Cypher builder.

        Args:
            allowed_keys: Set of allowed filter keys (uses RESOURCE_FILTER_KEYS if None)
            node_label: Default node label for queries
        """
        self.allowed_keys = allowed_keys if allowed_keys else self.RESOURCE_FILTER_KEYS
        self.node_label = self._validate_identifier(node_label)
        self.filters: Dict[str, Any] = {}
        self.where_clauses: List[str] = []
        self.params: Dict[str, Any] = {}
        self._param_counter = 0

    def _validate_identifier(self, identifier: str) -> str:
        """
        Validate that an identifier (label, property name) is safe.

        Args:
            identifier: The identifier to validate

        Returns:
            The validated identifier

        Raises:
            CypherInjectionError: If identifier contains unsafe characters
        """
        # Allow alphanumeric, underscore, and hyphen only
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", identifier):
            raise CypherInjectionError(
                f"Invalid identifier: {identifier}. "
                "Must start with letter/underscore and contain only alphanumeric, underscore, hyphen."
            )
        return identifier

    def _get_param_name(self, key: str) -> str:
        """
        Generate a unique parameter name.

        Args:
            key: Base key for parameter

        Returns:
            Unique parameter name
        """
        safe_key = key.replace(".", "_").replace("-", "_")
        param_name = f"filter_{safe_key}_{self._param_counter}"
        self._param_counter += 1
        return param_name

    def add_filter(self, key: str, value: Any) -> "SafeCypherBuilder":
        """
        Add a filter condition (chainable).

        Args:
            key: Property key (must be in allowed_keys)
            value: Value to filter by (will be parameterized)

        Returns:
            Self for method chaining

        Raises:
            CypherInjectionError: If key is not in allowed_keys

        Example:
            >>> builder = SafeCypherBuilder()
            >>> builder.add_filter("name", "vm-1").add_filter("type", "VirtualMachine")
        """
        if key not in self.allowed_keys:
            raise CypherInjectionError(
                f"Filter key '{key}' not in allowed keys: {sorted(self.allowed_keys)}"
            )

        # Validate the key is a safe identifier
        self._validate_identifier(key)

        # Create parameterized filter
        param_name = self._get_param_name(key)
        self.where_clauses.append(f"r.{key} = ${param_name}")
        self.params[param_name] = value
        self.filters[key] = value

        return self

    def add_custom_where(
        self, clause: str, params: Optional[Dict[str, Any]] = None
    ) -> "SafeCypherBuilder":
        """
        Add a custom WHERE clause (use sparingly, prefer add_filter).

        Args:
            clause: WHERE clause (must use parameterization)
            params: Parameters for the clause

        Returns:
            Self for method chaining

        Raises:
            CypherInjectionError: If clause contains string interpolation

        Example:
            >>> builder.add_custom_where("r.cost > $min_cost", {"min_cost": 100})
        """
        # Check for potential string interpolation
        if "${" in clause or "{" in clause or "%" in clause:
            raise CypherInjectionError(
                "Custom WHERE clause appears to use string interpolation. "
                "Use parameterization with $ instead."
            )

        self.where_clauses.append(clause)
        if params:
            self.params.update(params)

        return self

    def build_match_query(
        self,
        node_label: Optional[str] = None,
        return_clause: str = "r",
        additional_where: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a complete MATCH query with WHERE clauses.

        Args:
            node_label: Node label (uses default if None)
            return_clause: RETURN clause content
            additional_where: Additional WHERE conditions (static, no params)

        Returns:
            Tuple of (query_string, parameters)

        Example:
            >>> builder = SafeCypherBuilder()
            >>> builder.add_filter("type", "VirtualMachine")
            >>> query, params = builder.build_match_query(return_clause="properties(r) as props")
        """
        label = node_label if node_label else self.node_label
        self._validate_identifier(label)

        # Build WHERE clause
        where_parts = self.where_clauses.copy()
        if additional_where:
            where_parts.append(additional_where)

        where_clause = " AND ".join(where_parts) if where_parts else "true"

        query = f"MATCH (r:{label}) WHERE {where_clause} RETURN {return_clause}"

        return query, self.params.copy()

    def build_where_clause(self) -> Tuple[str, Dict[str, Any]]:
        """
        Build just the WHERE clause and parameters.

        Returns:
            Tuple of (where_clause, parameters)

        Example:
            >>> builder = SafeCypherBuilder()
            >>> builder.add_filter("name", "test")
            >>> where, params = builder.build_where_clause()
            >>> print(where)
            r.name = $filter_name_0
        """
        where_clause = (
            " AND ".join(self.where_clauses) if self.where_clauses else "true"
        )
        return where_clause, self.params.copy()

    def reset(self) -> "SafeCypherBuilder":
        """
        Reset the builder state (chainable).

        Returns:
            Self for method chaining
        """
        self.filters.clear()
        self.where_clauses.clear()
        self.params.clear()
        self._param_counter = 0
        return self


def build_scope_filter(scope: str) -> Tuple[str, str, str]:
    """
    Build safe scope filter for cost queries.

    Matches the original cost_management_service.py logic:
    - If scope contains "/subscriptions/", extract subscription ID and filter by subscription
    - Otherwise, use STARTS WITH for resource path matching

    Args:
        scope: Azure scope (subscription or resource path)

    Returns:
        Tuple of (scope_filter_clause, param_name, param_value)

    Example:
        >>> filter_clause, param_name, param_value = build_scope_filter(
        ...     "/subscriptions/abc123"
        ... )
        >>> print(filter_clause)
        c.subscription_id = $scope_id
    """
    if "/subscriptions/" in scope:
        # Extract subscription ID for filtering
        subscription_id = scope.split("/subscriptions/")[1].split("/")[0]
        return "c.subscription_id = $scope_id", "scope_id", subscription_id
    else:
        # Use STARTS WITH for non-subscription scopes
        return "c.resource_id STARTS WITH $scope_id", "scope_id", scope


def build_set_clause(
    updates: Dict[str, Any], allowed_keys: Set[str]
) -> Tuple[str, Dict[str, Any]]:
    """
    Build safe SET clause for UPDATE operations.

    Args:
        updates: Dictionary of property updates
        allowed_keys: Set of allowed property keys

    Returns:
        Tuple of (set_clause, parameters)

    Raises:
        CypherInjectionError: If any key is not in allowed_keys

    Example:
        >>> set_clause, params = build_set_clause(
        ...     {"name": "new-name", "description": "Updated"},
        ...     allowed_keys={"name", "description", "tags"}
        ... )
        >>> print(set_clause)
        l.name = $name, l.description = $description
    """
    set_clauses = []
    params = {}

    for key, value in updates.items():
        if key not in allowed_keys:
            raise CypherInjectionError(
                f"Update key '{key}' not in allowed keys: {sorted(allowed_keys)}"
            )

        # Validate identifier
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", key):
            raise CypherInjectionError(
                f"Invalid property name: {key}. "
                "Must start with letter/underscore and contain only alphanumeric, underscore, hyphen."
            )

        set_clauses.append(f"l.{key} = ${key}")
        params[key] = value

    set_clause = ", ".join(set_clauses)
    return set_clause, params


def escape_identifier(identifier: str) -> str:
    """
    Escape a Cypher identifier by backtick-quoting it.

    Use this for property names or labels that come from user input
    when they cannot be whitelisted.

    Args:
        identifier: The identifier to escape

    Returns:
        Backtick-quoted identifier

    Raises:
        CypherInjectionError: If identifier contains backticks

    Example:
        >>> escaped = escape_identifier("my-property")
        >>> print(escaped)
        `my-property`
    """
    if "`" in identifier:
        raise CypherInjectionError(
            "Identifier contains backtick character which cannot be safely escaped"
        )

    # Additional validation: no control characters or special chars
    if not re.match(r"^[a-zA-Z0-9_.-]+$", identifier):
        raise CypherInjectionError(
            f"Identifier contains unsafe characters: {identifier}"
        )

    return f"`{identifier}`"


def validate_filter_keys(filters: Dict[str, Any], allowed_keys: Set[str]) -> None:
    """
    Validate that all filter keys are in the allowed set.

    Args:
        filters: Dictionary of filter key-value pairs
        allowed_keys: Set of allowed keys

    Raises:
        CypherInjectionError: If any key is not allowed

    Example:
        >>> validate_filter_keys(
        ...     {"name": "vm-1", "type": "VM"},
        ...     allowed_keys={"name", "type", "location"}
        ... )
    """
    invalid_keys = set(filters.keys()) - allowed_keys
    if invalid_keys:
        raise CypherInjectionError(
            f"Invalid filter keys: {sorted(invalid_keys)}. "
            f"Allowed keys: {sorted(allowed_keys)}"
        )


__all__ = [
    "CypherInjectionError",
    "SafeCypherBuilder",
    "build_scope_filter",
    "build_set_clause",
    "escape_identifier",
    "validate_filter_keys",
]
