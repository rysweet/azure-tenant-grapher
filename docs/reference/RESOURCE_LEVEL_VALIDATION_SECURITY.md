# Resource-Level Validation Security Guide

Security best practices for handling sensitive data in fidelity validation reports.

## Sensitive Data in Azure Resources

Azure resources contain various types of sensitive information that must be protected:

### Critical Secrets (Always Redacted)

**Passwords and credentials:**
- Database passwords
- VM admin passwords
- Service account credentials
- Certificate private keys

**Access keys:**
- Storage account keys
- Container registry passwords
- Cosmos DB keys
- Redis cache access keys

**Tokens and secrets:**
- SAS tokens
- API keys
- Webhook secrets
- Application secrets

### Connection Strings (Redaction Level Dependent)

**Database connection strings:**
- SQL Server connection strings
- MySQL connection strings
- PostgreSQL connection strings
- MongoDB connection strings

**Service connection strings:**
- Service Bus connection strings
- Event Hub connection strings
- Storage connection strings
- IoT Hub connection strings

### Certificates and Cryptographic Material

- SSL/TLS certificates (private keys only)
- SSH keys
- Encryption keys
- Signing certificates

## Redaction Levels

### FULL Redaction (Default - Recommended)

**What is redacted:**
- All passwords, keys, secrets, tokens
- All connection strings (entire string)
- Certificate private keys
- Any property path containing: `password`, `key`, `secret`, `token`, `connectionString`, `certificate`

**What is preserved:**
- Resource names and IDs
- SKUs and tiers
- Locations and regions
- Tags (except sensitive tags)
- Configuration booleans
- Public endpoints (without credentials)

**When to use:**
- Production validation reports
- Reports shared outside security team
- Compliance audit documentation
- Long-term report storage

**Example output:**
```json
{
  "property_path": "properties.primaryKey",
  "source_value": "[REDACTED: key]",
  "target_value": "[REDACTED: key]",
  "match": true,
  "redaction_reason": "Contains sensitive keyword: key"
}
```

### MINIMAL Redaction (Internal Use Only)

**What is redacted:**
- Passwords and private keys only
- Explicit secrets (properties named `secret`, `password`)
- Certificate private keys

**What is preserved:**
- Connection strings (server names, database names visible)
- Non-password keys (e.g., partition keys, cache keys)
- Account names in connection strings
- API endpoint URLs

**When to use:**
- Internal security team review
- Debugging connectivity issues
- Investigating connection string mismatches
- Troubleshooting with DBAs

**Example output:**
```json
{
  "property_path": "properties.connectionStrings[0].connectionString",
  "source_value": "Server=tcp:myserver.database.windows.net,1433;Database=mydb;User ID=[REDACTED];Password=[REDACTED]",
  "target_value": "Server=tcp:myserver-dr.database.windows.net,1433;Database=mydb;User ID=[REDACTED];Password=[REDACTED]",
  "match": false,
  "redaction_reason": "Partial redaction: passwords removed"
}
```

### NONE (Development/Testing Only)

**What is redacted:**
- Nothing - all properties visible in plain text

**When to use:**
- Local development environments only
- Testing with synthetic/fake data
- Non-production tenants with no real secrets
- **NEVER in production**

**Security warning:**
```json
{
  "security_warnings": [
    "⚠️  CRITICAL: This report contains unredacted sensitive data!",
    "⚠️  Do NOT share this report outside secure development environment",
    "⚠️  Redaction level: NONE - all secrets visible",
    "⚠️  If this report is exposed, rotate all credentials immediately"
  ]
}
```

## Command Usage with Redaction

### Default (FULL Redaction)

```bash
# FULL redaction by default
azure-tenant-grapher fidelity --resource-level \
  --output validation-report.json
```

### Explicit Redaction Level

```bash
# FULL redaction (explicit)
azure-tenant-grapher fidelity --resource-level \
  --redaction-level FULL \
  --output validation-report.json

# MINIMAL redaction (internal security team only)
azure-tenant-grapher fidelity --resource-level \
  --redaction-level MINIMAL \
  --output internal-security-review.json

# NONE (development only - DO NOT USE IN PRODUCTION)
azure-tenant-grapher fidelity --resource-level \
  --redaction-level NONE \
  --output dev-test-validation.json
```

## Security Best Practices

### 1. Default to Maximum Security

Always use FULL redaction unless you have a specific, approved reason for less redaction:

```bash
# Good: Default security
azure-tenant-grapher fidelity --resource-level

# Bad: Unnecessary exposure
azure-tenant-grapher fidelity --resource-level --redaction-level MINIMAL
```

### 2. Verify Redaction Before Sharing

Always review reports before sharing outside your immediate team:

```bash
# Generate report with FULL redaction
azure-tenant-grapher fidelity --resource-level \
  --output validation-report.json

# Verify redaction applied
jq '.resources[].property_comparisons[] | select(.source_value | contains("REDACTED") | not)' \
  validation-report.json

# If output is empty, all sensitive data is redacted
```

