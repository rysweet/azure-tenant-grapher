# Enhancement: Hierarchical Organization for generate-spec Command

## Issue Summary
Enhance the generate-spec command to organize output by Azure's containment hierarchy for better readability and understanding.

## Current Behavior
- Resources are listed flat by type
- No clear relationship between resources and their containers
- Difficult to understand the overall tenant structure

## Proposed Solution
Implement hierarchical organization:
- **Tenant** (root level with purpose inference)
  - **Subscriptions** (grouped by purpose/environment)
    - **Regions** (geographic distribution)
      - **Resource Groups** (logical groupings)
        - **Resources** (actual Azure resources)

## Implementation Details
1. Create `HierarchicalSpecGenerator` class extending `TenantSpecificationGenerator`
2. Implement tenant purpose inference algorithm based on:
   - Resource types and distribution
   - Naming conventions
   - Tag patterns
3. Preserve hierarchy metadata in queries
4. Update markdown rendering for nested structure
5. Add configuration options for hierarchy depth

## Benefits
- Clearer understanding of tenant structure
- Better resource relationship visualization
- Easier identification of organizational patterns
- Improved documentation for stakeholders

## Acceptance Criteria
- [ ] Hierarchical output format implemented
- [ ] Purpose inference working at each level
- [ ] Backward compatibility maintained (flag for old format)
- [ ] Tests cover new functionality
- [ ] Documentation updated

## Branch Name
`feature/hierarchical-spec`
