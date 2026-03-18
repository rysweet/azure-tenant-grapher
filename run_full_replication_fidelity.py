#!/usr/bin/env python3
"""
Fidelity check for the full replication deployment.

Builds source→target mappings directly from the terraform state file,
handles both :ResourceGroup and :Resource Neo4j labels, and outputs
results to CSV + terminal.
"""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from neo4j import GraphDatabase

# ── Configuration — set via environment variables or .env ─────────────────────
SOURCE_SUBSCRIPTION = os.environ["SOURCE_SUBSCRIPTION"]
TARGET_SUBSCRIPTION = os.environ["TARGET_SUBSCRIPTION"]
TERRAFORM_DIR       = "output/full_replication_20260219_091727/terraform"
OUTPUT_CSV          = "output/full_replication_fidelity.csv"

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

SEP = "─" * 72

# ── Step 1: Extract created Azure resources from terraform state + plan ────────
print(SEP)
print("  STEP 1: Reading terraform state and plan config")
print(SEP)

result = subprocess.run(
    ["terraform", "show", "-json"],
    capture_output=True, text=True, cwd=TERRAFORM_DIR
)
state = json.loads(result.stdout)
tf_resources = state.get("values", {}).get("root_module", {}).get("resources", [])
azure_resources = [r for r in tf_resources if r["type"].startswith("azurerm_")]

# Load the plan config for source-of-truth RG locations
# (Neo4j ResourceGroup nodes don't store location; the plan was generated FROM the source)
with open(f"{TERRAFORM_DIR}/main.tf.json") as f:
    plan_config = json.load(f)
plan_rg_locations = {
    cfg.get("name", key): cfg.get("location", "")
    for key, cfg in plan_config.get("resource", {}).get("azurerm_resource_group", {}).items()
}
plan_sp_names = {
    cfg.get("name", key): key
    for key, cfg in plan_config.get("resource", {}).get("azurerm_service_plan", {}).items()
}
print(f"  Loaded {len(plan_rg_locations)} RG locations from plan config")

print(f"  Total state resources:   {len(tf_resources)}")
print(f"  Azure resources created: {len(azure_resources)}")

# Build target resource list: {tf_type, name, target_id, properties}
target_resources = []
for r in azure_resources:
    vals = r.get("values", {})
    target_resources.append({
        "tf_type":   r["type"],
        "name":      vals.get("name", ""),
        "target_id": vals.get("id", ""),
        "location":  vals.get("location", ""),
        "tags":      vals.get("tags") or {},
        "properties": {k: v for k, v in vals.items()
                       if k not in ("id", "name", "location", "tags",
                                    "timeouts", "password", "admin_password")},
    })

# ── Step 2: Query Neo4j for matching source resources ─────────────────────────
print(f"\n{SEP}")
print("  STEP 2: Querying Neo4j for source resources")
print(SEP)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def query_source_rg(session, name):
    """Look up a source ResourceGroup by name (case-insensitive)."""
    res = session.run("""
        MATCH (r:ResourceGroup)
        WHERE r.subscription_id = $sub
          AND toLower(r.name) = toLower($name)
        RETURN r.id AS id, r.name AS name, r.type AS type,
               r.location AS location, r.tags AS tags
        LIMIT 1
    """, sub=SOURCE_SUBSCRIPTION, name=name)
    row = res.single()
    return dict(row) if row else None

def query_source_resource(session, name, tf_type):
    """Look up a source :Resource by name, trying to match tf_type to Azure type."""
    # Map terraform type → Azure type fragment
    type_map = {
        "azurerm_service_plan": "Microsoft.Web/serverFarms",
        "azurerm_app_service_plan": "Microsoft.Web/serverFarms",
    }
    azure_type = type_map.get(tf_type)
    if azure_type:
        res = session.run("""
            MATCH (r:Resource)
            WHERE r.subscription_id = $sub
              AND toLower(r.name) = toLower($name)
              AND toLower(r.type) = toLower($type)
            RETURN r.id AS id, r.name AS name, r.type AS type,
                   r.location AS location, r.properties AS properties
            LIMIT 1
        """, sub=SOURCE_SUBSCRIPTION, name=name, type=azure_type)
    else:
        res = session.run("""
            MATCH (r:Resource)
            WHERE r.subscription_id = $sub
              AND toLower(r.name) = toLower($name)
            RETURN r.id AS id, r.name AS name, r.type AS type,
                   r.location AS location, r.properties AS properties
            LIMIT 1
        """, sub=SOURCE_SUBSCRIPTION, name=name)
    row = res.single()
    return dict(row) if row else None

def compare_dicts(src, tgt, prefix=""):
    """Recursively compare two dicts, return (matches, mismatches, mismatch_paths)."""
    if not isinstance(src, dict):
        src = {}
    if not isinstance(tgt, dict):
        tgt = {}
    matches, mismatches, paths = 0, 0, []
    all_keys = set(src) | set(tgt)
    for k in all_keys:
        path = f"{prefix}.{k}" if prefix else k
        sv, tv = src.get(k), tgt.get(k)
        if isinstance(sv, dict) or isinstance(tv, dict):
            m, mm, p = compare_dicts(sv or {}, tv or {}, path)
            matches += m; mismatches += mm; paths += p
        else:
            if sv == tv:
                matches += 1
            else:
                mismatches += 1
                paths.append(path)
    return matches, mismatches, paths

