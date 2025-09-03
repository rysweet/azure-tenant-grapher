"""
Test to identify and fix property name mismatches that cause Neo4j warnings.
This test specifically looks for queries that reference non-existent properties.
"""

import pytest
from neo4j import GraphDatabase
import os
from src.utils.neo4j_startup import ensure_neo4j_running
import warnings
import logging

logger = logging.getLogger(__name__)


@pytest.fixture
def neo4j_driver():
    """Create a Neo4j driver for testing."""
    ensure_neo4j_running()
    
    neo4j_port = os.environ.get("NEO4J_PORT", "7689")
    neo4j_uri = f"bolt://localhost:{neo4j_port}"
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "localtest123!")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    yield driver
    
    driver.close()


def test_identify_property_mismatches(neo4j_driver):
    """
    Test to identify which property names cause warnings.
    This will help us understand what queries are using wrong property names.
    """
    with neo4j_driver.session() as session:
        # First, create a test user with the correct property names
        session.run("""
            MERGE (u:User {id: 'test-property-user'})
            SET u.display_name = 'Test User',
                u.user_principal_name = 'test@example.com',
                u.job_title = 'Developer',
                u.mail = 'test@example.com'
        """)
        
        # Now test various property queries to see which ones work
        property_tests = [
            # Correct snake_case properties (should work)
            ("user_principal_name", "u.user_principal_name = 'test@example.com'", True),
            ("display_name", "u.display_name = 'Test User'", True),
            ("job_title", "u.job_title = 'Developer'", True),
            
            # Incorrect camelCase properties (should fail/return no results)
            ("userPrincipalName", "u.userPrincipalName = 'test@example.com'", False),
            ("displayName", "u.displayName = 'Test User'", False),
            ("jobTitle", "u.jobTitle = 'Developer'", False),
        ]
        
        results = []
        for prop_name, condition, should_work in property_tests:
            query = f"MATCH (u:User) WHERE {condition} RETURN u"
            try:
                result = session.run(query)
                records = list(result)
                found = len(records) > 0
                
                if should_work and not found:
                    results.append(f"ERROR: Query with {prop_name} (snake_case) should work but found no results")
                elif not should_work and found:
                    results.append(f"ERROR: Query with {prop_name} (camelCase) should not work but found results")
                else:
                    results.append(f"OK: Query with {prop_name} behaved as expected")
                    
            except Exception as e:
                results.append(f"EXCEPTION: Query with {prop_name} raised: {str(e)}")
        
        # Clean up
        session.run("MATCH (u:User {id: 'test-property-user'}) DETACH DELETE u")
        
        # Print results
        for result in results:
            logger.info(result)
            print(result)
        
        # Check if any errors were found
        errors = [r for r in results if r.startswith("ERROR")]
        assert not errors, f"Found property mismatches: {errors}"


def test_check_existing_user_properties(neo4j_driver):
    """
    Check what properties actually exist on User nodes in the database.
    """
    with neo4j_driver.session() as session:
        # Get all unique property keys from User nodes
        result = session.run("""
            MATCH (u:User)
            WITH u LIMIT 10
            UNWIND keys(u) as key
            RETURN DISTINCT key
            ORDER BY key
        """)
        
        properties = [record["key"] for record in result]
        
        print(f"\nActual User node properties found in database:")
        for prop in properties:
            print(f"  - {prop}")
        
        # Check for problematic property names
        camel_case_props = [p for p in properties if any(c.isupper() for c in p)]
        if camel_case_props:
            print(f"\nWARNING: Found camelCase properties that should be snake_case:")
            for prop in camel_case_props:
                print(f"  - {prop}")
        
        # Check for expected snake_case properties
        expected_props = ["id", "display_name", "user_principal_name", "job_title", "mail"]
        missing_props = [p for p in expected_props if p not in properties]
        if missing_props:
            print(f"\nINFO: Expected properties not found (might be okay if no users exist):")
            for prop in missing_props:
                print(f"  - {prop}")
        
        # Just print, don't return


def test_fix_camel_case_properties(neo4j_driver):
    """
    Test that demonstrates how to fix camelCase properties if they exist.
    """
    with neo4j_driver.session() as session:
        # Check if any User nodes have camelCase properties
        result = session.run("""
            MATCH (u:User)
            WHERE u.userPrincipalName IS NOT NULL
            RETURN count(u) as count
        """)
        
        count = result.single()["count"]
        
        if count > 0:
            print(f"\nFound {count} User nodes with camelCase 'userPrincipalName' property")
            
            # Fix the property name
            session.run("""
                MATCH (u:User)
                WHERE u.userPrincipalName IS NOT NULL
                SET u.user_principal_name = u.userPrincipalName
                REMOVE u.userPrincipalName
            """)
            
            print("Fixed: Renamed userPrincipalName to user_principal_name")
        else:
            print("\nNo User nodes with camelCase 'userPrincipalName' property found")
        
        # Check for other camelCase properties
        camel_case_fixes = [
            ("displayName", "display_name"),
            ("jobTitle", "job_title"),
            ("mailNickname", "mail_nickname")
        ]
        
        for old_name, new_name in camel_case_fixes:
            result = session.run(f"""
                MATCH (u:User)
                WHERE u.{old_name} IS NOT NULL
                RETURN count(u) as count
            """)
            
            count = result.single()["count"]
            if count > 0:
                print(f"Found {count} User nodes with '{old_name}' property")
                
                session.run(f"""
                    MATCH (u:User)
                    WHERE u.{old_name} IS NOT NULL
                    SET u.{new_name} = u.{old_name}
                    REMOVE u.{old_name}
                """)
                
                print(f"Fixed: Renamed {old_name} to {new_name}")


if __name__ == "__main__":
    # Run with more verbose output
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v", "-s"])