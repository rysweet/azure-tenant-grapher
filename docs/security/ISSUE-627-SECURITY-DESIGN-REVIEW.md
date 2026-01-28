# Security Design Review: Tenant Reset Feature (Issue #627)

**Date:** 2026-01-27
**Status:** CRITICAL SECURITY REVIEW REQUIRED BEFORE IMPLEMENTATION
**Risk Level:** EXTREME - This feature DELETES ACTUAL Azure resources and Entra ID objects

---

## Executive Summary

The Tenant Reset feature represents the **highest-risk functionality** in Azure Tenant Grapher. It will perform DESTRUCTIVE operations on production Azure environments, including:

- Deletion of Azure resources (VMs, Storage Accounts, Networks, etc.)
- Removal of Entra ID users, groups, and service principals
- Purging of RBAC role assignments
- Potential for complete tenant wipeout if misconfigured

**This feature requires defense-in-depth security controls to prevent catastrophic data loss.**

---

## 1. Threat Model

### 1.1 Attack Scenarios

#### Scenario 1: Accidental Deletion by Authorized User
**Likelihood:** HIGH
**Impact:** CRITICAL
**Description:** Operator runs reset command with wrong scope parameter, deleting production resources instead of test environment.

**Mitigations Required:**
- Multi-stage confirmation with typed verification
- Dry-run mode showing exact resources to be deleted
- Mandatory delay between confirmation stages (3-5 seconds)
- Resource count display before deletion
- No `--yes` or `--force` flag for automated confirmation

#### Scenario 2: Malicious Insider Deletion
**Likelihood:** MEDIUM
**Impact:** CRITICAL
**Description:** Malicious employee or compromised account intentionally wipes tenant resources.

**Mitigations Required:**
- Comprehensive audit logging (tamper-proof external storage)
- Rate limiting on reset operations (max 1 per hour per tenant)
- Mandatory approval workflow for production tenants
- Detection of anomalous deletion patterns
- Irreversible deletion marker in logs

#### Scenario 3: Configuration Tampering to Bypass ATG SP Preservation
**Likelihood:** MEDIUM
**Impact:** HIGH
**Description:** Attacker modifies `.env` or configuration to change ATG SP Client ID, causing system to delete the actual ATG service principal.

**Mitigations Required:**
- Configuration integrity validation (checksum/hash)
- Read-only ATG SP identification from multiple sources
- Fail-safe: If ATG SP cannot be identified with certainty, abort deletion
- Pre-flight verification: Confirm ATG SP exists before starting deletion
- Post-deletion verification: Confirm ATG SP still exists after completion

#### Scenario 4: API Abuse via Automated Scripts
**Likelihood:** LOW
**Impact:** CRITICAL
**Description:** Attacker gains API access and runs automated deletion loops.

**Mitigations Required:**
- Strict rate limiting (exponential backoff after failures)
- API key rotation and short-lived tokens
- Detection of repeated deletion attempts
- Circuit breaker pattern (auto-disable after N failures)

#### Scenario 5: Credential Theft Leading to Tenant Wipeout
**Likelihood:** MEDIUM
**Impact:** CRITICAL
**Description:** Stolen service principal credentials used to delete all tenant resources.

**Mitigations Required:**
- Principle of least privilege (deletion-only permissions)
- Conditional access policies (IP restrictions, MFA)
- Time-based access windows (credentials only valid during maintenance windows)
- Anomaly detection (deletion outside normal hours)

#### Scenario 6: Race Condition During Deletion
**Likelihood:** LOW
**Impact:** HIGH
**Description:** Multiple concurrent reset operations interfere with each other, causing partial deletion or ATG SP removal.

**Mitigations Required:**
- Distributed lock mechanism (Redis or file-based lock)
- Single-writer pattern for deletion operations
- Idempotency tokens for deletion requests
- State machine with atomic transitions

---

## 2. Authentication & Authorization

### 2.1 Current State Analysis

**Existing Authentication Pattern (from `auth.py`):**
```python
# Service principal authentication via Azure CLI
AZURE_TENANT_ID=<tenant-id>
AZURE_CLIENT_ID=<client-id>
AZURE_CLIENT_SECRET=<client-secret>
```

**Gaps Identified:**
1. No role-based access control within ATG
2. Anyone with `.env` credentials can perform ANY operation
3. No distinction between read-only and destructive operations
4. No approval workflow for high-risk operations

### 2.2 Recommended Authorization Model

#### Option 1: Azure RBAC-Based (RECOMMENDED)
```
ATG_RESET_ALLOWED_PRINCIPALS=principal1@domain.com,sp-reset-operator
ATG_RESET_REQUIRE_APPROVAL=true
ATG_RESET_APPROVER_GROUP=atg-reset-approvers
```

**Advantages:**
- Leverages existing Azure AD infrastructure
- Built-in audit trail via Azure AD sign-in logs
- MFA enforcement available
- Conditional access policies can be applied

**Implementation:**
- Check caller identity using `az account show`
- Verify caller is in allowed principals list
- For production tenants, require approval from approver group

#### Option 2: API Key with Scoped Permissions
```
ATG_API_KEY_READ=<read-only-key>
ATG_API_KEY_DELETE=<delete-permission-key>
```

**Advantages:**
- Simple to implement
- No external dependencies
- Suitable for CI/CD automation

**Disadvantages:**
- Requires secure key management
- No MFA support
- Prone to credential leakage

#### Option 3: Just-In-Time (JIT) Access (BEST PRACTICE)
```
# Credentials expire after 1 hour
ATG_RESET_TOKEN_TTL=3600
# Require fresh token for each reset operation
ATG_RESET_REQUIRE_FRESH_TOKEN=true
```

**Advantages:**
- Minimizes exposure window
- Forces operators to re-authenticate frequently
- Reduces risk from stolen credentials

**Implementation:**
- Issue short-lived SAS tokens for deletion operations
- Token includes scope (subscription, RG, resource)
- Token cannot be reused after expiration

### 2.3 Recommended Approach: Hybrid Model

**Combine all three approaches:**
1. **Azure RBAC** for identity verification
2. **API Keys** for CI/CD automation (read-only only)
3. **JIT tokens** for all destructive operations

---

## 3. ATG Service Principal Preservation

### 3.1 Fail-Safe Logic

**Critical Requirement:** The ATG service principal MUST NEVER be deleted, as it would lock out the system permanently.

#### 3.1.1 Multi-Source Verification

```python
def get_atg_service_principal_id() -> str:
    """
    Identify ATG SP from multiple independent sources.
    If sources disagree, ABORT deletion.
    """
    sources = {
        "env": os.getenv("AZURE_CLIENT_ID"),
        "config": read_config_file("ATG_SP_CLIENT_ID"),
        "azure_cli": subprocess.check_output(["az", "account", "show", "--query", "user.name"]),
        "neo4j": query_neo4j("MATCH (sp:ServicePrincipal {atg_managed: true}) RETURN sp.id")
    }

    # All sources must agree
    unique_values = set(sources.values())
    if len(unique_values) != 1:
        raise SecurityError(
            f"ATG SP ID mismatch across sources: {sources}. "
            "Aborting deletion to prevent loss of access."
        )

    return sources["env"]
```

