"""
Tests for Safe Cypher Query Builder

This test suite verifies that the SafeCypherBuilder prevents Cypher injection
and correctly constructs parameterized queries.

Test Coverage:
- Unit tests (60%): Core builder functionality with mocked dependencies
- Integration tests (30%): Builder used in typical query patterns
- E2E tests (10%): Injection prevention with real attack vectors
"""

import pytest

from src.utils.safe_cypher_builder import (
    CypherInjectionError,
    SafeCypherBuilder,
    build_scope_filter,
    build_set_clause,
    escape_identifier,
    validate_filter_keys,
)

# ============================================================================
# UNIT TESTS (60%)
# ============================================================================


class TestSafeCypherBuilderBasics:
    """Test basic SafeCypherBuilder functionality"""

    def test_initialization_with_defaults(self):
        """Test builder initializes with default settings"""
        builder = SafeCypherBuilder()
        assert builder.node_label == "Resource"
        assert "name" in builder.allowed_keys
        assert "type" in builder.allowed_keys
        assert len(builder.filters) == 0

    def test_initialization_with_custom_keys(self):
        """Test builder accepts custom allowed keys"""
        custom_keys = {"foo", "bar", "baz"}
        builder = SafeCypherBuilder(allowed_keys=custom_keys)
        assert builder.allowed_keys == custom_keys

    def test_initialization_with_custom_label(self):
        """Test builder accepts custom node label"""
        builder = SafeCypherBuilder(node_label="CustomNode")
        assert builder.node_label == "CustomNode"

    def test_add_filter_single(self):
        """Test adding single filter"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "test-vm")

        assert "name" in builder.filters
        assert builder.filters["name"] == "test-vm"
        assert len(builder.where_clauses) == 1
        assert len(builder.params) == 1

    def test_add_filter_multiple(self):
        """Test adding multiple filters"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "test-vm")
        builder.add_filter("type", "VirtualMachine")
        builder.add_filter("location", "eastus")

        assert len(builder.filters) == 3
        assert len(builder.where_clauses) == 3
        assert len(builder.params) == 3

    def test_add_filter_chaining(self):
        """Test filter chaining returns self"""
        builder = SafeCypherBuilder()
        result = builder.add_filter("name", "vm-1").add_filter("type", "VM")

        assert result is builder
        assert len(builder.filters) == 2

    def test_add_filter_with_disallowed_key(self):
        """Test that disallowed keys raise error"""
        builder = SafeCypherBuilder(allowed_keys={"name", "type"})

        with pytest.raises(CypherInjectionError) as exc_info:
            builder.add_filter("malicious_key", "value")

        assert "not in allowed keys" in str(exc_info.value).lower()
        assert "malicious_key" in str(exc_info.value)

    def test_parameter_uniqueness(self):
        """Test that parameters are uniquely named"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "vm-1")
        builder.add_filter("name", "vm-2")  # Same key, different value

        # Should have 2 different parameters
        assert len(builder.params) == 2
        param_names = list(builder.params.keys())
        assert param_names[0] != param_names[1]

    def test_reset_clears_state(self):
        """Test reset clears all state"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "vm-1")
        builder.add_filter("type", "VM")

        builder.reset()

        assert len(builder.filters) == 0
        assert len(builder.where_clauses) == 0
        assert len(builder.params) == 0

    def test_reset_returns_self(self):
        """Test reset returns self for chaining"""
        builder = SafeCypherBuilder()
        result = builder.reset()
        assert result is builder


