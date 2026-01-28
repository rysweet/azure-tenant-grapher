"""
Tests for Security Controls (Issue #627).

Test Coverage:
- Rate limiting enforcement (1 reset/hour/tenant)
- Distributed lock (concurrent prevention via Redis)
- Input validation (injection prevention)
- Audit log tamper detection
- No force flag bypass
- Secure error messages
- Pre-flight validation
- Post-deletion verification
- Exponential backoff
- Circuit breaker

Target: 100% coverage for all 10 security controls
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
import json
import hashlib
from pathlib import Path

# Imports will fail until implementation exists
from src.services.tenant_reset_service import (
    TenantResetService,
    TenantResetRateLimiter,
    SecureErrorHandler,
    validate_config_integrity,
)
from src.services.reset_confirmation import ResetScope
from src.services.audit_log import TamperProofAuditLog
from src.services.reset_confirmation import SecurityError


class TestRateLimiting:
    """Test rate limiting for tenant reset operations."""

    @pytest.fixture
    def rate_limiter(self, tmp_path):
        """Create TenantResetRateLimiter instance with isolated state file."""
        state_file = tmp_path / "test-rate-limiter-state.json"
        return TenantResetRateLimiter(state_file=state_file)

    def test_rate_limit_first_reset_allowed(self, rate_limiter):
        """Test that first reset is allowed immediately."""
        tenant_id = "tenant-1"

        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

        assert allowed is True
        assert wait_seconds is None

    def test_rate_limit_second_reset_blocked(self, rate_limiter):
        """
        CRITICAL: Test that second reset within 1 hour is blocked.
        """
        tenant_id = "tenant-1"

        # First reset
        allowed1, _ = rate_limiter.check_rate_limit(tenant_id)
        assert allowed1 is True

        # Second reset immediately (should be blocked)
        allowed2, wait_seconds = rate_limiter.check_rate_limit(tenant_id)
        assert allowed2 is False
        assert wait_seconds is not None
        assert wait_seconds > 0
        assert wait_seconds <= 3600  # Max 1 hour wait

    def test_rate_limit_reset_after_wait_period(self, rate_limiter):
        """Test that reset is allowed after wait period expires."""
        tenant_id = "tenant-1"

        # First reset
        rate_limiter.check_rate_limit(tenant_id)

        # Manually refill bucket (simulate 1 hour passing)
        bucket = rate_limiter.buckets[tenant_id]
        bucket["tokens"] = 1.0  # Refill to full
        bucket["last_refill"] = time.time()  # Reset refill timestamp

        # Second reset after refill (should be allowed)
        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)
        assert allowed is True
        assert wait_seconds is None

    def test_rate_limit_different_tenants_independent(self, rate_limiter):
        """Test that rate limits are per-tenant (independent)."""
        tenant_id_1 = "tenant-1"
        tenant_id_2 = "tenant-2"

        # Reset tenant 1
        allowed1, _ = rate_limiter.check_rate_limit(tenant_id_1)
        assert allowed1 is True

        # Reset tenant 2 immediately (should be allowed, different tenant)
        allowed2, _ = rate_limiter.check_rate_limit(tenant_id_2)
        assert allowed2 is True

    def test_rate_limit_exponential_backoff_after_failures(self, rate_limiter):
        """Test that rate limit increases exponentially after failures."""
        tenant_id = "tenant-1"

        # First reset
        rate_limiter.check_rate_limit(tenant_id)

        # Record 3 failures
        rate_limiter.record_failure(tenant_id)
        rate_limiter.record_failure(tenant_id)
        rate_limiter.record_failure(tenant_id)

        # Check that refill rate decreased (slower refill = longer wait)
        bucket = rate_limiter.buckets[tenant_id]
        assert bucket["refill_rate"] < 1.0 / 3600  # Slower than initial rate

    def test_rate_limit_wait_time_calculation(self, rate_limiter):
        """Test that wait time is calculated correctly."""
        tenant_id = "tenant-1"

        # First reset
        rate_limiter.check_rate_limit(tenant_id)

        # Second reset immediately
        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

        assert not allowed
        # Wait time should be close to 1 hour (3600 seconds)
        assert 3500 <= wait_seconds <= 3600


class TestDistributedLock:
    """Test distributed locking for concurrent reset prevention."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch("redis.Redis") as mock:
            yield mock.return_value

    @pytest.mark.asyncio
    async def test_lock_acquisition_success(self, mock_redis):
        """Test successful lock acquisition."""
        from src.services.tenant_reset_service import tenant_reset_lock

        tenant_id = "tenant-1"
        mock_redis.set.return_value = True  # Lock acquired

        async with tenant_reset_lock(tenant_id):
            # Inside lock - should succeed
            pass

        # Verify lock was acquired and released
        mock_redis.set.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_acquisition_failure_concurrent_reset(self, mock_redis):
        """
        CRITICAL: Test that concurrent reset is blocked by lock.
        """
        from src.services.tenant_reset_service import tenant_reset_lock

        tenant_id = "tenant-1"
        mock_redis.set.return_value = False  # Lock NOT acquired (already held)

        with pytest.raises(SecurityError) as exc:
            async with tenant_reset_lock(tenant_id):
                pass

        assert "already in progress" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_lock_auto_expiration(self, mock_redis):
        """Test that lock auto-expires after timeout."""
        from src.services.tenant_reset_service import tenant_reset_lock

        tenant_id = "tenant-1"
        timeout = 3600
        mock_redis.set.return_value = True

        async with tenant_reset_lock(tenant_id, timeout=timeout):
            pass

        # Verify expiration time was set
        call_args = mock_redis.set.call_args
        assert call_args[1]["ex"] == timeout

    @pytest.mark.asyncio
    async def test_lock_different_tenants_independent(self, mock_redis):
        """Test that locks are per-tenant (independent)."""
        from src.services.tenant_reset_service import tenant_reset_lock

        tenant_id_1 = "tenant-1"
        tenant_id_2 = "tenant-2"
        mock_redis.set.return_value = True

        # Lock tenant 1
        async with tenant_reset_lock(tenant_id_1):
            # Lock tenant 2 (should succeed, different tenant)
            async with tenant_reset_lock(tenant_id_2):
                pass

        # Both locks should be acquired
        assert mock_redis.set.call_count == 2

    @pytest.mark.asyncio
    async def test_lock_released_on_exception(self, mock_redis):
        """Test that lock is released even if operation fails."""
        from src.services.tenant_reset_service import tenant_reset_lock

        tenant_id = "tenant-1"
        mock_redis.set.return_value = True

        try:
            async with tenant_reset_lock(tenant_id):
                raise Exception("Operation failed")
        except Exception:
            pass

        # Lock should still be released
        mock_redis.delete.assert_called_once()


