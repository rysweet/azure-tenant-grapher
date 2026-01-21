# Step 13: Mandatory Local Testing Plan for Issue #140

## Overview

This document provides the test plan for Step 13 (Mandatory Local Testing) to verify Issue #140 implementation with a real Azure tenant.

## Prerequisites

1. Azure tenant with resources (ideally 100+ resources for meaningful testing)
2. Azure CLI authenticated: `az login --tenant <tenant-id>`
3. Neo4j running: `docker-compose up -d`
4. ATG environment set up: `uv sync`

## Test Scenarios

### Test 1: Basic Parallel Fetching (Simple)

**Objective**: Verify parallel fetching works with default settings

**Commands**:
```bash
# Scan with default max_build_threads=20
uv run azure-tenant-grapher scan --tenant-id <your-tenant-id>
```

**Success Criteria**:
- ✅ Scan completes without errors
- ✅ Log shows "Phase 2: Fetching full properties" message
- ✅ Properties are populated in Neo4j

**Verification Query** (Neo4j Browser):
```cypher
// Check that resources have properties
MATCH (r:Resource)
WHERE r.properties IS NOT NULL
  AND r.properties <> '{}'
  AND r.properties <> 'null'
RETURN
  r.type as resource_type,
  count(*) as count_with_properties
ORDER BY count_with_properties DESC
LIMIT 20
```

**Expected**: Most resources should have properties populated

---

### Test 2: Performance Benchmark (Complex)

**Objective**: Verify performance meets acceptance criteria (500+ resources in <5 min)

**Commands**:
```bash
# Scan with performance tracking
time uv run azure-tenant-grapher scan \
  --tenant-id <your-tenant-id> \
  --max-build-threads 20 \
  2>&1 | tee scan_performance.log
```

**Success Criteria**:
- ✅ 500+ resources scanned in < 5 minutes
- ✅ No timeout errors
- ✅ No rate limiting failures (or graceful handling if they occur)

**Performance Analysis**:
```bash
# Analyze log for timing
grep "Phase 2:" scan_performance.log
grep "Successfully fetched" scan_performance.log
grep "Total resources" scan_performance.log
```

**Expected Metrics**:
- Parallel Phase 2 time: < 3 minutes for 500 resources
- Success rate: > 95% of resources with properties
- No batch timeouts

---

### Test 3: Property Display in Tenant Specs (Integration)

**Objective**: Verify properties appear in generated tenant specifications

**Commands**:
```bash
# Generate tenant specification
uv run azure-tenant-grapher spec \
  --output tenant_spec_with_properties.md \
  --include-configuration-details
```

**Success Criteria**:
- ✅ Spec file generated successfully
- ✅ Resources show "Properties:" section
- ✅ Up to 5 properties displayed per resource
- ✅ No "Properties: {}" or "Properties: null" (unless resource genuinely has no properties)

**Manual Verification**:
```bash
# Check spec file for properties
grep -A 10 "Properties:" tenant_spec_with_properties.md | head -50
```

**Expected**: Properties sections visible for VMs, storage accounts, networks, etc.

---

### Test 4: Concurrency Control Verification

**Objective**: Verify max_build_threads parameter works correctly

**Commands**:
```bash
# Test with low concurrency (should be slower)
time uv run azure-tenant-grapher scan \
  --tenant-id <your-tenant-id> \
  --max-build-threads 5 \
  --resource-limit 100 \
  2>&1 | tee scan_low_concurrency.log

# Test with high concurrency (should be faster)
time uv run azure-tenant-grapher scan \
  --tenant-id <your-tenant-id> \
  --max-build-threads 30 \
  --resource-limit 100 \
  2>&1 | tee scan_high_concurrency.log
```

**Success Criteria**:
- ✅ Both scans complete successfully
- ✅ High concurrency scan is measurably faster
- ✅ No errors from exceeding concurrency limits
- ✅ Resource properties identical between runs