class TestQueryBuilding:
    """Test query construction methods"""

    def test_build_match_query_simple(self):
        """Test building simple MATCH query"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "test-vm")

        query, params = builder.build_match_query()

        assert "MATCH (r:Resource)" in query
        assert "WHERE" in query
        assert "RETURN r" in query
        assert "r.name = $" in query
        assert len(params) == 1
        assert "test-vm" in params.values()

    def test_build_match_query_multiple_filters(self):
        """Test building query with multiple filters"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "vm-1")
        builder.add_filter("type", "VirtualMachine")
        builder.add_filter("location", "eastus")

        query, params = builder.build_match_query()

        assert query.count("AND") == 2  # 3 filters = 2 ANDs
        assert len(params) == 3
        assert "vm-1" in params.values()
        assert "VirtualMachine" in params.values()
        assert "eastus" in params.values()

    def test_build_match_query_custom_return(self):
        """Test custom RETURN clause"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "vm-1")

        query, params = builder.build_match_query(
            return_clause="properties(r) as props"
        )

        assert "RETURN properties(r) as props" in query

    def test_build_match_query_custom_label(self):
        """Test custom node label"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "layer-1")

        query, params = builder.build_match_query(node_label="Layer")

        assert "MATCH (r:Layer)" in query

    def test_build_match_query_no_filters(self):
        """Test building query with no filters"""
        builder = SafeCypherBuilder()

        query, params = builder.build_match_query()

        assert "WHERE true" in query  # Fallback WHERE clause
        assert len(params) == 0

    def test_build_where_clause(self):
        """Test building WHERE clause only"""
        builder = SafeCypherBuilder()
        builder.add_filter("name", "vm-1")
        builder.add_filter("type", "VM")

        where_clause, params = builder.build_where_clause()

        assert "r.name = $" in where_clause
        assert "r.type = $" in where_clause
        assert "AND" in where_clause
        assert len(params) == 2

    def test_add_custom_where_safe(self):
        """Test adding safe custom WHERE clause"""
        builder = SafeCypherBuilder()
        builder.add_custom_where("r.cost > $min_cost", {"min_cost": 100})

        query, params = builder.build_match_query()

        assert "r.cost > $min_cost" in query
        assert params["min_cost"] == 100

    def test_add_custom_where_with_interpolation_fails(self):
        """Test that string interpolation in custom WHERE is rejected"""
        builder = SafeCypherBuilder()

        # Test various interpolation patterns
        with pytest.raises(CypherInjectionError):
            builder.add_custom_where("r.name = {variable}", {})

        with pytest.raises(CypherInjectionError):
            builder.add_custom_where("r.name = ${variable}", {})

        with pytest.raises(CypherInjectionError):
            builder.add_custom_where("r.name = %s", {})


class TestIdentifierValidation:
    """Test identifier validation and escaping"""

    def test_valid_identifiers(self):
        """Test that valid identifiers are accepted"""
        builder = SafeCypherBuilder()

        # These should all work
        builder._validate_identifier("Resource")
        builder._validate_identifier("Virtual_Machine")
        builder._validate_identifier("_private")
        builder._validate_identifier("name123")
        builder._validate_identifier("my-property")

    def test_invalid_identifiers(self):
        """Test that invalid identifiers are rejected"""
        builder = SafeCypherBuilder()

        # These should all fail
        with pytest.raises(CypherInjectionError):
            builder._validate_identifier("123invalid")  # Starts with number

        with pytest.raises(CypherInjectionError):
            builder._validate_identifier("invalid.property")  # Contains dot

        with pytest.raises(CypherInjectionError):
            builder._validate_identifier("invalid;property")  # Contains semicolon

        with pytest.raises(CypherInjectionError):
            builder._validate_identifier("invalid property")  # Contains space

    def test_escape_identifier_safe(self):
        """Test safe identifier escaping"""
        escaped = escape_identifier("my-property")
        assert escaped == "`my-property`"

        escaped = escape_identifier("prop.name")
        assert escaped == "`prop.name`"

    def test_escape_identifier_with_backtick_fails(self):
        """Test that identifiers with backticks are rejected"""
        with pytest.raises(CypherInjectionError):
            escape_identifier("mal`icious")

    def test_escape_identifier_with_special_chars_fails(self):
        """Test that identifiers with special chars are rejected"""
        with pytest.raises(CypherInjectionError):
            escape_identifier("mal;icious")

        with pytest.raises(CypherInjectionError):
            escape_identifier("mal'icious")


