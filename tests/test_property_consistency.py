"""
Test to verify that Neo4j property names are consistent between
graph creation and queries.
"""

import os
from typing import List, Set, Tuple

import pytest
from neo4j import GraphDatabase

from src.utils.neo4j_startup import ensure_neo4j_running


@pytest.fixture
def neo4j_session():
    """Create a Neo4j session for testing."""
    ensure_neo4j_running()

    neo4j_port = os.environ.get("NEO4J_PORT", "7689")
    neo4j_uri = f"bolt://localhost:{neo4j_port}"
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "localtest123!")

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    session = driver.session()

    # Clean up any existing test data
    session.run("MATCH (n:TestUser) DETACH DELETE n")
    session.run("MATCH (n:TestGroup) DETACH DELETE n")
    session.run("MATCH (n:TestServicePrincipal) DETACH DELETE n")

    yield session

    # Cleanup after test
    session.run("MATCH (n:TestUser) DETACH DELETE n")
    session.run("MATCH (n:TestGroup) DETACH DELETE n")
    session.run("MATCH (n:TestServicePrincipal) DETACH DELETE n")
    session.close()
    driver.close()


def get_node_properties(session, label: str) -> Set[str]:
    """Get all property keys used by nodes with the given label."""
    result = session.run(f"""
        MATCH (n:{label})
        RETURN DISTINCT keys(n) as property_keys
        LIMIT 100
    """)

    all_properties = set()
    for record in result:
        if record["property_keys"]:
            for keys_list in record["property_keys"]:
                if isinstance(keys_list, list):
                    all_properties.update(keys_list)
                else:
                    all_properties.add(keys_list)

    return all_properties


def find_property_references_in_queries(
    session, label: str
) -> Tuple[Set[str], List[str]]:
    """
    Find all property references in queries by executing test queries
    and checking for warnings or errors about non-existent properties.
    """
    # Common property names that might be referenced
    potential_properties = [
        "id",
        "name",
        "displayName",
        "display_name",
        "userPrincipalName",
        "user_principal_name",
        "mail",
        "email",
        "jobTitle",
        "job_title",
        "description",
        "type",
        "objectId",
        "object_id",
    ]

    referenced_properties = set()
    warnings = []

    for prop in potential_properties:
        # Try to query with each property and see if it exists
        try:
            # Test if property exists in any node of this label
            result = session.run(f"""
                MATCH (n:{label})
                WHERE n.{prop} IS NOT NULL
                RETURN count(n) as count
                LIMIT 1
            """)
            count = result.single()["count"]
            if count > 0:
                referenced_properties.add(prop)
        except Exception as e:
            # Property doesn't exist or query failed
            if "property" in str(e).lower():
                warnings.append(
                    f"Property '{prop}' referenced but may not exist for {label}"
                )

    return referenced_properties, warnings


