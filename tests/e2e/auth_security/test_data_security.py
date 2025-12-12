"""
End-to-end tests for data security in transit and at rest.

This module tests encryption, data sanitization, secure storage,
data leakage prevention, and compliance with security standards.
"""

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from tests.e2e.auth_security.security_utils import (
    AuditLogger,
    EncryptionHelper,
    SecurityScanner,
    check_security_headers,
)


class DataSecurityService:
    """Mock service for testing data security features."""

    def __init__(self, encryption_key: Optional[bytes] = None):
        self.encryption_key = encryption_key or EncryptionHelper.generate_key()
        self.audit_logger = AuditLogger()
        self.scanner = SecurityScanner()
        self.sensitive_fields = [
            "password",
            "secret",
            "token",
            "api_key",
            "private_key",
            "ssn",
            "credit_card",
            "bank_account",
        ]

    def sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data before storage or transmission."""
        sanitized = {}
        for key, value in data.items():
            if any(field in key.lower() for field in self.sensitive_fields):
                # Mask sensitive fields
                if isinstance(value, str):
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = None
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self.sanitize_data(value)
            elif isinstance(value, list):
                # Handle lists
                sanitized[key] = [
                    self.sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized

    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in data."""
        encrypted = {}
        for key, value in data.items():
            if any(field in key.lower() for field in self.sensitive_fields):
                if isinstance(value, str):
                    encrypted[key] = {
                        "encrypted": True,
                        "value": EncryptionHelper.encrypt_data(
                            value, self.encryption_key
                        ),
                    }
                else:
                    encrypted[key] = value
            elif isinstance(value, dict):
                encrypted[key] = self.encrypt_sensitive_data(value)
            else:
                encrypted[key] = value
        return encrypted

    def decrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in data."""
        decrypted = {}
        for key, value in data.items():
            if isinstance(value, dict) and value.get("encrypted"):
                decrypted[key] = EncryptionHelper.decrypt_data(
                    value["value"], self.encryption_key
                )
            elif isinstance(value, dict):
                decrypted[key] = self.decrypt_sensitive_data(value)
            else:
                decrypted[key] = value
        return decrypted

    def validate_data_integrity(self, data: Any) -> str:
        """Calculate hash for data integrity validation."""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def scan_for_data_leakage(self, text: str) -> List[str]:
        """Scan text for potential data leakage."""
        issues = []

        # Check for sensitive data patterns
        sensitive_patterns = self.scanner.scan_for_sensitive_data(text)
        issues.extend(sensitive_patterns)

        # Check for exposed secrets
        if re.search(
            r"(password|secret|token|key)\s*[:=]\s*['\"]?[\w\-\.]+", text, re.IGNORECASE
        ):
            issues.append("Potential exposed credentials detected")

        # Check for internal IPs
        if re.search(
            r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b", text
        ):
            issues.append("Internal IP address exposed")

        # Check for file paths
        if re.search(r"[C-Z]:\\|/(?:home|usr|var|etc|opt)/", text):
            issues.append("System file path exposed")

        return issues


class TestDataSecurity:
    """Test data security features."""

    def test_data_encryption_at_rest(self):
        """Test that sensitive data is encrypted when stored."""
        service = DataSecurityService()

        # Test data with sensitive fields
        test_data = {
            "username": "testuser",
            "password": "MySecretPassword123!",  # pragma: allowlist secret
            "email": "test@example.com",
            "api_key": "test_api_key_fake_value_for_testing",  # pragma: allowlist secret
            "profile": {
                "name": "Test User",
                "ssn": "123-45-6789",
                "credit_card": "4111111111111111",
            },
        }

        # Encrypt sensitive data
        encrypted_data = service.encrypt_sensitive_data(test_data)

        # Verify sensitive fields are encrypted
        assert encrypted_data["password"]["encrypted"] is True
        assert "MySecretPassword123!" not in str(encrypted_data)
        assert encrypted_data["api_key"]["encrypted"] is True
        assert "test_api_key" not in str(encrypted_data)

        # Verify non-sensitive fields are not encrypted
        assert encrypted_data["username"] == "testuser"
        assert encrypted_data["email"] == "test@example.com"

        # Decrypt and verify
        decrypted_data = service.decrypt_sensitive_data(encrypted_data)
        assert decrypted_data["password"] == test_data["password"]
        assert decrypted_data["api_key"] == test_data["api_key"]

    def test_data_sanitization(self):
        """Test that sensitive data is properly sanitized."""
        service = DataSecurityService()

        # Test data with various sensitive fields
        test_data = {
            "user_id": "12345",
            "password": "SecretPass123",  # pragma: allowlist secret
            "auth_token": "Bearer eyJhbGciOiJIUzI1NiIs...",
            "api_secret": "secret_key_value",  # pragma: allowlist secret
            "public_info": "This is public",
            "nested": {
                "private_key": "-----BEGIN RSA PRIVATE KEY-----",  # pragma: allowlist secret
                "public_data": "visible",
            },
        }

        # Sanitize data
        sanitized = service.sanitize_data(test_data)

        # Verify sensitive fields are redacted
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["auth_token"] == "***REDACTED***"
        assert sanitized["api_secret"] == "***REDACTED***"
        assert sanitized["nested"]["private_key"] == "***REDACTED***"

        # Verify non-sensitive fields are preserved
        assert sanitized["user_id"] == "12345"
        assert sanitized["public_info"] == "This is public"
        assert sanitized["nested"]["public_data"] == "visible"

    def test_secure_data_transmission(self, security_headers):
        """Test that data transmission includes proper security headers."""
        # Simulate API response headers
        response_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
        }

        # Check security headers
        issues = check_security_headers(response_headers)
        assert len(issues) == 0  # No security header issues

        # Test with missing headers
        incomplete_headers = {"Content-Type": "application/json"}
        issues = check_security_headers(incomplete_headers)
        assert len(issues) > 0
        assert any("X-Content-Type-Options" in issue for issue in issues)

    def test_data_integrity_validation(self):
        """Test data integrity checking mechanisms."""
        service = DataSecurityService()

        # Original data
        original_data = {
            "id": "12345",
            "name": "Test Entity",
            "value": 100,
            "timestamp": "2024-01-01T00:00:00Z",
        }

        # Calculate integrity hash
        original_hash = service.validate_data_integrity(original_data)

        # Verify same data produces same hash
        duplicate_hash = service.validate_data_integrity(original_data)
        assert original_hash == duplicate_hash

        # Modify data slightly
        tampered_data = original_data.copy()
        tampered_data["value"] = 101

        # Verify tampered data produces different hash
        tampered_hash = service.validate_data_integrity(tampered_data)
        assert original_hash != tampered_hash

    def test_data_leakage_prevention(self):
        """Test prevention of sensitive data leakage."""
        service = DataSecurityService()

        # Test various leakage scenarios
        test_cases = [
            ("Error: password=MySecret123 in config", ["exposed credentials"]),
            ("Server IP: 192.168.1.100", ["Internal IP"]),
            ("File path: /home/user/.ssh/id_rsa", ["file path"]),
            ("API Key: test_live_api_key_fake_value", ["API key"]),
            ("SSN: 123-45-6789", ["SSN"]),
        ]

        for text, expected_issues in test_cases:
            issues = service.scan_for_data_leakage(text)
            assert len(issues) > 0
            for expected in expected_issues:
                assert any(expected in issue for issue in issues)

    def test_secure_file_storage(self):
        """Test secure storage of files with encryption."""
        service = DataSecurityService()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file with sensitive data
            sensitive_content = {
                "database_password": "db_pass_123",  # pragma: allowlist secret
                "api_keys": {"stripe": "test_stripe_key_fake", "aws": "AKIA_test_key"},
            }

            # Encrypt before saving
            encrypted_content = service.encrypt_sensitive_data(sensitive_content)

            # Save encrypted file
            file_path = os.path.join(temp_dir, "sensitive_data.json")
            with open(file_path, "w") as f:
                json.dump(encrypted_content, f)

            # Read and verify encryption
            with open(file_path) as f:
                loaded_data = json.load(f)

            # Verify sensitive data is not in plain text
            file_content = open(file_path).read()
            assert "db_pass_123" not in file_content
            assert "test_stripe_key" not in file_content

            # Decrypt and verify
            decrypted = service.decrypt_sensitive_data(loaded_data)
            assert (
                decrypted["database_password"] == "db_pass_123"
            )  # pragma: allowlist secret

    def test_database_query_parameterization(self):
        """Test that database queries are parameterized to prevent injection."""

        # Mock database interface
        class SecureDatabase:
            def __init__(self):
                self.queries = []

            def execute_query(self, query: str, params: Optional[tuple] = None):
                """Execute parameterized query."""
                # Check for SQL injection patterns in query
                scanner = SecurityScanner()
                vulnerabilities = scanner.scan_for_sql_injection(query)

                if vulnerabilities and not params:
                    raise ValueError("Potential SQL injection detected")

                self.queries.append((query, params))
                return []

        db = SecureDatabase()

        # Safe parameterized query
        safe_query = "SELECT * FROM users WHERE id = ? AND status = ?"
        db.execute_query(safe_query, (123, "active"))

        # Unsafe query should be rejected
        unsafe_query = "SELECT * FROM users WHERE id = '123' OR '1'='1'"
        with pytest.raises(ValueError) as exc_info:
            db.execute_query(unsafe_query)
        assert "SQL injection" in str(exc_info.value)

    def test_sensitive_data_masking_in_logs(self):
        """Test that sensitive data is masked in logs."""
        service = DataSecurityService()
        audit_logger = AuditLogger()

        # Log entry with sensitive data
        log_data = {
            "event": "user_login",
            "username": "testuser",
            "password": "SecretPass123",  # pragma: allowlist secret
            "ip_address": "192.168.1.100",
            "session_token": "eyJhbGciOiJIUzI1NiIs...",
        }

        # Sanitize before logging
        sanitized_log = service.sanitize_data(log_data)

        # Log sanitized data
        audit_logger.events.append(sanitized_log)

        # Verify sensitive data is not in logs
        log_content = str(audit_logger.events)
        assert "SecretPass123" not in log_content
        assert "***REDACTED***" in log_content
        assert "testuser" in log_content  # Non-sensitive data preserved

    def test_secure_data_deletion(self):
        """Test secure deletion of sensitive data."""
        import os

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "sensitive.txt")

            # Write sensitive data
            sensitive_data = "PASSWORD=SuperSecret123\nAPI_KEY=sk_live_key"  # pragma: allowlist secret
            with open(file_path, "w") as f:
                f.write(sensitive_data)

            # Secure deletion (overwrite before delete)
            def secure_delete(filepath):
                """Securely delete file by overwriting first."""
                if os.path.exists(filepath):
                    filesize = os.path.getsize(filepath)
                    with open(filepath, "wb") as f:
                        # Overwrite with random data
                        f.write(os.urandom(filesize))
                        f.flush()
                        os.fsync(f.fileno())
                    os.remove(filepath)

            # Perform secure deletion
            secure_delete(file_path)

            # Verify file is deleted
            assert not os.path.exists(file_path)

    def test_data_anonymization(self):
        """Test data anonymization for compliance."""

        class DataAnonymizer:
            @staticmethod
            def anonymize_pii(data: Dict[str, Any]) -> Dict[str, Any]:
                """Anonymize personally identifiable information."""
                anonymized = data.copy()

                # Anonymize email
                if "email" in anonymized:
                    email = anonymized["email"]
                    if "@" in email:
                        local, domain = email.split("@")
                        anonymized["email"] = f"{local[:2]}***@{domain}"

                # Anonymize phone
                if "phone" in anonymized:
                    phone = str(anonymized["phone"])
                    anonymized["phone"] = f"***-***-{phone[-4:]}"

                # Anonymize name
                if "name" in anonymized:
                    name = anonymized["name"]
                    anonymized["name"] = f"{name[0]}***"

                # Hash user ID
                if "user_id" in anonymized:
                    anonymized["user_id"] = hashlib.sha256(
                        str(anonymized["user_id"]).encode()
                    ).hexdigest()[:16]

                return anonymized

        anonymizer = DataAnonymizer()

        # Test data with PII
        original_data = {
            "user_id": "12345",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "555-123-4567",
            "age": 30,
        }

        # Anonymize data
        anonymized = anonymizer.anonymize_pii(original_data)

        # Verify PII is anonymized
        assert anonymized["email"] == "jo***@example.com"
        assert anonymized["phone"] == "***-***-4567"
        assert anonymized["name"] == "J***"
        assert anonymized["user_id"] != "12345"
        assert len(anonymized["user_id"]) == 16  # Hashed

        # Non-PII data preserved
        assert anonymized["age"] == 30

    def test_encryption_key_management(self):
        """Test secure management of encryption keys."""

        class KeyManager:
            def __init__(self):
                self.keys = {}
                self.audit_logger = AuditLogger()

            def generate_key(self, key_id: str) -> bytes:
                """Generate and store encryption key."""
                key = EncryptionHelper.generate_key()
                # Never store key in plain text
                key_hash = hashlib.sha256(key).hexdigest()
                self.keys[key_id] = {
                    "hash": key_hash,
                    "created": datetime.now(timezone.utc).isoformat(),
                }
                self.audit_logger.log_security_violation(
                    violation_type="key_generation",
                    details=f"Key {key_id} generated",
                    source_ip="system",
                    user_id="system",
                )
                return key

            def rotate_key(self, old_key_id: str, new_key_id: str) -> bytes:
                """Rotate encryption key."""
                if old_key_id in self.keys:
                    self.keys[old_key_id]["rotated"] = True
                    self.keys[old_key_id]["rotated_to"] = new_key_id

                new_key = self.generate_key(new_key_id)
                return new_key

        key_manager = KeyManager()

        # Generate key
        key1 = key_manager.generate_key("key_2024_01")
        assert len(key1) > 0
        assert "key_2024_01" in key_manager.keys

        # Rotate key
        key2 = key_manager.rotate_key("key_2024_01", "key_2024_02")
        assert key1 != key2
        assert key_manager.keys["key_2024_01"].get("rotated") is True

    def test_secure_data_export(self):
        """Test that data exports are secured and audited."""
        service = DataSecurityService()
        audit_logger = AuditLogger()

        # Data to export
        export_data = {
            "users": [
                {"id": 1, "name": "User1", "ssn": "123-45-6789"},
                {"id": 2, "name": "User2", "ssn": "987-65-4321"},
            ],
            "api_key": "secret_key_123",  # pragma: allowlist secret
        }

        # Sanitize before export
        sanitized_export = service.sanitize_data(export_data)

        # Log export event
        audit_logger.log_security_violation(
            violation_type="data_export",
            details=f"Data exported with {len(export_data['users'])} users",
            source_ip="192.168.1.100",
            user_id="admin",
        )

        # Verify sensitive data is sanitized
        assert all(
            user.get("ssn") == "***REDACTED***" for user in sanitized_export["users"]
        )
        assert sanitized_export["api_key"] == "***REDACTED***"

        # Verify export was logged
        events = audit_logger.get_events(event_type="security_violation")
        assert len(events) == 1
        assert "data_export" in events[0]["violation_type"]

    def test_data_classification_enforcement(self):
        """Test that data classification levels are enforced."""

        class DataClassifier:
            CLASSIFICATIONS = {
                "public": 0,
                "internal": 1,
                "confidential": 2,
                "restricted": 3,
            }

            @classmethod
            def classify_field(cls, field_name: str, value: Any) -> str:
                """Classify data field based on content."""
                field_lower = field_name.lower()

                if any(
                    term in field_lower
                    for term in ["password", "secret", "key", "token"]
                ):
                    return "restricted"
                elif any(
                    term in field_lower for term in ["ssn", "credit_card", "bank"]
                ):
                    return "confidential"
                elif any(term in field_lower for term in ["email", "phone", "address"]):
                    return "internal"
                else:
                    return "public"

            @classmethod
            def can_access(cls, user_clearance: str, data_classification: str) -> bool:
                """Check if user can access data based on classification."""
                user_level = cls.CLASSIFICATIONS.get(user_clearance, 0)
                data_level = cls.CLASSIFICATIONS.get(data_classification, 3)
                return user_level >= data_level

        # Test classification
        assert DataClassifier.classify_field("password", "test") == "restricted"
        assert DataClassifier.classify_field("email", "test@example.com") == "internal"
        assert DataClassifier.classify_field("name", "John") == "public"

        # Test access control
        assert DataClassifier.can_access("restricted", "confidential")
        assert not DataClassifier.can_access("internal", "restricted")
        assert DataClassifier.can_access("public", "public")