#### 3.1.2 Pre-Flight Validation

```python
async def validate_atg_sp_before_deletion(tenant_id: str) -> bool:
    """
    Verify ATG SP exists and has correct permissions BEFORE deletion.
    """
    atg_sp_id = get_atg_service_principal_id()

    # 1. Confirm SP exists in Entra ID
    sp = await graph_client.service_principals.get(atg_sp_id)
    if not sp:
        raise SecurityError(f"ATG SP {atg_sp_id} not found. Cannot proceed.")

    # 2. Confirm SP has required roles
    required_roles = ["Contributor", "User Access Administrator"]
    actual_roles = await get_sp_roles(atg_sp_id, tenant_id)

    if not all(role in actual_roles for role in required_roles):
        raise SecurityError(
            f"ATG SP missing required roles. "
            f"Required: {required_roles}, Actual: {actual_roles}"
        )

    # 3. Store SP fingerprint for post-deletion validation
    return {
        "id": atg_sp_id,
        "app_id": sp.app_id,
        "display_name": sp.display_name,
        "roles": actual_roles
    }
```

#### 3.1.3 Post-Deletion Verification

```python
async def verify_atg_sp_after_deletion(fingerprint: dict) -> None:
    """
    Confirm ATG SP still exists after deletion with same properties.
    """
    sp = await graph_client.service_principals.get(fingerprint["id"])

    if not sp:
        # CRITICAL: ATG SP was deleted!
        await emergency_restore_procedure()
        raise SecurityError(
            "CRITICAL: ATG Service Principal was deleted! "
            "Emergency restoration initiated. "
            "Check audit logs immediately."
        )

    # Verify properties match
    if sp.app_id != fingerprint["app_id"]:
        raise SecurityError(f"ATG SP app_id changed from {fingerprint['app_id']} to {sp.app_id}")

    # Verify roles intact
    current_roles = await get_sp_roles(fingerprint["id"], tenant_id)
    if set(current_roles) != set(fingerprint["roles"]):
        await restore_sp_roles(fingerprint["id"], fingerprint["roles"])
        raise SecurityError("ATG SP roles were modified during deletion")
```

#### 3.1.4 Deletion Filter with Multiple Checks

```python
async def filter_safe_deletions(
    resources: List[AzureResource],
    identities: List[EntraIdentity]
) -> Tuple[List[AzureResource], List[EntraIdentity], List[str]]:
    """
    Filter out ATG SP and any resources it depends on.
    Returns: (safe_resources, safe_identities, blocked_items)
    """
    atg_sp_id = get_atg_service_principal_id()
    blocked = []

    # Block 1: ATG SP itself
    safe_identities = [i for i in identities if i.id != atg_sp_id]
    if len(safe_identities) < len(identities):
        blocked.append(f"ServicePrincipal:{atg_sp_id}")

    # Block 2: App registration associated with ATG SP
    atg_app_id = await get_app_registration_for_sp(atg_sp_id)
    safe_identities = [i for i in safe_identities if i.id != atg_app_id]
    if atg_app_id:
        blocked.append(f"AppRegistration:{atg_app_id}")

    # Block 3: Resources managed by ATG (e.g., ATG's own storage account)
    atg_managed_tag = "managed-by:azure-tenant-grapher"
    safe_resources = [r for r in resources if atg_managed_tag not in r.tags]
    blocked_resources = len(resources) - len(safe_resources)
    if blocked_resources > 0:
        blocked.append(f"{blocked_resources} ATG-managed resources")

    # Block 4: RBAC assignments granting ATG SP access
    # (Do NOT delete these or ATG will lose access mid-operation)
    atg_role_assignments = await get_role_assignments_for_sp(atg_sp_id)
    blocked.extend([f"RoleAssignment:{ra.id}" for ra in atg_role_assignments])

    return safe_resources, safe_identities, blocked
```

### 3.2 Configuration Integrity

**Problem:** Attacker modifies `.env` to change `AZURE_CLIENT_ID`, causing system to protect wrong SP.

**Solution: Configuration Hash Validation**

```python
import hashlib
import hmac

def validate_config_integrity(config_file: Path) -> bool:
    """
    Verify configuration hasn't been tampered with.
    Uses HMAC signature stored in separate file.
    """
    config_content = config_file.read_bytes()
    signature_file = config_file.parent / f"{config_file.name}.sig"

    if not signature_file.exists():
        # First run - create signature
        secret = os.urandom(32)  # Store in secure location (Key Vault)
        signature = hmac.new(secret, config_content, hashlib.sha256).hexdigest()
        signature_file.write_text(signature)
        return True

    # Verify signature
    expected_signature = signature_file.read_text().strip()
    secret = get_hmac_secret_from_keyvault()
    actual_signature = hmac.new(secret, config_content, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise SecurityError(
            "Configuration file has been modified! "
            "Aborting deletion to prevent security breach. "
            "Check .env file for unauthorized changes."
        )

    return True
```

---

## 4. Confirmation Security

### 4.1 Multi-Stage Confirmation Flow

**Requirement:** No single action should trigger deletion. Require multiple explicit confirmations.

