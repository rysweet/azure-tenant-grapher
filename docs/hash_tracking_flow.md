# Hash-Based Version Tracking Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Graph Construction Files                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  src/relationship_rules/                                    │ │
│  │  src/services/azure_discovery_service.py                    │ │
│  │  src/resource_processor.py                                  │ │
│  │  src/azure_tenant_grapher.py                                │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             │ HashTracker.calculate_hash()
                             ▼
                    ┌────────────────┐
                    │  SHA256 Hash   │
                    │  (64 chars)    │
                    └────────────────┘
                             │
                             │ Store in
                             ▼
                    ┌────────────────────────────────────┐
                    │   .atg_graph_version (JSON)        │
                    │  ┌──────────────────────────────┐  │
                    │  │ version: "1.0.0"             │  │
                    │  │ construction_hash: "7f6..."  │  │
                    │  │ tracked_paths: [...]         │  │
                    │  │ last_modified: "..."         │  │
                    │  │ description: "..."           │  │
                    │  └──────────────────────────────┘  │
                    └────────────────────────────────────┘
                             │
                             │ Validated by
                             ▼
                    ┌────────────────────┐
                    │  VersionDetector   │
                    │                    │
                    │  detect_mismatch() │
                    └────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        Hash Validation           Version Validation
        (< 50ms, no DB)           (< 50ms, DB query)
                │                         │
                └────────────┬────────────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │  Mismatch Result?  │
                    └────────────────────┘
                        │          │
                    ✅ Match    ❌ Mismatch
                        │          │
                        │          └──► Report changed files
                        │          └──► Suggest rebuild
                        │
                        └──► Continue normal operation
```

## Developer Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     1. Developer Modifies Code                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Edit: src/relationship_rules/new_rule.py                   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              2. Calculate New Hash (Manual Step)                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  $ python3 -c "from src.version_tracking.hash_tracker      │ │
│  │    import calculate_construction_hash;                      │ │
│  │    print(calculate_construction_hash())"                    │ │
│  │                                                              │ │
│  │  Output: abc123def456... (new hash)                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              3. Update Version File (Manual Step)                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Edit .atg_graph_version:                                   │ │
│  │  {                                                           │ │
│  │    "version": "1.0.1",              ← Bump version          │ │
│  │    "last_modified": "2026-01-17...", ← Update timestamp     │ │
│  │    "description": "Added new rule", ← Describe change       │ │
│  │    "construction_hash": "abc123...", ← New hash             │ │
│  │    "tracked_paths": [...]           ← (unchanged)           │ │
│  │  }                                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  4. Commit Changes (Git)                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  $ git add src/relationship_rules/new_rule.py               │ │
│  │  $ git add .atg_graph_version                               │ │
│  │  $ git commit -m "Add new relationship rule"                │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│           5. Pre-Commit Hook Validation (Automatic)              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Check: Construction files changed?                         │ │
│  │    ✅ YES: src/relationship_rules/new_rule.py               │ │
│  │                                                              │ │
│  │  Check: .atg_graph_version also staged?                     │ │
│  │    ✅ YES: .atg_graph_version updated                       │ │
│  │                                                              │ │
│  │  Result: ✅ Commit allowed                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    Commit succeeds ✅
```

## Mismatch Detection Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                 Application Startup / Query                      │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              1. VersionDetector.detect_mismatch()                │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         2. Read .atg_graph_version (Semaphore File)              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  stored_hash = "7f608873a1c53bb0..."                        │ │
│  │  stored_version = "1.0.0"                                   │ │
│  │  tracked_paths = [...]                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         3. Calculate Current Hash (HashTracker)                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Walk tracked_paths                                         │ │
│  │  Hash each file (chunked reading)                           │ │
│  │  Combine hashes with paths                                  │ │
│  │  current_hash = "abc123def456..."                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Performance: ~10-20ms                                           │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              4. Compare Hashes (Fast Path)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  stored_hash == current_hash?                               │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                    │                    │
                ✅ Match            ❌ Mismatch
                    │                    │
                    │                    ▼
                    │        ┌────────────────────────────┐
                    │        │  Detect Changed Files      │
                    │        │  - Added: +new_file.py     │
                    │        │  - Modified: file.py       │
                    │        │  - Removed: -old_file.py   │
                    │        └────────────────────────────┘
                    │                    │
                    │                    ▼
                    │        ┌────────────────────────────┐
                    │        │  Return Mismatch Details   │
                    │        │  {                         │
                    │        │    type: "hash_mismatch"   │
                    │        │    reason: "..."           │
                    │        │    changed_files: [...]    │
                    │        │    stored_hash: "..."      │
                    │        │    current_hash: "..."     │
                    │        │  }                         │
                    │        └────────────────────────────┘
                    │                    │
                    │                    ▼
                    │              STOP ❌
                    │         (Skip version check)
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│         5. Compare Versions (Slow Path, DB Query)                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Read metadata from Neo4j                                   │ │
│  │  metadata_version = "0.9.0"                                 │ │
│  │                                                              │ │
│  │  stored_version == metadata_version?                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Performance: ~20-50ms (DB query)                                │
└─────────────────────────────────────────────────────────────────┘
                    │                    │
                ✅ Match            ❌ Mismatch
                    │                    │
                    ▼                    ▼
            Return None      Return version_mismatch
         (No mismatch)       {
                               type: "version_mismatch"
                               semaphore_version: "1.0.0"
                               metadata_version: "0.9.0"
                               reason: "..."
                             }
