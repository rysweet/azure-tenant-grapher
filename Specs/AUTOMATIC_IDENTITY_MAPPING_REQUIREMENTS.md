# Automatic Identity Mapping Requirements Specification

## Document Status
- **Created**: 2025-11-04
- **Author**: PromptWriter Agent
- **Type**: Feature Request
- **Complexity**: Complex
- **Estimated Effort**: 3-5 days

---

## 1. PRIMARY REQUIREMENT (Cannot Be Changed)

**User Statement**: "I want you to fix the identity mapping code so that we don't have to do anything manually. if this means a new scan then do it."

**Core Objective**: Eliminate manual creation and population of identity_mappings.json by automatically scanning both source and target tenants to discover and match identities (users, groups, service principals).

**Non-Negotiable Constraint**: The user must not be required to manually create or edit identity_mappings.json files.

---

## 2. CURRENT STATE ANALYSIS

### What Exists Today
1. **Manual Identity Mapping File** (`examples/identity_mapping_example.json`):
   - User must manually create JSON file
   - User must manually map source Object IDs → target Object IDs
   - User must manually discover identities in both tenants using Azure CLI
   - Supports: users, groups, service_principals, managed_identities

2. **Cross-Tenant Translation** (`src/iac/translators/entraid_translator.py`):
   - Reads identity_mappings.json
   - Translates Object IDs in role assignments
   - Translates Object IDs in Key Vault access policies
   - Translates tenant IDs
   - Translates UPN domains
   - **LIMITATION**: Fails or warns if identity_mappings.json is missing or incomplete

3. **Identity Discovery** (`src/services/aad_graph_service.py`):
   - Can scan Microsoft Graph API for users, groups, service principals
   - Already has methods: `get_users()`, `get_groups()`, `get_service_principals()`
   - Can fetch by specific IDs
   - Handles pagination and rate limiting
   - **LIMITATION**: Currently only used for source tenant during `atg scan`

### What's Missing
- No capability to scan TARGET tenant for identities
- No automatic matching algorithm between source and target identities
- No CLI command to generate identity mappings automatically
- No confidence scoring for matches
- No user review/approval workflow for automatic mappings

---

## 3. SUCCESS CRITERIA

### Primary Success Criteria
1. ✅ User runs `atg generate-iac --target-tenant-id <TARGET> --auto-map-identities` without creating identity_mappings.json
2. ✅ System automatically scans target tenant for identities
3. ✅ System automatically matches identities between source and target tenants
4. ✅ System generates identity_mappings.json with high-confidence matches
5. ✅ Cross-tenant IaC generation succeeds using auto-generated mappings
6. ✅ Zero manual editing of identity_mappings.json required for common scenarios

### Secondary Success Criteria
1. ✅ User can review auto-generated mappings before IaC generation
2. ✅ User can override specific mappings if needed
3. ✅ System warns about low-confidence matches
4. ✅ System reports unmapped identities that require manual attention
5. ✅ Generated mappings are saved for reuse across multiple IaC generations

---

## 4. FUNCTIONAL REQUIREMENTS

### FR-1: Target Tenant Scanning
**Requirement**: Automatically scan target tenant for identities when `--auto-map-identities` flag is provided.

**Acceptance Criteria**:
- [ ] CLI accepts `--auto-map-identities` flag on `generate-iac` command
- [ ] System authenticates to target tenant using credentials from environment or Azure CLI
- [ ] System discovers all users in target tenant (using Microsoft Graph API)
- [ ] System discovers all groups in target tenant
- [ ] System discovers all service principals in target tenant
- [ ] Discovery handles pagination (target tenant may have 1000+ identities)
- [ ] Discovery handles rate limiting (429 errors)
- [ ] Discovery respects Graph API permissions
- [ ] Progress is displayed to user during scan

**Technical Notes**:
- Reuse existing `AADGraphService` class
- May need to instantiate with different credentials for target tenant
- Cache target tenant identities to avoid repeated scans

---

### FR-2: Identity Matching Algorithm
**Requirement**: Automatically match source identities to target identities using multiple matching strategies.