# ── Step 3: Build classifications ─────────────────────────────────────────────
print(f"\n{SEP}")
print("  STEP 3: Matching target resources to source and comparing")
print(SEP)

classifications = []

with driver.session() as session:
    for t in target_resources:
        name    = t["name"]
        tf_type = t["tf_type"]

        if tf_type == "azurerm_resource_group":
            source = query_source_rg(session, name)
            if source:
                # Use plan config location as source-of-truth: Neo4j RG nodes lack location
                src_location = plan_rg_locations.get(name, source.get("location", ""))
                src_props = {"location": src_location, "tags": source.get("tags") or {}}
                tgt_props = {"location": t.get("location", ""),       "tags": t.get("tags") or {}}
                matches, mismatches, mismatch_paths = compare_dicts(src_props, tgt_props)
                status = "exact_match" if mismatches == 0 else "drifted"
                classifications.append({
                    "name":       name,
                    "type":       "Microsoft.Resources/resourceGroups",
                    "source_id":  source["id"],
                    "target_id":  t["target_id"],
                    "status":     status,
                    "matches":    matches,
                    "mismatches": mismatches,
                    "mismatch_properties": "; ".join(mismatch_paths),
                })
            else:
                classifications.append({
                    "name":       name,
                    "type":       "Microsoft.Resources/resourceGroups",
                    "source_id":  "",
                    "target_id":  t["target_id"],
                    "status":     "missing_source",
                    "matches":    0,
                    "mismatches": 0,
                    "mismatch_properties": "",
                })
        else:
            source = query_source_resource(session, name, tf_type)
            if source:
                src_props = {}
                raw = source.get("properties")
                if isinstance(raw, str):
                    try:
                        src_props = json.loads(raw)
                    except Exception:
                        pass
                elif isinstance(raw, dict):
                    src_props = raw
                tgt_props = t.get("properties", {})
                matches, mismatches, mismatch_paths = compare_dicts(src_props, tgt_props)
                status = "exact_match" if mismatches == 0 else "drifted"
                classifications.append({
                    "name":       name,
                    "type":       source.get("type", tf_type),
                    "source_id":  source["id"],
                    "target_id":  t["target_id"],
                    "status":     status,
                    "matches":    matches,
                    "mismatches": mismatches,
                    "mismatch_properties": "; ".join(mismatch_paths),
                })
            else:
                classifications.append({
                    "name":       name,
                    "type":       tf_type,
                    "source_id":  "",
                    "target_id":  t["target_id"],
                    "status":     "missing_source",
                    "matches":    0,
                    "mismatches": 0,
                    "mismatch_properties": "",
                })

driver.close()

# ── Step 4: Metrics ───────────────────────────────────────────────────────────
total         = len(classifications)
exact_match   = sum(1 for c in classifications if c["status"] == "exact_match")
drifted       = sum(1 for c in classifications if c["status"] == "drifted")
missing_src   = sum(1 for c in classifications if c["status"] == "missing_source")
missing_tgt   = sum(1 for c in classifications if c["status"] == "missing_target")
fidelity_pct  = (exact_match / total * 100) if total else 0.0

# Top mismatched properties
prop_counts: dict = {}
for c in classifications:
    for p in c["mismatch_properties"].split("; "):
        if p:
            prop_counts[p] = prop_counts.get(p, 0) + 1
top_props = sorted(prop_counts.items(), key=lambda x: x[1], reverse=True)[:10]

# ── Step 5: Pretty-print ──────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  FIDELITY RESULTS — Full Replication Deployment")
print(SEP)
print(f"  {'Total resources compared:':<35} {total}")
print(f"  {'Exact match:':<35} {exact_match}")
print(f"  {'Drifted:':<35} {drifted}")
print(f"  {'Missing in source (new in target):':<35} {missing_src}")
print(f"  {'Missing in target:':<35} {missing_tgt}")
print(f"  {'Fidelity score:':<35} {fidelity_pct:.1f}%")
print(SEP)

if top_props:
    print("\n  Top mismatched properties:")
    for prop, cnt in top_props:
        print(f"    {prop:<50} {cnt:>4} occurrences")

print(f"\n  {'#':<4}  {'Resource Name':<40}  {'Type':<30}  {'Status':<16}  {'Match':>5}  {'Drift':>5}")
print(f"  {'─'*4}  {'─'*40}  {'─'*30}  {'─'*16}  {'─'*5}  {'─'*5}")
for i, c in enumerate(classifications, 1):
    name  = (c["name"][:38]  + "..") if len(c["name"])  > 40 else c["name"]
    rtype = (c["type"][:28]  + "..") if len(c["type"])  > 30 else c["type"]
    print(f"  {i:<4}  {name:<40}  {rtype:<30}  {c['status']:<16}  {c['matches']:>5}  {c['mismatches']:>5}")

print(f"\n  Fidelity score: {fidelity_pct:.1f}%")
print(SEP)

# ── Step 6: Write CSV ─────────────────────────────────────────────────────────
Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)
fieldnames = ["name", "type", "source_id", "target_id", "status",
              "matches", "mismatches", "mismatch_properties"]
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(classifications)

print(f"\n  CSV saved → {OUTPUT_CSV}  ({len(classifications)} rows)")
