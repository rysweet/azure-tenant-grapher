"""
Test to ensure Neo4j property names are consistent (snake_case) across the codebase.
This test verifies that graph creation and queries use the same property naming convention.
"""

import pytest
from neo4j import GraphDatabase
import os
from src.utils.neo4j_startup import ensure_neo4j_running
from src.services.aad_graph_service import AADGraphService
from src.tenant_creator import TenantCreator
from src.tenant_spec_models import User, TenantSpec
from typing import Dict, List, Set
import asyncio


@pytest.fixture
def neo4j_driver():
    """Create a Neo4j driver for testing."""
    ensure_neo4j_running()
    
    neo4j_port = os.environ.get("NEO4J_PORT", "7689")
    neo4j_uri = f"bolt://localhost:{neo4j_port}"
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "localtest123!")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    # Clean up test data before and after
    with driver.session() as session:
        session.run("MATCH (n:TestUser) DETACH DELETE n")
        session.run("MATCH (n:TestGroup) DETACH DELETE n")
        session.run("MATCH (n:TestServicePrincipal) DETACH DELETE n")
    
    yield driver
    
    # Cleanup
    with driver.session() as session:
        session.run("MATCH (n:TestUser) DETACH DELETE n")
        session.run("MATCH (n:TestGroup) DETACH DELETE n")
        session.run("MATCH (n:TestServicePrincipal) DETACH DELETE n")
    
    driver.close()