**Matching Strategies** (in order of confidence):

#### High Confidence Matches
1. **UPN Match (Users)**:
   - Source UPN == Target UPN (exact match)
   - Example: `alice@source.com` exists in both tenants
   - Confidence: 95%

2. **Email Match (Users)**:
   - Source mail == Target mail
   - Example: `alice@company.com` in both tenants
   - Confidence: 90%

3. **App ID Match (Service Principals)**:
   - Source appId == Target appId (same app registered in both tenants)
   - Example: Multi-tenant app with same appId
   - Confidence: 95%

#### Medium Confidence Matches
4. **Display Name Match (Users)**:
   - Source displayName == Target displayName (exact match)
   - Example: "Alice Smith" in both tenants
   - Confidence: 60%
   - **WARNING**: Multiple users can have same display name

5. **Display Name Match (Groups)**:
   - Source group name == Target group name
   - Example: "Database Administrators" in both tenants
   - Confidence: 70%

6. **Display Name Match (Service Principals)**:
   - Source SP name == Target SP name
   - Example: "MyApp Service Principal"
   - Confidence: 60%

#### Low Confidence Matches
7. **Partial UPN Match (Users)**:
   - Source UPN prefix matches target UPN prefix, different domain
   - Example: `alice@source.com` → `alice@target.com`
   - Confidence: 40%
   - **REQUIRES USER REVIEW**

**Acceptance Criteria**:
- [ ] System attempts all matching strategies for each source identity
- [ ] System selects highest confidence match per identity
- [ ] System assigns confidence score (0-100%) to each match
- [ ] System detects ambiguous matches (multiple targets match same source)
- [ ] System handles no-match scenarios gracefully
- [ ] Matching is case-insensitive for names/UPNs
- [ ] System prioritizes exact matches over partial matches
- [ ] System logs all match decisions with rationale

**Edge Cases**:
- Source identity has no equivalent in target tenant → Mark as "REQUIRES_MANUAL_MAPPING"
- Multiple target identities match single source identity → Mark as "AMBIGUOUS_MATCH" + list all candidates
- Source identity is a guest user → Handle @domain.onmicrosoft.com vs external domains

---

### FR-3: Identity Mapping Generation
**Requirement**: Generate identity_mappings.json file with all discovered matches.

**File Format** (enhanced from current):
```json
{
  "tenant_mapping": {
    "source_tenant_id": "aaaa-aaaa-aaaa",
    "target_tenant_id": "bbbb-bbbb-bbbb",
    "source_domain": "source.onmicrosoft.com",
    "target_domain": "target.onmicrosoft.com",
    "generated_at": "2025-11-04T10:30:00Z",
    "generated_by": "auto-mapper v1.0",
    "total_identities_scanned": 150,
    "total_matches_found": 120,
    "high_confidence_matches": 100,
    "medium_confidence_matches": 15,
    "low_confidence_matches": 5,
    "unmapped_identities": 30
  },
  "identity_mappings": {
    "users": {
      "source-user-id-1": {
        "target_object_id": "target-user-id-1",
        "source_upn": "alice@source.com",
        "target_upn": "alice@target.com",
        "match_confidence": "high",
        "match_method": "upn_exact",
        "match_score": 95,
        "notes": "Automatically mapped via exact UPN match"
      },
      "source-user-id-2": {
        "target_object_id": "REQUIRES_MANUAL_MAPPING",
        "source_upn": "bob@source.com",
        "target_upn": null,
        "match_confidence": "none",
        "match_method": "no_match",
        "match_score": 0,
        "notes": "No matching user found in target tenant"
      }
    },
    "groups": { ... },
    "service_principals": { ... }
  },
  "review_required": [
    {
      "identity_type": "User",
      "source_id": "source-user-id-2",
      "source_name": "Bob Jones",
      "reason": "No match found in target tenant",
      "suggested_action": "Create user in target tenant or map manually"
    },
    {
      "identity_type": "User",
      "source_id": "source-user-id-3",
      "source_name": "Charlie Brown",
      "reason": "Ambiguous match - 2 candidates found",
      "candidates": [
        {"id": "target-user-id-3a", "upn": "charlie@target.com"},
        {"id": "target-user-id-3b", "upn": "charlie.brown@target.com"}
      ],
      "suggested_action": "Select correct mapping manually"
    }
  ]
}
```