class TestInputValidation:
    """Test input validation to prevent injection attacks."""

    def test_valid_tenant_id_guid_format(self):
        """Test that valid GUID tenant ID passes validation."""
        from src.services.reset_confirmation import ResetScope

        tenant_id = "12345678-1234-1234-1234-123456789abc"

        # Should not raise
        scope = ResetScope(level="tenant", tenant_id=tenant_id)
        assert scope.tenant_id == tenant_id

    def test_invalid_tenant_id_injection_attempt(self):
        """
        CRITICAL: Test that malformed tenant ID is rejected.
        """
        from src.services.reset_confirmation import ResetScope

        # Cypher injection attempt
        malicious_tenant_id = "'; DROP ALL; --"

        with pytest.raises(ValueError) as exc:
            ResetScope(level="tenant", tenant_id=malicious_tenant_id)

        assert "invalid" in str(exc.value).lower()

    def test_valid_subscription_id_guid_format(self):
        """Test that valid GUID subscription ID passes validation."""
        from src.services.reset_confirmation import ResetScope

        subscription_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        scope = ResetScope(
            level="subscription",
            tenant_id="12345678-1234-1234-1234-123456789abc",
            subscription_id=subscription_id,
        )
        assert scope.subscription_id == subscription_id

    def test_invalid_subscription_id_rejected(self):
        """Test that malformed subscription ID is rejected."""
        from src.services.reset_confirmation import ResetScope

        malicious_subscription_id = "../../../etc/passwd"

        with pytest.raises(ValueError) as exc:
            ResetScope(
                level="subscription",
                tenant_id="12345678-1234-1234-1234-123456789abc",
                subscription_id=malicious_subscription_id,
            )

        assert "invalid" in str(exc.value).lower()

    def test_valid_resource_group_name(self):
        """Test that valid resource group name passes validation."""
        from src.services.reset_confirmation import ResetScope

        resource_group = "my-test-rg_123"

        scope = ResetScope(
            level="resource-group",
            tenant_id="12345678-1234-1234-1234-123456789abc",
            subscription_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            resource_group=resource_group,
        )
        assert scope.resource_group == resource_group

    def test_invalid_resource_group_name_injection(self):
        """
        CRITICAL: Test that malformed resource group name is rejected.
        """
        from src.services.reset_confirmation import ResetScope

        # Path traversal attempt
        malicious_rg_name = "../../../etc/passwd"

        with pytest.raises(ValueError) as exc:
            ResetScope(
                level="resource-group",
                tenant_id="12345678-1234-1234-1234-123456789abc",
                subscription_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                resource_group=malicious_rg_name,
            )

        assert "invalid" in str(exc.value).lower()

    def test_resource_group_name_length_limit(self):
        """Test that resource group name > 90 chars is rejected."""
        from src.services.reset_confirmation import ResetScope

        long_rg_name = "a" * 91  # Exceeds 90 char limit

        with pytest.raises(ValueError) as exc:
            ResetScope(
                level="resource-group",
                tenant_id="12345678-1234-1234-1234-123456789abc",
                subscription_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                resource_group=long_rg_name,
            )

        assert "invalid" in str(exc.value).lower()

    def test_valid_azure_resource_id(self):
        """Test that valid Azure resource ID passes validation."""
        from src.services.reset_confirmation import ResetScope

        resource_id = (
            "/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/"
            "resourceGroups/test-rg/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        scope = ResetScope(
            level="resource",
            tenant_id="12345678-1234-1234-1234-123456789abc",
            resource_id=resource_id,
        )
        assert scope.resource_id == resource_id

    def test_invalid_resource_id_format_rejected(self):
        """Test that malformed resource ID is rejected."""
        from src.services.reset_confirmation import ResetScope

        malicious_resource_id = "'; DELETE FROM resources; --"

        with pytest.raises(ValueError) as exc:
            ResetScope(
                level="resource",
                tenant_id="12345678-1234-1234-1234-123456789abc",
                resource_id=malicious_resource_id,
            )

        assert "invalid" in str(exc.value).lower()


