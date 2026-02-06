#!/usr/bin/env python3
"""
Diagnostic script for Issue #889: Managed Identity RBAC & Resource Bindings

This script helps diagnose why RBAC role assignments and resource bindings
are lost during Managed Identity replication.

Root causes to check:
1. Scan permissions (User Access Administrator role required)
2. Role assignments discovered in Neo4j
3. Cross-tenant identity mapping configuration
4. Neo4j data integrity for identity properties
"""

import sys
from typing import Dict, List, Any
import json

def check_neo4j_role_assignments(session) -> Dict[str, Any]:
    """Check if role assignments were discovered and stored in Neo4j."""
    query = """
    MATCH (ra:Resource {type: "Microsoft.Authorization/roleAssignments"})
    RETURN count(ra) as total,
           collect(ra.name)[0..5] as samples
    """
    result = session.run(query).single()

    return {
        "status": "OK" if result["total"] > 0 else "FAIL",
        "total_role_assignments": result["total"],
        "sample_names": result["samples"],
        "message": f"Found {result['total']} role assignments in Neo4j" if result["total"] > 0
                   else "NO role assignments found - check scan permissions"
    }

def check_managed_identity_data(session, mi_name: str = None) -> Dict[str, Any]:
    """Check if Managed Identity nodes have complete identity properties."""
    query = """
    MATCH (mi:Resource)
    WHERE mi.type = "Microsoft.ManagedIdentity/userAssignedIdentities"
    """ + (f"AND mi.name = '{mi_name}'" if mi_name else "") + """
    RETURN mi.name as name,
           mi.identity as identity,
           mi.properties as properties
    LIMIT 5
    """

    results = list(session.run(query))

    return {
        "status": "OK" if len(results) > 0 else "FAIL",
        "count": len(results),
        "identities": [
            {
                "name": r["name"],
                "has_identity_property": r["identity"] is not None,
                "has_properties": r["properties"] is not None
            }
            for r in results
        ],
        "message": f"Found {len(results)} Managed Identities in Neo4j"
    }

def check_identity_relationships(session, mi_name: str = None) -> Dict[str, Any]:
    """Check if identity relationships exist in Neo4j."""
    query = """
    MATCH (mi:Resource)-[r]-(other)
    WHERE mi.type = "Microsoft.ManagedIdentity/userAssignedIdentities"
    """ + (f"AND mi.name = '{mi_name}'" if mi_name else "") + """
    RETURN type(r) as rel_type,
           count(*) as count
    """

    results = list(session.run(query))
    rel_counts = {r["rel_type"]: r["count"] for r in results}

    return {
        "status": "OK" if len(rel_counts) > 0 else "WARN",
        "relationships": rel_counts,
        "message": "Found relationships: " + ", ".join([f"{k}: {v}" for k, v in rel_counts.items()])
                   if rel_counts else "No identity relationships found"
    }

def check_resource_identity_bindings(session) -> Dict[str, Any]:
    """Check if resources have identity bindings preserved."""
    query = """
    MATCH (r:Resource)
    WHERE r.identity IS NOT NULL
    AND r.identity.userAssignedIdentities IS NOT NULL
    RETURN r.type as type,
           count(*) as count
    """

    results = list(session.run(query))
    type_counts = {r["type"]: r["count"] for r in results}

    return {
        "status": "OK" if len(type_counts) > 0 else "WARN",
        "resources_with_identity": type_counts,
        "message": "Found resources with identity bindings: " +
                   ", ".join([f"{k}: {v}" for k, v in type_counts.items()])
                   if type_counts else "No resources with identity bindings found"
    }

def run_diagnostics(neo4j_uri: str, neo4j_user: str, neo4j_password: str, mi_name: str = None):
    """Run all diagnostic checks."""
    from neo4j import GraphDatabase

    print("=" * 80)
    print("Issue #889 Diagnostic Tool: Managed Identity RBAC & Resource Bindings")
    print("=" * 80)
    print()

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    checks = []

    with driver.session() as session:
        print("1. Checking Role Assignments in Neo4j...")
        result = check_neo4j_role_assignments(session)
        checks.append(("Role Assignments", result))
        print(f"   [{result['status']}] {result['message']}")
        if result['sample_names']:
            print(f"   Samples: {', '.join(result['sample_names'][:3])}")
        print()

        print("2. Checking Managed Identity Data Integrity...")
        result = check_managed_identity_data(session, mi_name)
        checks.append(("MI Data Integrity", result))
        print(f"   [{result['status']}] {result['message']}")
        for mi in result['identities'][:3]:
            print(f"   - {mi['name']}: identity={mi['has_identity_property']}, properties={mi['has_properties']}")
        print()

        print("3. Checking Identity Relationships...")
        result = check_identity_relationships(session, mi_name)
        checks.append(("Identity Relationships", result))
        print(f"   [{result['status']}] {result['message']}")
        print()

        print("4. Checking Resource Identity Bindings...")
        result = check_resource_identity_bindings(session)
        checks.append(("Resource Bindings", result))
        print(f"   [{result['status']}] {result['message']}")
        print()

    driver.close()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    failures = [name for name, result in checks if result["status"] == "FAIL"]
    warnings = [name for name, result in checks if result["status"] == "WARN"]

    if not failures and not warnings:
        print("✅ ALL CHECKS PASSED - Issue may be in IaC emission, not discovery")
        print("\nNext steps:")
        print("1. Check if role_assignment handler is registered in handlers/__init__.py")
        print("2. Verify identity mapping exists for cross-tenant deployments")
        print("3. Check emission logs for role assignment filtering messages")
    elif failures:
        print(f"❌ {len(failures)} CRITICAL ISSUES FOUND:")
        for name in failures:
            print(f"   - {name}")
        print("\nNext steps:")
        if "Role Assignments" in failures:
            print("1. Verify scan has 'User Access Administrator' or 'Owner' role")
            print("2. Re-run scan with proper permissions")
        if "MI Data Integrity" in failures:
            print("1. Check if Managed Identities are being discovered")
            print("2. Verify Neo4j schema allows identity properties")
    elif warnings:
        print(f"⚠️  {len(warnings)} WARNINGS FOUND:")
        for name in warnings:
            print(f"   - {name}")
        print("\nThese may be expected if your tenant has no MIs or identity relationships")

    print()
    return 0 if not failures else 1

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Diagnose Managed Identity RBAC & Resource Binding issues")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", help="Neo4j connection URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument("--neo4j-password", required=True, help="Neo4j password")
    parser.add_argument("--mi-name", help="Specific Managed Identity name to check (optional)")

    args = parser.parse_args()

    sys.exit(run_diagnostics(args.neo4j_uri, args.neo4j_user, args.neo4j_password, args.mi_name))