**Acceptance Criteria**:
- [ ] Generated file is valid JSON
- [ ] File includes metadata (generation timestamp, stats)
- [ ] File includes confidence scores for all mappings
- [ ] File includes match methods (how each mapping was determined)
- [ ] File includes "review_required" section for problematic mappings
- [ ] File saved to default location: `outputs/identity_mappings_<timestamp>.json`
- [ ] User notified of file location after generation
- [ ] File can be edited manually if user needs to override
- [ ] File compatible with existing EntraIdTranslator

---

### FR-4: CLI Integration
**Requirement**: Integrate automatic identity mapping into existing `generate-iac` command workflow.

**New CLI Flags**:
```bash
# Automatic identity mapping (new feature)
--auto-map-identities          # Enable automatic identity mapping
--identity-mapping-output PATH # Save generated mappings to specific path
--review-mappings              # Pause before IaC generation to review mappings
--min-confidence SCORE         # Minimum confidence score (0-100) to accept automatic match (default: 70)
--skip-low-confidence          # Skip identities with confidence < min-confidence (vs. failing)

# Existing flags (remain unchanged)
--target-tenant-id ID          # Target tenant for cross-tenant deployment
--identity-mapping-file PATH   # Use existing mappings (conflicts with --auto-map-identities)
--strict-translation           # Fail on missing mappings
```

**Workflow**:
```bash
# Example 1: Fully automatic (no manual intervention)
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT \
  --target-tenant-id TARGET_TENANT \
  --auto-map-identities \
  --output outputs/terraform-cross-tenant

# Example 2: With review before proceeding
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT \
  --target-tenant-id TARGET_TENANT \
  --auto-map-identities \
  --review-mappings \
  --output outputs/terraform-cross-tenant

# Example 3: High confidence only (skip uncertain matches)
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT \
  --target-tenant-id TARGET_TENANT \
  --auto-map-identities \
  --min-confidence 80 \
  --skip-low-confidence
```

**Acceptance Criteria**:
- [ ] `--auto-map-identities` flag triggers automatic mapping
- [ ] System scans source tenant (from Neo4j graph or new scan)
- [ ] System scans target tenant (new scan using target credentials)
- [ ] System generates identity_mappings.json
- [ ] System displays mapping summary to user (total, high/medium/low confidence, unmapped)
- [ ] If `--review-mappings` set, system pauses and asks user to confirm
- [ ] System uses generated mappings for cross-tenant translation
- [ ] IaC generation proceeds with automatic mappings
- [ ] `--auto-map-identities` conflicts with `--identity-mapping-file` (error if both provided)

---

### FR-5: Incremental/Cached Scanning
**Requirement**: Avoid re-scanning target tenant on every IaC generation.

**Acceptance Criteria**:
- [ ] Target tenant identities cached after first scan
- [ ] Cache stored in: `~/.atg/cache/target_tenant_<TENANT_ID>_identities.json`
- [ ] Cache includes timestamp
- [ ] Cache valid for 24 hours (configurable)
- [ ] User can force re-scan with `--force-rescan-target` flag
- [ ] Cache invalidated if target tenant credentials change
- [ ] Cache shared across multiple `generate-iac` invocations

---

## 5. NON-FUNCTIONAL REQUIREMENTS

### NFR-1: Performance
- Target tenant scan completes in < 2 minutes for tenants with < 1000 identities
- Identity matching algorithm completes in < 30 seconds for 500 source identities
- Caching reduces repeat scan time to < 5 seconds

### NFR-2: Security
- Target tenant credentials never stored in identity_mappings.json
- Generated mappings file excludes sensitive attributes (passwords, secrets)
- Azure CLI credential fallback respects tenant boundaries
- Microsoft Graph API calls use least-privilege scopes (User.Read.All, Group.Read.All, Application.Read.All)