class TestHelperFunctions:
    """Test standalone helper functions"""

    def test_build_scope_filter_subscription(self):
        """Test scope filter for subscription"""
        scope = "/subscriptions/abc-123/resourceGroups/rg1"
        filter_clause, param_name, param_value = build_scope_filter(scope)

        assert "c.subscription_id = $scope_id" in filter_clause
        assert param_name == "scope_id"
        assert param_value == "abc-123"

    def test_build_scope_filter_resource_path(self):
        """Test scope filter for resource path with subscription"""
        scope = (
            "/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Compute/vms/vm1"
        )
        filter_clause, param_name, param_value = build_scope_filter(scope)

        # When scope contains /subscriptions/, always extracts subscription ID
        assert "c.subscription_id = $scope_id" in filter_clause
        assert param_name == "scope_id"
        assert param_value == "abc"

    def test_build_scope_filter_non_subscription_path(self):
        """Test scope filter for resource path without subscription"""
        scope = "/some/resource/path"
        filter_clause, param_name, param_value = build_scope_filter(scope)

        assert "c.resource_id STARTS WITH $scope_id" in filter_clause
        assert param_name == "scope_id"
        assert param_value == scope

    def test_build_set_clause_safe(self):
        """Test safe SET clause building"""
        updates = {"name": "new-name", "description": "Updated"}
        allowed = {"name", "description", "tags"}

        set_clause, params = build_set_clause(updates, allowed)

        assert "l.name = $name" in set_clause
        assert "l.description = $description" in set_clause
        assert params["name"] == "new-name"
        assert params["description"] == "Updated"

    def test_build_set_clause_with_disallowed_key(self):
        """Test SET clause rejects disallowed keys"""
        updates = {"malicious": "value"}
        allowed = {"name", "description"}

        with pytest.raises(CypherInjectionError) as exc_info:
            build_set_clause(updates, allowed)

        assert "not in allowed keys" in str(exc_info.value).lower()

    def test_validate_filter_keys_valid(self):
        """Test validating valid filter keys"""
        filters = {"name": "vm-1", "type": "VM"}
        allowed = {"name", "type", "location"}

        # Should not raise
        validate_filter_keys(filters, allowed)

    def test_validate_filter_keys_invalid(self):
        """Test validating invalid filter keys"""
        filters = {"name": "vm-1", "malicious": "value"}
        allowed = {"name", "type"}

        with pytest.raises(CypherInjectionError) as exc_info:
            validate_filter_keys(filters, allowed)

        assert "malicious" in str(exc_info.value).lower()


# ============================================================================
# INTEGRATION TESTS (30%)
# ============================================================================


