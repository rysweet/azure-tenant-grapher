# Security Summary: Tenant Reset Feature (Issue #627)

**Risk Level:** EXTREME (Deletes actual Azure resources and Entra ID objects)

## Executive Summary

The Tenant Reset feature will perform DESTRUCTIVE operations that can lead to:
- Complete tenant wipeout if misconfigured
- Permanent data loss
- System lockout if ATG service principal is deleted
- Compliance violations without proper audit trails

**STATUS: 10 BLOCKING security controls must be implemented before release.**

---

## Critical Security Controls (MUST HAVE)

### 1. Multi-Stage Confirmation ✋
- **What:** 5-stage confirmation flow with typed verification
- **Why:** Prevent accidental deletions
- **How:** User must type tenant ID exactly, acknowledge ATG SP preservation, wait 3 seconds, type "DELETE"
- **Status:** ❌ Not Implemented

### 2. ATG Service Principal Preservation 🛡️
- **What:** NEVER delete the service principal used by ATG
- **Why:** Would permanently lock out system from tenant
- **How:** Multi-source verification (env, config, Azure CLI, Neo4j), pre/post-deletion validation
- **Status:** ❌ Not Implemented

### 3. Tamper-Proof Audit Logging 📝
- **What:** Cryptographic chain of audit log entries
- **Why:** Compliance, forensics, accountability
- **How:** Each entry includes hash of previous entry (blockchain-like), stored append-only
- **Status:** ❌ Not Implemented

### 4. Rate Limiting ⏱️
- **What:** Maximum 1 reset per hour per tenant
- **Why:** Prevent rapid-fire accidental deletions or API abuse
- **How:** Token bucket algorithm with exponential backoff after failures
- **Status:** ❌ Not Implemented

### 5. Input Validation 🔒
- **What:** Strict validation of all scope parameters
- **Why:** Prevent injection attacks (Cypher, SQL)
- **How:** GUID format validation, Azure resource ID validation, whitelist patterns
- **Status:** ❌ Not Implemented

### 6. NO --force Flag 🚫
- **What:** Explicitly NO --force or --yes flag in CLI
- **Why:** Prevent confirmation bypass
- **How:** Remove flag from Click command definition
- **Status:** ❌ Not Implemented

### 7. Pre-Flight ATG SP Validation ✅
- **What:** Verify ATG SP exists BEFORE starting deletion
- **Why:** Fail-safe to prevent proceeding if SP already missing
- **How:** Check SP in Entra ID, verify permissions, store fingerprint
- **Status:** ❌ Not Implemented

### 8. Post-Deletion ATG SP Verification ✔️
- **What:** Confirm ATG SP still exists AFTER deletion
- **Why:** Detect if SP was accidentally deleted
- **How:** Compare fingerprint, trigger emergency restore if missing
- **Status:** ❌ Not Implemented

### 9. Distributed Lock 🔐
- **What:** Prevent concurrent reset operations on same tenant
- **Why:** Race conditions could cause ATG SP deletion or partial failures
- **How:** Redis-based distributed lock with timeout
- **Status:** ❌ Not Implemented

### 10. Secure Error Messages 🤐
- **What:** Sanitize error messages to prevent information disclosure
- **Why:** Error messages could leak resource IDs, credentials, internal paths
- **How:** Regex-based sanitization (remove GUIDs, IDs, paths)
- **Status:** ❌ Not Implemented

---

## Threat Model Summary

### Top 5 Threats

1. **Accidental Deletion by Authorized User** (HIGH likelihood, CRITICAL impact)
   - Operator runs command with wrong scope
   - Mitigations: Multi-stage confirmation, dry-run mode, resource preview

2. **Malicious Insider Deletion** (MEDIUM likelihood, CRITICAL impact)
   - Compromised account wipes tenant
   - Mitigations: Audit logging, rate limiting, approval workflow

3. **Configuration Tampering → ATG SP Deletion** (MEDIUM likelihood, HIGH impact)
   - Attacker modifies `.env` to bypass SP preservation
   - Mitigations: Configuration integrity validation, multi-source verification

4. **API Abuse via Automation** (LOW likelihood, CRITICAL impact)
   - Stolen credentials used in deletion script loop
   - Mitigations: Rate limiting, circuit breaker, anomaly detection