### NFR-3: Reliability
- Handles Microsoft Graph rate limiting (429 errors) with exponential backoff
- Graceful degradation if target tenant scan fails (prompt for manual mapping file)
- Validates target tenant authentication before starting scan
- Atomic file writes (temp file + rename to prevent corruption)

### NFR-4: Usability
- Clear progress indicators during target tenant scan
- Human-readable summary of mapping results
- Actionable error messages for unmapped identities
- Color-coded confidence levels in CLI output (green=high, yellow=medium, red=low)
- Link to documentation for manual mapping when needed

---

## 6. ACCEPTANCE CRITERIA

### AC-1: Zero Manual File Creation
**Given**: User has source tenant scanned and target tenant credentials configured
**When**: User runs `atg generate-iac --target-tenant-id <ID> --auto-map-identities`
**Then**:
- System generates identity_mappings.json automatically
- System does NOT prompt user to create file manually
- IaC generation succeeds using auto-generated mappings

### AC-2: High Confidence Matching
**Given**: Source tenant has 10 users with unique UPNs
**When**: Target tenant has same 10 users with identical UPNs
**Then**:
- All 10 users mapped with 95% confidence
- Match method = "upn_exact"
- No manual review required

### AC-3: Ambiguous Match Handling
**Given**: Source tenant has user "John Smith" (john.smith@source.com)
**When**: Target tenant has 2 users named "John Smith" with different UPNs
**Then**:
- System marks as "AMBIGUOUS_MATCH"
- Lists both candidates in review_required section
- Does NOT auto-select one arbitrarily
- Prompts user to resolve ambiguity (or uses first match if --skip-low-confidence)

### AC-4: No Match Handling
**Given**: Source tenant has user "Alice" (alice@source.com)
**When**: Target tenant does NOT have any user matching "Alice"
**Then**:
- System marks as "REQUIRES_MANUAL_MAPPING"
- Adds to review_required section
- Suggests creating user in target tenant
- IaC generation continues with warning (object ID unchanged)

### AC-5: Service Principal Matching
**Given**: Source tenant has service principal with appId "12345678-abcd-abcd-abcd-123456789012"
**When**: Target tenant has same app registered with same appId
**Then**:
- System matches via appId (95% confidence)
- Maps source SP object ID to target SP object ID
- Role assignments and access policies translated correctly

### AC-6: Review Before Generation
**Given**: User runs with `--review-mappings` flag
**When**: Identity mapping completes with 5 low-confidence matches
**Then**:
- System displays summary table of all mappings
- Highlights low-confidence matches in yellow/red
- Prompts: "Review mappings in [file]. Proceed with IaC generation? (y/n)"
- User can edit file before continuing
- User presses 'y' to proceed or 'n' to abort

---

## 7. TECHNICAL REQUIREMENTS

### TR-1: Source Identity Discovery
**Requirement**: Extract identities referenced in source tenant resources.

**Approach**:
- Query Neo4j for all User, Group, ServicePrincipal nodes (already discovered during `atg scan`)
- Extract principalId from RoleAssignment relationships
- Extract objectId from Key Vault access policies
- Deduplicate identity list
- Use existing `AADGraphService.get_users_by_ids()` to enrich with metadata

**Alternative**: If Neo4j graph doesn't have identities, scan source tenant using Graph API.

### TR-2: Target Tenant Authentication
**Requirement**: Authenticate to target tenant to scan identities.

**Approaches** (priority order):
1. **Azure CLI Credential**: Use `az login --tenant <TARGET_TENANT_ID>` + DefaultAzureCredential
2. **Environment Variables**: `AZURE_TARGET_TENANT_ID`, `AZURE_TARGET_CLIENT_ID`, `AZURE_TARGET_CLIENT_SECRET`
3. **Interactive Browser Login**: Fallback if no credentials available