class TestAuditLogTamperDetection:
    """Test tamper-proof audit logging."""

    @pytest.fixture
    def audit_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "audit.jsonl"

    @pytest.fixture
    def audit_log(self, audit_log_file):
        """Create TamperProofAuditLog instance."""
        return TamperProofAuditLog(audit_log_file)

    def test_audit_log_initial_entry(self, audit_log):
        """Test initial audit log entry."""
        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-1",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-1"},
                "resources_deleted": ["resource-1", "resource-2"],
                "identities_deleted": ["identity-1"],
                "operator": "user@example.com",
                "duration_seconds": 120.5,
            },
        )

        # Log file should exist
        assert audit_log.log_path.exists()

        # Should have two lines (genesis + new entry)
        lines = audit_log.log_path.read_text().splitlines()
        assert len(lines) == 2

    def test_audit_log_cryptographic_chain(self, audit_log):
        """Test that audit log creates cryptographic chain."""
        # Log first entry
        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-1",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-1"},
                "resources_deleted": ["resource-1"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 100.0,
            },
        )

        # Log second entry
        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-2",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-2"},
                "resources_deleted": ["resource-2"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 200.0,
            },
        )

        lines = audit_log.log_path.read_text().splitlines()
        assert len(lines) == 3  # genesis + 2 entries

        entry1 = json.loads(lines[1])  # First real entry (after genesis)
        entry2 = json.loads(lines[2])  # Second real entry

        # Second entry should reference first entry's hash
        assert entry2["previous_hash"] == entry1["hash"]

    def test_audit_log_tampering_detection(self, audit_log):
        """
        CRITICAL: Test that tampering with audit log is detected.
        """
        # Log entry
        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-1",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-1"},
                "resources_deleted": ["resource-1"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 100.0,
            },
        )

        # Tamper with log file
        content = audit_log.log_path.read_text()
        tampered_content = content.replace("tenant-1", "tenant-2")
        audit_log.log_path.write_text(tampered_content)

        # Verify integrity should raise ValueError (tampering detection)
        with pytest.raises(ValueError) as exc:
            audit_log.verify_integrity()

        assert "AUDIT LOG TAMPERING DETECTED" in str(exc.value)

    def test_audit_log_integrity_verification_success(self, audit_log):
        """Test that unmodified audit log passes integrity check."""
        # Log entries
        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-1",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-1"},
                "resources_deleted": ["resource-1"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 100.0,
            },
        )

        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-2",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-2"},
                "resources_deleted": ["resource-2"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 200.0,
            },
        )

        # Should pass integrity check
        assert audit_log.verify_integrity() is True

    def test_audit_log_append_only(self, audit_log):
        """Test that audit log is append-only."""
        # Log entries
        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-1",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-1"},
                "resources_deleted": ["resource-1"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 100.0,
            },
        )

        first_content = audit_log.log_path.read_text()

        audit_log.append(
            event="tenant_reset",
            tenant_id="tenant-2",
            details={
                "scope": {"level": "tenant", "tenant_id": "tenant-2"},
                "resources_deleted": ["resource-2"],
                "identities_deleted": [],
                "operator": "user@example.com",
                "duration_seconds": 200.0,
            },
        )

        second_content = audit_log.log_path.read_text()

        # First entry should still be present
        assert first_content in second_content