### 3. Secure Report Storage

Store validation reports in encrypted, access-controlled locations:

```bash
# Store in encrypted directory
REPORT_DIR="/secure/compliance-reports/$(date +%Y/%m)"
mkdir -p "$REPORT_DIR"
chmod 700 "$REPORT_DIR"

azure-tenant-grapher fidelity --resource-level \
  --output "${REPORT_DIR}/validation-$(date +%Y%m%d).json"

# Set restrictive permissions
chmod 600 "${REPORT_DIR}/validation-$(date +%Y%m%d).json"
```

### 4. Rotate Credentials After Exposure

If unredacted reports are accidentally exposed:

```bash
# 1. Identify exposed resources
jq '.resources[] | select(.property_comparisons[] | select(.match == false and (.source_value | contains("REDACTED") | not)))' \
  exposed-report.json > exposed-resources.json

# 2. Rotate all credentials for exposed resources
./rotate-credentials.sh exposed-resources.json

# 3. Audit access to exposed report
./audit-report-access.sh exposed-report.json

# 4. Document incident
./log-security-incident.sh "Validation report exposure" exposed-report.json
```

### 5. Limit MINIMAL Redaction Use

Require approval for MINIMAL redaction:

```bash
# Example approval workflow
if [ "$REDACTION_LEVEL" = "MINIMAL" ]; then
  echo "MINIMAL redaction requires security team approval"
  echo "Approval ticket: $APPROVAL_TICKET"
  read -p "Have you obtained approval? (yes/no): " approval

  if [ "$approval" != "yes" ]; then
    echo "Approval required. Using FULL redaction."
    REDACTION_LEVEL="FULL"
  fi
fi

azure-tenant-grapher fidelity --resource-level \
  --redaction-level "$REDACTION_LEVEL" \
  --output validation-report.json
```

### 6. Never Use NONE in Production

Enforce redaction level restrictions:

```bash
# CI/CD pipeline check
if [ "$ENVIRONMENT" = "production" ] && [ "$REDACTION_LEVEL" = "NONE" ]; then
  echo "ERROR: NONE redaction not allowed in production"
  exit 1
fi

# Development environment check
if [ "$ENVIRONMENT" != "development" ] && [ "$REDACTION_LEVEL" = "NONE" ]; then
  echo "WARNING: NONE redaction should only be used in development"
  read -p "Continue anyway? (yes/no): " confirm
  [ "$confirm" != "yes" ] && exit 1
fi
```

## Redaction Detection Patterns

### Property Path Patterns

ATG redacts properties matching these patterns:

```
# Always redacted (case-insensitive)
*password*
*secret*
*token*
*apikey*
*api_key*
*accesskey*
*access_key*
*privatekey*
*private_key*
*connectionstring*
*connection_string*

# Resource-specific patterns
properties.primaryKey
properties.secondaryKey
properties.adminPassword
properties.sshPublicKeys[].privateKey
properties.certificates[].data
properties.encryptionKeys[]*
```

### Value-Based Redaction

ATG also redacts values that match sensitive patterns:

```
# Connection string patterns
Server=*;Password=*
AccountName=*;AccountKey=*
Endpoint=*;SharedAccessKey=*

# Key formats
[A-Za-z0-9/+]{64,}==  # Base64-encoded keys
[A-Fa-f0-9]{64,}       # Hex-encoded keys
```

### Custom Redaction Rules

Add custom redaction patterns in configuration:

```yaml
# .atg-config.yaml
security:
  redaction:
    additional_property_patterns:
      - "*customSecret*"
      - "*internalKey*"
      - "properties.legacyPassword"

    additional_value_patterns:
      - "^sk-[A-Za-z0-9]{48}$"  # OpenAI-style keys
      - "^ghp_[A-Za-z0-9]{36}$" # GitHub personal access tokens
```

## Compliance Requirements

### GDPR / Privacy Regulations

When validating resources containing personal data:

```bash
# Always use FULL redaction for GDPR-covered resources
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Sql/servers/databases" \
  --redaction-level FULL \
  --output gdpr-validation.json

# Add metadata for compliance tracking
jq '. + {
  compliance: {
    regulation: "GDPR",
    data_classification: "Personal Data",
    retention_period: "90 days",
    approval_required: true
  }
}' gdpr-validation.json > gdpr-validation-final.json
```

### SOC 2 / Audit Requirements

For SOC 2 compliance audits:

```bash
# Generate audit-compliant report
azure-tenant-grapher fidelity --resource-level \
  --track \
  --redaction-level FULL \
  --output "soc2-audit-$(date +%Y%m%d).json"

# Add audit trail metadata
jq '. + {
  audit_trail: {
    auditor: "External Audit Firm",
    audit_period: "2026-Q1",
    report_classification: "Confidential",
    reviewed_by: "Security Team",
    approved_by: "CISO"
  }
}' "soc2-audit-$(date +%Y%m%d).json" > "soc2-audit-final-$(date +%Y%m%d).json"
```