```python
class TenantResetConfirmation:
    """
    Multi-stage confirmation with security delays and typed verification.
    """

    def __init__(self, scope: ResetScope, tenant_id: str):
        self.scope = scope
        self.tenant_id = tenant_id
        self.resources_to_delete = []
        self.identities_to_delete = []

    async def confirm(self) -> bool:
        """
        Full confirmation flow with security delays.
        """
        # Stage 1: Display scope and get initial confirmation
        if not await self._stage1_scope_confirmation():
            return False

        # Stage 2: Preview resources (with count limits for safety)
        if not await self._stage2_preview_resources():
            return False

        # Stage 3: Typed verification (must type tenant ID)
        if not await self._stage3_typed_verification():
            return False

        # Stage 4: ATG SP preservation acknowledgment
        if not await self._stage4_atg_sp_acknowledgment():
            return False

        # Stage 5: Final confirmation with delay
        if not await self._stage5_final_confirmation_with_delay():
            return False

        return True

    async def _stage1_scope_confirmation(self) -> bool:
        print(f"\n{'='*60}")
        print(f"TENANT RESET - DESTRUCTIVE OPERATION")
        print(f"{'='*60}")
        print(f"Scope: {self.scope}")
        print(f"Tenant: {self.tenant_id}")
        print(f"\nThis will PERMANENTLY DELETE Azure resources and Entra ID objects.")
        print(f"This action CANNOT be undone.")
        print(f"{'='*60}\n")

        response = input("Do you understand this is a PERMANENT DELETION? (yes/no): ")
        return response.lower() == "yes"

    async def _stage2_preview_resources(self) -> bool:
        print("\nFetching resources to be deleted...")
        self.resources_to_delete = await get_resources_in_scope(self.scope)
        self.identities_to_delete = await get_identities_in_scope(self.scope)

        print(f"\nResources to be deleted: {len(self.resources_to_delete)}")
        print(f"Identities to be deleted: {len(self.identities_to_delete)}")

        # Safety check: Abort if scope too large
        if len(self.resources_to_delete) > 1000:
            print("\n❌ ERROR: Scope too large (>1000 resources).")
            print("Use more specific scope (subscription, resource group).")
            return False

        # Display first 20 resources
        print("\nFirst 20 resources:")
        for i, resource in enumerate(self.resources_to_delete[:20], 1):
            print(f"  {i}. {resource.type} - {resource.name}")

        if len(self.resources_to_delete) > 20:
            print(f"  ... and {len(self.resources_to_delete) - 20} more")

        response = input("\nProceed with deletion? (yes/no): ")
        return response.lower() == "yes"

    async def _stage3_typed_verification(self) -> bool:
        print(f"\n⚠️  TYPED VERIFICATION REQUIRED")
        print(f"To confirm, type the tenant ID exactly: {self.tenant_id}")

        response = input("Tenant ID: ")

        if response != self.tenant_id:
            print(f"❌ Tenant ID mismatch. Entered: {response}, Expected: {self.tenant_id}")
            return False

        return True

    async def _stage4_atg_sp_acknowledgment(self) -> bool:
        atg_sp_id = get_atg_service_principal_id()

        print(f"\n🛡️  ATG SERVICE PRINCIPAL PRESERVATION")
        print(f"The following service principal will be PRESERVED:")
        print(f"  Client ID: {atg_sp_id}")
        print(f"  Purpose: Azure Tenant Grapher access")
        print(f"\nIf this SP is deleted, you will lose access to the tenant.")

        response = input("I understand the ATG SP will be preserved (yes/no): ")
        return response.lower() == "yes"

    async def _stage5_final_confirmation_with_delay(self) -> bool:
        print(f"\n⏳ FINAL CONFIRMATION (3 second delay)")
        print(f"This is your last chance to abort.")

        for i in range(3, 0, -1):
            print(f"Proceeding in {i}...")
            await asyncio.sleep(1)

        print("\n❗ FINAL CONFIRMATION")
        response = input("Type 'DELETE' to proceed: ")

        return response == "DELETE"
```

### 4.2 Bypass Prevention

**Threat:** Operator uses `--yes` or `--force` flag to bypass confirmations.

**Mitigation:** NO BYPASS FLAGS ALLOWED for tenant-level resets.

```python
@click.command("reset-tenant")
@click.option("--tenant-id", required=True)
@click.option("--scope", type=click.Choice(["subscription", "resource-group", "resource"]))
@click.option("--dry-run", is_flag=True, help="Preview only, do not delete")
# NO --force or --yes flag!
def reset_tenant(tenant_id: str, scope: str, dry_run: bool):
    """
    Reset Azure tenant by deleting resources and identities.

    SECURITY: No --force flag to prevent bypass of confirmations.
    """
    if dry_run:
        # Dry run can skip confirmations
        preview_deletion(tenant_id, scope)
        return

    # Always require full confirmation flow
    confirmation = TenantResetConfirmation(scope, tenant_id)
    if not asyncio.run(confirmation.confirm()):
        print("Deletion cancelled.")
        return

    # Proceed with deletion
    perform_reset(tenant_id, scope)
```

### 4.3 Race Condition Protection

**Threat:** Two operators start reset operations simultaneously, causing conflicts.

**Mitigation: Distributed Lock**

```python
from redis import Redis
from contextlib import contextmanager

@contextmanager
def tenant_reset_lock(tenant_id: str, timeout: int = 3600):
    """
    Acquire distributed lock for tenant reset operation.
    Prevents concurrent resets on same tenant.
    """
    redis_client = Redis(host='localhost', port=6379)
    lock_key = f"atg:reset:lock:{tenant_id}"

    # Try to acquire lock
    acquired = redis_client.set(
        lock_key,
        "locked",
        nx=True,  # Only set if not exists
        ex=timeout  # Auto-expire after timeout
    )

    if not acquired:
        raise SecurityError(
            f"Tenant reset already in progress for {tenant_id}. "
            "Wait for current operation to complete."
        )

    try:
        yield
    finally:
        # Release lock
        redis_client.delete(lock_key)
```

---

## 5. Audit Trail

### 5.1 Tamper-Proof Logging

**Requirement:** All deletion operations must be logged to **append-only, tamper-proof** storage.

```python
import json
from datetime import datetime, timezone
from typing import Dict, Any

class TamperProofAuditLog:
    """
    Append-only audit log with cryptographic chain.
    Each entry includes hash of previous entry to detect tampering.
    """

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.previous_hash = self._get_last_entry_hash()

    def log_deletion(
        self,
        tenant_id: str,
        scope: ResetScope,
        resources_deleted: List[str],
        identities_deleted: List[str],
        operator: str,
        duration_seconds: float
    ) -> None:
        """
        Log deletion operation with cryptographic chain.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "tenant_reset",
            "tenant_id": tenant_id,
            "scope": str(scope),
            "resources_deleted_count": len(resources_deleted),
            "identities_deleted_count": len(identities_deleted),
            "resources_sample": resources_deleted[:10],  # First 10 for audit
            "identities_sample": identities_deleted[:10],
            "operator": operator,
            "operator_ip": self._get_operator_ip(),
            "duration_seconds": duration_seconds,
            "previous_entry_hash": self.previous_hash,
        }

        # Calculate hash of this entry
        entry_json = json.dumps(entry, sort_keys=True)
        current_hash = hashlib.sha256(entry_json.encode()).hexdigest()
        entry["entry_hash"] = current_hash

        # Append to log file (append-only mode)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Update previous hash for next entry
        self.previous_hash = current_hash

        # Also log to external system (Azure Monitor, Splunk, etc.)
        self._send_to_external_logging(entry)

    def _get_last_entry_hash(self) -> str:
        """
        Get hash of last entry for chain validation.
        """
        if not self.log_file.exists():
            return "0" * 64  # Genesis hash

        with open(self.log_file, "r") as f:
            lines = f.readlines()
            if not lines:
                return "0" * 64

            last_entry = json.loads(lines[-1])
            return last_entry.get("entry_hash", "0" * 64)

    def verify_integrity(self) -> bool:
        """
        Verify audit log hasn't been tampered with.
        Walks entire chain and validates hashes.
        """
        with open(self.log_file, "r") as f:
            lines = f.readlines()

        previous_hash = "0" * 64  # Genesis

        for line in lines:
            entry = json.loads(line)

            # Verify previous hash matches
            if entry["previous_entry_hash"] != previous_hash:
                raise SecurityError(
                    f"Audit log tampered! Entry at {entry['timestamp']} "
                    f"has invalid previous_entry_hash."
                )

            # Recalculate entry hash
            entry_copy = entry.copy()
            stored_hash = entry_copy.pop("entry_hash")
            entry_json = json.dumps(entry_copy, sort_keys=True)
            calculated_hash = hashlib.sha256(entry_json.encode()).hexdigest()

            if stored_hash != calculated_hash:
                raise SecurityError(
                    f"Audit log tampered! Entry at {entry['timestamp']} "
                    f"has invalid entry_hash."
                )

            previous_hash = stored_hash

        return True

    def _send_to_external_logging(self, entry: Dict[str, Any]) -> None:
        """
        Send audit entry to external logging system for redundancy.
        """
        # Azure Monitor example
        try:
            from azure.monitor.ingestion import LogsIngestionClient

            client = LogsIngestionClient(
                endpoint=os.getenv("AZURE_MONITOR_ENDPOINT"),
                credential=DefaultAzureCredential()
            )

            client.upload(
                rule_id=os.getenv("AZURE_MONITOR_RULE_ID"),
                stream_name="Custom-ATG_Audit_CL",
                logs=[entry]
            )
        except Exception as e:
            # Log locally if external logging fails
            logger.error(f"Failed to send audit log to external system: {e}")
```

