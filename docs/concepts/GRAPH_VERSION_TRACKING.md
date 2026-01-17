# Graph Construction Version Tracking

**Type**: Concept (Understanding-oriented)
**Audience**: All Azure Tenant Grapher users
**Last Updated**: 2026-01-16

## What Is Version Tracking?

Graph Construction Version Tracking ensures your Neo4j database matches the graph construction logic in your current version of Azure Tenant Grapher. When the code that builds relationships or stores data changes, your existing database may contain outdated or incomplete information.

## The Problem It Solves

### Scenario: The Silent Mismatch

You scan your Azure tenant with ATG version 1.0. Your Neo4j database contains a complete graph based on version 1.0's understanding of Azure resources and relationships.

Three months later, ATG version 1.5 is released with:
- New relationship types (e.g., `DELEGATED_TO` for Azure Lighthouse)
- Additional node properties (e.g., `compliance_tags`)
- Improved resource type detection

You upgrade ATG and run `atg scan` again. The new scan adds resources, but the database still contains old relationship logic mixed with new. Your queries may:
- Miss new relationships entirely
- Return incomplete property data
- Show inconsistent results between old and new resources

**Version tracking prevents this by detecting the mismatch and guiding you to rebuild.**

## How It Works

### Automatic Detection (<100ms)

Every time you run an ATG command, the version tracker:

1. Reads the graph construction version from your codebase (`GRAPH_CONSTRUCTION_VERSION` constant)
2. Queries Neo4j for the stored version in the metadata node
3. Compares the two versions
4. Warns you if they don't match

This check happens instantly before any scan operations begin.

### Version Storage

ATG stores a single metadata node in Neo4j:

```cypher
// Metadata node structure
(:ATG_Metadata {
  graph_construction_version: "1.5.0",
  last_scan_at: "2026-01-16T14:30:00Z"
})
```

No separate schema version tracking - just one version number that changes when graph construction logic changes.

### What Triggers a Version Change

A version change occurs when code changes affect how the graph is built:

- **New relationship types** - Adding `LIGHTHOUSE_DELEGATED` relationships
- **Modified relationship logic** - Changing how `CREATED_BY` is determined
- **New node properties** - Adding `cost_center` to resources
- **Schema changes** - New node labels or property types
- **Relationship direction changes** - Reversing edge directions

Version changes do NOT occur for:
- Bug fixes in the CLI
- UI improvements
- Performance optimizations that don't change graph structure
- Documentation updates

## Design Principles

### Non-Blocking by Default

Version mismatches warn but never block operations. You remain in control:

```bash
$ atg scan --tenant-id my-tenant

⚠️  Version Mismatch Detected
   Current code: 1.5.0
   Database: 1.0.0

   Your graph may be incomplete. Consider rebuilding:
   atg rebuild --tenant-id my-tenant

Continuing with scan...
```

The warning appears, but the scan proceeds. You decide when to rebuild.

### User Control

ATG never automatically rebuilds your database. Rebuilds require explicit user action:

```bash
# You must explicitly rebuild
atg rebuild --tenant-id my-tenant

# Or use --auto-rebuild flag in CI/CD
atg scan --tenant-id my-tenant --auto-rebuild
```

This prevents data loss from accidental rebuilds.

### CI/CD Safety

For automated pipelines where data loss is acceptable, use `--block-on-mismatch`:

```bash
# Fail the pipeline if version mismatch detected
atg scan --tenant-id my-tenant --block-on-mismatch

# Or auto-rebuild in CI
atg scan --tenant-id my-tenant --auto-rebuild
```

## Version Changelog

ATG uses git history as the changelog. To see what changed between versions:

```bash
# See graph construction changes
git log --grep="GRAPH_CONSTRUCTION_VERSION" --oneline

# View specific version changes
git show <commit-hash>
```

No manual `changes[]` array - the git commit messages document why versions changed.

## When to Rebuild

### Always Rebuild When:
- Upgrading major versions (1.x → 2.x)
- Adding new relationship types you need
- Security advisories recommend it
- Compliance requirements mandate it

### Consider Rebuilding When:
- Queries return unexpected results
- New features aren't working as expected
- Documentation mentions "requires rebuild"

### Skip Rebuilding When:
- You're testing or experimenting
- The warning doesn't mention features you use
- You're in the middle of development
- Time constraints outweigh data completeness

## Backup Before Rebuild

Always backup metadata before rebuilding:

```bash
# Create backup
atg backup-metadata --tenant-id my-tenant

# Rebuild safely
atg rebuild --tenant-id my-tenant
```

The backup command is separate (not built into rebuild) following the principle that each command does one thing well.

## Related Documentation

- [How to Handle Version Mismatches](../howto/handle-version-mismatches.md) - Step-by-step workflows
- [Version Tracking Tutorial](../tutorials/version-tracking-tutorial.md) - Complete walkthrough
- [Command Reference: atg rebuild](../reference/commands.md#rebuild) - All command options

## Frequently Asked Questions

**Q: Can I ignore version warnings?**
A: Yes. Warnings are non-blocking. You may continue using an outdated graph, but queries may return incomplete data.

**Q: Will I lose my data when rebuilding?**
A: Rebuilding re-scans Azure and reconstructs the graph. Historical metadata can be backed up with `atg backup-metadata`.

**Q: How often do versions change?**
A: Typically 2-4 times per major release cycle, only when graph construction logic changes.

**Q: Can I downgrade ATG versions?**
A: Not recommended. Older code may not understand newer graph structures. Rebuild after downgrading.

**Q: Does version tracking affect performance?**
A: Negligible impact (<100ms startup check). No performance impact during scans.
