"""Fidelity validation for architecture replication deployment.

Compares deployed Terraform resources against source resources from Neo4j
to calculate fidelity metrics: exact_match, drifted, missing.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Configuration
SOURCE_SUBSCRIPTION = "<source-subscription-id>"
TARGET_SUBSCRIPTION = "<target-subscription-id>"
OUTPUT_DIR = "/Users/csiska/repos/azure-tenant-grapher/output/arch_replication_20260222_154009"
TFSTATE_PATH = f"{OUTPUT_DIR}/terraform/terraform.tfstate"
MAPPINGS_PATH = f"{OUTPUT_DIR}/03_resource_mappings.json"
OUTPUT_PATH = f"{OUTPUT_DIR}/05_fidelity_validation.json"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

# Resource group type - excluded from non-RG analysis
RG_TYPE = "azurerm_resource_group"

# Properties to compare for fidelity
COMPARE_PROPERTIES = ["location", "tags"]

# Supplemental target->source name overrides for cases where the deployed name
# differs from the mapping file (e.g. uniqueness suffix was applied at deploy time)
DEPLOYED_NAME_OVERRIDES: Dict[str, str] = {
    "crwdpurpleag4569e1": "crwdpurpleag",
}

# Azure resource type mapping: Terraform type -> Azure provider type segment
TERRAFORM_TYPE_TO_AZURE = {
    "azurerm_application_insights": "Microsoft.Insights/components",
    "azurerm_lb": "Microsoft.Network/loadBalancers",
    "azurerm_monitor_action_group": "Microsoft.Insights/actionGroups",
    "azurerm_private_dns_zone": "Microsoft.Network/privateDnsZones",
    "azurerm_public_ip": "Microsoft.Network/publicIPAddresses",
    "azurerm_storage_account": "Microsoft.Storage/storageAccounts",
    "azurerm_virtual_network": "Microsoft.Network/virtualNetworks",
    "azurerm_subnet": "Microsoft.Network/virtualNetworks/subnets",
    "azurerm_resource_group": "Microsoft.Resources/resourceGroups",
}


def load_tfstate(path: str) -> Dict:
    """Load and return terraform state file."""
    logger.info(f"Loading terraform state from {path}")
    with open(path) as f:
        return json.load(f)


def load_resource_mappings(path: str) -> List[Dict]:
    """Load and return resource mappings file."""
    logger.info(f"Loading resource mappings from {path}")
    with open(path) as f:
        return json.load(f)


def get_deployed_non_rg_resources(tfstate: Dict) -> List[Dict]:
    """Extract all non-resource-group deployed resources from terraform state."""
    resources = []
    for res in tfstate.get("resources", []):
        if res.get("type") == RG_TYPE:
            continue
        if res.get("mode") != "managed":
            continue
        for instance in res.get("instances", []):
            attrs = instance.get("attributes", {})
            resources.append(
                {
                    "tf_type": res["type"],
                    "tf_name": res["name"],
                    "name": attrs.get("name", ""),
                    "location": attrs.get("location", ""),
                    "tags": attrs.get("tags") or {},
                    "resource_group_name": attrs.get("resource_group_name", ""),
                    "id": attrs.get("id", ""),
                    "azure_type": TERRAFORM_TYPE_TO_AZURE.get(res["type"], res["type"]),
                }
            )
    return resources


def query_neo4j_source_resources(uri: str, user: str, password: str, subscription_id: str) -> List[Dict]:
    """Query Neo4j for source resources from the given subscription."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.error("neo4j package not installed. Install with: pip install neo4j")
        sys.exit(1)

    logger.info(f"Querying Neo4j at {uri} for source resources in subscription {subscription_id}")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    results = []

    try:
        with driver.session() as session:
            # Query source resources - try Original label first, fall back to subscription filter
            query = """
            MATCH (r:Resource)
            WHERE r.subscription_id = $subscription_id
            RETURN r.id as id,
                   r.name as name,
                   r.type as type,
                   r.location as location,
                   r.tags as tags,
                   r.resource_group as resource_group,
                   r.subscription_id as subscription_id
            """
            result = session.run(query, subscription_id=subscription_id)
            for record in result:
                tags = record["tags"]
                # Tags may be stored as JSON string in Neo4j
                if isinstance(tags, str):
                    try:
                        tags = json.loads(tags)
                    except (json.JSONDecodeError, TypeError):
                        tags = {}
                if tags is None:
                    tags = {}

                results.append(
                    {
                        "id": record["id"],
                        "name": record["name"],
                        "type": record["type"],
                        "location": record["location"] or "",
                        "tags": tags,
                        "resource_group": record["resource_group"],
                        "subscription_id": record["subscription_id"],
                    }
                )

        logger.info(f"Found {len(results)} source resources in Neo4j")
    finally:
        driver.close()

    return results