### 5.2 Audit Log Fields

**Minimum required fields:**
- `timestamp` (UTC ISO 8601)
- `operation` (always "tenant_reset")
- `tenant_id`
- `scope` (tenant, subscription, resource group, resource)
- `resources_deleted_count`
- `identities_deleted_count`
- `resources_sample` (first 10 resource IDs)
- `identities_sample` (first 10 identity IDs)
- `operator` (user principal name or service principal ID)
- `operator_ip` (source IP address)
- `duration_seconds`
- `atg_sp_preserved` (boolean - MUST be true)
- `confirmation_stages_completed` (list of stages: scope, preview, typed, atg_sp, final)
- `entry_hash` (SHA-256 of entry for chain validation)
- `previous_entry_hash` (hash of previous entry for tamper detection)

### 5.3 Audit Log Storage

**Requirements:**
1. **Append-only**: No modification or deletion allowed
2. **Redundant**: Store in at least 2 locations (local + cloud)
3. **Immutable**: Use Azure Blob Storage with immutability policy
4. **Long retention**: Minimum 7 years for compliance

**Recommended Storage:**
```python
# Primary: Local append-only file
AUDIT_LOG_PRIMARY = "/var/log/atg/tenant-reset-audit.jsonl"

# Secondary: Azure Blob Storage with immutability
AUDIT_LOG_BLOB_CONTAINER = "atg-audit-logs"
AUDIT_LOG_BLOB_IMMUTABILITY_DAYS = 2555  # 7 years
```

---

## 6. Rate Limiting

### 6.1 Prevention of Rapid-Fire Deletions

**Threat:** Operator accidentally runs deletion script in loop, or attacker automates deletions.

**Mitigation: Token Bucket Rate Limiter**

```python
import time
from collections import defaultdict
from threading import Lock

class TenantResetRateLimiter:
    """
    Rate limiter for tenant reset operations.
    Prevents rapid-fire deletions using token bucket algorithm.
    """

    def __init__(self):
        self.buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "tokens": 1.0,  # Start with 1 token (allows 1 immediate reset)
            "last_refill": time.time(),
            "max_tokens": 1.0,  # Max 1 token (1 reset per hour)
            "refill_rate": 1.0 / 3600,  # 1 token per hour
        })
        self.lock = Lock()

    def check_rate_limit(self, tenant_id: str) -> Tuple[bool, Optional[float]]:
        """
        Check if tenant reset is allowed under rate limit.

        Returns:
            (allowed, wait_seconds)
            If allowed is False, wait_seconds indicates how long to wait.
        """
        with self.lock:
            bucket = self.buckets[tenant_id]

            # Refill tokens based on time elapsed
            now = time.time()
            elapsed = now - bucket["last_refill"]
            tokens_to_add = elapsed * bucket["refill_rate"]

            bucket["tokens"] = min(
                bucket["max_tokens"],
                bucket["tokens"] + tokens_to_add
            )
            bucket["last_refill"] = now

            # Check if we have enough tokens (need 1 token per reset)
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True, None
            else:
                # Calculate wait time for next token
                tokens_needed = 1.0 - bucket["tokens"]
                wait_seconds = tokens_needed / bucket["refill_rate"]
                return False, wait_seconds

    def record_failure(self, tenant_id: str) -> None:
        """
        Record failed deletion attempt.
        After 3 failures, increase wait time exponentially.
        """
        with self.lock:
            bucket = self.buckets[tenant_id]

            failure_count = bucket.get("failure_count", 0) + 1
            bucket["failure_count"] = failure_count

            # Exponential backoff after repeated failures
            if failure_count >= 3:
                # Double the refill rate (half the speed)
                bucket["refill_rate"] *= 0.5
                bucket["max_tokens"] = 1.0  # Keep max at 1

                print(f"⚠️  WARNING: {failure_count} failed deletion attempts for tenant {tenant_id}")
                print(f"Rate limit increased to {1.0 / bucket['refill_rate'] / 3600:.1f} hours per reset")

# Global rate limiter instance
rate_limiter = TenantResetRateLimiter()

async def reset_tenant(tenant_id: str, scope: ResetScope):
    """
    Reset tenant with rate limiting.
    """
    # Check rate limit
    allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

    if not allowed:
        wait_hours = wait_seconds / 3600
        raise RateLimitError(
            f"Tenant reset rate limit exceeded for {tenant_id}. "
            f"Please wait {wait_hours:.1f} hours before trying again. "
            f"This prevents accidental rapid-fire deletions."
        )

    try:
        # Perform deletion
        await perform_deletion(tenant_id, scope)
    except Exception as e:
        # Record failure for backoff
        rate_limiter.record_failure(tenant_id)
        raise
```

### 6.2 Rate Limit Configuration

```python
# Configuration (environment variables)
ATG_RESET_MAX_PER_HOUR = 1  # Maximum 1 reset per hour per tenant
ATG_RESET_MAX_PER_DAY = 5  # Maximum 5 resets per day per tenant
ATG_RESET_FAILURE_BACKOFF_MULTIPLIER = 2.0  # Double wait time after failures
```

---

## 7. Input Validation

### 7.1 Scope Parameter Validation

**Threat:** Injection attacks via malformed scope parameters.

