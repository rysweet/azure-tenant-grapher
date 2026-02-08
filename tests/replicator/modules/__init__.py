"""
Unit tests for replicator brick modules.

This package contains comprehensive unit tests for all 7 brick modules:
- ResourceTypeResolver: Type resolution logic
- ConfigurationSimilarity: Similarity computation and clustering
- GraphStructureAnalyzer: Spectral distance and scoring
- InstanceSelector: All selection strategies
- PatternInstanceFinder: Neo4j queries (mocked)
- OrphanedResourceManager: Orphaned resource finding (mocked)
- TargetGraphBuilder: Graph construction from instances

All tests use mocking for external dependencies (Neo4j, NetworkX graphs) and follow
the testing pyramid (60% unit, 30% integration, 10% E2E).
"""