5. **Race Condition During Deletion** (LOW likelihood, HIGH impact)
   - Concurrent operations interfere with each other
   - Mitigations: Distributed lock, single-writer pattern

---

## Authentication & Authorization Recommendations

### Recommended: Hybrid Model

1. **Azure RBAC** for identity verification
   - Leverages existing Azure AD infrastructure
   - MFA and conditional access available
   - Built-in audit trail

2. **JIT Tokens** for destructive operations
   - Short-lived tokens (1 hour expiration)
   - Token includes scope (subscription, RG, resource)
   - Forces re-authentication

3. **API Keys** for CI/CD (read-only only)
   - Automation support
   - Separate keys for read vs. delete operations

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- Multi-stage confirmation flow
- Tamper-proof audit logging
- Input validation
- Security test suite

### Phase 2: ATG SP Protection (Week 3)
- Multi-source verification
- Pre/post-flight validation
- Configuration integrity

### Phase 3: Rate Limiting & Locking (Week 4)
- Token bucket rate limiter
- Distributed lock (Redis)
- Exponential backoff

### Phase 4: Error Handling (Week 5)
- Secure error handler
- Partial failure recovery
- Soft-delete pattern (optional)

### Phase 5: Security Review (Week 6)
- External security review
- Penetration testing
- Vulnerability fixes

### Phase 6: Beta Testing (Week 7-8)
- Deploy to test tenant
- Limited user group
- Monitor audit logs

### Phase 7: Production (Week 9+)
- Final security sign-off
- Production deployment
- Incident response plan

---

## Testing Requirements

### Minimum Security Tests

1. `test_atg_sp_never_deleted` - Verify ATG SP preservation
2. `test_no_force_flag_bypass` - Verify no --force flag
3. `test_rate_limiting_enforced` - Verify rate limits work
4. `test_audit_log_tamper_detection` - Verify tamper-proof logs
5. `test_input_validation_prevents_injection` - Verify injection prevention
6. `test_concurrent_reset_prevented` - Verify distributed lock
7. `test_error_messages_no_information_disclosure` - Verify error sanitization
8. `test_configuration_tampering_detected` - Verify config integrity

### Penetration Testing Scenarios

1. Bypass ATG SP preservation via config tampering
2. Rapid-fire deletion loop
3. Tamper with audit log
4. Concurrent reset operations
5. Injection via resource group name

---

## Incident Response Plans

### Accidental Deletion
1. Check soft-delete status
2. Restore from graph backup
3. Use Azure Resource Manager undelete
4. Re-deploy from IaC

### ATG SP Deletion (CRITICAL)
1. Restore from Azure AD recycle bin (90-day retention)
2. If permanent: Create new SP, update config, re-run auth setup
3. Root cause: How was protection bypassed?

### Malicious Deletion
1. Revoke credentials immediately
2. Enable resource locks
3. Restore from backups
4. Contact security team, preserve evidence

---

## Go/No-Go Checklist

**DO NOT RELEASE until all items checked:**

- [ ] Multi-stage confirmation implemented and tested
- [ ] ATG SP preservation implemented and tested
- [ ] Tamper-proof audit log implemented and tested
- [ ] Rate limiting implemented and tested
- [ ] Input validation implemented and tested
- [ ] NO --force flag (verified in CLI)
- [ ] Pre-flight ATG SP validation implemented
- [ ] Post-deletion ATG SP verification implemented
- [ ] Distributed lock implemented and tested
- [ ] Secure error handler implemented and tested
- [ ] Security test suite (8+ tests) passes
- [ ] Penetration testing completed with no HIGH findings
- [ ] External security review completed
- [ ] Incident response plan documented
- [ ] Beta testing completed in non-production tenant

---

## Key Takeaways

1. **This is the HIGHEST-RISK feature in ATG** - requires defense-in-depth security
2. **ATG SP preservation is CRITICAL** - system lockout if deleted
3. **Multi-stage confirmation is NON-NEGOTIABLE** - prevents accidental deletions
4. **Audit logging is MANDATORY** - compliance and forensics requirement
5. **No shortcuts allowed** - all 10 MUST-HAVE controls required before release

---

**For detailed analysis, see:** `ISSUE-627-SECURITY-DESIGN-REVIEW.md`

**Document Version:** 1.0
**Last Updated:** 2026-01-27
**Next Review:** After implementation, before production release