```python
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class ResetScope:
    """
    Validated reset scope with strict input validation.
    """
    level: str  # "tenant" | "subscription" | "resource-group" | "resource"
    tenant_id: str
    subscription_id: Optional[str] = None
    resource_group: Optional[str] = None
    resource_id: Optional[str] = None

    def __post_init__(self):
        self._validate()

    def _validate(self):
        """
        Validate all scope parameters to prevent injection attacks.
        """
        # Validate level
        valid_levels = {"tenant", "subscription", "resource-group", "resource"}
        if self.level not in valid_levels:
            raise ValueError(f"Invalid scope level: {self.level}. Must be one of {valid_levels}")

        # Validate tenant ID (GUID format)
        if not self._is_valid_guid(self.tenant_id):
            raise ValueError(f"Invalid tenant ID format: {self.tenant_id}")

        # Validate subscription ID if provided
        if self.subscription_id and not self._is_valid_guid(self.subscription_id):
            raise ValueError(f"Invalid subscription ID format: {self.subscription_id}")

        # Validate resource group name if provided
        if self.resource_group:
            if not self._is_valid_resource_group_name(self.resource_group):
                raise ValueError(f"Invalid resource group name: {self.resource_group}")

        # Validate resource ID if provided
        if self.resource_id:
            if not self._is_valid_azure_resource_id(self.resource_id):
                raise ValueError(f"Invalid resource ID format: {self.resource_id}")

        # Validate consistency
        if self.level == "subscription" and not self.subscription_id:
            raise ValueError("Subscription ID required for subscription-level reset")

        if self.level == "resource-group" and not (self.subscription_id and self.resource_group):
            raise ValueError("Subscription ID and resource group required for RG-level reset")

        if self.level == "resource" and not self.resource_id:
            raise ValueError("Resource ID required for resource-level reset")

    @staticmethod
    def _is_valid_guid(value: str) -> bool:
        """Validate GUID format."""
        guid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return re.match(guid_pattern, value) is not None

    @staticmethod
    def _is_valid_resource_group_name(value: str) -> bool:
        """
        Validate resource group name.
        Azure rules: 1-90 chars, alphanumeric, underscore, hyphen, period, parentheses.
        """
        if not (1 <= len(value) <= 90):
            return False

        pattern = r'^[a-zA-Z0-9_\-\.\(\)]+$'
        if not re.match(pattern, value):
            return False

        # Cannot end with period
        if value.endswith('.'):
            return False

        return True

    @staticmethod
    def _is_valid_azure_resource_id(value: str) -> bool:
        """
        Validate Azure resource ID format.
        Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
        """
        pattern = r'^/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[^/]+/providers/[^/]+/[^/]+/[^/]+$'
        return re.match(pattern, value) is not None
```

### 7.2 SQL Injection Prevention (Neo4j)

**Threat:** Cypher injection via unsanitized user input.

```python
async def delete_resources_from_graph(scope: ResetScope) -> None:
    """
    Delete resources from Neo4j graph with parameterized queries.
    """
    # BAD (vulnerable to injection):
    # query = f"MATCH (r:Resource {{tenant_id: '{scope.tenant_id}'}}) DELETE r"

    # GOOD (parameterized):
    query = """
        MATCH (r:Resource {tenant_id: $tenant_id})
        WHERE r.id <> $atg_sp_id
        DELETE r
    """

    params = {
        "tenant_id": scope.tenant_id,
        "atg_sp_id": get_atg_service_principal_id()
    }

    async with get_neo4j_session() as session:
        await session.run(query, params)
```

---

## 8. Error Handling

### 8.1 Secure Error Messages

**Threat:** Error messages leak sensitive information (resource IDs, credentials, internal paths).

```python
class SecureErrorHandler:
    """
    Error handler that sanitizes error messages to prevent information disclosure.
    """

    @staticmethod
    def sanitize_error(error: Exception) -> str:
        """
        Sanitize error message to remove sensitive information.
        """
        message = str(error)

        # Remove Azure resource IDs
        message = re.sub(
            r'/subscriptions/[0-9a-fA-F-]{36}/[^\s]+',
            '/subscriptions/***REDACTED***/...',
            message
        )

        # Remove GUIDs
        message = re.sub(
            r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
            '***GUID***',
            message
        )

        # Remove file paths
        message = re.sub(
            r'/[a-zA-Z0-9_\-/]+',
            '/***PATH***',
            message
        )

        # Remove IP addresses
        message = re.sub(
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            '***IP***',
            message
        )

        return message

    @staticmethod
    def handle_deletion_error(
        error: Exception,
        resource: AzureResource,
        audit_log: TamperProofAuditLog
    ) -> None:
        """
        Handle deletion error securely.
        """
        # Log full error details to audit log (secure storage)
        audit_log.log_error(
            operation="delete_resource",
            resource_id=resource.id,
            error=str(error),
            stack_trace=traceback.format_exc()
        )

        # Display sanitized error to user
        sanitized_error = SecureErrorHandler.sanitize_error(error)
        print(f"❌ Failed to delete resource: {sanitized_error}")
        print(f"Check audit log for full details: {audit_log.log_file}")
```

### 8.2 Partial Failure Recovery

**Threat:** Deletion fails partway through, leaving tenant in inconsistent state.

```python
class DeletionTransaction:
    """
    Transactional deletion with rollback support.
    """

    def __init__(self, scope: ResetScope):
        self.scope = scope
        self.deleted_resources: List[str] = []
        self.deleted_identities: List[str] = []
        self.failed_resources: List[Tuple[str, Exception]] = []

    async def execute(self) -> None:
        """
        Execute deletion with partial failure tracking.
        """
        resources = await get_resources_in_scope(self.scope)
        identities = await get_identities_in_scope(self.scope)

        # Phase 1: Delete resources (continue on failure)
        for resource in resources:
            try:
                await delete_azure_resource(resource)
                self.deleted_resources.append(resource.id)
            except Exception as e:
                self.failed_resources.append((resource.id, e))
                logger.error(f"Failed to delete resource {resource.id}: {e}")

        # Phase 2: Delete identities (only if all resources deleted)
        if self.failed_resources:
            print(f"⚠️  Skipping identity deletion due to {len(self.failed_resources)} failed resource deletions")
        else:
            for identity in identities:
                try:
                    await delete_entra_identity(identity)
                    self.deleted_identities.append(identity.id)
                except Exception as e:
                    logger.error(f"Failed to delete identity {identity.id}: {e}")

        # Phase 3: Report results
        self._report_results()

    def _report_results(self) -> None:
        """
        Report deletion results with recovery instructions.
        """
        print(f"\n{'='*60}")
        print(f"DELETION SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Resources deleted: {len(self.deleted_resources)}")
        print(f"✅ Identities deleted: {len(self.deleted_identities)}")
        print(f"❌ Failed deletions: {len(self.failed_resources)}")

        if self.failed_resources:
            print(f"\n⚠️  PARTIAL FAILURE - Some resources could not be deleted")
            print(f"Failed resources:")
            for resource_id, error in self.failed_resources[:10]:
                sanitized_error = SecureErrorHandler.sanitize_error(error)
                print(f"  - {resource_id}: {sanitized_error}")

            if len(self.failed_resources) > 10:
                print(f"  ... and {len(self.failed_resources) - 10} more")

            print(f"\n🔧 Recovery options:")
            print(f"1. Re-run reset command (will skip already-deleted resources)")
            print(f"2. Manually delete failed resources in Azure Portal")
            print(f"3. Check audit log for full error details")
```