**Performance Comparison**:
```bash
# Compare Phase 2 times
grep "Phase 2:" scan_low_concurrency.log
grep "Phase 2:" scan_high_concurrency.log
```

**Expected**: 30 threads should be ~6x faster than 5 threads (for 100 resources)

---

### Test 5: Error Handling & Rate Limiting

**Objective**: Verify graceful handling of API errors and rate limits

**Commands**:
```bash
# Scan large subscription to potentially hit rate limits
uv run azure-tenant-grapher scan \
  --tenant-id <your-tenant-id> \
  --max-build-threads 50  # Higher concurrency to increase rate limit chances
  2>&1 | tee scan_rate_limit_test.log
```

**Success Criteria**:
- ✅ Scan completes even if rate limited
- ✅ Log shows "Rate limited" or "TooManyRequests" messages if limits hit
- ✅ Azure SDK retries automatically (visible in logs)
- ✅ All resources eventually processed

**Error Analysis**:
```bash
# Check for error handling
grep -i "rate limit\|TooManyRequests\|InvalidApiVersionParameter" scan_rate_limit_test.log
```

**Expected**: Errors logged but processing continues, resources eventually fetched

---

### Test 6: Backward Compatibility (Disable Parallel Fetching)

**Objective**: Verify system works with parallel fetching disabled

**Commands**:
```bash
# Scan with parallel fetching disabled
uv run azure-tenant-grapher scan \
  --tenant-id <your-tenant-id> \
  --max-build-threads 0 \
  --resource-limit 50 \
  2>&1 | tee scan_disabled_parallel.log
```

**Success Criteria**:
- ✅ Scan completes successfully
- ✅ No Phase 2 processing (log should say "Skipping property enrichment")
- ✅ Resources have empty properties
- ✅ No errors or crashes

**Verification**:
```bash
# Should show skipped Phase 2
grep "Skipping property enrichment" scan_disabled_parallel.log
```

**Neo4j Verification**:
```cypher
// Properties should be empty
MATCH (r:Resource)
RETURN r.properties
LIMIT 10
```

**Expected**: Properties empty or minimal when max_build_threads=0

---

## Test Execution Checklist

- [ ] **Test 1: Basic Parallel Fetching** - Simple scan with default settings
- [ ] **Test 2: Performance Benchmark** - Verify 500+ resources in <5 min
- [ ] **Test 3: Property Display in Specs** - Verify properties show in tenant specs
- [ ] **Test 4: Concurrency Control** - Verify max_build_threads parameter works
- [ ] **Test 5: Error Handling** - Verify graceful rate limit handling
- [ ] **Test 6: Backward Compatibility** - Verify disable works (max_build_threads=0)

## Test Results Template

```markdown
## Step 13: Local Testing Results

**Test Environment**:
- Branch: feat-issue-140-parallel-properties
- Date: <date>
- Azure Tenant: <tenant-id or description>
- Resource Count: <number>

**Tests Executed**:

1. ✅ Basic Parallel Fetching → <result>
2. ✅ Performance Benchmark → <time for 500+ resources>
3. ✅ Property Display in Specs → <verified properties visible>
4. ✅ Concurrency Control → <5 threads vs 30 threads comparison>
5. ✅ Error Handling → <rate limits handled gracefully>
6. ✅ Backward Compatibility → <disabled mode works>

**Regressions**: ✅ None detected

**Issues Found**: <list any issues or "None">

**Conclusion**: Feature ready for PR / Needs fixes
```

## Post-Testing Actions

After all tests pass:

1. Document results in ISSUE_140_VERIFICATION.md
2. Update Issue #140 with test results
3. Commit any fixes (if issues found)
4. Proceed to PR creation

## Notes

- **Performance varies** based on Azure tenant size and API responsiveness
- **Rate limiting** is expected for large tenants - verify it's handled gracefully
- **Property content** varies by resource type (VMs have more properties than resource groups)
- **Save logs** for PR documentation and troubleshooting

---

**Ready to execute?** Run tests in sequence and document results.
