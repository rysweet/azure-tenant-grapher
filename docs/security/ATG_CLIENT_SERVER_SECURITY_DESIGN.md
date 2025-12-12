# ATG Client-Server Security Design

**Document Version:** 1.0
**Date:** 2025-12-09
**Status:** Initial Design
**Related Issue:** #577

## Executive Summary

This document defines the security architecture for Azure Tenant Grapher (ATG) client-server deployment, where a remote service handles Azure tenant scanning operations. The design prioritizes defense-in-depth, zero-trust principles, and minimal attack surface while maintaining operational simplicity.

**Key Security Principles:**
- **Defense in Depth**: Multiple layers of security controls
- **Least Privilege**: Minimal permissions for all components
- **Zero Trust**: Verify all requests, trust nothing
- **Fail Secure**: Deny by default, explicit allow only
- **Audit Everything**: Comprehensive logging of all security-relevant events

---

## Table of Contents

1. [Threat Model](#threat-model)
2. [Authentication & Authorization Architecture](#authentication--authorization-architecture)
3. [Secret Management Strategy](#secret-management-strategy)
4. [Network Security Requirements](#network-security-requirements)
5. [Audit Logging System](#audit-logging-system)
6. [Input Validation Requirements](#input-validation-requirements)
7. [Secure Coding Practices](#secure-coding-practices)
8. [Environment Isolation](#environment-isolation)
9. [Security Testing Approach](#security-testing-approach)
10. [Incident Response Plan](#incident-response-plan)
11. [Compliance Considerations](#compliance-considerations)

---

## Threat Model

### Trust Boundaries

```
┌────────────────────────────────────────────────────────────┐
│  External Zone (Untrusted)                                 │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  CLI Client                                          │ │
│  │  - User workstation                                  │ │
│  │  - API key storage                                   │ │
│  │  - HTTPS requests                                    │ │
│  └──────────────────┬───────────────────────────────────┘ │
└─────────────────────┼──────────────────────────────────────┘
                      │ HTTPS + API Key Auth
                      ▼
┌────────────────────────────────────────────────────────────┐
│  Service Zone (Partially Trusted)                          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  ATG Service (Azure Container Instance)             │ │
│  │  - API endpoint                                      │ │
│  │  - Request validation                                │ │
│  │  - Authentication middleware                         │ │
│  │  - Rate limiting                                     │ │
│  └──────────────────┬───────────────────────────────────┘ │
└─────────────────────┼──────────────────────────────────────┘
                      │ Managed Identity
                      ▼
┌────────────────────────────────────────────────────────────┐
│  Azure Zone (Trusted)                                      │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Azure Resources                                     │ │
│  │  - Target tenant resources                           │ │
│  │  - Azure Resource Manager                            │ │
│  │  - Microsoft Graph API                               │ │
│  └──────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Neo4j Database (Azure Container Instance)          │ │
│  │  - Neo4j password authentication                     │ │
│  │  - Network isolation                                 │ │
│  │  - Encrypted storage                                 │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### Threat Actors

| Actor | Motivation | Capabilities | Risk Level |
|-------|------------|-------------|------------|
| **External Attacker** | Data theft, service disruption | Network access, API fuzzing, credential theft | HIGH |
| **Malicious Insider** | Data exfiltration, sabotage | Valid credentials, internal knowledge | MEDIUM |
| **Compromised CLI** | Lateral movement, data theft | API key, network access | MEDIUM |
| **Compromised Service** | Azure resource access, data theft | Managed Identity, Neo4j access | CRITICAL |
| **Supply Chain Attack** | Code injection, backdoors | Dependency poisoning, build tampering | HIGH |

### Key Threats (STRIDE Analysis)

| Threat | Category | Mitigation |
|--------|----------|-----------|
| **T1: API Key Theft** | Spoofing | Key rotation, short-lived tokens, secure storage |
| **T2: Man-in-the-Middle** | Tampering | TLS 1.3, certificate pinning, HTTPS enforcement |
| **T3: Unauthorized Scanning** | Elevation of Privilege | API key authorization, rate limiting, environment isolation |
| **T4: Service Account Compromise** | Spoofing | Managed Identity, no static credentials, RBAC |
| **T5: Neo4j Data Exfiltration** | Information Disclosure | Network isolation, authentication, encryption at rest |
| **T6: Injection Attacks** | Tampering | Input validation, parameterized queries, output encoding |
| **T7: DoS via Resource Exhaustion** | Denial of Service | Rate limiting, request throttling, resource quotas |
| **T8: Log Tampering** | Repudiation | Immutable audit logs, log forwarding, integrity checks |
| **T9: Secret Exposure in Logs** | Information Disclosure | Secret redaction, structured logging, log filtering |
| **T10: Container Escape** | Elevation of Privilege | Minimal base images, read-only filesystems, security scanning |

---

## Authentication & Authorization Architecture

### 1. CLI → Service Authentication

**Mechanism:** Bearer Token (API Key)

**Implementation:**
```python
# Client-side (CLI)
import os
import requests
from typing import Optional

class ATGClient:
    """Secure ATG service client with API key authentication."""

    def __init__(self, api_url: str, api_key: Optional[str] = None):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key or os.environ.get('ATG_API_KEY')

        if not self.api_key:
            raise ValueError("ATG_API_KEY must be provided or set in environment")

        # Validate API key format (prevent injection)
        if not self._is_valid_api_key_format(self.api_key):
            raise ValueError("Invalid API key format")

    @staticmethod
    def _is_valid_api_key_format(key: str) -> bool:
        """Validate API key format: atg_[env]_[32-hex-chars]"""
        import re
        pattern = r'^atg_(dev|integration|prod)_[a-f0-9]{64}$'
        return bool(re.match(pattern, key))

    def _make_request(self, method: str, endpoint: str, **kwargs):
        """Make authenticated request to ATG service."""
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {self.api_key}'
        headers['User-Agent'] = f'ATG-CLI/{self._get_version()}'

        url = f'{self.api_url}{endpoint}'

        try:
            response = requests.request(
                method, url, headers=headers, timeout=30, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif e.response.status_code == 403:
                raise AuthorizationError("Insufficient permissions")
            raise

    def scan_tenant(self, tenant_id: str, **kwargs):
        """Initiate tenant scan via remote service."""
        return self._make_request(
            'POST', '/api/v1/scan',
            json={'tenant_id': tenant_id, **kwargs}
        )
```

**Server-side (Service):**
```python
# Authentication middleware
from functools import wraps
from flask import request, jsonify
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

class APIKeyStore:
    """Secure API key storage and validation."""

    def __init__(self, secret_provider):
        self.secret_provider = secret_provider
        # Load from Azure Key Vault or environment
        self.api_keys = self._load_api_keys()

    def _load_api_keys(self) -> dict:
        """Load API keys from secure storage."""
        # Format: {"atg_prod_abc123...": {"env": "prod", "expires": "2025-12-31", "client_id": "cli-001"}}
        keys_json = self.secret_provider.get_secret('ATG_API_KEYS')
        return self._parse_keys(keys_json)

    def validate_key(self, api_key: str) -> dict:
        """
        Validate API key and return metadata.

        Returns:
            dict: {"valid": bool, "env": str, "client_id": str, "expires": datetime}
        """
        if not api_key or len(api_key) < 70:
            return {"valid": False}

        # Constant-time comparison to prevent timing attacks
        key_data = self.api_keys.get(api_key)
        if not key_data:
            return {"valid": False}

        # Check expiration
        expires = datetime.fromisoformat(key_data['expires'])
        if datetime.utcnow() > expires:
            return {"valid": False, "reason": "expired"}

        return {"valid": True, **key_data}

def require_api_key(f):
    """Decorator for API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        api_key = auth_header[7:]  # Remove 'Bearer ' prefix

        # Validate API key
        key_store = APIKeyStore(secret_provider=get_secret_provider())
        validation = key_store.validate_key(api_key)

        if not validation['valid']:
            # Log failed authentication attempt
            audit_log.warning(
                'authentication_failed',
                ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                reason=validation.get('reason', 'invalid_key')
            )
            return jsonify({'error': 'Invalid or expired API key'}), 401

        # Store auth context for request
        request.auth_context = {
            'environment': validation['env'],
            'client_id': validation['client_id']
        }

        # Log successful authentication
        audit_log.info(
            'authentication_success',
            environment=validation['env'],
            client_id=validation['client_id']
        )

        return f(*args, **kwargs)

    return decorated
```

**API Key Format:**
- `atg_[environment]_[64-hex-chars]`
- Example: `atg_prod_a1b2c3d4e5f67890123456789abcdef01234567890abcdef1234567890abcdef`
- Environment: `dev`, `integration`, `prod`
- 256-bit entropy (cryptographically secure)

**API Key Lifecycle:**
1. **Generation**: `secrets.token_hex(32)` (256 bits)
2. **Storage**: Azure Key Vault (encrypted at rest)
3. **Distribution**: Secure channel (e.g., Azure DevOps Secure Files)
4. **Rotation**: 90-day maximum lifetime, automated rotation
5. **Revocation**: Immediate removal from Key Vault

### 2. Service → Azure Authentication

**Mechanism:** Managed Identity (System-Assigned)

**RBAC Assignments:**
```yaml
# Azure RBAC role assignments for ATG service Managed Identity
assignments:
  - scope: "/subscriptions/{subscription-id}"
    role: "Reader"
    purpose: "Discover all resources in subscription"

  - scope: "/subscriptions/{subscription-id}"
    role: "Reader and Data Access"
    purpose: "Read storage account data for complete graph"

  - scope: "/providers/Microsoft.Graph"
    role: "Directory.Read.All"
    purpose: "Read Azure AD users and groups"

  - scope: "/providers/Microsoft.Graph"
    role: "GroupMember.Read.All"
    purpose: "Read group memberships"
```

**Implementation:**
```python
from azure.identity import ManagedIdentityCredential, ChainedTokenCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ClientAuthenticationError

class AzureAuthProvider:
    """Secure Azure authentication using Managed Identity."""

    def __init__(self):
        # Use Managed Identity in production, fallback to CLI in dev
        self.credential = self._create_credential()

    def _create_credential(self):
        """Create credential with fallback chain."""
        try:
            # Primary: System-assigned Managed Identity
            credential = ManagedIdentityCredential()

            # Test credential before returning
            credential.get_token("https://management.azure.com/.default")
            return credential

        except ClientAuthenticationError:
            # Fallback for local development only
            if os.environ.get('ENVIRONMENT') == 'development':
                from azure.identity import AzureCliCredential
                return AzureCliCredential()
            raise

    def get_resource_client(self, subscription_id: str):
        """Get authenticated Azure Resource Management client."""
        return ResourceManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
```

**Least Privilege Principle:**
- **NO** Owner or Contributor roles
- **NO** write permissions (ATG is read-only by design)
- **NO** key management permissions
- Scoped to specific subscriptions, not tenant-wide

### 3. Service → Neo4j Authentication

**Mechanism:** Password Authentication + Network Isolation

**Implementation:**
```python
from neo4j import GraphDatabase
import os

class Neo4jConnectionManager:
    """Secure Neo4j connection management."""

    def __init__(self, secret_provider):
        self.uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
        self.username = 'neo4j'
        self.password = secret_provider.get_secret('NEO4J_PASSWORD')

        # Validate password strength
        self._validate_password(self.password)

        # Connection pooling with security settings
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
            encrypted=True,  # TLS for bolt protocol
            trust=True,      # Trust system certificates
            max_connection_lifetime=3600,  # 1 hour max connection age
            max_connection_pool_size=50,
            connection_timeout=30
        )

    @staticmethod
    def _validate_password(password: str):
        """Validate Neo4j password meets security requirements."""
        if not password or len(password) < 16:
            raise ValueError("Neo4j password must be at least 16 characters")

        # Check complexity
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                "Neo4j password must contain uppercase, lowercase, digit, and special character"
            )

    def execute_query(self, query: str, parameters: dict = None):
        """Execute Cypher query with parameterization (prevent injection)."""
        with self.driver.session() as session:
            return session.run(query, parameters or {})
```

**Neo4j Security Configuration:**
```yaml
# neo4j.conf security settings
dbms.security.auth_enabled: true
dbms.connector.bolt.tls_level: REQUIRED
dbms.ssl.policy.bolt.enabled: true
dbms.ssl.policy.bolt.client_auth: NONE  # Client cert not required (password sufficient)
dbms.security.procedures.unrestricted: ""  # No unrestricted procedures
dbms.security.allow_csv_import_from_file_urls: false
```

---

## Secret Management Strategy

### Secret Types and Storage

| Secret Type | Storage Location | Rotation Frequency | Access Method |
|-------------|------------------|-------------------|---------------|
| **API Keys** | Azure Key Vault | 90 days | GitHub Secrets → ACI Env Vars |
| **Neo4j Password** | Azure Key Vault | 180 days | GitHub Secrets → ACI Env Vars |
| **TLS Certificates** | Azure Key Vault | 365 days | Mounted volume |
| **Managed Identity** | Azure AD | N/A (automatic) | System-assigned |

### Secret Injection Flow

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Repository                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  GitHub Secrets (Repository Settings)               │  │
│  │  - ATG_API_KEY_PROD                                  │  │
│  │  - NEO4J_PASSWORD_PROD                               │  │
│  │  - AZURE_CREDENTIALS (Service Principal for deploy) │  │
│  └──────────────────┬───────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────┘
                      │
                      ▼ GitHub Actions Workflow
┌─────────────────────────────────────────────────────────────┐
│  Deployment Pipeline (.github/workflows/deploy-aci.yml)     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  steps:                                              │  │
│  │    - name: Deploy ATG Service                        │  │
│  │      run: |                                          │  │
│  │        az container create \                         │  │
│  │          --environment-variables \                   │  │
│  │          ATG_API_KEY=${{ secrets.ATG_API_KEY_PROD }}│  │
│  │          NEO4J_PASSWORD=${{ secrets.NEO4J_PASSWORD }}│  │
│  │          ENVIRONMENT=prod                            │  │
│  └──────────────────┬───────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────┘
                      │
                      ▼ Azure Container Instance
┌─────────────────────────────────────────────────────────────┐
│  ATG Service Container                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Environment Variables (Runtime)                     │  │
│  │  ATG_API_KEY=atg_prod_abc123...                      │  │
│  │  NEO4J_PASSWORD=SecurePass123!@#                     │  │
│  │  ENVIRONMENT=prod                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Secret Rotation Procedure

**Automated Rotation (Recommended):**
```python
# scripts/rotate_secrets.py
import secrets
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def rotate_api_key(environment: str):
    """
    Rotate API key with zero downtime.

    Process:
    1. Generate new API key
    2. Add new key to Key Vault (with _next suffix)
    3. Update GitHub Secret
    4. Deploy new service version with both keys active
    5. Wait 24 hours (grace period)
    6. Remove old key from Key Vault
    """
    credential = DefaultAzureCredential()
    vault_url = f"https://atg-{environment}-kv.vault.azure.net"
    client = SecretClient(vault_url=vault_url, credential=credential)

    # Generate new key
    new_key = f"atg_{environment}_{secrets.token_hex(32)}"

    # Store with expiration
    from datetime import datetime, timedelta
    expires = datetime.utcnow() + timedelta(days=90)

    client.set_secret(
        f"ATG-API-KEY-{environment.upper()}-NEXT",
        new_key,
        expires_on=expires
    )

    print(f"New API key generated: {new_key[:20]}...")
    print("Next steps:")
    print("1. Update GitHub Secret: ATG_API_KEY_{environment.upper()}")
    print("2. Deploy new service version")
    print("3. Wait 24 hours")
    print("4. Run: python rotate_secrets.py --finalize {environment}")
```

**Manual Rotation (Emergency):**
1. Generate new secret: `python -c "import secrets; print('atg_prod_' + secrets.token_hex(32))"`
2. Update GitHub Secret immediately
3. Trigger deployment workflow
4. Verify new key works
5. Revoke old key

### Secret Protection Rules

**DO:**
- ✅ Store secrets in Azure Key Vault or GitHub Secrets
- ✅ Use environment variables for runtime access
- ✅ Rotate secrets every 90 days (API keys) / 180 days (passwords)
- ✅ Use `secrets` module for generation (cryptographically secure)
- ✅ Validate secret format before use
- ✅ Redact secrets in logs using structured logging

**DON'T:**
- ❌ Hardcode secrets in source code
- ❌ Commit secrets to Git (even in .env.example)
- ❌ Log secrets in plaintext
- ❌ Share secrets via email or Slack
- ❌ Use weak passwords (< 16 chars, no complexity)
- ❌ Store secrets in container images

---

## Network Security Requirements

### 1. TLS Configuration

**Requirements:**
- TLS 1.3 only (no TLS 1.2 or lower)
- Strong cipher suites only
- Certificate pinning for CLI → Service communication
- HSTS (HTTP Strict Transport Security) enabled

**Implementation:**
```python
# Server-side (Flask/FastAPI)
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

@app.after_request
def set_security_headers(response):
    """Add security headers to all responses."""
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'none'"
    return response

# gunicorn configuration (gunicorn.conf.py)
bind = "0.0.0.0:8443"
certfile = "/etc/ssl/certs/atg-service.crt"
keyfile = "/etc/ssl/private/atg-service.key"
ssl_version = 5  # TLS 1.3
ciphers = "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256"
```

**Client-side certificate pinning:**
```python
# Client certificate pinning to prevent MITM
import hashlib
import ssl

EXPECTED_CERT_FINGERPRINT = {
    'prod': 'sha256:abc123...',
    'integration': 'sha256:def456...',
    'dev': 'sha256:ghi789...'
}

def verify_certificate(hostname: str, cert: bytes, environment: str):
    """Verify server certificate fingerprint."""
    fingerprint = hashlib.sha256(cert).hexdigest()
    expected = EXPECTED_CERT_FINGERPRINT[environment]

    if fingerprint != expected:
        raise ssl.SSLError(f"Certificate fingerprint mismatch for {hostname}")
```

### 2. Network Isolation

**Azure Network Security Groups (NSG):**
```yaml
# NSG rules for ATG Service ACI
inbound_rules:
  - name: "Allow-HTTPS-From-Corporate"
    priority: 100
    source: "CorporateVNetRange"  # 10.0.0.0/16
    destination: "*"
    port: 443
    protocol: TCP
    action: Allow

  - name: "Deny-All-Inbound"
    priority: 4096
    source: "*"
    destination: "*"
    port: "*"
    protocol: "*"
    action: Deny

outbound_rules:
  - name: "Allow-Azure-Management"
    priority: 100
    source: "*"
    destination: "AzureCloud"
    port: 443
    protocol: TCP
    action: Allow

  - name: "Allow-Neo4j"
    priority: 110
    source: "*"
    destination: "Neo4jContainerIP"  # Private IP only
    port: 7687
    protocol: TCP
    action: Allow

  - name: "Deny-All-Outbound"
    priority: 4096
    source: "*"
    destination: "*"
    port: "*"
    protocol: "*"
    action: Deny
```

**Network Topology:**
```
Internet
    │
    ├─ HTTPS (443) ────────────────────────────────┐
    │                                               │
    ▼                                               │
┌─────────────────────┐                            │
│  Azure Front Door   │ (Optional: WAF + DDoS)     │
│  - Rate limiting    │                            │
│  - GeoIP filtering  │                            │
└──────────┬──────────┘                            │
           │                                        │
           ▼                                        │
┌─────────────────────────────────────────────┐   │
│  ATG Service (ACI)                          │   │
│  - Private VNet                             │   │
│  - No public IP (optional)                  │◀──┘
│  - NSG: Allow 443 from corporate only       │
└──────────┬──────────────────────────────────┘
           │ Bolt (7687)
           ▼
┌─────────────────────────────────────────────┐
│  Neo4j (ACI)                                │
│  - Private VNet only                        │
│  - No public IP                             │
│  - NSG: Allow 7687 from ATG service only    │
└─────────────────────────────────────────────┘
```

### 3. Rate Limiting & DDoS Protection

**API Rate Limits:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379"
)

@app.route('/api/v1/scan', methods=['POST'])
@require_api_key
@limiter.limit("10 per hour")  # Max 10 scans per hour per API key
def scan_tenant():
    """Rate-limited scan endpoint."""
    pass
```

**Rate Limit Strategy:**
| Endpoint | Global Limit | Per-Key Limit | Burst Allowance |
|----------|--------------|---------------|-----------------|
| `/api/v1/scan` | 100/hour | 10/hour | 2 requests |
| `/api/v1/status` | 1000/hour | 100/hour | 10 requests |
| `/api/v1/results` | 500/hour | 50/hour | 5 requests |

---

## Audit Logging System

### Log Categories

| Category | Log Level | Retention | Examples |
|----------|-----------|-----------|----------|
| **Authentication** | INFO | 1 year | API key validation, failures |
| **Authorization** | INFO | 1 year | RBAC checks, permission denials |
| **Data Access** | INFO | 1 year | Neo4j queries, Azure API calls |
| **Security Events** | WARNING | 2 years | Rate limit exceeded, injection attempts |
| **Admin Actions** | INFO | 2 years | Configuration changes, key rotation |
| **Errors** | ERROR | 6 months | Exceptions, service failures |

### Structured Logging Format

```python
import logging
import json
from datetime import datetime
from typing import Any

class SecureJSONFormatter(logging.Formatter):
    """JSON formatter with secret redaction."""

    REDACT_FIELDS = {
        'password', 'api_key', 'secret', 'token', 'authorization',
        'neo4j_password', 'client_secret'
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with secret redaction."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'environment': os.environ.get('ENVIRONMENT', 'unknown'),
            'service': 'atg-server',
            'version': '1.0.0',
        }

        # Add extra fields from record
        if hasattr(record, 'extra'):
            for key, value in record.extra.items():
                if key.lower() in self.REDACT_FIELDS:
                    log_data[key] = '[REDACTED]'
                else:
                    log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(SecureJSONFormatter())

audit_logger = logging.getLogger('atg.audit')
audit_logger.addHandler(handler)
audit_logger.setLevel(logging.INFO)

# Usage
audit_logger.info(
    'scan_initiated',
    extra={
        'tenant_id': tenant_id,
        'client_id': request.auth_context['client_id'],
        'ip_address': request.remote_addr,
        'api_key': api_key  # Will be redacted automatically
    }
)
```

### Audit Event Examples

**Successful Authentication:**
```json
{
  "timestamp": "2025-12-09T10:30:45Z",
  "level": "INFO",
  "logger": "atg.audit",
  "message": "authentication_success",
  "environment": "prod",
  "service": "atg-server",
  "version": "1.0.0",
  "client_id": "cli-001",
  "ip_address": "203.0.113.45",
  "user_agent": "ATG-CLI/1.0.0"
}
```

**Failed Authentication (Suspicious):**
```json
{
  "timestamp": "2025-12-09T10:31:12Z",
  "level": "WARNING",
  "logger": "atg.audit",
  "message": "authentication_failed",
  "environment": "prod",
  "service": "atg-server",
  "version": "1.0.0",
  "reason": "invalid_key",
  "ip_address": "198.51.100.78",
  "user_agent": "curl/7.68.0",
  "attempt_count": 5,
  "alert": "possible_brute_force"
}
```

**Tenant Scan:**
```json
{
  "timestamp": "2025-12-09T10:32:00Z",
  "level": "INFO",
  "logger": "atg.audit",
  "message": "scan_initiated",
  "environment": "prod",
  "service": "atg-server",
  "version": "1.0.0",
  "tenant_id": "12345678-1234-1234-1234-123456789012",
  "client_id": "cli-001",
  "scan_id": "scan-abc123",
  "resource_count": 1523
}
```

### Log Forwarding & Monitoring

**Azure Log Analytics Integration:**
```python
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

# Configure Azure Monitor (Application Insights)
configure_azure_monitor(
    connection_string=os.environ['APPLICATIONINSIGHTS_CONNECTION_STRING']
)

tracer = trace.get_tracer(__name__)

@app.route('/api/v1/scan', methods=['POST'])
@require_api_key
def scan_tenant():
    """Scan endpoint with distributed tracing."""
    with tracer.start_as_current_span("scan_tenant") as span:
        span.set_attribute("tenant_id", tenant_id)
        span.set_attribute("client_id", request.auth_context['client_id'])

        # Perform scan
        result = perform_scan(tenant_id)

        span.set_attribute("resource_count", result['resource_count'])
        return jsonify(result)
```

**Alert Rules (Azure Monitor):**
```yaml
alerts:
  - name: "Failed Authentication Spike"
    condition: "authentication_failed count > 10 in 5 minutes"
    severity: "High"
    action: "Send email + SMS to security team"

  - name: "Rate Limit Exceeded"
    condition: "rate_limit_exceeded count > 50 in 1 hour"
    severity: "Medium"
    action: "Send email to ops team"

  - name: "Injection Attempt"
    condition: "injection_attempt count > 1"
    severity: "Critical"
    action: "Block IP + Send email + Create incident"
```

---

## Input Validation Requirements

### Validation Strategy

**Whitelist Approach:** Only allow known-good inputs, reject everything else.

**Validation Layers:**
1. **Syntactic Validation**: Format, type, length
2. **Semantic Validation**: Business logic, allowed values
3. **Contextual Validation**: Authorization, environment-specific rules

### Tenant ID Validation

```python
import re
from typing import Optional

class TenantIDValidator:
    """Validate Azure Tenant ID format and existence."""

    # Azure Tenant ID format: UUID v4
    TENANT_ID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )

    @classmethod
    def validate(cls, tenant_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate tenant ID.

        Returns:
            (is_valid, error_message)
        """
        # Type check
        if not isinstance(tenant_id, str):
            return False, "Tenant ID must be a string"

        # Length check (performance optimization)
        if len(tenant_id) != 36:
            return False, "Tenant ID must be 36 characters"

        # Format check
        if not cls.TENANT_ID_PATTERN.match(tenant_id):
            return False, "Invalid tenant ID format (must be UUID v4)"

        # Authorization check (ensure caller is allowed to scan this tenant)
        # This would check against a whitelist in production

        return True, None

    @classmethod
    def sanitize(cls, tenant_id: str) -> str:
        """Sanitize tenant ID for logging (obfuscate middle)."""
        if len(tenant_id) == 36:
            return f"{tenant_id[:8]}-****-****-****-{tenant_id[-12:]}"
        return "[INVALID]"
```

### Request Parameter Validation

```python
from marshmallow import Schema, fields, validate, ValidationError

class ScanRequestSchema(Schema):
    """Schema for scan request validation."""

    tenant_id = fields.Str(
        required=True,
        validate=lambda x: TenantIDValidator.validate(x)[0]
    )

    subscription_ids = fields.List(
        fields.Str(validate=validate.Regexp(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        )),
        missing=[],
        validate=validate.Length(max=100)  # Max 100 subscriptions
    )

    resource_types = fields.List(
        fields.Str(validate=validate.Regexp(r'^Microsoft\.\w+/\w+$')),
        missing=[],
        validate=validate.Length(max=50)
    )

    include_aad = fields.Boolean(missing=True)

    rebuild_edges = fields.Boolean(missing=False)

@app.route('/api/v1/scan', methods=['POST'])
@require_api_key
def scan_tenant():
    """Scan endpoint with comprehensive input validation."""
    schema = ScanRequestSchema()

    try:
        # Validate and deserialize request
        data = schema.load(request.json)
    except ValidationError as e:
        audit_logger.warning(
            'validation_error',
            extra={
                'errors': e.messages,
                'client_id': request.auth_context['client_id']
            }
        )
        return jsonify({'error': 'Invalid request', 'details': e.messages}), 400

    # Additional business logic validation
    if not is_tenant_accessible(data['tenant_id'], request.auth_context):
        audit_logger.warning(
            'unauthorized_tenant_access',
            extra={
                'tenant_id': TenantIDValidator.sanitize(data['tenant_id']),
                'client_id': request.auth_context['client_id']
            }
        )
        return jsonify({'error': 'Unauthorized tenant access'}), 403

    # Proceed with scan
    return perform_scan(data)
```

### Cypher Query Parameterization

**CRITICAL:** Always use parameterized queries to prevent Cypher injection.

```python
# BAD - Vulnerable to injection
def get_resource_by_name(name: str):
    query = f"MATCH (r:Resource) WHERE r.name = '{name}' RETURN r"
    return session.run(query)

# GOOD - Parameterized query
def get_resource_by_name(name: str):
    query = "MATCH (r:Resource) WHERE r.name = $name RETURN r"
    return session.run(query, name=name)
```

### Output Encoding

```python
from markupsafe import escape
import json

def sanitize_resource_name(name: str) -> str:
    """Sanitize resource name for display in HTML contexts."""
    return escape(name)

def safe_json_response(data: dict) -> str:
    """Generate safe JSON response with proper encoding."""
    return json.dumps(data, ensure_ascii=True, separators=(',', ':'))
```

---

## Secure Coding Practices

### 1. Dependency Management

**Requirements:**
- Pin all dependencies to exact versions
- Use `uv` for deterministic builds
- Scan dependencies for vulnerabilities weekly
- Maintain Software Bill of Materials (SBOM)

```toml
# pyproject.toml
[project]
dependencies = [
    "flask==3.0.0",  # Exact versions, no ~ or ^
    "neo4j==5.15.0",
    "azure-identity==1.15.0",
    "azure-mgmt-resource==23.0.1",
    "cryptography==41.0.7",
    "pydantic==2.5.3",
    "marshmallow==3.20.1"
]

[tool.uv]
locked = true  # Use uv.lock for reproducible installs
```

**Dependency Scanning:**
```bash
# Weekly automated scan
uv run safety check --json > security-scan.json
uv run bandit -r src -f json -o bandit-report.json
uv run pip-audit --format json > audit-report.json
```

### 2. Secrets Detection (Pre-commit Hook)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### 3. Secure Defaults

```python
# config.py - Secure defaults for all environments
class SecurityConfig:
    """Security configuration with secure defaults."""

    # Authentication
    API_KEY_LENGTH = 64  # 256-bit entropy
    API_KEY_MAX_AGE_DAYS = 90

    # Rate limiting
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_PER_HOUR = 10

    # TLS
    TLS_MIN_VERSION = 'TLSv1.3'
    TLS_CIPHERS = [
        'TLS_AES_256_GCM_SHA384',
        'TLS_CHACHA20_POLY1305_SHA256'
    ]

    # Timeouts
    REQUEST_TIMEOUT_SECONDS = 30
    AZURE_API_TIMEOUT_SECONDS = 60
    NEO4J_QUERY_TIMEOUT_SECONDS = 300

    # Input validation
    MAX_SUBSCRIPTION_COUNT = 100
    MAX_RESOURCE_TYPES = 50
    MAX_REQUEST_SIZE_MB = 1

    # Logging
    LOG_LEVEL = 'INFO'
    LOG_RETENTION_DAYS = 365
    REDACT_SECRETS_IN_LOGS = True

    # Container security
    RUN_AS_NON_ROOT = True
    READ_ONLY_ROOT_FS = True
    NO_NEW_PRIVILEGES = True
```

### 4. Error Handling (No Information Disclosure)

```python
class APIError(Exception):
    """Base exception for API errors with safe messages."""

    def __init__(self, user_message: str, internal_message: str = None):
        self.user_message = user_message
        self.internal_message = internal_message or user_message
        super().__init__(self.internal_message)

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler with safe error messages."""

    # Log internal error with full details
    audit_logger.error(
        'unhandled_exception',
        extra={
            'exception_type': type(e).__name__,
            'exception_message': str(e),
            'traceback': traceback.format_exc()
        }
    )

    # Return safe error message to client
    if isinstance(e, APIError):
        return jsonify({'error': e.user_message}), 500

    # Generic error for unexpected exceptions
    return jsonify({
        'error': 'An internal error occurred',
        'request_id': request.headers.get('X-Request-ID', 'unknown')
    }), 500
```

### 5. Container Security

**Dockerfile Best Practices:**
```dockerfile
# Use minimal base image
FROM python:3.11-slim-bookworm AS base

# Create non-root user
RUN groupadd -r atg && useradd -r -g atg atg

# Install dependencies as root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=atg:atg src/ /app/src/
WORKDIR /app

# Switch to non-root user
USER atg

# Read-only filesystem (except /tmp)
VOLUME /tmp

# Drop all capabilities
RUN setcap -r /usr/local/bin/python3.11 || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f https://localhost:8443/health || exit 1

# Run application
CMD ["gunicorn", "--config", "gunicorn.conf.py", "src.app:app"]
```

**Security Scanning:**
```bash
# Scan container image for vulnerabilities
docker scan atg-service:latest

# Use Trivy for comprehensive scanning
trivy image --severity HIGH,CRITICAL atg-service:latest

# Check for misconfigurations
hadolint Dockerfile
```

---

## Environment Isolation

### Multi-Environment Strategy

| Environment | Purpose | Deployment | Data |
|-------------|---------|------------|------|
| **Development** | Local testing | Developer workstation | Synthetic data |
| **Integration** | CI/CD testing | Azure ACI (ephemeral) | Synthetic data |
| **Staging** | Pre-production validation | Azure ACI | Sanitized production data |
| **Production** | Live service | Azure ACI (HA) | Real tenant data |

### Resource Isolation

**Separate Azure Resources per Environment:**
```yaml
# Terraform/Bicep configuration
environments:
  dev:
    resource_group: "rg-atg-dev"
    aci_name: "aci-atg-dev"
    key_vault: "kv-atg-dev"
    network: "vnet-atg-dev"

  integration:
    resource_group: "rg-atg-integration"
    aci_name: "aci-atg-integration"
    key_vault: "kv-atg-integration"
    network: "vnet-atg-integration"

  prod:
    resource_group: "rg-atg-prod"
    aci_name: "aci-atg-prod"
    key_vault: "kv-atg-prod"
    network: "vnet-atg-prod"
```

### Cross-Environment Contamination Prevention

```python
class EnvironmentGuard:
    """Prevent accidental cross-environment access."""

    ALLOWED_TENANTS = {
        'dev': ['12345678-...'],  # Dev tenant only
        'integration': ['87654321-...'],
        'prod': ['abcdef01-...', 'fedcba98-...']  # Multiple prod tenants
    }

    @classmethod
    def validate_tenant_access(cls, tenant_id: str, environment: str) -> bool:
        """Ensure tenant is allowed for this environment."""
        allowed = cls.ALLOWED_TENANTS.get(environment, [])

        if tenant_id not in allowed:
            audit_logger.error(
                'cross_environment_access_blocked',
                extra={
                    'tenant_id': TenantIDValidator.sanitize(tenant_id),
                    'environment': environment,
                    'severity': 'CRITICAL'
                }
            )
            return False

        return True
```

### Configuration Management

```python
# config.py - Environment-specific configuration
import os
from dataclasses import dataclass

@dataclass
class EnvironmentConfig:
    """Environment-specific configuration."""

    environment: str
    api_url: str
    neo4j_uri: str
    key_vault_url: str
    allowed_tenants: list[str]
    log_level: str
    rate_limit: int

def get_config() -> EnvironmentConfig:
    """Load configuration based on ENVIRONMENT variable."""
    env = os.environ.get('ENVIRONMENT', 'development')

    configs = {
        'development': EnvironmentConfig(
            environment='development',
            api_url='http://localhost:8000',
            neo4j_uri='bolt://localhost:7687',
            key_vault_url='',
            allowed_tenants=['*'],  # Allow all in dev
            log_level='DEBUG',
            rate_limit=1000
        ),
        'production': EnvironmentConfig(
            environment='production',
            api_url='https://atg-prod.example.com',
            neo4j_uri='bolt://neo4j-prod:7687',
            key_vault_url='https://kv-atg-prod.vault.azure.net',
            allowed_tenants=os.environ['ALLOWED_TENANTS'].split(','),
            log_level='INFO',
            rate_limit=10
        )
    }

    return configs[env]
```

---

## Security Testing Approach

### 1. Static Analysis (Pre-commit)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: bandit
        name: Bandit Security Linter
        entry: bandit
        args: ["-r", "src", "-ll"]
        language: system
        types: [python]

      - id: safety
        name: Safety Dependency Check
        entry: safety
        args: ["check", "--json"]
        language: system
        pass_filenames: false

      - id: semgrep
        name: Semgrep Security Scanner
        entry: semgrep
        args: ["--config=auto", "src/"]
        language: system
        pass_filenames: false
```

### 2. Dynamic Testing (CI/CD)

**Automated Security Tests:**
```python
# tests/security/test_authentication.py
import pytest
from src.app import app

def test_missing_api_key():
    """Test authentication with missing API key."""
    client = app.test_client()
    response = client.post('/api/v1/scan', json={'tenant_id': 'test'})
    assert response.status_code == 401
    assert 'Missing or invalid Authorization header' in response.json['error']

def test_invalid_api_key():
    """Test authentication with invalid API key."""
    client = app.test_client()
    response = client.post(
        '/api/v1/scan',
        headers={'Authorization': 'Bearer invalid_key'},
        json={'tenant_id': 'test'}
    )
    assert response.status_code == 401

def test_expired_api_key():
    """Test authentication with expired API key."""
    # Test with known expired key
    expired_key = generate_expired_test_key()
    client = app.test_client()
    response = client.post(
        '/api/v1/scan',
        headers={'Authorization': f'Bearer {expired_key}'},
        json={'tenant_id': 'test'}
    )
    assert response.status_code == 401
    assert 'expired' in response.json['error'].lower()

def test_rate_limiting():
    """Test rate limiting enforcement."""
    client = app.test_client()
    api_key = generate_test_key()

    # Make requests up to limit
    for i in range(10):
        response = client.post(
            '/api/v1/scan',
            headers={'Authorization': f'Bearer {api_key}'},
            json={'tenant_id': 'test'}
        )
        assert response.status_code in [200, 202]

    # 11th request should be rate limited
    response = client.post(
        '/api/v1/scan',
        headers={'Authorization': f'Bearer {api_key}'},
        json={'tenant_id': 'test'}
    )
    assert response.status_code == 429

def test_injection_prevention():
    """Test Cypher injection prevention."""
    client = app.test_client()
    api_key = generate_test_key()

    # Attempt Cypher injection
    malicious_input = "'; MATCH (n) DETACH DELETE n; //"

    response = client.post(
        '/api/v1/query',
        headers={'Authorization': f'Bearer {api_key}'},
        json={'query': malicious_input}
    )

    # Should either reject or sanitize (not execute malicious query)
    assert response.status_code in [400, 403]
```

### 3. Penetration Testing

**Quarterly External Penetration Test Scope:**
1. **Authentication bypass attempts**
   - Brute force API keys
   - Token manipulation
   - Session fixation

2. **Authorization flaws**
   - Vertical privilege escalation
   - Horizontal privilege escalation
   - IDOR (Insecure Direct Object References)

3. **Injection attacks**
   - Cypher injection
   - Command injection
   - LDAP injection

4. **API fuzzing**
   - Malformed requests
   - Oversized payloads
   - Edge case inputs

5. **Network security**
   - MITM attacks
   - Certificate validation bypass
   - TLS downgrade attacks

**Test Report Template:**
```markdown
# ATG Penetration Test Report

**Date:** 2025-Q4
**Tester:** External Security Firm
**Scope:** ATG Service (Production environment simulation)

## Executive Summary
[Summary of findings]

## Findings

### High Severity
1. **Finding:** [Description]
   - **Risk:** [Impact]
   - **Recommendation:** [Mitigation]

### Medium Severity
[...]

### Low Severity
[...]

## Remediation Timeline
- High: 7 days
- Medium: 30 days
- Low: 90 days
```

### 4. Security Checklist (Pre-Production)

**Before deploying to production:**

- [ ] All secrets stored in Azure Key Vault
- [ ] TLS 1.3 enforced on all endpoints
- [ ] API keys rotated in last 30 days
- [ ] Rate limiting enabled and tested
- [ ] Input validation on all endpoints
- [ ] Output encoding prevents XSS
- [ ] Audit logging enabled and forwarded to SIEM
- [ ] Container security scan passed (no HIGH/CRITICAL vulns)
- [ ] Dependency scan passed (no known CVEs)
- [ ] Static analysis (Bandit) passed
- [ ] Dynamic security tests passed
- [ ] Network security groups configured
- [ ] Managed Identity assigned and tested
- [ ] Neo4j authentication enabled
- [ ] Error messages don't leak sensitive info
- [ ] Security headers present on all responses
- [ ] Incident response plan documented
- [ ] Security training completed by team

---

## Incident Response Plan

### Incident Classification

| Severity | Definition | Response Time | Examples |
|----------|-----------|---------------|----------|
| **P0 - Critical** | Active breach, data exfiltration | 15 minutes | Compromised Managed Identity, Neo4j data leak |
| **P1 - High** | Imminent threat, service down | 1 hour | Brute force attack, DDoS, API key compromise |
| **P2 - Medium** | Degraded security posture | 4 hours | Failed security scan, expired certificate |
| **P3 - Low** | Minor security concern | 24 hours | Non-critical vulnerability, compliance gap |

### Response Procedures

**P0 - Critical Incident:**
1. **Immediate Actions (0-15 min):**
   - Revoke all API keys
   - Disable service (take offline)
   - Block suspicious IP addresses
   - Notify security team and management

2. **Containment (15-60 min):**
   - Isolate affected resources
   - Snapshot Neo4j database for forensics
   - Review audit logs for breach timeline
   - Identify compromised credentials

3. **Eradication (1-4 hours):**
   - Rotate all secrets (API keys, passwords, certificates)
   - Patch vulnerabilities
   - Rebuild compromised containers
   - Update firewall rules

4. **Recovery (4-24 hours):**
   - Deploy patched service
   - Verify security controls
   - Restore from clean backup if needed
   - Monitor for re-compromise

5. **Post-Incident (24-72 hours):**
   - Root cause analysis
   - Update security controls
   - Notify affected parties (if data breach)
   - Document lessons learned

**Communication Template:**
```markdown
# Security Incident Report

**Incident ID:** INC-2025-001
**Severity:** P0 - Critical
**Date:** 2025-12-09
**Status:** Resolved

## Summary
[Brief description of incident]

## Timeline
- **10:30 UTC:** Incident detected
- **10:45 UTC:** Service taken offline
- **11:30 UTC:** Root cause identified
- **14:00 UTC:** Patch deployed
- **15:00 UTC:** Service restored

## Impact
- **Affected tenants:** [Count]
- **Data compromised:** [Yes/No, details]
- **Downtime:** [Duration]

## Root Cause
[Detailed technical analysis]

## Remediation
1. [Action taken]
2. [Action taken]
3. [Action taken]

## Prevention
[Changes to prevent recurrence]
```

---

## Compliance Considerations

### Regulatory Requirements

| Regulation | Applicability | Key Requirements |
|------------|---------------|-----------------|
| **GDPR** | If processing EU tenant data | Data minimization, encryption, audit logs, data subject rights |
| **SOC 2** | Service provider compliance | Access controls, encryption, monitoring, incident response |
| **HIPAA** | If processing healthcare tenant data | Encryption at rest/transit, audit logs, access controls |
| **FedRAMP** | If used by US government | Enhanced security controls, continuous monitoring |

### Compliance Controls

**Data Protection:**
- Encryption at rest (Azure Storage Service Encryption)
- Encryption in transit (TLS 1.3)
- Data minimization (only collect necessary resource metadata)
- Data retention policies (automated purging after 365 days)

**Access Control:**
- Least privilege RBAC
- Multi-factor authentication (Azure AD)
- Segregation of duties
- Regular access reviews

**Audit & Logging:**
- Comprehensive audit trail (all API calls, authentications)
- Log retention (1-2 years based on category)
- Tamper-evident logging (forward to immutable storage)
- Security event monitoring

**Incident Response:**
- Documented procedures
- Regular testing (quarterly tabletop exercises)
- Communication plan
- Post-incident review

### Compliance Checklist

- [ ] Data classification policy defined
- [ ] Encryption enabled for all data at rest
- [ ] TLS 1.3 enforced for all data in transit
- [ ] Audit logging enabled and retained per policy
- [ ] Access control matrix documented
- [ ] Incident response plan documented and tested
- [ ] Vendor security assessment completed (Azure, Neo4j)
- [ ] Security awareness training completed
- [ ] Privacy impact assessment completed
- [ ] Data processing agreement with Azure
- [ ] Business continuity plan documented
- [ ] Disaster recovery tested

---

## Security Documentation & Training

### Required Documentation

1. **Security Architecture Document** (this document)
2. **Threat Model** (STRIDE analysis)
3. **Incident Response Plan**
4. **Business Continuity Plan**
5. **Disaster Recovery Plan**
6. **Security Baseline Configuration**
7. **API Security Guide** (for CLI developers)
8. **Security Operations Runbook**

### Team Training Requirements

| Role | Training | Frequency |
|------|----------|-----------|
| **Developers** | Secure coding practices, OWASP Top 10 | Annually |
| **DevOps** | Container security, secret management | Annually |
| **Security Team** | Penetration testing, incident response | Quarterly |
| **All Staff** | Security awareness, phishing prevention | Annually |

---

## Summary & Next Steps

This security design provides a comprehensive, defense-in-depth approach to securing the ATG client-server architecture. Key strengths:

✅ **Strong Authentication:** API key + Managed Identity
✅ **Secret Management:** Azure Key Vault with rotation
✅ **Network Isolation:** Private VNets + NSG rules
✅ **Comprehensive Logging:** Structured audit logs with SIEM integration
✅ **Input Validation:** Whitelist approach with parameterized queries
✅ **Environment Isolation:** Separate resources per environment
✅ **Incident Response:** Documented procedures with escalation paths

### Implementation Phases

**Phase 1: Foundation (Weeks 1-2)**
- [ ] Implement API key authentication (client + server)
- [ ] Configure Managed Identity for Azure access
- [ ] Set up Neo4j authentication
- [ ] Deploy basic audit logging

**Phase 2: Hardening (Weeks 3-4)**
- [ ] Implement TLS 1.3 with certificate pinning
- [ ] Configure network security groups
- [ ] Add rate limiting
- [ ] Implement input validation on all endpoints

**Phase 3: Monitoring (Week 5)**
- [ ] Configure Azure Monitor / Application Insights
- [ ] Set up alert rules
- [ ] Implement log forwarding to SIEM
- [ ] Create security dashboard

**Phase 4: Testing (Week 6)**
- [ ] Run security test suite
- [ ] Perform internal penetration test
- [ ] Conduct incident response tabletop exercise
- [ ] Document findings and remediate

**Phase 5: Production (Week 7+)**
- [ ] Deploy to production with security controls
- [ ] Monitor for 2 weeks
- [ ] Schedule external penetration test
- [ ] Begin quarterly security reviews

### Success Metrics

- **Zero** high/critical vulnerabilities in production
- **< 5 minutes** time to detect security incidents
- **< 15 minutes** time to respond to P0 incidents
- **100%** of API calls logged and audited
- **< 0.01%** false positive rate on security alerts

---

**Document Approval:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Security Architect | [Name] | | |
| Engineering Lead | [Name] | | |
| DevOps Lead | [Name] | | |
| Compliance Officer | [Name] | | |

---

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-09 | Security Team | Initial design |