```

## Pre-Commit Hook Flow

```
┌─────────────────────────────────────────────────────────────────┐
│               Developer: $ git commit -m "..."                   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         Git: Execute .git/hooks/pre-commit                       │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         Hook: Get Staged Files (git diff --cached)               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Staged files:                                              │ │
│  │    src/relationship_rules/new_rule.py                       │ │
│  │    tests/test_new_rule.py                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│     Hook: Check if Construction Files Changed                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Pattern: "src/relationship_rules/|                         │ │
│  │            src/services/azure_discovery_service.py|         │ │
│  │            src/resource_processor.py|                       │ │
│  │            src/azure_tenant_grapher.py"                     │ │
│  │                                                              │ │
│  │  Match: ✅ src/relationship_rules/new_rule.py               │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                 ┌───────────┴───────────┐
                 │                       │
          ❌ No Match              ✅ Match Found
                 │                       │
                 ▼                       ▼
        Allow Commit       ┌─────────────────────────────┐
        (exit 0)           │  Check if .atg_graph_version│
                           │  is Also Staged             │
                           └─────────────────────────────┘
                                       │
                           ┌───────────┴───────────┐
                           │                       │
                    ✅ YES Staged          ❌ NOT Staged
                           │                       │
                           ▼                       ▼
                  Allow Commit         ┌─────────────────────┐
                  (exit 0)             │  BLOCK Commit       │
                                       │  Show Error:        │
                                       │  ❌ ERROR: Graph    │
                                       │  construction files │
                                       │  changed but        │
                                       │  .atg_graph_version │
                                       │  not updated!       │
                                       │                     │
                                       │  Instructions:      │
                                       │  1. Bump version    │
                                       │  2. Update hash     │
                                       │  3. Update timestamp│
                                       │  4. Add description │
                                       │                     │
                                       │  Or: git commit     │
                                       │      --no-verify    │
                                       └─────────────────────┘
                                               │
                                               ▼
                                        Exit 1 (fail)
                                        Commit blocked ❌
```

## Performance Optimization

```
Traditional Approach (Slow):
┌──────────────────────────────────────┐
│ 1. Query Neo4j metadata    (~50ms)   │
│ 2. Compare versions        (~1ms)    │
│ 3. Return result                     │
│                                      │
│ Total: ~50-100ms                     │
└──────────────────────────────────────┘

Hash-First Approach (Fast):
┌──────────────────────────────────────┐
│ 1. Calculate hash          (~20ms)   │ ← Fast path
│ 2. Compare hashes          (~1ms)    │
│ ↓                                    │
│ If mismatch → STOP                   │ ← Early exit
│ Return changed files                 │
│                                      │
│ 3. Query Neo4j metadata    (~50ms)   │ ← Only if needed
│ 4. Compare versions        (~1ms)    │
│                                      │
│ Total: ~20ms (mismatch case)         │ ← 60% faster!
│        ~70ms (match case)            │
└──────────────────────────────────────┘
```

## Key Benefits

1. **Fast Detection**: Hash check avoids DB query (60% faster)
2. **Precise Reporting**: Shows exactly which files changed
3. **Automatic Enforcement**: Pre-commit hook prevents mistakes
4. **Human Readable**: JSON format is easy to understand
5. **Version Control Friendly**: Git tracks version file changes
6. **Backward Compatible**: Still reads old plain text format

## Common Scenarios

### Scenario 1: Code Changed, Version Updated ✅

```
Developer:
  1. Edit src/relationship_rules/new_rule.py
  2. Update .atg_graph_version (bump version, new hash)
  3. git commit

Pre-commit Hook:
  ✅ Construction files changed: new_rule.py
  ✅ .atg_graph_version also staged
  → Allow commit

Result: ✅ Commit succeeds
```

### Scenario 2: Code Changed, Version NOT Updated ❌

```
Developer:
  1. Edit src/relationship_rules/new_rule.py
  2. (Forgot to update .atg_graph_version)
  3. git commit

Pre-commit Hook:
  ✅ Construction files changed: new_rule.py
  ❌ .atg_graph_version NOT staged
  → Block commit
  → Show instructions

Result: ❌ Commit blocked
```

### Scenario 3: Graph Startup with Outdated Code ❌

```
System Startup:
  1. VersionDetector.detect_mismatch()
  2. Calculate current hash
  3. Compare to stored hash

Detection:
  ❌ Hash mismatch
  → Report: "src/relationship_rules/rule.py modified"
  → Suggest: Rebuild graph

Result: ❌ Warning shown, rebuild suggested
```

### Scenario 4: Graph Startup with Current Code ✅

```
System Startup:
  1. VersionDetector.detect_mismatch()
  2. Calculate current hash
  3. Compare to stored hash
  4. Hashes match → Skip version check

Result: ✅ No warnings, continue normal operation
```