---

## 9. Rollback Capability

### 9.1 Deletion Soft-Delete Pattern

**Concept:** Instead of immediate permanent deletion, use soft-delete pattern with grace period.

```python
class SoftDeleteManager:
    """
    Soft-delete pattern: Mark resources as deleted but retain for recovery period.
    """

    SOFT_DELETE_RETENTION_DAYS = 30

    async def soft_delete_resource(self, resource: AzureResource) -> None:
        """
        Mark resource as soft-deleted in Neo4j and Azure.
        Actual deletion occurs after retention period.
        """
        # 1. Tag resource in Azure with deletion marker
        await self._tag_resource_for_deletion(resource)

        # 2. Mark as soft-deleted in Neo4j
        query = """
            MATCH (r:Resource {id: $resource_id})
            SET r.soft_deleted = true,
                r.soft_deleted_at = datetime(),
                r.soft_delete_expires_at = datetime() + duration({days: $retention_days})
        """

        async with get_neo4j_session() as session:
            await session.run(query, {
                "resource_id": resource.id,
                "retention_days": self.SOFT_DELETE_RETENTION_DAYS
            })

        # 3. Schedule permanent deletion after retention period
        await self._schedule_permanent_deletion(resource.id)

    async def restore_soft_deleted_resource(self, resource_id: str) -> None:
        """
        Restore resource that was soft-deleted (if within retention period).
        """
        # 1. Check if resource is soft-deleted
        query = """
            MATCH (r:Resource {id: $resource_id, soft_deleted: true})
            WHERE r.soft_delete_expires_at > datetime()
            RETURN r
        """

        async with get_neo4j_session() as session:
            result = await session.run(query, {"resource_id": resource_id})
            resource = await result.single()

        if not resource:
            raise ValueError(f"Resource {resource_id} not found or retention period expired")

        # 2. Remove deletion marker
        query = """
            MATCH (r:Resource {id: $resource_id})
            REMOVE r.soft_deleted, r.soft_deleted_at, r.soft_delete_expires_at
        """

        async with get_neo4j_session() as session:
            await session.run(query, {"resource_id": resource_id})

        # 3. Remove deletion tag from Azure resource
        await self._remove_deletion_tag(resource_id)

    async def _tag_resource_for_deletion(self, resource: AzureResource) -> None:
        """
        Tag Azure resource with deletion marker.
        """
        from azure.mgmt.resource import ResourceManagementClient

        client = get_resource_management_client()

        # Add tag indicating soft deletion
        existing_tags = resource.tags or {}
        existing_tags["atg:soft-deleted"] = "true"
        existing_tags["atg:soft-deleted-at"] = datetime.now(timezone.utc).isoformat()

        # Update resource tags
        await client.resources.update_by_id(
            resource.id,
            {"tags": existing_tags}
        )
```

### 9.2 Backup Before Deletion

**Pattern:** Create Neo4j graph snapshot before deletion.

```python
async def backup_graph_before_deletion(tenant_id: str, scope: ResetScope) -> Path:
    """
    Backup Neo4j graph state before deletion.
    Allows restoration if deletion was mistake.
    """
    backup_dir = Path(f"/var/backups/atg/pre-deletion-backups/{tenant_id}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"backup-{timestamp}.cypher"

    # Export affected portion of graph to Cypher statements
    query = """
        MATCH (n)
        WHERE n.tenant_id = $tenant_id
        OPTIONAL MATCH (n)-[r]->()
        RETURN n, r
    """

    async with get_neo4j_session() as session:
        result = await session.run(query, {"tenant_id": tenant_id})

        with open(backup_file, "w") as f:
            f.write(f"// Neo4j Graph Backup - Tenant {tenant_id}\n")
            f.write(f"// Created: {timestamp}\n")
            f.write(f"// Scope: {scope}\n\n")

            async for record in result:
                node = record["n"]
                relationship = record["r"]

                # Export node creation statement
                labels = ":".join(node.labels)
                props = json.dumps(dict(node))
                f.write(f"CREATE (n:{labels} {props})\n")

                # Export relationship if present
                if relationship:
                    rel_type = relationship.type
                    rel_props = json.dumps(dict(relationship))
                    f.write(f"CREATE (n)-[:{rel_type} {rel_props}]->()\n")

    print(f"✅ Graph backup created: {backup_file}")
    print(f"To restore: cypher-shell < {backup_file}")

    return backup_file
```

---

## 10. Security Requirements Summary

### 10.1 MUST HAVE (P0 - Blocking)

| Requirement | Status | Implementation |
|------------|--------|---------------|
| Multi-stage confirmation with typed verification | ❌ NOT IMPLEMENTED | `TenantResetConfirmation` class |
| ATG SP preservation with multi-source verification | ❌ NOT IMPLEMENTED | `get_atg_service_principal_id()` |
| Tamper-proof audit logging | ❌ NOT IMPLEMENTED | `TamperProofAuditLog` class |
| Rate limiting (1 per hour per tenant) | ❌ NOT IMPLEMENTED | `TenantResetRateLimiter` class |
| Input validation (GUID, resource ID format) | ❌ NOT IMPLEMENTED | `ResetScope` dataclass |
| NO --force or --yes flags | ❌ NOT IMPLEMENTED | CLI command definition |
| Pre-flight ATG SP validation | ❌ NOT IMPLEMENTED | `validate_atg_sp_before_deletion()` |
| Post-deletion ATG SP verification | ❌ NOT IMPLEMENTED | `verify_atg_sp_after_deletion()` |
| Distributed lock (prevent concurrent resets) | ❌ NOT IMPLEMENTED | `tenant_reset_lock()` context manager |
| Secure error messages (no information disclosure) | ❌ NOT IMPLEMENTED | `SecureErrorHandler` class |

### 10.2 SHOULD HAVE (P1 - Important)

| Requirement | Status | Implementation |
|------------|--------|---------------|
| Configuration integrity validation | ❌ NOT IMPLEMENTED | `validate_config_integrity()` |
| Soft-delete with 30-day retention | ❌ NOT IMPLEMENTED | `SoftDeleteManager` class |
| Graph backup before deletion | ❌ NOT IMPLEMENTED | `backup_graph_before_deletion()` |
| Exponential backoff after failures | ❌ NOT IMPLEMENTED | Rate limiter failure tracking |
| External audit log redundancy (Azure Monitor) | ❌ NOT IMPLEMENTED | `_send_to_external_logging()` |
| JIT token authentication | ❌ NOT IMPLEMENTED | Token generation service |
| Approval workflow for production tenants | ❌ NOT IMPLEMENTED | Approval service |