def normalize_location(location: str) -> str:
    """Normalize Azure location strings for comparison."""
    if not location:
        return ""
    return location.lower().replace(" ", "")


def normalize_tags(tags: Any) -> Dict:
    """Normalize tags for comparison."""
    if not tags:
        return {}
    if isinstance(tags, str):
        try:
            return json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            return {}
    return dict(tags)


def compare_properties(source: Dict, target: Dict) -> Tuple[str, List[str]]:
    """Compare key properties between source and target resource.

    Returns:
        Tuple of (status, drifted_properties) where status is 'match' or 'drift'
    """
    drifted = []

    # Compare location
    src_loc = normalize_location(source.get("location", ""))
    tgt_loc = normalize_location(target.get("location", ""))
    if src_loc and tgt_loc and src_loc != tgt_loc:
        drifted.append(f"location: '{src_loc}' -> '{tgt_loc}'")

    # Compare tags (check source tags are present in target, ignoring extras)
    src_tags = normalize_tags(source.get("tags", {}))
    tgt_tags = normalize_tags(target.get("tags", {}))

    tag_drifts = []
    for key, src_val in src_tags.items():
        tgt_val = tgt_tags.get(key)
        if tgt_val is None:
            tag_drifts.append(f"tags.{key}: '{src_val}' -> MISSING")
        elif str(src_val).lower() != str(tgt_val).lower():
            tag_drifts.append(f"tags.{key}: '{src_val}' -> '{tgt_val}'")

    drifted.extend(tag_drifts)

    status = "match" if not drifted else "drift"
    return status, drifted


def build_source_lookup(source_resources: List[Dict]) -> Dict[str, Dict]:
    """Build a lookup map of source resources by name (case-insensitive)."""
    lookup = {}
    for r in source_resources:
        name = (r.get("name") or "").lower()
        if name:
            lookup[name] = r
    return lookup


def extract_source_name_from_target(target_name: str, mappings: List[Dict]) -> Optional[str]:
    """Find the source name for a given target resource name using mappings.

    Checks deployed-name overrides first, then the mapping file, then
    falls back to stripping the -replica suffix.
    """
    # Check hardcoded overrides for deploy-time name changes (e.g. uniqueness suffix)
    override = DEPLOYED_NAME_OVERRIDES.get(target_name) or DEPLOYED_NAME_OVERRIDES.get(target_name.lower())
    if override:
        return override

    # Check mappings file
    for m in mappings:
        if m.get("target_name", "").lower() == target_name.lower():
            return m.get("source_name")

    return None