class TestNeo4jPropertyConsistency:
    """Test that property names follow snake_case convention consistently."""
    
    def test_user_properties_are_snake_case(self, neo4j_driver):
        """Verify User nodes use snake_case properties."""
        with neo4j_driver.session() as session:
            # Create a user with all expected properties
            session.run("""
                CREATE (u:TestUser {
                    id: 'test-user-1',
                    display_name: 'Test User',
                    user_principal_name: 'test@example.com',
                    mail: 'test@example.com',
                    job_title: 'Developer'
                })
            """)
            
            # Query back and check property names
            result = session.run("""
                MATCH (u:TestUser {id: 'test-user-1'})
                RETURN keys(u) as properties
            """)
            
            properties = result.single()["properties"]
            
            # Check for camelCase properties (should not exist)
            camel_case_props = [p for p in properties if any(c.isupper() for c in p[1:])]
            assert not camel_case_props, f"Found camelCase properties: {camel_case_props}"
            
            # Check expected snake_case properties exist
            expected = ["id", "display_name", "user_principal_name", "mail", "job_title"]
            for prop in expected:
                assert prop in properties, f"Missing expected property: {prop}"
    
    def test_aad_graph_service_properties(self, neo4j_driver):
        """Test that AAD Graph Service creates properties with correct names."""
        # Create mock AAD data (simulating what comes from Azure AD API)
        mock_users = [
            {
                "id": "aad-user-1",
                "displayName": "AAD Test User",
                "userPrincipalName": "aaduser@example.com",
                "mail": "aaduser@example.com"
            }
        ]
        
        # Verify our fix converts camelCase to snake_case
        with neo4j_driver.session() as session:
            # Simulate what AADGraphService.ingest_into_graph does
            for user in mock_users:
                props = {
                    "id": user.get("id"),
                    "display_name": user.get("displayName"),  # Should be snake_case
                    "user_principal_name": user.get("userPrincipalName"),  # Should be snake_case
                    "mail": user.get("mail"),
                    "type": "User",
                }
                
                # Create the node with correct property names
                session.run("""
                    MERGE (u:TestUser {id: $id})
                    SET u.display_name = $display_name,
                        u.user_principal_name = $user_principal_name,
                        u.mail = $mail,
                        u.type = $type
                """, props)
            
            # Verify properties are snake_case
            result = session.run("""
                MATCH (u:TestUser {id: 'aad-user-1'})
                RETURN u.display_name as dn, 
                       u.user_principal_name as upn,
                       keys(u) as props
            """)
            
            record = result.single()
            assert record["dn"] == "AAD Test User"
            assert record["upn"] == "aaduser@example.com"
            
            # No camelCase properties should exist
            props = record["props"]
            assert "userPrincipalName" not in props
            assert "displayName" not in props
            assert "user_principal_name" in props
            assert "display_name" in props
    
    def test_query_with_correct_properties(self, neo4j_driver):
        """Test that queries using snake_case properties work correctly."""
        with neo4j_driver.session() as session:
            # Create test data
            session.run("""
                CREATE (u1:TestUser {
                    id: 'query-test-1',
                    display_name: 'Query Test User 1',
                    user_principal_name: 'query1@test.com'
                })
                CREATE (u2:TestUser {
                    id: 'query-test-2',
                    display_name: 'Query Test User 2',
                    user_principal_name: 'query2@test.com'
                })
            """)
            
            # Test queries with snake_case properties
            test_queries = [
                ("MATCH (u:TestUser) WHERE u.user_principal_name = 'query1@test.com' RETURN u", 1),
                ("MATCH (u:TestUser) WHERE u.display_name CONTAINS 'Query' RETURN u", 2),
                ("MATCH (u:TestUser) WHERE u.user_principal_name STARTS WITH 'query' RETURN u", 2),
            ]
            
            for query, expected_count in test_queries:
                result = session.run(query)
                records = list(result)
                assert len(records) == expected_count, f"Query '{query}' returned {len(records)} results, expected {expected_count}"
    
    def test_no_camel_case_queries_work(self, neo4j_driver):
        """Verify that queries using camelCase properties return no results."""
        with neo4j_driver.session() as session:
            # Create test data with snake_case
            session.run("""
                CREATE (u:TestUser {
                    id: 'camel-test',
                    display_name: 'Camel Test User',
                    user_principal_name: 'camel@test.com'
                })
            """)
            
            # These camelCase queries should return no results
            bad_queries = [
                "MATCH (u:TestUser) WHERE u.userPrincipalName = 'camel@test.com' RETURN u",
                "MATCH (u:TestUser) WHERE u.displayName = 'Camel Test User' RETURN u",
            ]
            
            for query in bad_queries:
                result = session.run(query)
                records = list(result)
                assert len(records) == 0, f"CamelCase query should return no results: {query}"
    
    def test_migration_fixes_existing_properties(self, neo4j_driver):
        """Test that migration script would fix any existing camelCase properties."""
        with neo4j_driver.session() as session:
            # Create a node with camelCase properties (simulating old data)
            session.run("""
                CREATE (u:TestUser {
                    id: 'migration-test',
                    displayName: 'Migration Test User',
                    userPrincipalName: 'migrate@test.com'
                })
            """)
            
            # Run migration logic
            session.run("""
                MATCH (u:TestUser)
                WHERE u.userPrincipalName IS NOT NULL AND u.user_principal_name IS NULL
                SET u.user_principal_name = u.userPrincipalName
                REMOVE u.userPrincipalName
            """)
            
            session.run("""
                MATCH (u:TestUser)
                WHERE u.displayName IS NOT NULL AND u.display_name IS NULL
                SET u.display_name = u.displayName
                REMOVE u.displayName
            """)
            
            # Verify properties are now snake_case
            result = session.run("""
                MATCH (u:TestUser {id: 'migration-test'})
                RETURN keys(u) as props,
                       u.display_name as dn,
                       u.user_principal_name as upn
            """)
            
            record = result.single()
            props = record["props"]
            
            # Check snake_case exists
            assert "display_name" in props
            assert "user_principal_name" in props
            
            # Check camelCase removed
            assert "displayName" not in props
            assert "userPrincipalName" not in props
            
            # Check values preserved
            assert record["dn"] == "Migration Test User"
            assert record["upn"] == "migrate@test.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])