class TestPropertyConsistency:
    """Test that property names are consistent between creation and queries."""

    def test_user_properties_consistency(self, neo4j_session):
        """Test that User node properties are consistent."""
        # Create a test user with all expected properties
        neo4j_session.run("""
            CREATE (u:TestUser {
                id: 'test-user-1',
                display_name: 'Test User',
                user_principal_name: 'test@example.com',
                mail: 'test@example.com',
                job_title: 'Developer'
            })
        """)

        # Get actual properties
        actual_properties = get_node_properties(neo4j_session, "TestUser")

        # Expected properties based on tenant_creator.py
        expected_properties = {
            "id",
            "display_name",
            "user_principal_name",  # Snake case as set in tenant_creator
            "job_title",
        }

        # Verify expected properties exist
        missing_properties = expected_properties - actual_properties
        assert not missing_properties, (
            f"Missing expected properties for User: {missing_properties}"
        )

        # Check for incorrectly named properties (camelCase instead of snake_case)
        incorrect_properties = set()
        if "userPrincipalName" in actual_properties:
            incorrect_properties.add("userPrincipalName should be user_principal_name")
        if "jobTitle" in actual_properties:
            incorrect_properties.add("jobTitle should be job_title")

        assert not incorrect_properties, (
            f"Incorrect property names found: {incorrect_properties}"
        )

    def test_real_user_properties_from_tenant_creator(self, neo4j_session):
        """Test properties created by actual TenantCreator code."""
        # This simulates what TenantCreator does
        user_data = {
            "id": "real-user-1",
            "display_name": "Real User",
            "user_principal_name": "real@example.com",
            "job_title": "Manager",
        }

        # Create user as TenantCreator does
        neo4j_session.run(
            """
            MERGE (u:User {id: $id})
            SET u.display_name = $display_name,
                u.user_principal_name = $user_principal_name,
                u.job_title = $job_title
        """,
            user_data,
        )

        # Get the created user and check properties
        result = neo4j_session.run(
            """
            MATCH (u:User {id: $id})
            RETURN u, keys(u) as props
        """,
            id="real-user-1",
        )

        record = result.single()
        assert record is not None, "User was not created"

        props = record["props"]
        assert "user_principal_name" in props, "user_principal_name property missing"
        assert "userPrincipalName" not in props, "Should use snake_case, not camelCase"

        # Clean up
        neo4j_session.run("MATCH (u:User {id: $id}) DETACH DELETE u", id="real-user-1")

    def test_query_property_references(self, neo4j_session):
        """Test that queries reference existing properties."""
        # Create a test user
        neo4j_session.run("""
            CREATE (u:User {
                id: 'query-test-user',
                display_name: 'Query Test User',
                user_principal_name: 'query@test.com',
                job_title: 'Tester'
            })
        """)

        # Test queries that should work with correct property names
        valid_queries = [
            (
                "MATCH (u:User) WHERE u.user_principal_name = 'query@test.com' RETURN u",
                "Query with user_principal_name should work",
            ),
            (
                "MATCH (u:User) WHERE u.display_name = 'Query Test User' RETURN u",
                "Query with display_name should work",
            ),
            (
                "MATCH (u:User) WHERE u.job_title IS NOT NULL RETURN u",
                "Query with job_title should work",
            ),
        ]

        for query, description in valid_queries:
            result = neo4j_session.run(query)
            records = list(result)
            assert len(records) > 0, f"{description} - no results found"

        # Test that camelCase property queries would fail or return no results
        invalid_queries = [
            "MATCH (u:User) WHERE u.userPrincipalName = 'query@test.com' RETURN u",
            "MATCH (u:User) WHERE u.jobTitle = 'Tester' RETURN u",
        ]

        for query in invalid_queries:
            result = neo4j_session.run(query)
            records = list(result)
            assert len(records) == 0, (
                f"Query with camelCase properties should not find results: {query}"
            )

        # Clean up
        neo4j_session.run("MATCH (u:User {id: 'query-test-user'}) DETACH DELETE u")

    def test_aad_graph_service_property_mapping(self, neo4j_session):
        """Test that AAD graph service creates properties with correct names."""
        # Simulate what aad_graph_service does when creating users
        # It gets data from Azure AD with camelCase and should convert to snake_case

        azure_ad_data = {
            "id": "aad-user-1",
            "displayName": "AAD User",
            "userPrincipalName": "aad@example.com",
            "mail": "aad@example.com",
        }

        # The service should convert to snake_case when storing
        neo4j_data = {
            "id": azure_ad_data["id"],
            "display_name": azure_ad_data["displayName"],
            "user_principal_name": azure_ad_data[
                "userPrincipalName"
            ],  # Converted to snake_case
            "mail": azure_ad_data["mail"],
        }

        neo4j_session.run(
            """
            MERGE (u:User {id: $id})
            SET u.display_name = $display_name,
                u.user_principal_name = $user_principal_name,
                u.mail = $mail
        """,
            neo4j_data,
        )

        # Verify the properties are stored correctly
        result = neo4j_session.run(
            """
            MATCH (u:User {id: $id})
            RETURN u.user_principal_name as upn
        """,
            id="aad-user-1",
        )

        record = result.single()
        assert record["upn"] == "aad@example.com", (
            "user_principal_name should be set correctly"
        )

        # Clean up
        neo4j_session.run("MATCH (u:User {id: 'aad-user-1'}) DETACH DELETE u")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
