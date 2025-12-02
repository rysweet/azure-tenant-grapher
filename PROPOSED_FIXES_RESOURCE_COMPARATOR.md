# Proposed Code Fixes for resource_comparator.py

**Based on Root Cause Analysis**
**Target File**: `/home/azureuser/src/azure-tenant-grapher/src/iac/resource_comparator.py`

---

## Fix #1: Improved Fallback Strategy with Heuristic Name Cleaning

**Location**: Lines 283-341 (`_get_original_azure_id` method)

**Problem**: When SCAN_SOURCE_NODE is missing, the fallback uses transformed abstracted IDs that don't match target scan IDs.

**Solution**: Add heuristic logic to attempt to reverse-engineer the original name from the abstracted ID.

### Implementation

```python
def _get_original_azure_id(
    self, abstracted_resource: Dict[str, Any]
) -> Optional[str]:
    """
    Get original Azure ID by querying SCAN_SOURCE_NODE relationship.

    If relationship doesn't exist, attempts heuristic cleanup of abstracted ID
    to match against target scan.

    Args:
        abstracted_resource: Resource from abstracted graph

    Returns:
        Original Azure resource ID, or best-effort cleaned ID if not found
    """
    abstracted_id = abstracted_resource.get("id")
    if not abstracted_id:
        logger.warning(
            f"Abstracted resource missing 'id' field: {abstracted_resource}"
        )
        return None

    # Check if resource already has original_id property (optimization)
    if "original_id" in abstracted_resource:
        original_id = abstracted_resource["original_id"]
        if original_id:
            logger.debug(
                f"Using cached original_id for {abstracted_id}: {original_id}"
            )
            return original_id

    # Query Neo4j for SCAN_SOURCE_NODE relationship
    query = """
    MATCH (abs:Resource {id: $abstracted_id})
    MATCH (abs)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
    RETURN orig.id AS original_id
    LIMIT 1
    """

    try:
        with self.session_manager.session() as session:
            result = session.run(query, {"abstracted_id": abstracted_id})
            record = result.single()

            if record and record.get("original_id"):
                original_id = record["original_id"]
                logger.debug(
                    f"Found original ID for {abstracted_id}: {original_id}"
                )
                return original_id
            else:
                logger.debug(
                    f"No SCAN_SOURCE_NODE relationship found for {abstracted_id}, "
                    "attempting heuristic cleanup"
                )
                # FALLBACK: Attempt heuristic cleanup of abstracted ID
                return self._heuristic_clean_abstracted_id(abstracted_id)

    except Exception as e:
        logger.warning(
            f"Error querying SCAN_SOURCE_NODE for {abstracted_id}: {e}, "
            "attempting heuristic cleanup",
            exc_info=True,
        )
        # FALLBACK: Attempt heuristic cleanup of abstracted ID
        return self._heuristic_clean_abstracted_id(abstracted_id)


def _heuristic_clean_abstracted_id(self, abstracted_id: str) -> str:
    """
    Attempt to clean abstracted ID back to original Azure ID format.

    Abstracted IDs often have patterns like:
    - Suffix: resource_name_abc123_def456 → resource-name
    - Underscores: my_resource → my-resource (Azure convention)

    This is a HEURISTIC approach and may not work for all resource types.
    The proper fix is to ensure SCAN_SOURCE_NODE relationships exist.

    Args:
        abstracted_id: Abstracted resource ID with transformed name

    Returns:
        Best-effort cleaned ID
    """
    import re

    # Split ID into parts
    parts = abstracted_id.split("/")
    if len(parts) < 2:
        logger.warning(
            f"Cannot clean abstracted ID (unexpected format): {abstracted_id}"
        )
        return abstracted_id

    # Extract resource name (last part of ID)
    resource_name = parts[-1]
    original_name = resource_name

    # Pattern 1: Remove suffix pattern _hexhex_hexhex (e.g., _a9c787_f05ca8)
    # This is added by abstraction process to make names unique
    cleaned_name = re.sub(r'_[a-f0-9]{6}_[a-f0-9]{6}$', '', resource_name)

    if cleaned_name != resource_name:
        logger.debug(
            f"Removed hex suffix: {resource_name} → {cleaned_name}"
        )
        original_name = cleaned_name

    # Pattern 2: Replace underscores with hyphens (Azure naming convention)
    # BUT: Only if we removed a suffix (otherwise we might break valid names)
    if original_name != resource_name:
        hyphen_name = original_name.replace('_', '-')
        if hyphen_name != original_name:
            logger.debug(
                f"Replaced underscores: {original_name} → {hyphen_name}"
            )
            original_name = hyphen_name

    # Rebuild ID with cleaned name
    if original_name != resource_name:
        parts[-1] = original_name
        cleaned_id = "/".join(parts)
        logger.info(
            f"Heuristic cleanup applied: {abstracted_id} → {cleaned_id} "
            "(SCAN_SOURCE_NODE missing - this is a FALLBACK approach)"
        )
        return cleaned_id

    # No cleanup possible - return original
    logger.debug(
        f"No heuristic cleanup applied to {abstracted_id} "
        "(no patterns matched)"
    )
    return abstracted_id
```

