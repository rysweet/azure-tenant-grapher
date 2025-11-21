"""
Demo script for Bug #52: Principal ID Abstraction

This script demonstrates that principal IDs in role assignments
are now properly abstracted at the graph layer.
"""

import json

from src.services.id_abstraction_service import IDAbstractionService


def demo_principal_id_abstraction():
    """Demonstrate principal ID abstraction."""
    print("=" * 80)
    print("Bug #52: Principal ID Abstraction Demo")
    print("=" * 80)

    # Create an ID abstraction service with a test seed
    service = IDAbstractionService(tenant_seed="demo-tenant-seed", hash_length=16)

    # Example 1: Abstracting a single principal ID
    print("\n1. Abstracting a single principal ID:")
    source_principal_id = "12345678-1234-1234-1234-123456789012"
    abstracted = service.abstract_principal_id(source_principal_id)
    print(f"   Source:     {source_principal_id}")
    print(f"   Abstracted: {abstracted}")

    # Example 2: Demonstrating determinism
    print("\n2. Demonstrating determinism (same input = same output):")
    abstracted_again = service.abstract_principal_id(source_principal_id)
    print(f"   First call:  {abstracted}")
    print(f"   Second call: {abstracted_again}")
    print(f"   Match: {abstracted == abstracted_again}")

    # Example 3: Different principal IDs produce different abstractions
    print("\n3. Different principal IDs produce different abstractions:")
    principal_id_2 = "87654321-4321-4321-4321-210987654321"
    abstracted_2 = service.abstract_principal_id(principal_id_2)
    print(f"   Principal 1: {source_principal_id} -> {abstracted}")
    print(f"   Principal 2: {principal_id_2} -> {abstracted_2}")
    print(f"   Different: {abstracted != abstracted_2}")

    # Example 4: Role assignment with abstracted principal ID
    print("\n4. Role assignment properties with abstracted principal ID:")
    role_assignment = {
        "id": "/subscriptions/sub123/providers/Microsoft.Authorization/roleAssignments/ra123",
        "name": "owner-role-assignment",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "roleDefinitionId": "/subscriptions/sub123/providers/Microsoft.Authorization/roleDefinitions/owner",
            "principalId": source_principal_id,
            "principalType": "ServicePrincipal",
            "scope": "/subscriptions/sub123",
        },
    }

    print("\n   Original properties:")
    print(f"   {json.dumps(role_assignment['properties'], indent=6)}")

    # Simulate what happens in the graph layer
    abstracted_props = role_assignment["properties"].copy()
    abstracted_props["principalId"] = service.abstract_principal_id(
        abstracted_props["principalId"]
    )

    print("\n   Abstracted properties (stored in graph):")
    print(f"   {json.dumps(abstracted_props, indent=6)}")

    # Example 5: Cross-tenant deployment safety
    print("\n5. Cross-tenant deployment safety:")
    print(
        f"   Original principal ID ({source_principal_id}) is from SOURCE tenant"
    )
    print(
        f"   Abstracted ID ({abstracted}) is tenant-agnostic and safe for TARGET tenant"
    )
    print(
        "   This prevents SOURCE tenant GUIDs from appearing in deployment templates"
    )

    print("\n" + "=" * 80)
    print("Bug #52 FIX: Principal IDs are now abstracted at the graph layer!")
    print("=" * 80)


if __name__ == "__main__":
    demo_principal_id_abstraction()