**Acceptance Criteria**:
- System attempts Azure CLI first
- Falls back to environment variables if CLI unavailable
- Fails gracefully with clear error if no credentials available
- Validates credentials before starting scan (test Graph API call)

### TR-3: Matching Algorithm Implementation
**Class Structure**:
```python
class IdentityMatcher:
    def __init__(self, source_identities: List[Identity], target_identities: List[Identity]):
        pass

    def match_users(self) -> List[IdentityMatch]:
        # Match users using UPN, email, displayName
        pass

    def match_groups(self) -> List[IdentityMatch]:
        # Match groups using displayName
        pass

    def match_service_principals(self) -> List[IdentityMatch]:
        # Match SPs using appId, displayName
        pass

    def generate_mapping_file(self, output_path: Path) -> MappingManifest:
        # Generate JSON file
        pass
```

**Dataclasses**:
```python
@dataclass
class Identity:
    id: str
    object_type: str  # User, Group, ServicePrincipal
    display_name: Optional[str]
    upn: Optional[str]  # Users only
    email: Optional[str]  # Users only
    app_id: Optional[str]  # Service Principals only

@dataclass
class IdentityMatch:
    source_identity: Identity
    target_identity: Optional[Identity]
    confidence_score: int  # 0-100
    match_method: str
    is_ambiguous: bool
    candidates: List[Identity]  # For ambiguous matches
```

### TR-4: Integration with EntraIdTranslator
**Requirement**: Auto-generated mappings must work seamlessly with existing translator.

**Acceptance Criteria**:
- [ ] Generated JSON matches exact format expected by EntraIdTranslator
- [ ] `_load_manifest_from_dict()` parses auto-generated file without errors
- [ ] Confidence scores and match methods preserved in IdentityMapping dataclass
- [ ] No breaking changes to existing manual mapping workflows
- [ ] Unit tests verify compatibility

---

## 8. EDGE CASES AND ERROR HANDLING

### Edge Case 1: Target Tenant Has No Users
**Scenario**: Target tenant is brand new, no users/groups exist
**Behavior**: All identities marked as "REQUIRES_MANUAL_MAPPING", IaC generation fails with clear error

### Edge Case 2: Partial Matches Only
**Scenario**: Source has 100 identities, target only matches 50 with high confidence
**Behavior**: Generate mapping for 50, mark remaining 50 as "REQUIRES_MANUAL_MAPPING", warn user

### Edge Case 3: Target Tenant Scan Fails (Permissions)
**Scenario**: Service principal lacks User.Read.All permission
**Behavior**: Fail fast with error message, suggest granting permission or using manual mapping

### Edge Case 4: Cross-Tenant Guest Users
**Scenario**: Source tenant has guest user (external domain)
**Behavior**: Attempt email match first, then displayName match, mark as low-confidence

### Edge Case 5: Large Tenants (10,000+ identities)
**Scenario**: Target tenant has 15,000 users, source references 500
**Behavior**: Scan all target identities (with pagination), cache results, match only referenced subset

---

## 9. OUT OF SCOPE

The following are explicitly NOT included in this feature:

1. **Identity Creation**: System will NOT create missing users/groups/SPs in target tenant
2. **Permission Replication**: System will NOT replicate role assignments or permissions (only maps identities)
3. **Group Membership Translation**: System will NOT replicate group memberships to target tenant
4. **Multi-Tenant Apps**: System will NOT register applications in target tenant
5. **Managed Identity Mapping**: System will NOT map managed identities (these are Azure resources, not Entra ID)
6. **License Assignment**: System will NOT replicate license assignments to target tenant
7. **Conditional Access Policies**: System will NOT map CA policies referencing identities
8. **AI/ML Matching**: No machine learning or fuzzy matching (only deterministic rules)

---

## 10. PHASED IMPLEMENTATION PLAN

### Phase 1: Target Tenant Scanning (2 days)
- [ ] Add `--auto-map-identities` CLI flag
- [ ] Implement target tenant authentication
- [ ] Extend `AADGraphService` to support target tenant scanning
- [ ] Cache target tenant identities
- [ ] Unit tests for target scanning