class TestSecureErrorMessages:
    """Test secure error message sanitization."""

    def test_error_message_sanitizes_resource_ids(self):
        """Test that resource IDs are redacted from error messages."""
        error = Exception(
            "Failed to delete resource "
            "/subscriptions/12345678-1234-1234-1234-123456789012/"
            "resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-prod-001"
        )

        sanitized = SecureErrorHandler.sanitize_error(error)

        # Sensitive info should be redacted
        assert "12345678-1234-1234-1234-123456789012" not in sanitized
        assert "***REDACTED***" in sanitized or "***GUID***" in sanitized

    def test_error_message_sanitizes_guids(self):
        """Test that GUIDs are redacted from error messages."""
        error = Exception(
            "Operation failed for principal 87654321-4321-4321-4321-210987654321"
        )

        sanitized = SecureErrorHandler.sanitize_error(error)

        assert "87654321-4321-4321-4321-210987654321" not in sanitized
        assert "***GUID***" in sanitized

    def test_error_message_sanitizes_file_paths(self):
        """Test that file paths are redacted from error messages."""
        error = Exception("Failed to read /home/user/.azure/credentials.json")

        sanitized = SecureErrorHandler.sanitize_error(error)

        assert "/home/user/.azure/credentials.json" not in sanitized
        assert "***PATH***" in sanitized

    def test_error_message_sanitizes_ip_addresses(self):
        """Test that IP addresses are redacted from error messages."""
        error = Exception("Connection failed to 192.168.1.100:443")

        sanitized = SecureErrorHandler.sanitize_error(error)

        assert "192.168.1.100" not in sanitized
        assert "***IP***" in sanitized

    def test_error_message_preserves_general_info(self):
        """Test that general error information is preserved."""
        error = Exception("Connection timeout")

        sanitized = SecureErrorHandler.sanitize_error(error)

        # General message should be preserved
        assert "Connection timeout" in sanitized


class TestNoForceFlag:
    """Test that --force and --yes flags do NOT exist."""

    def test_cli_no_force_flag_tenant_command(self):
        """Test that tenant reset command has no --force flag."""
        from click.testing import CliRunner
        from src.commands.tenant_reset import reset_tenant_command

        runner = CliRunner()
        result = runner.invoke(reset_tenant_command, ["--help"])

        assert "--force" not in result.output

    def test_cli_force_flag_rejected(self):
        """
        CRITICAL: Test that using --force flag fails.
        """
        from click.testing import CliRunner
        from src.commands.tenant_reset import reset_tenant_command

        runner = CliRunner()
        result = runner.invoke(
            reset_tenant_command,
            ["--tenant-id", "test-tenant", "--force"]
        )

        assert result.exit_code != 0
        assert "no such option" in result.output.lower()

    def test_cli_yes_flag_rejected(self):
        """
        CRITICAL: Test that using --yes flag fails.
        """
        from click.testing import CliRunner
        from src.commands.tenant_reset import reset_tenant_command

        runner = CliRunner()
        result = runner.invoke(
            reset_tenant_command,
            ["--tenant-id", "test-tenant", "--yes"]
        )

        assert result.exit_code != 0
        assert "no such option" in result.output.lower()


# Marker for security-critical tests
pytestmark = pytest.mark.security