---

## Fix #2: Enhanced Logging for Diagnostics

**Location**: Lines 183-281 (`_classify_abstracted_resource` method)

**Problem**: When classification fails, we don't know WHY it failed (which ID was used, whether it was in target map, etc.)

**Solution**: Add detailed debug logging to show the comparison process.

### Implementation

```python
def _classify_abstracted_resource(
    self,
    abstracted_resource: Dict[str, Any],
    target_resource_map: Dict[str, TargetResource],
) -> ResourceClassification:
    """
    Classify a single abstracted resource by comparing with target.

    Args:
        abstracted_resource: Resource from abstracted graph
        target_resource_map: Map of target resources by ID

    Returns:
        ResourceClassification for this resource
    """
    abstracted_id = abstracted_resource.get("id", "unknown")

    # Step 1: Get original Azure ID via SCAN_SOURCE_NODE or fallback to abstracted ID
    original_id = self._get_original_azure_id(abstracted_resource)

    # Bug #16 fix: If no original_id (SCAN_SOURCE_NODE missing), use abstracted ID
    # In cross-tenant mode, we'll normalize it anyway
    if not original_id:
        original_id = abstracted_resource.get("id")
        if not original_id:
            # No ID at all - classify as NEW (safe default)
            logger.debug(
                f"No ID found for abstracted resource {abstracted_id}, "
                "classifying as NEW"
            )
            return ResourceClassification(
                abstracted_resource=abstracted_resource,
                target_resource=None,
                classification=ResourceState.NEW,
            )
        logger.debug(
            f"Using abstracted ID as fallback for {abstracted_id} "
            "(SCAN_SOURCE_NODE not found)"
        )

    # Step 2: Normalize ID for cross-tenant comparison (Bug #13 fix)
    # In cross-tenant mode, replace source subscription with target subscription
    normalized_id = self._normalize_resource_id_for_comparison(original_id)

    # Bug #111: Check if normalized_id is None before calling .lower()
    if not normalized_id:
        logger.warning(
            f"Normalized ID is None for resource {abstracted_id}, classifying as NEW"
        )
        return ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=None,
            classification=ResourceState.NEW,
        )

    # NEW: Enhanced logging for diagnostics
    logger.debug(
        f"Classifying resource:\n"
        f"  Abstracted ID:  {abstracted_id}\n"
        f"  Original ID:    {original_id}\n"
        f"  Normalized ID:  {normalized_id}\n"
        f"  Target map key: {normalized_id.lower()}\n"
        f"  In target map:  {normalized_id.lower() in target_resource_map}"
    )

    # Step 3: Find in target scan (case-insensitive)
    target_resource = target_resource_map.get(normalized_id.lower())

    if not target_resource:
        # Resource not found in target - it's NEW
        logger.debug(
            f"Resource {abstracted_id} not found in target scan, classifying as NEW\n"
            f"  Original ID: {original_id}\n"
            f"  Normalized ID: {normalized_id}\n"
            f"  Lookup key: {normalized_id.lower()}\n"
            f"  Available target IDs (sample): {list(target_resource_map.keys())[:5]}"
        )
        return ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=None,
            classification=ResourceState.NEW,
        )

    # Step 3: Compare properties
    property_differences = self._compare_properties(
        abstracted_resource, target_resource
    )

    if not property_differences:
        # Properties match - EXACT_MATCH
        logger.debug(
            f"Resource {abstracted_id} matches target exactly, classifying as "
            "EXACT_MATCH"
        )
        return ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=target_resource,
            classification=ResourceState.EXACT_MATCH,
        )
    else:
        # Properties differ - DRIFTED
        logger.debug(
            f"Resource {abstracted_id} has {len(property_differences)} property "
            "differences, classifying as DRIFTED"
        )
        drift_details = {"property_differences": property_differences}
        return ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=target_resource,
            classification=ResourceState.DRIFTED,
            drift_details=drift_details,
        )
```

