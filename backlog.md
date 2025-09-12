# Backlog

## Workflow for Implementing Features

When implementing new features or fixing issues, follow this workflow:

1. **Create a new issue in the repo** with a descriptive title and detailed description
2. **Analyze the issue** and capture requirements and design, update the issue
3. **Break down into smaller tasks** if needed
4. **Create a feature branch** following naming convention (feature/issue-XXX-description)
5. **Write failing tests first**, then implement the fix
6. **Write additional unit and integration tests**
7. **Run all tests** to ensure everything passes
8. **Update documentation** as needed
9. **Run pre-commit hooks and linters**
10. **Push branch and create PR**
11. **Review PR** and provide feedback
12. **Address feedback** and iterate until CI passes

## Current Issues

### 1.  Fix 'atg scan' and 'atg build' command inconsistency
**Status**: Completed - PR #256
- The scan and build commands should be identical (one should be an alias of the other)
- The help text was different and PR #229 changes didn't appear in atg scan
- Fixed by adding missing filter options to scan command

### 2.  Improve 'atg generate-spec' organization by resource containment
**Status**: Completed - PR #257
- Reorganized output by containment hierarchy
- Added purpose inference at each level
- Starts with tenant summary, then subscriptions, regions, resource groups, and resources

### 3. = Fix managed identity inclusion in filtered builds
**Status**: In Progress
- When using filters (--filter-by-subscriptions or --filter-by-rgs)
- Should include referenced managed identities
- Should include roles/groups assigned to those identities
- Requires Graph API integration

## Future Enhancements

- Add support for cross-subscription peering visualization
- Implement cost analysis integration
- Add security posture assessment
- Improve performance for large tenants
- Add support for Azure Arc resources