#!/usr/bin/env python3
"""
Run resource-level fidelity calculation and output results to CSV + terminal.
"""
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config_manager import Neo4jConfig
from src.utils.session_manager import Neo4jSessionManager
from src.validation.resource_fidelity_calculator import (
    RedactionLevel,
    ResourceFidelityCalculator,
)

# ── Configuration ─────────────────────────────────────────────────────────────
SOURCE_SUBSCRIPTION = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
TARGET_SUBSCRIPTION = "ff7d97e0-db31-4969-9a0e-a1e6d19ccc78"
MAPPINGS_FILE       = "output/iteration2_20260219_083319/03_resource_mappings.json"
OUTPUT_CSV          = "output/fidelity_results.csv"

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ── Load mappings ─────────────────────────────────────────────────────────────
with open(MAPPINGS_FILE) as f:
    raw = json.load(f)

resource_mappings = [{"source_id": m["source_id"], "target_id": m["target_id"]} for m in raw]
print(f"Loaded {len(resource_mappings)} resource mappings from {MAPPINGS_FILE}\n")

# ── Run fidelity ──────────────────────────────────────────────────────────────
neo4j_config    = Neo4jConfig(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
session_manager = Neo4jSessionManager(neo4j_config)
session_manager.connect()

try:
    calculator = ResourceFidelityCalculator(
        session_manager=session_manager,
        source_subscription_id=SOURCE_SUBSCRIPTION,
        target_subscription_id=TARGET_SUBSCRIPTION,
    )

    result = calculator.calculate_fidelity_with_mappings(
        resource_mappings=resource_mappings,
        redaction_level=RedactionLevel.FULL,
    )
finally:
    session_manager.disconnect()

# ── Pretty-print summary ──────────────────────────────────────────────────────
m = result.metrics
SEP = "─" * 70

print(SEP)
print("  RESOURCE FIDELITY RESULTS")
print(SEP)
print(f"  {'Total resources compared:':<35} {m.total_resources}")
print(f"  {'Exact match:':<35} {m.exact_match}")
print(f"  {'Drifted:':<35} {m.drifted}")
print(f"  {'Missing in target:':<35} {m.missing_target}")
print(f"  {'Missing in source:':<35} {m.missing_source}")
print(f"  {'Fidelity score:':<35} {m.match_percentage:.1f}%")
print(SEP)

if m.top_mismatched_properties:
    print("\n  Top mismatched properties:")
    for entry in m.top_mismatched_properties:
        print(f"    {entry['property']:<50} {entry['count']:>4} occurrences")
    print()

print(f"\n  {'#':<4}  {'Resource Name':<40}  {'Type':<25}  {'Status':<16}  {'Match':>5}  {'Drift':>5}")
print(f"  {'─'*4}  {'─'*40}  {'─'*25}  {'─'*16}  {'─'*5}  {'─'*5}")
for i, c in enumerate(result.classifications, 1):
    name  = (c.resource_name[:38] + "..") if len(c.resource_name) > 40 else c.resource_name
    rtype = (c.resource_type[:23] + "..") if len(c.resource_type) > 25 else c.resource_type
    print(f"  {i:<4}  {name:<40}  {rtype:<25}  {c.status.value:<16}  {c.match_count:>5}  {c.mismatch_count:>5}")

print(f"\n  Fidelity score: {m.match_percentage:.1f}%")
print(SEP)

# ── Write CSV ─────────────────────────────────────────────────────────────────
Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)

rows = []
for c in result.classifications:
    # One row per resource with summary columns
    base = {
        "resource_name":   c.resource_name,
        "resource_type":   c.resource_type,
        "resource_id":     c.resource_id,
        "status":          c.status.value,
        "source_exists":   c.source_exists,
        "target_exists":   c.target_exists,
        "match_count":     c.match_count,
        "mismatch_count":  c.mismatch_count,
        "total_props":     c.match_count + c.mismatch_count,
    }
    # Flatten mismatched property paths into a semicolon-separated list
    mismatches = [p.property_path for p in c.property_comparisons if not p.match and not p.redacted]
    base["mismatched_properties"] = "; ".join(mismatches) if mismatches else ""
    rows.append(base)

fieldnames = [
    "resource_name", "resource_type", "resource_id",
    "status", "source_exists", "target_exists",
    "match_count", "mismatch_count", "total_props", "mismatched_properties",
]

with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n  CSV saved → {OUTPUT_CSV}  ({len(rows)} rows)")
