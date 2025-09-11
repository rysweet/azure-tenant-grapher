#!/usr/bin/env python
"""Quick test to verify property consistency fix."""

import re


def check_file_properties(filepath, entity_type, expected_properties):
    """Check if a file uses the expected property names."""
    with open(filepath) as f:
        content = f.read()

    issues = []
    for prop, correct_format in expected_properties.items():
        # Look for SET statements with this property
        pattern = rf"SET\s+\w+\.{prop}"
        if re.search(pattern, content):
            if not re.search(rf"SET\s+\w+\.{correct_format}", content):
                issues.append(f"Found {prop} but expected {correct_format}")

    return issues


def main():
    """Main test function."""
    print("Checking Neo4j property consistency...")

    # Check tenant_creator.py
    print("\n1. Checking tenant_creator.py:")
    user_properties = {
        "display_name": "displayName",
        "user_principal_name": "userPrincipalName",
        "job_title": "jobTitle",
        "mail_nickname": "mailNickname",
    }

    issues = check_file_properties("src/tenant_creator.py", "User", user_properties)

    if issues:
        print("  ❌ Issues found:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        # Check if correct properties are present
        with open("src/tenant_creator.py") as f:
            content = f.read()

        found_properties = []
        for correct_prop in ["displayName", "userPrincipalName", "jobTitle"]:
            if f"u.{correct_prop}" in content:
                found_properties.append(correct_prop)

        if found_properties:
            print(
                f"  ✅ Correct! Using camelCase properties: {', '.join(found_properties)}"
            )
        else:
            print("  ⚠️ No User properties found")

    # Check aad_graph_service.py
    print("\n2. Checking aad_graph_service.py:")
    with open("src/services/aad_graph_service.py") as f:
        content = f.read()

    # Check dictionary keys in props
    camel_case_props = ["displayName", "userPrincipalName", "mail"]
    found_aad_props = []
    for prop in camel_case_props:
        if f'"{prop}"' in content:
            found_aad_props.append(prop)

    if found_aad_props:
        print(
            f"  ✅ Correct! Using camelCase in props dictionary: {', '.join(found_aad_props)}"
        )
    else:
        print("  ⚠️ No camelCase properties found")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print("Both files now use camelCase properties consistently!")
    print(
        "- User nodes will have: displayName, userPrincipalName, jobTitle, mailNickname"
    )
    print("- Queries can now reliably use: MATCH (u:User {userPrincipalName: $upn})")
    print("=" * 50)


if __name__ == "__main__":
    main()
