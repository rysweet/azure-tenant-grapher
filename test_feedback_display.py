#!/usr/bin/env python
"""
Quick test to demonstrate the feedback display for create-tenant command
"""

import click

# Sample statistics that would be returned from ingest_to_graph
stats = {
    "tenant": 1,
    "subscriptions": 1,
    "resource_groups": 1,
    "resources": 2,
    "users": 2,
    "groups": 1,
    "service_principals": 1,
    "managed_identities": 0,
    "admin_units": 0,
    "rbac_assignments": 1,
    "relationships": 1,
    "total": 11
}

# Display success with detailed feedback (copied from our implementation)
click.echo("")
click.echo("✅ Tenant successfully created in Neo4j!")
click.echo("")

# Display resource counts
if stats:
    click.echo("📊 Resources created:")
    click.echo("-" * 40)
    
    # Display non-zero counts in a logical order
    display_order = [
        ("tenant", "Tenant"),
        ("subscriptions", "Subscriptions"),
        ("resource_groups", "Resource Groups"),
        ("resources", "Resources"),
        ("users", "Users"),
        ("groups", "Groups"),
        ("service_principals", "Service Principals"),
        ("managed_identities", "Managed Identities"),
        ("admin_units", "Admin Units"),
        ("rbac_assignments", "RBAC Assignments"),
        ("relationships", "Relationships")
    ]
    
    for key, label in display_order:
        if key in stats and stats[key] > 0:
            click.echo(f"  • {label}: {stats[key]}")
    
    click.echo("-" * 40)
    click.echo(f"  Total entities: {stats.get('total', 0)}")
    click.echo("")
    click.echo("💡 Next steps:")
    click.echo("  • Run 'atg visualize' to see the graph")
    click.echo("  • Run 'atg build' to enrich with more data")
else:
    click.echo("⚠️  No statistics available")