# Graph Enrichment Plan

This document outlines the plan for enriching the Azure Tenant Grapher Neo4j graph with additional relationships and metadata.

## Overview

The graph enrichment process adds semantic relationships between resources beyond the basic Azure resource hierarchy.

## Relationship Types

### Current Relationships

1. **Tag-based relationships** - Resources with matching tags
2. **Network relationships** - Resources in the same virtual network or subnet
3. **Diagnostic relationships** - Resources connected via diagnostic settings
4. **Monitoring relationships** - Resources with monitoring configurations
5. **Dependency relationships** - Explicit dependencies between resources
6. **RBAC relationships** - Role assignments and permissions

### Planned Enrichments

Future relationship types to be added:

- **Cost relationships** - Resources with related cost patterns
- **Compliance relationships** - Resources sharing compliance requirements
- **Performance relationships** - Resources with performance dependencies
- **Data flow relationships** - Data movement between resources

## Implementation Status

See the modular relationship rules in `src/relationship_rules/` for current implementations.
