# Architecture Improvements

This document tracks architectural improvements and refactoring plans for Azure Tenant Grapher.

## Current Architecture

See `docs/design/SPA_ARCHITECTURE.md` for the current system architecture.

## Proposed Improvements

### Modularity Enhancements

- **Relationship Rules**: Further modularization of relationship detection logic
- **IaC Handlers**: Plugin architecture for resource-specific handlers
- **Service Layer**: Cleaner separation between services

### Performance Optimizations

- **Graph Queries**: Optimize Neo4j Cypher queries for large tenants
- **Parallel Processing**: Improve parallelization in resource discovery
- **Caching**: Strategic caching for frequently accessed data

### Code Quality

- **Type Safety**: Enhanced TypeScript types in SPA
- **Error Handling**: More comprehensive error handling patterns
- **Testing**: Improved test coverage across all modules

## Implementation Status

Track progress on specific improvement initiatives here.

## Related Documents

- `docs/design/SPA_ARCHITECTURE.md` - Current architecture
- `IMPLEMENTATION_SUMMARY.md` - Implementation overview