### 10.3 COULD HAVE (P2 - Nice to Have)

| Requirement | Status | Implementation |
|------------|--------|---------------|
| Anomaly detection (deletion outside normal hours) | ❌ NOT IMPLEMENTED | ML-based anomaly detector |
| Circuit breaker after N failures | ❌ NOT IMPLEMENTED | Circuit breaker pattern |
| Conditional access policies (IP restrictions) | ❌ NOT IMPLEMENTED | Azure AD configuration |
| Time-based access windows | ❌ NOT IMPLEMENTED | Time-window validator |

---

## 11. Testing Requirements

### 11.1 Security Test Cases

```python
# tests/security/test_tenant_reset_security.py

import pytest
from src.commands.tenant_reset import reset_tenant, TenantResetConfirmation

class TestTenantResetSecurity:
    """
    Security-focused tests for tenant reset feature.
    """

    @pytest.mark.security
    async def test_atg_sp_never_deleted(self):
        """
        CRITICAL: Verify ATG service principal is NEVER deleted.
        """
        atg_sp_id = get_atg_service_principal_id()

        # Perform tenant-level reset
        await reset_tenant(tenant_id="test-tenant", scope="tenant")

        # Verify ATG SP still exists
        sp = await graph_client.service_principals.get(atg_sp_id)
        assert sp is not None, "ATG Service Principal was deleted!"

    @pytest.mark.security
    async def test_no_force_flag_bypass(self):
        """
        Verify --force flag does NOT exist to prevent confirmation bypass.
        """
        from click.testing import CliRunner
        from src.commands.tenant_reset import reset_tenant_command

        runner = CliRunner()
        result = runner.invoke(reset_tenant_command, ["--force"])

        assert result.exit_code != 0, "Force flag should not be supported"
        assert "no such option" in result.output.lower()

    @pytest.mark.security
    async def test_rate_limiting_enforced(self):
        """
        Verify rate limiting prevents rapid-fire deletions.
        """
        tenant_id = "test-tenant"

        # First deletion should succeed
        await reset_tenant(tenant_id=tenant_id, scope="subscription", subscription_id="sub1")

        # Second deletion within 1 hour should fail
        with pytest.raises(RateLimitError) as exc:
            await reset_tenant(tenant_id=tenant_id, scope="subscription", subscription_id="sub2")

        assert "rate limit" in str(exc.value).lower()

    @pytest.mark.security
    async def test_audit_log_tamper_detection(self):
        """
        Verify audit log detects tampering.
        """
        audit_log = TamperProofAuditLog(Path("/tmp/test-audit.log"))

        # Create some log entries
        audit_log.log_deletion(
            tenant_id="tenant1",
            scope=ResetScope(level="tenant", tenant_id="tenant1"),
            resources_deleted=["res1", "res2"],
            identities_deleted=["id1"],
            operator="user@example.com",
            duration_seconds=120.5
        )

        # Tamper with log file
        with open(audit_log.log_file, "r+") as f:
            content = f.read()
            f.seek(0)
            f.write(content.replace("tenant1", "tenant2"))  # Modify entry

        # Verify integrity check fails
        with pytest.raises(SecurityError) as exc:
            audit_log.verify_integrity()

        assert "tampered" in str(exc.value).lower()

    @pytest.mark.security
    async def test_input_validation_prevents_injection(self):
        """
        Verify input validation prevents injection attacks.
        """
        # Test Cypher injection attempt
        with pytest.raises(ValueError):
            ResetScope(
                level="tenant",
                tenant_id="'; DROP ALL; --"
            )

        # Test resource group injection
        with pytest.raises(ValueError):
            ResetScope(
                level="resource-group",
                tenant_id="valid-guid",
                subscription_id="valid-guid",
                resource_group="../../../etc/passwd"
            )

    @pytest.mark.security
    async def test_concurrent_reset_prevented(self):
        """
        Verify distributed lock prevents concurrent resets.
        """
        tenant_id = "test-tenant"

        # Start first reset (with lock held)
        async with tenant_reset_lock(tenant_id):
            # Try to start second reset - should fail
            with pytest.raises(SecurityError) as exc:
                async with tenant_reset_lock(tenant_id):
                    pass

        assert "already in progress" in str(exc.value).lower()

    @pytest.mark.security
    async def test_error_messages_no_information_disclosure(self):
        """
        Verify error messages don't leak sensitive information.
        """
        error = Exception(
            "Failed to delete resource "
            "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-prod-001"
        )

        sanitized = SecureErrorHandler.sanitize_error(error)

        # Verify sensitive info is redacted
        assert "12345678-1234-1234-1234-123456789012" not in sanitized
        assert "rg-prod" not in sanitized
        assert "vm-prod-001" not in sanitized
        assert "***REDACTED***" in sanitized or "***GUID***" in sanitized

    @pytest.mark.security
    async def test_configuration_tampering_detected(self):
        """
        Verify configuration tampering is detected.
        """
        config_file = Path("/tmp/test-config.env")
        config_file.write_text("AZURE_CLIENT_ID=test-id")

        # Initial validation creates signature
        assert validate_config_integrity(config_file) is True

        # Tamper with config
        config_file.write_text("AZURE_CLIENT_ID=malicious-id")

        # Tampering should be detected
        with pytest.raises(SecurityError) as exc:
            validate_config_integrity(config_file)

        assert "modified" in str(exc.value).lower()
```

### 11.2 Penetration Testing Scenarios

1. **Scenario: Bypass ATG SP Preservation**
   - Modify `.env` to change `AZURE_CLIENT_ID`
   - Run reset command
   - Expected: System detects config tampering and aborts

2. **Scenario: Rapid-Fire Deletion Loop**
   - Write script that calls reset API in loop
   - Expected: Rate limiter blocks after 1st attempt

3. **Scenario: Tamper with Audit Log**
   - Modify audit log file to hide deletion
   - Expected: Integrity check fails on next operation

4. **Scenario: Concurrent Reset Operations**
   - Start two reset operations simultaneously
   - Expected: Second operation blocked by distributed lock

5. **Scenario: Injection via Resource Group Name**
   - Provide resource group name: `rg-test'; DROP TABLE resources; --`
   - Expected: Input validation rejects malformed name

---

## 12. Rollout Plan

### Phase 1: Foundation (Week 1-2)
1. Implement `TenantResetConfirmation` multi-stage flow
2. Implement `TamperProofAuditLog` with cryptographic chain
3. Implement `ResetScope` input validation
4. Write security test suite