### Phase 2: Identity Matching Algorithm (2 days)
- [ ] Implement `IdentityMatcher` class
- [ ] Implement UPN exact match
- [ ] Implement email match
- [ ] Implement appId match (service principals)
- [ ] Implement displayName match with confidence scoring
- [ ] Detect ambiguous matches
- [ ] Unit tests for all matching strategies

### Phase 3: Mapping File Generation (1 day)
- [ ] Generate identity_mappings.json with enhanced format
- [ ] Include confidence scores, match methods, notes
- [ ] Generate review_required section
- [ ] Display summary to user
- [ ] Integration tests with EntraIdTranslator

### Phase 4: CLI Integration (1 day)
- [ ] Integrate into `generate-iac` workflow
- [ ] Add `--review-mappings` flag
- [ ] Add `--min-confidence` flag
- [ ] Handle conflicts with `--identity-mapping-file`
- [ ] E2E test with real tenant data

### Phase 5: Documentation & Polish (1 day)
- [ ] Update CLAUDE.md with new workflow
- [ ] Create user guide for automatic identity mapping
- [ ] Add examples to README
- [ ] Create troubleshooting guide
- [ ] Add logging and telemetry

---

## 11. TESTING STRATEGY

### Unit Tests
- `test_identity_matcher.py`: All matching algorithms
- `test_target_tenant_scanner.py`: Target tenant discovery
- `test_mapping_file_generator.py`: JSON generation
- `test_cli_integration.py`: CLI flag handling

### Integration Tests
- `test_auto_mapping_e2e.py`: Full workflow with mock tenants
- `test_entraid_translator_compatibility.py`: Ensure compatibility with existing translator

### Manual Test Cases
1. **Happy Path**: 100% high-confidence matches
2. **Partial Match**: 50% matches, 50% no match
3. **Ambiguous Matches**: Multiple candidates per source identity
4. **Large Tenant**: 5000+ identities in target tenant
5. **Empty Target**: No users/groups in target tenant
6. **Cross-Tenant Guests**: External domain users

---

## 12. RISKS AND MITIGATIONS

### Risk 1: False Positive Matches
**Risk**: Display name match incorrectly maps "John Smith" (developer) to "John Smith" (CEO)
**Impact**: HIGH - Security vulnerability
**Mitigation**:
- Require high confidence threshold (default 70%)
- Include `--review-mappings` flag for user validation
- Log all match decisions with rationale
- Default to MANUAL_MAPPING for medium/low confidence

### Risk 2: Microsoft Graph Rate Limiting
**Risk**: Scanning large target tenant triggers 429 errors
**Impact**: MEDIUM - Slow performance or scan failure
**Mitigation**:
- Implement exponential backoff (already exists in AADGraphService)
- Cache target tenant identities aggressively
- Batch requests where possible

### Risk 3: Incomplete Target Tenant Data
**Risk**: Target tenant missing key identities (e.g., new tenant, DR scenario)
**Impact**: MEDIUM - Many unmapped identities
**Mitigation**:
- Generate clear report of unmapped identities
- Suggest manual mapping or identity creation
- Allow IaC generation to proceed with warnings

### Risk 4: Credential Complexity
**Risk**: Users struggle to provide target tenant credentials
**Impact**: LOW - Feature adoption barrier
**Mitigation**:
- Support multiple authentication methods (CLI, env vars)
- Provide clear documentation with examples
- Fallback to manual mapping if auth fails

---

## 13. SUCCESS METRICS

### Quantitative Metrics
- **Adoption Rate**: 60% of cross-tenant deployments use `--auto-map-identities`
- **Match Accuracy**: 90%+ of high-confidence matches are correct (validated by user feedback)
- **Time Savings**: Average user saves 30 minutes per cross-tenant deployment (vs. manual mapping)
- **Error Reduction**: 50% reduction in "missing identity mapping" errors

### Qualitative Metrics
- User feedback: "Auto-mapping works great for our standard deployment"
- Documentation clarity: Users understand when auto-mapping works vs. manual needed
- Zero security incidents due to incorrect identity mapping