def run_fidelity_validation():
    """Main fidelity validation routine."""
    # Load inputs
    tfstate = load_tfstate(TFSTATE_PATH)
    mappings = load_resource_mappings(MAPPINGS_PATH)

    # Get deployed non-RG resources
    deployed = get_deployed_non_rg_resources(tfstate)
    logger.info(f"Found {len(deployed)} deployed non-RG resources in terraform state")

    # Query Neo4j for source resources
    source_resources = query_neo4j_source_resources(
        NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, SOURCE_SUBSCRIPTION
    )

    # Also include source resources from target subscription that are in the mappings
    # (some resources are replicated within the same target subscription)
    source_resources_target_sub = query_neo4j_source_resources(
        NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TARGET_SUBSCRIPTION
    )

    # Merge: source lookup includes both subscriptions
    all_source_resources = source_resources + source_resources_target_sub
    source_lookup = build_source_lookup(all_source_resources)

    logger.info(f"Total source resources available for lookup: {len(all_source_resources)}")

    # Process each deployed resource
    results = []
    exact_match_count = 0
    drifted_count = 0
    missing_count = 0

    for deployed_res in deployed:
        target_name = deployed_res["name"]

        # Find source name from mappings
        source_name = extract_source_name_from_target(target_name, mappings)

        if source_name is None:
            # Try stripping -replica suffix as fallback
            if target_name.endswith("-replica"):
                source_name = target_name[: -len("-replica")]
            else:
                source_name = target_name

        # Look up source resource
        source_res = source_lookup.get(source_name.lower())

        if source_res is None:
            # Resource not found in source
            status = "missing"
            drifted_props = []
            missing_count += 1
            logger.warning(f"Source resource not found for target '{target_name}' (source name: '{source_name}')")
        else:
            # Compare properties
            status, drifted_props = compare_properties(source_res, deployed_res)
            if status == "match":
                exact_match_count += 1
            else:
                drifted_count += 1

        result_entry = {
            "source_name": source_name,
            "target_name": target_name,
            "tf_type": deployed_res["tf_type"],
            "azure_type": deployed_res["azure_type"],
            "resource_group": deployed_res["resource_group_name"],
            "status": status,
            "drifted_properties": drifted_props,
            "source_location": source_res.get("location", "N/A") if source_res else "N/A",
            "target_location": deployed_res.get("location", "N/A"),
            "source_tags_count": len(normalize_tags(source_res.get("tags"))) if source_res else 0,
            "target_tags_count": len(normalize_tags(deployed_res.get("tags"))),
        }
        results.append(result_entry)

    total = len(results)
    fidelity_score = (exact_match_count / total * 100) if total > 0 else 0.0

    # Build output JSON
    output = {
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_subscription": SOURCE_SUBSCRIPTION,
        "target_subscription": TARGET_SUBSCRIPTION,
        "tfstate_path": TFSTATE_PATH,
        "mappings_path": MAPPINGS_PATH,
        "summary": {
            "total_resources": total,
            "exact_match": exact_match_count,
            "drifted": drifted_count,
            "missing": missing_count,
            "fidelity_score_pct": round(fidelity_score, 1),
        },
        "resources": results,
    }

    # Save results
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"Saved fidelity validation results to {OUTPUT_PATH}")

    # Print summary table
    print("\n" + "=" * 120)
    print("ARCHITECTURE REPLICATION FIDELITY VALIDATION SUMMARY")
    print("=" * 120)
    print(f"{'SOURCE NAME':<40} {'TARGET NAME':<45} {'STATUS':<10} {'DRIFTED PROPERTIES'}")
    print("-" * 120)

    for r in sorted(results, key=lambda x: (x["status"], x["source_name"])):
        source = r["source_name"][:38] if len(r["source_name"]) > 38 else r["source_name"]
        target = r["target_name"][:43] if len(r["target_name"]) > 43 else r["target_name"]
        status = r["status"]
        drifted = "; ".join(r["drifted_properties"]) if r["drifted_properties"] else "-"

        status_display = {
            "match": "MATCH",
            "drift": "DRIFT",
            "missing": "MISSING",
        }.get(status, status.upper())

        print(f"{source:<40} {target:<45} {status_display:<10} {drifted}")

    print("=" * 120)
    print(f"\nSUMMARY METRICS:")
    print(f"  Total resources evaluated : {total}")
    print(f"  Exact match               : {exact_match_count}")
    print(f"  Drifted                   : {drifted_count}")
    print(f"  Missing source            : {missing_count}")
    print(f"  Fidelity score            : {fidelity_score:.1f}%")
    print(f"\nResults saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    run_fidelity_validation()