### Phase 2: ATG SP Protection (Week 3)
1. Implement `get_atg_service_principal_id()` multi-source verification
2. Implement pre-flight and post-deletion validation
3. Implement configuration integrity checking
4. Add ATG SP preservation tests

### Phase 3: Rate Limiting & Locking (Week 4)
1. Implement `TenantResetRateLimiter` token bucket algorithm
2. Implement distributed lock using Redis
3. Add exponential backoff for failures
4. Test concurrent operation prevention

### Phase 4: Error Handling (Week 5)
1. Implement `SecureErrorHandler` message sanitization
2. Implement partial failure recovery
3. Implement soft-delete pattern (optional)
4. Test error scenarios

### Phase 5: Security Review & Penetration Testing (Week 6)
1. External security review by independent team
2. Penetration testing against common attack vectors
3. Fix vulnerabilities identified
4. Update security documentation

### Phase 6: Limited Beta (Week 7-8)
1. Deploy to non-production test tenant
2. Limited user group testing
3. Monitor audit logs for anomalies
4. Collect feedback on UX flow

### Phase 7: Production Release (Week 9+)
1. Final security sign-off
2. Production deployment
3. Monitoring dashboard setup
4. Incident response plan

---

## 13. Incident Response Plan

### 13.1 Accidental Deletion Incident

**Detection:**
- Audit log shows unexpected deletion
- User reports missing resources
- Monitoring alerts on large-scale deletion

**Response:**
1. **Immediate Actions:**
   - Check soft-delete status (if implemented)
   - Locate graph backup file
   - Identify scope of deletion from audit log

2. **Recovery:**
   - Restore from soft-delete if within retention period
   - Restore Neo4j graph from backup
   - Use Azure Resource Manager undelete API (if available)
   - Re-deploy from IaC if available

3. **Post-Incident:**
   - Root cause analysis: Why did confirmation fail?
   - Update confirmation flow to prevent recurrence
   - Document lessons learned

### 13.2 ATG SP Deletion Incident

**Detection:**
- Post-deletion verification fails
- Subsequent ATG operations fail with auth errors
- Monitoring alerts on SP deletion

**Response:**
1. **CRITICAL - Immediate Actions:**
   - Check if SP is soft-deleted (Azure AD recycle bin)
   - Restore SP from Azure AD recycle bin (90-day retention)
   - If permanent deletion:
     - Create new SP with same permissions
     - Update `.env` with new Client ID
     - Re-run authentication setup

2. **Root Cause:**
   - How was ATG SP deleted despite protection?
   - Was configuration tampered with?
   - Was there a bug in preservation logic?

3. **Prevention:**
   - Strengthen multi-source verification
   - Add external monitoring of ATG SP health
   - Implement automated SP backup/recreation

### 13.3 Malicious Deletion Incident

**Detection:**
- Audit log shows deletion outside normal hours
- Deletion from unexpected IP address
- Large-scale deletion without approval

**Response:**
1. **Immediate Actions:**
   - Revoke credentials immediately
   - Enable Azure resource locks
   - Restore from backups
   - Contact security team

2. **Investigation:**
   - Review audit logs for timeline
   - Identify compromised credentials
   - Check for lateral movement
   - Preserve evidence for forensics

3. **Containment:**
   - Rotate all credentials
   - Enable MFA if not already
   - Implement IP whitelisting
   - Review access policies

---

## 14. Recommendations

### 14.1 High Priority (Implement Before Launch)

1. **Multi-Stage Confirmation**: MUST HAVE to prevent accidental deletions
2. **ATG SP Preservation**: MUST HAVE to prevent lockout
3. **Tamper-Proof Audit Log**: MUST HAVE for compliance and forensics
4. **Rate Limiting**: MUST HAVE to prevent abuse
5. **Input Validation**: MUST HAVE to prevent injection attacks
6. **NO --force Flag**: MUST HAVE to prevent confirmation bypass

### 14.2 Medium Priority (Implement Soon After)

1. **Configuration Integrity**: Important for detecting tampering
2. **Soft-Delete Pattern**: Provides recovery window
3. **Graph Backup**: Enables restoration after accidental deletion
4. **External Audit Logging**: Redundancy for tamper-proof logs
5. **JIT Token Authentication**: Reduces credential exposure window

### 14.3 Long-Term Improvements

1. **Anomaly Detection**: ML-based detection of unusual patterns
2. **Approval Workflows**: For production tenant operations
3. **Conditional Access**: IP restrictions, MFA requirements
4. **Circuit Breaker**: Auto-disable after repeated failures

---

## 15. Security Checklist for Implementation

- [ ] Multi-stage confirmation implemented and tested
- [ ] Typed verification (must type tenant ID) implemented
- [ ] NO --force or --yes flag in CLI command
- [ ] ATG SP multi-source verification implemented
- [ ] Pre-flight ATG SP validation implemented
- [ ] Post-deletion ATG SP verification implemented
- [ ] Configuration integrity validation implemented
- [ ] Tamper-proof audit log with cryptographic chain implemented
- [ ] Audit log external redundancy (Azure Monitor) implemented
- [ ] Rate limiter (1 per hour per tenant) implemented
- [ ] Exponential backoff after failures implemented
- [ ] Distributed lock (prevent concurrent resets) implemented
- [ ] Input validation (GUID, resource ID) implemented
- [ ] Cypher query parameterization (prevent injection) implemented
- [ ] Secure error handler (no information disclosure) implemented
- [ ] Partial failure recovery implemented
- [ ] Soft-delete pattern (30-day retention) implemented
- [ ] Graph backup before deletion implemented
- [ ] Security test suite (10+ tests) implemented
- [ ] Penetration testing completed
- [ ] External security review completed
- [ ] Incident response plan documented
- [ ] Monitoring dashboard configured
- [ ] Beta testing in non-production tenant completed

---

## 16. Conclusion

The Tenant Reset feature represents the **highest-risk functionality** in Azure Tenant Grapher. Without proper security controls, it could lead to:

- Catastrophic data loss
- Tenant lockout (if ATG SP deleted)
- Compliance violations
- Unauthorized access and abuse

**This security review identifies 10 MUST-HAVE controls that are BLOCKING for feature launch:**

1. Multi-stage confirmation with typed verification
2. ATG SP preservation with multi-source verification
3. Tamper-proof audit logging
4. Rate limiting (1 per hour per tenant)
5. Input validation (prevent injection)
6. NO --force or --yes flags
7. Pre-flight ATG SP validation
8. Post-deletion ATG SP verification
9. Distributed lock (prevent concurrent resets)
10. Secure error messages (no information disclosure)

**All 10 controls must be implemented and tested before this feature can be safely released to production.**

---

**Document Revision:** 1.0
**Last Updated:** 2026-01-27
**Next Review:** After implementation, before production release