class TestTypicalQueryPatterns:
    """Test typical query construction patterns"""

    def test_resource_query_pattern(self):
        """Test typical resource query pattern"""
        builder = SafeCypherBuilder()

        # Typical resource filtering
        resource_type = "VirtualMachine"
        filters = {"location": "eastus", "resource_group": "prod-rg"}

        builder.add_filter("type", resource_type)
        for key, value in filters.items():
            builder.add_filter(key, value)

        query, params = builder.build_match_query(
            return_clause="properties(r) as props"
        )

        assert "MATCH (r:Resource)" in query
        assert len(params) == 3
        assert params.get("filter_type_0") or any(
            "VirtualMachine" == v for v in params.values()
        )

    def test_layer_update_pattern(self):
        """Test typical layer update pattern"""
        updates = {
            "name": "updated-layer",
            "description": "Updated description",
            "tags": ["tag1", "tag2"],
        }

        allowed = SafeCypherBuilder.LAYER_FILTER_KEYS | {"tags"}
        set_clause, params = build_set_clause(updates, allowed)

        # Verify SET clause is safe
        assert "l.name = $name" in set_clause
        assert "l.description = $description" in set_clause
        assert params["name"] == "updated-layer"

    def test_cost_aggregation_pattern(self):
        """Test typical cost aggregation pattern"""
        scope = "/subscriptions/abc-123"
        filter_clause, param_name, param_value = build_scope_filter(scope)

        # Build full query
        query = f"""
        MATCH (c:Cost)
        WHERE {filter_clause}
            AND c.date >= date($start_date)
            AND c.date <= date($end_date)
        WITH sum(c.actual_cost) AS total
        RETURN total
        """

        params = {
            param_name: param_value,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        assert "c.subscription_id = $scope_id" in query
        assert "$start_date" in query
        assert "$end_date" in query
        assert len(params) == 3

    def test_pagination_pattern(self):
        """Test query with pagination"""
        builder = SafeCypherBuilder()
        builder.add_filter("type", "VirtualMachine")

        query, params = builder.build_match_query()

        # Add pagination manually (as shown in layer_aware_query_service.py)
        query += " SKIP 10 LIMIT 20"

        assert "SKIP 10" in query
        assert "LIMIT 20" in query


# ============================================================================
# E2E / INJECTION PREVENTION TESTS (10%)
# ============================================================================


class TestInjectionPrevention:
    """Test actual injection attack prevention"""

    def test_sql_injection_attempt_in_filter_value(self):
        """Test that SQL injection in value is harmless"""
        builder = SafeCypherBuilder()

        # Attacker tries SQL injection
        malicious_value = "'; DROP DATABASE; --"
        builder.add_filter("name", malicious_value)

        query, params = builder.build_match_query()

        # Value is parameterized, so it's safe
        assert malicious_value in params.values()
        assert "DROP" not in query
        assert "$" in query  # Parameter marker present

    def test_cypher_injection_attempt_in_filter_value(self):
        """Test that Cypher injection in value is harmless"""
        builder = SafeCypherBuilder()

        # Attacker tries Cypher injection
        malicious_value = "' OR 1=1 OR r.name = '"
        builder.add_filter("name", malicious_value)

        query, params = builder.build_match_query()

        # Value is parameterized, so injection is impossible
        assert malicious_value in params.values()
        assert query.count("OR") == 0  # No OR in query structure

    def test_filter_key_injection_attempt(self):
        """Test that malicious filter keys are rejected"""
        builder = SafeCypherBuilder(allowed_keys={"name", "type"})

        # Attacker tries to inject via filter key
        with pytest.raises(CypherInjectionError):
            builder.add_filter("name'; DROP DATABASE; --", "value")

    def test_identifier_injection_in_label(self):
        """Test that injection in node label is prevented"""
        with pytest.raises(CypherInjectionError):
            SafeCypherBuilder(node_label="Resource'; DROP DATABASE; --")

    def test_union_injection_attempt(self):
        """Test UNION-based injection is prevented"""
        builder = SafeCypherBuilder()

        malicious_value = "' UNION SELECT * FROM secrets --"
        builder.add_filter("name", malicious_value)

        query, params = builder.build_match_query()

        # UNION should not appear in query structure
        assert "UNION" not in query
        assert malicious_value in params.values()

    def test_comment_injection_attempt(self):
        """Test comment-based injection is prevented"""
        builder = SafeCypherBuilder()

        malicious_value = "value' --"
        builder.add_filter("name", malicious_value)

        query, params = builder.build_match_query()

        # Comment should be in parameter, not query
        assert "--" not in query
        assert malicious_value in params.values()

    def test_nested_query_injection_attempt(self):
        """Test nested query injection is prevented"""
        builder = SafeCypherBuilder()

        malicious_value = "') MATCH (n) DETACH DELETE n RETURN ('"
        builder.add_filter("name", malicious_value)

        query, params = builder.build_match_query()

        # DELETE should not appear in query structure
        assert "DELETE" not in query
        assert "DETACH" not in query
        assert malicious_value in params.values()


# ============================================================================
# EDGE CASES AND ERROR CONDITIONS
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_filters(self):
        """Test handling of empty filters"""
        builder = SafeCypherBuilder()

        query, params = builder.build_match_query()

        assert "WHERE true" in query
        assert len(params) == 0

    def test_special_characters_in_values(self):
        """Test special characters in filter values are safe"""
        builder = SafeCypherBuilder()

        # These should all be safe when parameterized
        builder.add_filter("name", "vm-with-dash")
        builder.add_filter("type", "Type.With.Dots")
        builder.add_filter("location", "region/subregion")

        query, params = builder.build_match_query()

        assert len(params) == 3
        assert "vm-with-dash" in params.values()

    def test_unicode_in_values(self):
        """Test Unicode characters in values"""
        builder = SafeCypherBuilder()

        builder.add_filter("name", "机器-虚拟")

        query, params = builder.build_match_query()

        assert "机器-虚拟" in params.values()

    def test_none_values(self):
        """Test None values are handled"""
        builder = SafeCypherBuilder()

        builder.add_filter("name", None)

        query, params = builder.build_match_query()

        assert None in params.values()

    def test_builder_reuse_after_reset(self):
        """Test builder can be reused after reset"""
        builder = SafeCypherBuilder()

        # First use
        builder.add_filter("name", "vm-1")
        query1, params1 = builder.build_match_query()

        # Reset and reuse
        builder.reset()
        builder.add_filter("type", "VM")
        query2, params2 = builder.build_match_query()

        assert "vm-1" not in params2.values()
        assert "VM" in params2.values()
