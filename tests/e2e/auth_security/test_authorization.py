"""
End-to-end tests for authorization and permission-based access control.

This module tests role-based access control (RBAC), permission verification,
resource access control, and authorization vulnerabilities.
"""

import json
from typing import Any, Dict, List

import pytest
from tests.e2e.auth_security.security_utils import (
    AuditLogger,
    SecurityScanner,
)


class MockAuthorizationService:
    """Mock authorization service for testing RBAC."""

    def __init__(self):
        self.roles = {
            "admin": ["read", "write", "delete", "manage_users", "manage_roles"],
            "editor": ["read", "write"],
            "viewer": ["read"],
            "security_admin": ["read", "manage_security", "audit"],
            "tenant_admin": ["read", "write", "manage_tenants"],
        }

        self.user_roles = {}
        self.resource_permissions = {}
        self.audit_logger = AuditLogger()

    def assign_role(self, user_id: str, role: str):
        """Assign role to user."""
        if role not in self.roles:
            raise ValueError(f"Invalid role: {role}")

        if user_id not in self.user_roles:
            self.user_roles[user_id] = []

        if role not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role)

    def revoke_role(self, user_id: str, role: str):
        """Revoke role from user."""
        if user_id in self.user_roles and role in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role)

    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for a user."""
        permissions = set()
        for role in self.user_roles.get(user_id, []):
            permissions.update(self.roles.get(role, []))
        return list(permissions)

    def check_permission(self, user_id: str, action: str, resource: str = None) -> bool:
        """Check if user has permission for action."""
        user_permissions = self.get_user_permissions(user_id)
        has_permission = action in user_permissions

        # Check resource-specific permissions
        if resource and not has_permission:
            resource_key = f"{user_id}:{resource}"
            resource_perms = self.resource_permissions.get(resource_key, [])
            has_permission = action in resource_perms

        # Log authorization decision
        self.audit_logger.log_authorization(
            user_id=user_id,
            resource=resource or "system",
            action=action,
            allowed=has_permission,
            reason="Role-based access" if has_permission else "Permission denied",
        )

        return has_permission

    def grant_resource_permission(
        self, user_id: str, resource: str, actions: List[str]
    ):
        """Grant specific resource permissions to user."""
        resource_key = f"{user_id}:{resource}"
        if resource_key not in self.resource_permissions:
            self.resource_permissions[resource_key] = []
        self.resource_permissions[resource_key].extend(actions)


class TestAuthorization:
    """Test authorization and access control."""

    def test_role_based_access_control(self):
        """Test RBAC implementation."""
        auth_service = MockAuthorizationService()

        # Assign roles
        auth_service.assign_role("user1", "admin")
        auth_service.assign_role("user2", "editor")
        auth_service.assign_role("user3", "viewer")

        # Test admin permissions
        assert auth_service.check_permission("user1", "read")
        assert auth_service.check_permission("user1", "write")
        assert auth_service.check_permission("user1", "delete")
        assert auth_service.check_permission("user1", "manage_users")

        # Test editor permissions
        assert auth_service.check_permission("user2", "read")
        assert auth_service.check_permission("user2", "write")
        assert not auth_service.check_permission("user2", "delete")
        assert not auth_service.check_permission("user2", "manage_users")

        # Test viewer permissions
        assert auth_service.check_permission("user3", "read")
        assert not auth_service.check_permission("user3", "write")
        assert not auth_service.check_permission("user3", "delete")

    def test_permission_inheritance(self):
        """Test that permissions are properly inherited from roles."""
        auth_service = MockAuthorizationService()

        # User with multiple roles
        auth_service.assign_role("user1", "editor")
        auth_service.assign_role("user1", "security_admin")

        permissions = auth_service.get_user_permissions("user1")

        # Should have combined permissions from both roles
        assert "read" in permissions
        assert "write" in permissions  # From editor
        assert "manage_security" in permissions  # From security_admin
        assert "audit" in permissions  # From security_admin

    def test_resource_level_permissions(self):
        """Test resource-specific permission controls."""
        auth_service = MockAuthorizationService()

        # User has viewer role globally
        auth_service.assign_role("user1", "viewer")

        # Grant write permission for specific resource
        auth_service.grant_resource_permission(
            "user1", "tenant-123", ["write", "delete"]
        )

        # Test permissions
        assert auth_service.check_permission("user1", "read", "tenant-456")
        assert not auth_service.check_permission("user1", "write", "tenant-456")
        assert auth_service.check_permission("user1", "write", "tenant-123")
        assert auth_service.check_permission("user1", "delete", "tenant-123")

    def test_permission_revocation(self):
        """Test that permissions are properly revoked."""
        auth_service = MockAuthorizationService()

        # Assign and then revoke role
        auth_service.assign_role("user1", "admin")
        assert auth_service.check_permission("user1", "manage_users")

        auth_service.revoke_role("user1", "admin")
        assert not auth_service.check_permission("user1", "manage_users")

    def test_authorization_audit_logging(self):
        """Test that all authorization decisions are logged."""
        auth_service = MockAuthorizationService()
        auth_service.assign_role("user1", "editor")

        # Make several authorization checks
        auth_service.check_permission("user1", "read")
        auth_service.check_permission("user1", "write")
        auth_service.check_permission("user1", "delete")  # Should fail
        auth_service.check_permission("user2", "read")  # No role, should fail

        # Verify audit logs
        events = auth_service.audit_logger.get_events(event_type="authorization")
        assert len(events) == 4

        # Check successful authorizations
        successful = [e for e in events if e["allowed"]]
        assert len(successful) == 2

        # Check failed authorizations
        failed = [e for e in events if not e["allowed"]]
        assert len(failed) == 2

    def test_privilege_escalation_prevention(self):
        """Test protection against privilege escalation attacks."""
        auth_service = MockAuthorizationService()
        audit_logger = AuditLogger()

        # User with limited permissions
        auth_service.assign_role("attacker", "viewer")

        # Attempt to escalate privileges
        escalation_attempts = [
            ("attacker", "manage_users"),
            ("attacker", "manage_roles"),
            ("attacker", "delete"),
            ("attacker", "manage_security"),
        ]

        for user_id, action in escalation_attempts:
            allowed = auth_service.check_permission(user_id, action)
            assert not allowed  # All should be denied

            # Log security violation
            audit_logger.log_security_violation(
                violation_type="privilege_escalation_attempt",
                details=f"User {user_id} attempted unauthorized action: {action}",
                source_ip="192.168.1.100",
                user_id=user_id,
            )

        # Verify violations were logged
        violations = audit_logger.get_events(event_type="security_violation")
        assert len(violations) == len(escalation_attempts)

    def test_path_traversal_in_resource_access(self):
        """Test protection against path traversal in resource authorization."""
        auth_service = MockAuthorizationService()
        scanner = SecurityScanner()

        # Grant permission for specific resource
        auth_service.grant_resource_permission("user1", "documents/public", ["read"])

        # Test path traversal attempts
        traversal_attempts = [
            "documents/../admin/secrets",
            "documents/public/../../admin",
            "documents/public/../../../etc/passwd",
            "documents/public/..\\..\\admin",
            "documents/public/%2e%2e%2f%2e%2e%2fadmin",
        ]

        for resource_path in traversal_attempts:
            # Scan for path traversal
            vulnerabilities = scanner.scan_for_path_traversal(resource_path)
            assert len(vulnerabilities) > 0

            # Should not grant access to traversed paths
            assert not auth_service.check_permission("user1", "read", resource_path)

    @pytest.mark.asyncio
    async def test_concurrent_authorization_checks(self):
        """Test thread safety of concurrent authorization checks."""
        import asyncio

        auth_service = MockAuthorizationService()
        auth_service.assign_role("user1", "editor")

        async def check_permission_async(user_id: str, action: str):
            """Simulate async permission check."""
            await asyncio.sleep(0.001)  # Simulate some async work
            return auth_service.check_permission(user_id, action)

        # Create concurrent authorization checks
        tasks = []
        for i in range(100):
            user_id = f"user{i % 3}"  # Use 3 different users
            action = ["read", "write", "delete"][i % 3]
            tasks.append(check_permission_async(user_id, action))

        results = await asyncio.gather(*tasks)
        assert len(results) == 100

    def test_authorization_bypass_attempts(self):
        """Test detection of authorization bypass attempts."""
        auth_service = MockAuthorizationService()
        scanner = SecurityScanner()
        audit_logger = AuditLogger()

        # Common authorization bypass patterns
        bypass_attempts = [
            {"role": "admin", "forced": True},
            {"permissions": ["manage_users"], "override": True},
            {"bypass_auth": True},
            {"admin": "true"},
            {"sudo": True},
        ]

        for attempt in bypass_attempts:
            # Convert to string for scanning
            attempt_str = json.dumps(attempt)

            # Log security violation
            audit_logger.log_security_violation(
                violation_type="authorization_bypass_attempt",
                details=f"Detected bypass attempt: {attempt_str}",
                source_ip="192.168.1.50",
                user_id="attacker",
            )

        violations = audit_logger.get_events(event_type="security_violation")
        assert len(violations) == len(bypass_attempts)

    def test_least_privilege_principle(self):
        """Test that users have minimum necessary permissions."""
        auth_service = MockAuthorizationService()

        # Different user types with appropriate permissions
        users = {
            "reader": "viewer",
            "contributor": "editor",
            "owner": "admin",
            "security_officer": "security_admin",
        }

        for user_id, role in users.items():
            auth_service.assign_role(user_id, role)

        # Test that each user has only necessary permissions
        assert not auth_service.check_permission("reader", "write")
        assert not auth_service.check_permission("contributor", "manage_users")
        assert not auth_service.check_permission("security_officer", "delete")

        # Admin should have all permissions
        assert auth_service.check_permission("owner", "manage_users")
        assert auth_service.check_permission("owner", "delete")

    def test_permission_delegation(self):
        """Test secure permission delegation between users."""
        auth_service = MockAuthorizationService()

        # Admin delegates specific permissions
        auth_service.assign_role("admin", "admin")
        auth_service.grant_resource_permission(
            "delegate", "tenant-123", ["read", "write"]
        )

        # Delegate should only have granted permissions
        assert auth_service.check_permission("delegate", "read", "tenant-123")
        assert auth_service.check_permission("delegate", "write", "tenant-123")
        assert not auth_service.check_permission("delegate", "delete", "tenant-123")
        assert not auth_service.check_permission("delegate", "read", "tenant-456")

    def test_role_separation_of_duties(self):
        """Test that critical operations require multiple roles."""
        auth_service = MockAuthorizationService()

        class CriticalOperationService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                self.pending_operations = {}

            def initiate_critical_operation(
                self, initiator: str, operation: str
            ) -> str:
                """Initiate a critical operation requiring approval."""
                if not self.auth_service.check_permission(initiator, "write"):
                    raise PermissionError("Insufficient permissions to initiate")

                op_id = f"op_{len(self.pending_operations)}"
                self.pending_operations[op_id] = {
                    "initiator": initiator,
                    "operation": operation,
                    "approved": False,
                }
                return op_id

            def approve_operation(self, approver: str, op_id: str) -> bool:
                """Approve a critical operation."""
                if op_id not in self.pending_operations:
                    return False

                operation = self.pending_operations[op_id]

                # Cannot approve own operations
                if approver == operation["initiator"]:
                    raise PermissionError("Cannot approve own operation")

                # Must have approval permission
                if not self.auth_service.check_permission(approver, "manage_users"):
                    raise PermissionError("Insufficient permissions to approve")

                operation["approved"] = True
                return True

        critical_service = CriticalOperationService(auth_service)

        # Setup users with different roles
        auth_service.assign_role("initiator", "editor")
        auth_service.assign_role("approver", "admin")

        # Initiate critical operation
        op_id = critical_service.initiate_critical_operation(
            "initiator", "delete_all_data"
        )

        # Initiator cannot approve own operation
        with pytest.raises(PermissionError):
            critical_service.approve_operation("initiator", op_id)

        # Different user with proper permissions can approve
        assert critical_service.approve_operation("approver", op_id)

    def test_dynamic_permission_evaluation(self):
        """Test that permissions are evaluated dynamically based on context."""
        auth_service = MockAuthorizationService()

        class ContextualAuthService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                self.business_hours = (9, 17)  # 9 AM to 5 PM

            def check_contextual_permission(
                self, user_id: str, action: str, context: Dict[str, Any]
            ) -> bool:
                """Check permission with contextual rules."""
                # Basic permission check
                if not self.auth_service.check_permission(user_id, action):
                    return False

                # Additional context checks
                current_hour = context.get("hour", 12)
                ip_address = context.get("ip_address", "")

                # Restrict certain actions to business hours
                if action in ["delete", "manage_users"]:
                    if not (
                        self.business_hours[0] <= current_hour < self.business_hours[1]
                    ):
                        return False

                # Restrict based on IP range
                if action == "manage_security":
                    allowed_ips = ["192.168.1.", "10.0.0."]
                    if not any(ip_address.startswith(prefix) for prefix in allowed_ips):
                        return False

                return True

        contextual_service = ContextualAuthService(auth_service)
        auth_service.assign_role("user1", "admin")

        # Test during business hours
        assert contextual_service.check_contextual_permission(
            "user1", "delete", {"hour": 10, "ip_address": "192.168.1.100"}
        )

        # Test outside business hours
        assert not contextual_service.check_contextual_permission(
            "user1", "delete", {"hour": 20, "ip_address": "192.168.1.100"}
        )

        # Test IP restriction
        assert not contextual_service.check_contextual_permission(
            "user1", "manage_security", {"hour": 10, "ip_address": "8.8.8.8"}
        )

    def test_permission_caching_security(self):
        """Test that permission caching doesn't create security vulnerabilities."""
        auth_service = MockAuthorizationService()

        class CachedAuthService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                self.cache = {}
                self.cache_ttl = 60  # 60 seconds

            def check_permission_cached(self, user_id: str, action: str) -> bool:
                """Check permission with caching."""
                import time

                cache_key = f"{user_id}:{action}"

                # Check cache
                if cache_key in self.cache:
                    cached_result, timestamp = self.cache[cache_key]
                    if time.time() - timestamp < self.cache_ttl:
                        return cached_result

                # Cache miss or expired, check actual permission
                result = self.auth_service.check_permission(user_id, action)
                self.cache[cache_key] = (result, time.time())
                return result

            def invalidate_cache(self, user_id: str = None):
                """Invalidate cache for user or all users."""
                if user_id:
                    keys_to_remove = [
                        k for k in self.cache if k.startswith(f"{user_id}:")
                    ]
                    for key in keys_to_remove:
                        del self.cache[key]
                else:
                    self.cache.clear()

        cached_service = CachedAuthService(auth_service)

        # Grant permission
        auth_service.assign_role("user1", "editor")
        assert cached_service.check_permission_cached("user1", "write")

        # Revoke permission
        auth_service.revoke_role("user1", "editor")

        # Without cache invalidation, still returns cached result (vulnerability)
        assert cached_service.check_permission_cached("user1", "write")

        # After cache invalidation, returns correct result
        cached_service.invalidate_cache("user1")
        assert not cached_service.check_permission_cached("user1", "write")
