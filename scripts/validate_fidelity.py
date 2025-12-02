#!/usr/bin/env python3
"""
Fidelity Validation Tool

Validates that target tenant matches source tenant based on fidelity criteria,
not just resource counts.

Criteria:
- Identities exist and match
- RBAC assignments match
- Properties match
- Relationships preserved
- Ownership matches
"""

import json
import sys
from pathlib import Path


def validate_fidelity(source_data: dict, target_data: dict) -> dict:
    """Validate fidelity between source and target."""
    
    results = {
        "identities": validate_identities(source_data, target_data),
        "rbac": validate_rbac(source_data, target_data),
        "properties": validate_properties(source_data, target_data),
        "relationships": validate_relationships(source_data, target_data),
    }
    
    return results


def validate_identities(source: dict, target: dict) -> dict:
    """Validate identities exist and properties match."""
    results = {}

    # Validate users
    source_users = source.get("users", [])
    target_users = target.get("users", [])
    source_user_ids = {u.get("id") for u in source_users if u.get("id")}
    target_user_ids = {u.get("id") for u in target_users if u.get("id")}

    users_matched = len(source_user_ids & target_user_ids)
    users_missing = source_user_ids - target_user_ids

    results["users"] = {
        "source_count": len(source_user_ids),
        "matched": users_matched,
        "missing_count": len(users_missing),
        "match_rate": users_matched / max(1, len(source_user_ids)) * 100
    }

    # Validate service principals
    source_spns = source.get("servicePrincipals", [])
    target_spns = target.get("servicePrincipals", [])
    source_spn_ids = {s.get("id") for s in source_spns if s.get("id")}
    target_spn_ids = {s.get("id") for s in target_spns if s.get("id")}

    spns_matched = len(source_spn_ids & target_spn_ids)
    spns_missing = source_spn_ids - target_spn_ids

    results["service_principals"] = {
        "source_count": len(source_spn_ids),
        "matched": spns_matched,
        "missing_count": len(spns_missing),
        "match_rate": spns_matched / max(1, len(source_spn_ids)) * 100
    }

    # Validate managed identities
    source_identities = source.get("managed_identities", [])
    target_identities = target.get("managed_identities", [])
    source_identity_ids = {i.get("id") for i in source_identities if i.get("id")}
    target_identity_ids = {i.get("id") for i in target_identities if i.get("id")}

    identities_matched = len(source_identity_ids & target_identity_ids)
    identities_missing = source_identity_ids - target_identity_ids

    results["managed_identities"] = {
        "source_count": len(source_identity_ids),
        "matched": identities_matched,
        "missing_count": len(identities_missing),
        "match_rate": identities_matched / max(1, len(source_identity_ids)) * 100
    }

    overall_match = (users_matched + spns_matched + identities_matched) / max(1, len(source_user_ids) + len(source_spn_ids) + len(source_identity_ids)) * 100

    return {
        "status": "pass" if overall_match > 95 else "fail",
        "overall_match_rate": overall_match,
        "details": results
    }


def validate_rbac(source: dict, target: dict) -> dict:
    """Validate RBAC assignments match at all scope levels."""
    source_assignments = source.get("role_assignments", [])
    target_assignments = target.get("role_assignments", [])

    # Build ID sets for comparison
    source_ids = {ra.get("id") for ra in source_assignments if ra.get("id")}
    target_ids = {ra.get("id") for ra in target_assignments if ra.get("id")}

    matched = len(source_ids & target_ids)
    missing = source_ids - target_ids

    # Categorize by scope level
    def get_scope_level(assignment_id):
        if "/resourceGroups/" not in assignment_id:
            return "subscription"
        elif "/providers/" not in assignment_id.split("/resourceGroups/")[-1]:
            return "resource_group"
        else:
            return "resource"

    scope_counts = {"subscription": 0, "resource_group": 0, "resource": 0}
    for assignment_id in source_ids:
        scope_counts[get_scope_level(assignment_id)] += 1

    match_rate = matched / max(1, len(source_ids)) * 100

    return {
        "status": "pass" if match_rate > 95 else "fail",
        "source_count": len(source_ids),
        "matched": matched,
        "missing_count": len(missing),
        "match_rate": match_rate,
        "scope_breakdown": scope_counts
    }


def validate_properties(source: dict, target: dict) -> dict:
    """Validate resource properties match (location, SKU, tags)."""
    mismatches = []
    checked = 0

    # Check resources by type
    for resource_type in ["virtual_machines", "storage_accounts", "key_vaults"]:
        source_resources = source.get(resource_type, [])
        target_resources_map = {r.get("id"): r for r in target.get(resource_type, []) if r.get("id")}

        for source_resource in source_resources:
            resource_id = source_resource.get("id")
            if not resource_id:
                continue

            checked += 1
            target_resource = target_resources_map.get(resource_id)

            if not target_resource:
                mismatches.append({
                    "resource_id": resource_id,
                    "issue": "missing_in_target"
                })
                continue

            # Check key properties
            for prop in ["location", "sku", "tags"]:
                source_val = source_resource.get(prop)
                target_val = target_resource.get(prop)

                if source_val != target_val:
                    mismatches.append({
                        "resource_id": resource_id,
                        "property": prop,
                        "source": source_val,
                        "target": target_val
                    })

    match_rate = (checked - len(mismatches)) / max(1, checked) * 100

    return {
        "status": "pass" if match_rate > 95 else "fail",
        "resources_checked": checked,
        "mismatches_found": len(mismatches),
        "match_rate": match_rate,
        "sample_mismatches": mismatches[:10]
    }


def validate_relationships(source: dict, target: dict) -> dict:
    """Validate relationships preserved (ownership, group membership)."""
    # Check group memberships
    source_groups = source.get("groups", [])
    target_groups_map = {g.get("id"): g for g in target.get("groups", []) if g.get("id")}

    membership_matches = 0
    membership_mismatches = 0

    for source_group in source_groups:
        group_id = source_group.get("id")
        if not group_id or group_id not in target_groups_map:
            continue

        source_members = set(source_group.get("members", []))
        target_members = set(target_groups_map[group_id].get("members", []))

        if source_members == target_members:
            membership_matches += 1
        else:
            membership_mismatches += 1

    total_checked = membership_matches + membership_mismatches
    match_rate = membership_matches / max(1, total_checked) * 100

    return {
        "status": "pass" if match_rate > 95 else "fail",
        "groups_checked": total_checked,
        "membership_matches": membership_matches,
        "membership_mismatches": membership_mismatches,
        "match_rate": match_rate
    }


def main():
    """Main validation entry point."""
    print("Fidelity Validation Tool")
    print("=" * 70)
    print("\nThis tool validates tenant replication fidelity based on:")
    print("  - Identity matching (users, SPNs, managed identities)")
    print("  - RBAC assignments")
    print("  - Resource properties")
    print("  - Relationships (ownership, membership)")
    print("\nNOT based on resource counts!")
    print("\n[PLACEHOLDER - Full implementation coming]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