---

## Fix #3: Validation Warning in compare_resources

**Location**: Lines 83-150 (`compare_resources` method)

**Problem**: No warning when an unusually high number of resources are classified as NEW (indicates SCAN_SOURCE_NODE issue).

**Solution**: Add validation check after classification to detect potential issues.

### Implementation

```python
def compare_resources(
    self,
    abstracted_resources: List[Dict[str, Any]],
    target_scan: TargetScanResult,
) -> ComparisonResult:
    """
    Compare abstracted graph resources with target scan.

    This method performs the core comparison logic:
    1. For each abstracted resource, find its original Azure ID via SCAN_SOURCE_NODE
    2. Match against target scan resources
    3. Classify as NEW, EXACT_MATCH, or DRIFTED
    4. Detect ORPHANED resources in target but not in abstracted graph

    Args:
        abstracted_resources: Resources from abstracted graph
        target_scan: Result of target tenant scan

    Returns:
        ComparisonResult with classifications and summary

    Note:
        Never raises exceptions - all errors are logged and resources
        are classified as NEW (safe default) on errors.
    """
    logger.info(
        f"Starting resource comparison: {len(abstracted_resources)} abstracted "
        f"resources vs {len(target_scan.resources)} target resources"
    )

    classifications: List[ResourceClassification] = []
    matched_target_ids = set()  # Track which target resources we've matched

    # Build lookup map of target resources by ID (case-insensitive)
    target_resource_map = self._build_target_resource_map(target_scan.resources)

    # Process each abstracted resource
    for abstracted_resource in abstracted_resources:
        classification = self._classify_abstracted_resource(
            abstracted_resource, target_resource_map
        )
        classifications.append(classification)

        # Track matched target resources
        if classification.target_resource:
            # Bug #111: Ensure id is not None before calling .lower()
            if classification.target_resource.id:
                matched_target_ids.add(
                    classification.target_resource.id.lower()
                )  # Case-insensitive

    # Detect orphaned resources (in target but not in abstracted graph)
    orphaned_classifications = self._detect_orphaned_resources(
        target_scan.resources, matched_target_ids
    )
    classifications.extend(orphaned_classifications)

    # Generate summary
    summary = self._generate_summary(classifications)

    # NEW: Validation check for suspicious classification patterns
    self._validate_classification_summary(summary, len(abstracted_resources))

    logger.info(
        f"Resource comparison complete: {summary[ResourceState.NEW.value]} new, "
        f"{summary[ResourceState.EXACT_MATCH.value]} exact matches, "
        f"{summary[ResourceState.DRIFTED.value]} drifted, "
        f"{summary[ResourceState.ORPHANED.value]} orphaned"
    )

    return ComparisonResult(classifications=classifications, summary=summary)


def _validate_classification_summary(
    self, summary: Dict[str, int], total_resources: int
) -> None:
    """
    Validate classification summary for suspicious patterns.

    Logs warnings if classification ratios indicate potential issues like
    missing SCAN_SOURCE_NODE relationships.

    Args:
        summary: Classification summary counts
        total_resources: Total number of abstracted resources
    """
    if total_resources == 0:
        return

    new_count = summary.get(ResourceState.NEW.value, 0)
    exact_match_count = summary.get(ResourceState.EXACT_MATCH.value, 0)
    drifted_count = summary.get(ResourceState.DRIFTED.value, 0)

    new_percentage = (new_count / total_resources) * 100
    matched_count = exact_match_count + drifted_count
    matched_percentage = (matched_count / total_resources) * 100

    # Expected: Most resources should match (EXACT_MATCH or DRIFTED)
    # NEW resources should be < 50% in most scenarios

    if new_percentage > 50.0:
        logger.warning(
            f"SUSPICIOUS CLASSIFICATION PATTERN DETECTED:\n"
            f"  {new_count}/{total_resources} ({new_percentage:.1f}%) classified as NEW\n"
            f"  {matched_count}/{total_resources} ({matched_percentage:.1f}%) classified as EXACT_MATCH/DRIFTED\n"
            f"\n"
            f"This may indicate:\n"
            f"  1. SCAN_SOURCE_NODE relationships are missing/broken in the graph\n"
            f"  2. Target scan is incomplete or from different environment\n"
            f"  3. Resource ID normalization issues\n"
            f"\n"
            f"RECOMMENDED ACTIONS:\n"
            f"  1. Run diagnostic query:\n"
            f"     MATCH (abs:Resource:Abstracted)\n"
            f"     WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->(:Resource:Original)\n"
            f"     RETURN abs.type, count(*) as missing_count\n"
            f"     ORDER BY missing_count DESC\n"
            f"  2. Verify target scan completed successfully\n"
            f"  3. Check logs for 'heuristic cleanup' messages\n"
            f"\n"
            f"See ROOT_CAUSE_ANALYSIS_SMART_IMPORT.md for details"
        )

    if new_percentage > 90.0:
        logger.error(
            f"CRITICAL: {new_percentage:.1f}% of resources classified as NEW. "
            f"This will likely cause false positives/negatives in smart import. "
            f"Investigation required before proceeding."
        )
```