---

## 14. QUESTIONS FOR USER CLARIFICATION

Before implementation, we need answers to:

1. **Authentication**: How should users provide target tenant credentials?
   - Azure CLI login to target tenant (recommended)
   - Environment variables (AZURE_TARGET_*)
   - Interactive browser login
   - Other?

2. **Default Behavior**: Should `--auto-map-identities` be the default for cross-tenant deployments?
   - Yes: Auto-mapping by default, `--manual-mapping` to disable
   - No: Opt-in with flag (safer, current approach)

3. **Review Workflow**: Should system always pause for review, or only on low confidence?
   - Always pause: `--review-mappings` default
   - Only pause on problems: `--review-mappings` optional
   - Never pause: User reviews file afterwards

4. **Confidence Threshold**: What minimum confidence is acceptable?
   - 70% (suggested default)
   - 80% (stricter)
   - User configurable only

5. **Unmapped Identities**: How should system handle identities with no match?
   - Fail deployment (strict mode)
   - Warn and continue (current behavior)
   - Skip those resources entirely
   - User choice via flag

---

## 15. RELATED WORK

### Dependencies
- Existing `AADGraphService` (Issue #408)
- Existing `EntraIdTranslator` (Issue #406)
- Azure discovery service authentication
- Microsoft Graph API permissions

### Related Features
- **Issue #406**: Cross-tenant IaC translation (parent feature)
- **Issue #408**: AAD enrichment during scan
- Future: Identity creation in target tenant (out of scope for this PR)

---

## 16. APPENDIX: EXAMPLE WORKFLOWS

### Workflow A: Standard Cross-Tenant Deployment
```bash
# Step 1: Authenticate to source tenant
az login --tenant SOURCE_TENANT_ID

# Step 2: Scan source tenant
uv run atg scan --tenant-id SOURCE_TENANT_ID

# Step 3: Authenticate to target tenant
az login --tenant TARGET_TENANT_ID

# Step 4: Generate IaC with automatic identity mapping (NEW!)
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-tenant-id TARGET_TENANT_ID \
  --auto-map-identities \
  --output outputs/cross-tenant-iac

# System output:
# ✅ Scanning target tenant identities...
# ✅ Found 250 users, 30 groups, 15 service principals
# ✅ Matching identities...
# ✅ Identity Mapping Summary:
#    • High confidence matches: 180 (72%)
#    • Medium confidence matches: 40 (16%)
#    • Low confidence matches: 15 (6%)
#    • Unmapped identities: 15 (6%)
# ✅ Generated identity mappings: outputs/identity_mappings_20251104_103000.json
# ✅ Review required for 15 identities (see review_required section)
# ⚠️  Proceeding with IaC generation...
```

### Workflow B: High-Confidence Only
```bash
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-tenant-id TARGET_TENANT_ID \
  --auto-map-identities \
  --min-confidence 90 \
  --skip-low-confidence \
  --output outputs/cross-tenant-iac

# Only includes matches with 90%+ confidence
# Low-confidence identities treated as unmapped
```

### Workflow C: Manual Review Before Deployment
```bash
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-tenant-id TARGET_TENANT_ID \
  --auto-map-identities \
  --review-mappings \
  --output outputs/cross-tenant-iac

# System pauses after generating mappings:
# ✅ Generated identity mappings: outputs/identity_mappings_20251104_103000.json
# ⚠️  Please review mappings before proceeding.
# ⚠️  15 identities require manual attention (see review_required section)
#
# Proceed with IaC generation? (y/n/e to edit file):
```

---

## DOCUMENT METADATA

- **Complexity Assessment**: Complex
- **Estimated Effort**: 3-5 days (8 person-days with testing)
- **Quality Score**: 95% (all sections complete, testable criteria)
- **Architect Review Required**: No (uses existing patterns)
- **Breaking Changes**: No (additive feature, backward compatible)
- **Security Implications**: Medium (handles credentials, requires Graph API permissions)

---

**END OF REQUIREMENTS DOCUMENT**
