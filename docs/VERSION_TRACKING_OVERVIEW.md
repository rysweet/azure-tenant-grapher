# Graph Version Tracking - Documentation Overview

**Quick Links:**
- [Concepts](concepts/GRAPH_VERSION_TRACKING.md) - Why version tracking exists
- [Tutorial](tutorials/version-tracking-tutorial.md) - 30-minute walkthrough
- [How-To Guide](howto/handle-version-mismatches.md) - Specific scenarios
- [Command Reference](reference/version-tracking-commands.md) - All flags and options

---

## What Is This Feature?

Graph Construction Version Tracking ensures your Neo4j database matches the graph construction logic in your current version of Azure Tenant Grapher. When ATG's code changes how relationships are built or data is stored, you get clear warnings and guidance for updating your database.

**Key Benefit**: Never silently work with an incomplete or outdated graph.

## Quick Start (5 Minutes)

### 1. Understanding Version Warnings

When you see this warning:

```
⚠️  Version Mismatch Detected
   Current code: 1.8.0
   Database: 1.5.0
   Consider rebuilding: atg rebuild --tenant-id my-tenant
```

**It means**: Your database was built with older logic and may be missing new relationships or properties.

**What to do**: Read [what changed](#checking-what-changed), then decide whether to [rebuild now or later](#when-to-rebuild).

### 2. Checking What Changed

```bash
# View version changes
git log --grep="GRAPH_CONSTRUCTION_VERSION" --oneline

# See specific change details
git show <commit-hash>
```

**Look for**: Features you use, security fixes, compliance requirements.

### 3. Safe Rebuild Workflow

```bash
# Step 1: Backup (always!)
atg backup-metadata --tenant-id my-tenant

# Step 2: Rebuild
atg rebuild --tenant-id my-tenant

# Step 3: Verify
atg scan --tenant-id my-tenant --dry-run
# Should show: ✓ Version check passed
```

**Time required**: ~1 minute per 100 resources (typical: 5-15 minutes)

## When to Rebuild

### Rebuild Immediately If:
- ✅ Security vulnerability fixed
- ✅ Feature you need isn't working
- ✅ Major version upgrade (1.x → 2.x)
- ✅ Compliance requirement

### Schedule for Maintenance Window:
- ⏱️ Minor version upgrade (1.5 → 1.6)
- ⏱️ New features you'll use eventually
- ⏱️ Large tenant (>5,000 resources)

### Safe to Skip:
- ⛔ Feature doesn't apply to you
- ⛔ Test/dev environment
- ⛔ Temporary graph

## Common Scenarios

### Scenario 1: First Time Seeing Warning

**You just upgraded ATG and see a version warning.**

1. Read the warning to see version numbers
2. Check [what changed](howto/handle-version-mismatches.md#scenario-2-checking-what-changed-between-versions)
3. Decide: [now, scheduled, or skip](howto/handle-version-mismatches.md#deciding-whether-to-rebuild)
4. If rebuilding: [follow safe workflow](howto/handle-version-mismatches.md#scenario-3-safely-rebuilding-your-graph)

**Full guide**: [Handle Version Mismatches - Scenario 1](howto/handle-version-mismatches.md#scenario-1-first-time-seeing-a-version-warning)

### Scenario 2: CI/CD Integration

**You run ATG in automated pipelines.**

**Option A - Block on Mismatch** (production):
```bash
atg scan --tenant-id prod --block-on-mismatch
# Fails pipeline if mismatch → manual rebuild required
```

**Option B - Auto-Rebuild** (test environments):
```bash
atg scan --tenant-id test --auto-rebuild
# Automatically rebuilds if mismatch → then scans
```

**Full guide**: [CI/CD Integration](howto/handle-version-mismatches.md#scenario-4-handling-version-mismatches-in-cicd)

### Scenario 3: Can't Rebuild Right Now

**You see the warning but can't rebuild during business hours.**

1. Acknowledge the warning (document decision)
2. Continue using current graph (operations are non-blocking)
3. Schedule rebuild for maintenance window
4. Warning appears each time (reminder)

**Full guide**: [Postponing a Rebuild](howto/handle-version-mismatches.md#scenario-6-postponing-a-rebuild)

## Learning Path

### New User (30 minutes)

Follow the complete tutorial with hands-on examples:

**[Version Tracking Tutorial](tutorials/version-tracking-tutorial.md)** (30 min)
- Step-by-step walkthrough
- Real commands with expected output
- Learn by doing

### Experienced User (10 minutes)

Read concepts and reference as-needed:

**[Version Tracking Concepts](concepts/GRAPH_VERSION_TRACKING.md)** (10 min read)
- Why version tracking exists
- Design principles
- When to rebuild

**[Command Reference](reference/version-tracking-commands.md)** (lookup)
- All command flags
- Exit codes
- Environment variables

### Need to Solve Specific Problem (5 minutes)

Jump directly to relevant scenario:

**[Handle Version Mismatches](howto/handle-version-mismatches.md)**
- Scenario-based guide
- Copy-paste commands
- Troubleshooting section

## Documentation Map

```
docs/
├── VERSION_TRACKING_OVERVIEW.md (← you are here)
│
├── concepts/
│   └── GRAPH_VERSION_TRACKING.md
│       └── Understanding: Why version tracking? How does it work?
│
├── tutorials/
│   └── version-tracking-tutorial.md
│       └── Learning: Complete 30-min walkthrough with examples
│
├── howto/
│   └── handle-version-mismatches.md
│       └── Doing: Specific scenarios with step-by-step workflows
│
└── reference/
    └── version-tracking-commands.md
        └── Information: Complete command syntax and options
```

## Frequently Asked Questions

**Q: Will version warnings block my scans?**
A: No. Warnings are non-blocking by default. Scans continue normally. You control when to rebuild.

**Q: How often do versions change?**
A: Typically 2-4 times per major release, only when graph construction logic changes.

**Q: Will I lose data when rebuilding?**
A: The graph is rebuilt from Azure (current state). Historical metadata can be backed up with `atg backup-metadata`.

**Q: Can I ignore version warnings forever?**
A: Yes, but your graph becomes increasingly incomplete as new features accumulate over time.

**Q: How long does rebuilding take?**
A: ~1 minute per 100 resources. Typical tenants (500-1,000 resources): 5-15 minutes.

**Q: What if rebuild fails partway through?**
A: See [Recovering from a Failed Rebuild](howto/handle-version-mismatches.md#scenario-5-recovering-from-a-failed-rebuild) for step-by-step recovery.

## Command Quick Reference

```bash
# Check version status
atg info --tenant-id <id>

# Scan with version check (default)
atg scan --tenant-id <id>

# Backup before rebuild
atg backup-metadata --tenant-id <id>

# Rebuild graph
atg rebuild --tenant-id <id>

# CI/CD: Block on mismatch
atg scan --tenant-id <id> --block-on-mismatch

# CI/CD: Auto-rebuild
atg scan --tenant-id <id> --auto-rebuild
```

## Key Design Principles

1. **Non-blocking by default** - Warnings never stop operations
2. **User control** - No automatic rebuilds without explicit permission
3. **Fast checks** - Version detection <100ms
4. **Clear guidance** - Warnings explain what to do next
5. **Safe rebuilds** - Automatic backup, confirmation prompts, time estimates

## Next Steps

**If you're new to version tracking:**
→ Start with [Version Tracking Tutorial](tutorials/version-tracking-tutorial.md)

**If you just saw a warning:**
→ Jump to [Handle Version Mismatches - Scenario 1](howto/handle-version-mismatches.md#scenario-1-first-time-seeing-a-version-warning)

**If you need command syntax:**
→ Reference [Version Tracking Commands](reference/version-tracking-commands.md)

**If you want to understand deeply:**
→ Read [Version Tracking Concepts](concepts/GRAPH_VERSION_TRACKING.md)

---

**Related Documentation:**
- [Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md) - Graph database schema
- [Scale Operations](SCALE_OPERATIONS.md) - Layer management
- [Installation Guide](quickstart/installation.md) - Setup and prerequisites