---

## Fix #4: Add Method to Extract Resource Name from ID

**Location**: Add new helper method around line 555

**Purpose**: Utility method to extract resource name from Azure resource ID.

### Implementation

```python
def _extract_resource_name_from_id(self, resource_id: str) -> Optional[str]:
    """
    Extract resource name from Azure resource ID.

    Azure resource IDs have format:
    /subscriptions/{sub}/resourceGroups/{rg}/providers/{type}/{name}

    Args:
        resource_id: Azure resource ID

    Returns:
        Resource name, or None if ID format is invalid
    """
    if not resource_id:
        return None

    parts = resource_id.split("/")
    if len(parts) < 2:
        return None

    # Resource name is typically the last part
    return parts[-1]
```

---

## Summary of Changes

| Fix | Priority | Impact | Complexity |
|-----|----------|--------|------------|
| Fix #1: Heuristic ID cleanup | **HIGH** | Mitigates false positives/negatives | Medium |
| Fix #2: Enhanced logging | **MEDIUM** | Enables debugging | Low |
| Fix #3: Validation warnings | **MEDIUM** | Detects issues early | Low |
| Fix #4: Helper method | **LOW** | Code quality | Low |

---

## Testing Checklist

After implementing these fixes:

- [ ] Run unit tests: `pytest tests/iac/test_resource_comparator.py -v`
- [ ] Run with enhanced logging: `export LOG_LEVEL=DEBUG`
- [ ] Check for "heuristic cleanup" messages in logs
- [ ] Check for "SUSPICIOUS CLASSIFICATION" warnings
- [ ] Verify classification summary shows < 50% NEW resources
- [ ] Run diagnostic Neo4j query to check SCAN_SOURCE_NODE relationships

---

## Important Notes

⚠️ **These fixes are MITIGATIONS, not solutions**:
- The root cause is missing SCAN_SOURCE_NODE relationships
- These fixes attempt to work around that issue
- The proper fix is to ensure relationships exist in the graph

✅ **Immediate Benefits**:
- Better diagnostics (logging)
- Early warning system (validation)
- Fallback strategy (heuristic cleanup)

🔧 **Long-term Solution Required**:
- Fix graph abstraction process to create SCAN_SOURCE_NODE relationships
- See ROOT_CAUSE_ANALYSIS_SMART_IMPORT.md section "Fix #1"

Arrr, implement these fixes and ye should see fewer false positives and negatives! 🏴‍☠️