### PCI DSS Requirements

For environments processing payment data:

```bash
# Maximum security for PCI environments
azure-tenant-grapher fidelity --resource-level \
  --redaction-level FULL \
  --output pci-validation.json

# Verify no cardholder data exposed
jq '.resources[].property_comparisons[] | select(
  .source_value | test("[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}")
)' pci-validation.json

# If any output, report contains unredacted card numbers - DO NOT USE
```

## Incident Response

### If Unredacted Report Is Exposed

**Immediate actions (first 15 minutes):**

1. **Contain exposure:**
   ```bash
   # Revoke access to exposed location
   ./revoke-access.sh <exposed-report-location>

   # Delete exposed report copies
   ./secure-delete.sh <exposed-report>
   ```

2. **Identify exposed resources:**
   ```bash
   # Extract all resources from report
   jq '.resources[] | {
     resource_name: .resource_name,
     resource_type: .resource_type,
     resource_id: .resource_id
   }' exposed-report.json > exposed-resources.json
   ```

3. **Rotate credentials immediately:**
   ```bash
   # Rotate all credentials for exposed resources
   ./emergency-credential-rotation.sh exposed-resources.json
   ```

**Short-term actions (first hour):**

4. **Audit access:**
   ```bash
   # Who accessed the exposed report?
   ./audit-file-access.sh <exposed-report> > access-audit.log
   ```

5. **Notify stakeholders:**
   ```bash
   # Notify security team
   ./notify-security-team.sh "Validation report exposure incident"

   # Notify compliance team if PII/PCI data exposed
   ./notify-compliance-team.sh exposed-resources.json
   ```

**Medium-term actions (first day):**

6. **Full security review:**
   - Review all resources in exposed report
   - Audit access logs for compromised resources
   - Monitor for unauthorized access attempts

7. **Documentation:**
   - Document incident timeline
   - Record actions taken
   - Identify root cause
   - Implement preventive measures

## Security Automation

### Automated Redaction Verification

```python
#!/usr/bin/env python3
"""Verify validation report has proper redaction."""

import json
import re
import sys

def verify_redaction(report_path):
    """Check for exposed sensitive data in validation report."""

    with open(report_path) as f:
        report = json.load(f)

    # Patterns that should be redacted
    sensitive_patterns = [
        r'password\s*=\s*[^\s]+',
        r'key\s*=\s*[A-Za-z0-9/+]{20,}',
        r'token\s*=\s*[A-Za-z0-9\-_]+',
        r'[A-Za-z0-9/+]{64}==',  # Base64 keys
    ]

    violations = []

    for resource in report.get('resources', []):
        for prop in resource.get('property_comparisons', []):
            source_val = str(prop.get('source_value', ''))
            target_val = str(prop.get('target_value', ''))

            for pattern in sensitive_patterns:
                if re.search(pattern, source_val, re.IGNORECASE):
                    violations.append({
                        'resource': resource['resource_name'],
                        'property': prop['property_path'],
                        'issue': 'Unredacted sensitive data in source_value'
                    })

                if re.search(pattern, target_val, re.IGNORECASE):
                    violations.append({
                        'resource': resource['resource_name'],
                        'property': prop['property_path'],
                        'issue': 'Unredacted sensitive data in target_value'
                    })

    if violations:
        print(f"❌ SECURITY VIOLATION: {len(violations)} unredacted sensitive values found")
        for v in violations:
            print(f"  - {v['resource']}.{v['property']}: {v['issue']}")
        return False
    else:
        print("✅ Redaction verification passed")
        return True

if __name__ == "__main__":
    report_file = sys.argv[1]
    success = verify_redaction(report_file)
    sys.exit(0 if success else 1)
```

Usage:

```bash
# Generate report
azure-tenant-grapher fidelity --resource-level \
  --output validation-report.json

# Verify redaction
python3 verify-redaction.py validation-report.json

# Only proceed if verification passes
if [ $? -eq 0 ]; then
  echo "Safe to share report"
  cp validation-report.json /shared/reports/
else
  echo "DO NOT SHARE - redaction verification failed"
  exit 1
fi
```

## Additional Resources

- [Azure Key Vault Integration](./KEY_VAULT_INTEGRATION.md) - Secure credential storage
- [Compliance Audit Guide](./COMPLIANCE_AUDIT_GUIDE.md) - Audit trail requirements
- [Data Classification Guide](./DATA_CLASSIFICATION_GUIDE.md) - Classifying resource sensitivity

---

**Last Updated**: 2026-02-05
**Status**: current
**Category**: reference
**Security Classification**: Public (guidance document)
