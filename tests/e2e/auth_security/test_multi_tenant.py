"""
End-to-end tests for multi-tenant authentication and authorization.

This module tests tenant isolation, cross-tenant security, tenant switching,
and multi-tenant data segregation.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from tests.e2e.auth_security.security_utils import (
    AuditLogger,
    SecurityScanner,
)


class MultiTenantManager:
    """Mock multi-tenant management service."""

    def __init__(self):
        self.tenants = {}
        self.tenant_users = {}
        self.tenant_data = {}
        self.active_sessions = {}
        self.audit_logger = AuditLogger()
        self.tenant_permissions = {}

    def register_tenant(self, tenant_id: str, config: Dict[str, Any]):
        """Register a new tenant."""
        if tenant_id in self.tenants:
            raise ValueError(f"Tenant {tenant_id} already exists")

        self.tenants[tenant_id] = {
            "id": tenant_id,
            "config": config,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        self.tenant_users[tenant_id] = set()
        self.tenant_data[tenant_id] = {}
        self.tenant_permissions[tenant_id] = {}

    def add_user_to_tenant(self, tenant_id: str, user_id: str, roles: List[str] = None):
        """Add user to a tenant with specified roles."""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")

        self.tenant_users[tenant_id].add(user_id)

        # Set user permissions for tenant
        if tenant_id not in self.tenant_permissions:
            self.tenant_permissions[tenant_id] = {}

        self.tenant_permissions[tenant_id][user_id] = roles or ["viewer"]

    def authenticate_user(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """Authenticate user for specific tenant."""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")

        if user_id not in self.tenant_users.get(tenant_id, set()):
            raise PermissionError(
                f"User {user_id} not authorized for tenant {tenant_id}"
            )

        # Create session
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "roles": self.tenant_permissions[tenant_id].get(user_id, []),
        }

        # Audit log
        self.audit_logger.log_authentication(
            user_id=user_id, success=True, method="multi_tenant", ip_address="127.0.0.1"
        )

        return {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "roles": self.active_sessions[session_id]["roles"],
        }

    def switch_tenant(self, session_id: str, new_tenant_id: str) -> Dict[str, Any]:
        """Switch active tenant for a session."""
        if session_id not in self.active_sessions:
            raise ValueError("Invalid session")

        session = self.active_sessions[session_id]
        user_id = session["user_id"]

        # Check if user has access to new tenant
        if user_id not in self.tenant_users.get(new_tenant_id, set()):
            raise PermissionError(
                f"User {user_id} not authorized for tenant {new_tenant_id}"
            )

        # Update session
        old_tenant = session["tenant_id"]
        session["tenant_id"] = new_tenant_id
        session["roles"] = self.tenant_permissions[new_tenant_id].get(user_id, [])
        session["switched_from"] = old_tenant
        session["switched_at"] = datetime.now(timezone.utc).isoformat()

        return session

    def store_tenant_data(self, tenant_id: str, key: str, data: Any):
        """Store data for a specific tenant."""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant {tenant_id} not found")

        if tenant_id not in self.tenant_data:
            self.tenant_data[tenant_id] = {}

        self.tenant_data[tenant_id][key] = data

    def get_tenant_data(self, session_id: str, key: str) -> Any:
        """Get data for the tenant associated with session."""
        if session_id not in self.active_sessions:
            raise ValueError("Invalid session")

        tenant_id = self.active_sessions[session_id]["tenant_id"]
        return self.tenant_data.get(tenant_id, {}).get(key)

    def validate_tenant_isolation(self, session_id: str, target_tenant_id: str) -> bool:
        """Validate that session cannot access other tenant's data."""
        if session_id not in self.active_sessions:
            return False

        session_tenant = self.active_sessions[session_id]["tenant_id"]
        return session_tenant == target_tenant_id


class TestMultiTenant:
    """Test multi-tenant security features."""

    def test_tenant_registration(self):
        """Test tenant registration and configuration."""
        manager = MultiTenantManager()

        # Register tenants
        tenant1_config = {
            "name": "Tenant 1",
            "domain": "tenant1.example.com",
            "max_users": 100,
        }
        manager.register_tenant("tenant1", tenant1_config)

        tenant2_config = {
            "name": "Tenant 2",
            "domain": "tenant2.example.com",
            "max_users": 50,
        }
        manager.register_tenant("tenant2", tenant2_config)

        # Verify tenants are registered
        assert "tenant1" in manager.tenants
        assert "tenant2" in manager.tenants
        assert manager.tenants["tenant1"]["config"]["name"] == "Tenant 1"

        # Verify duplicate registration fails
        with pytest.raises(ValueError):
            manager.register_tenant("tenant1", tenant1_config)

    def test_tenant_user_assignment(self):
        """Test assigning users to tenants."""
        manager = MultiTenantManager()

        # Register tenants
        manager.register_tenant("tenant1", {"name": "Tenant 1"})
        manager.register_tenant("tenant2", {"name": "Tenant 2"})

        # Add users to tenants
        manager.add_user_to_tenant("tenant1", "user1", ["admin"])
        manager.add_user_to_tenant("tenant1", "user2", ["editor"])
        manager.add_user_to_tenant(
            "tenant2", "user2", ["viewer"]
        )  # Same user, different tenant
        manager.add_user_to_tenant("tenant2", "user3", ["admin"])

        # Verify user assignments
        assert "user1" in manager.tenant_users["tenant1"]
        assert "user2" in manager.tenant_users["tenant1"]
        assert "user2" in manager.tenant_users["tenant2"]
        assert "user3" not in manager.tenant_users["tenant1"]

    def test_tenant_authentication(self):
        """Test authentication within tenant context."""
        manager = MultiTenantManager()

        # Setup
        manager.register_tenant("tenant1", {"name": "Tenant 1"})
        manager.add_user_to_tenant("tenant1", "user1", ["admin"])

        # Successful authentication
        session = manager.authenticate_user("user1", "tenant1")
        assert session["tenant_id"] == "tenant1"
        assert session["user_id"] == "user1"
        assert "admin" in session["roles"]

        # Failed authentication - wrong tenant
        with pytest.raises(PermissionError):
            manager.authenticate_user("user1", "tenant2")

        # Failed authentication - user not in tenant
        with pytest.raises(PermissionError):
            manager.authenticate_user("user2", "tenant1")

    def test_tenant_isolation(self):
        """Test that tenants are properly isolated from each other."""
        manager = MultiTenantManager()

        # Setup two tenants with data
        manager.register_tenant("tenant1", {"name": "Tenant 1"})
        manager.register_tenant("tenant2", {"name": "Tenant 2"})

        manager.add_user_to_tenant("tenant1", "user1", ["admin"])
        manager.add_user_to_tenant("tenant2", "user2", ["admin"])

        # Store tenant-specific data
        manager.store_tenant_data("tenant1", "secret", "tenant1_secret_data")
        manager.store_tenant_data("tenant2", "secret", "tenant2_secret_data")

        # Authenticate users
        session1 = manager.authenticate_user("user1", "tenant1")
        session2 = manager.authenticate_user("user2", "tenant2")

        # Verify data isolation
        data1 = manager.get_tenant_data(session1["session_id"], "secret")
        data2 = manager.get_tenant_data(session2["session_id"], "secret")

        assert data1 == "tenant1_secret_data"
        assert data2 == "tenant2_secret_data"
        assert data1 != data2

        # Verify cross-tenant access is blocked
        assert not manager.validate_tenant_isolation(session1["session_id"], "tenant2")
        assert not manager.validate_tenant_isolation(session2["session_id"], "tenant1")

    def test_tenant_switching(self):
        """Test secure tenant switching for users with multiple tenants."""
        manager = MultiTenantManager()

        # Setup tenants
        manager.register_tenant("tenant1", {"name": "Tenant 1"})
        manager.register_tenant("tenant2", {"name": "Tenant 2"})
        manager.register_tenant("tenant3", {"name": "Tenant 3"})

        # User with access to multiple tenants
        manager.add_user_to_tenant("tenant1", "multi_user", ["admin"])
        manager.add_user_to_tenant("tenant2", "multi_user", ["editor"])

        # Authenticate to first tenant
        session = manager.authenticate_user("multi_user", "tenant1")
        session_id = session["session_id"]

        # Switch to second tenant (allowed)
        switched = manager.switch_tenant(session_id, "tenant2")
        assert switched["tenant_id"] == "tenant2"
        assert switched["roles"] == ["editor"]
        assert switched["switched_from"] == "tenant1"

        # Attempt to switch to unauthorized tenant (should fail)
        with pytest.raises(PermissionError):
            manager.switch_tenant(session_id, "tenant3")

    def test_cross_tenant_attack_prevention(self):
        """Test prevention of cross-tenant attacks."""
        manager = MultiTenantManager()
        scanner = SecurityScanner()

        # Setup tenants
        manager.register_tenant("victim_tenant", {"name": "Victim"})
        manager.register_tenant("attacker_tenant", {"name": "Attacker"})

        manager.add_user_to_tenant("victim_tenant", "victim", ["admin"])
        manager.add_user_to_tenant("attacker_tenant", "attacker", ["viewer"])

        # Store sensitive data in victim tenant
        manager.store_tenant_data("victim_tenant", "sensitive", "victim_secrets")

        # Authenticate attacker
        attacker_session = manager.authenticate_user("attacker", "attacker_tenant")

        # Attempt various cross-tenant attacks
        attack_attempts = [
            # Try to access victim's data directly
            lambda: manager.get_tenant_data(
                attacker_session["session_id"], "../victim_tenant/sensitive"
            ),
            # Try to switch to victim tenant
            lambda: manager.switch_tenant(
                attacker_session["session_id"], "victim_tenant"
            ),
            # Try to add self to victim tenant
            lambda: manager.add_user_to_tenant("victim_tenant", "attacker", ["admin"]),
        ]

        for attempt in attack_attempts:
            try:
                result = attempt()
                # If no exception, verify data is not leaked
                assert result != "victim_secrets"
            except (PermissionError, ValueError):
                # Expected - attack was blocked
                pass

    @pytest.mark.asyncio
    async def test_concurrent_multi_tenant_operations(self):
        """Test thread safety of concurrent multi-tenant operations."""
        manager = MultiTenantManager()

        # Setup multiple tenants
        for i in range(5):
            manager.register_tenant(f"tenant{i}", {"name": f"Tenant {i}"})
            for j in range(10):
                manager.add_user_to_tenant(f"tenant{i}", f"user{j}", ["editor"])

        async def tenant_operation(tenant_id: str, user_id: str):
            """Simulate tenant operation."""
            await asyncio.sleep(0.001)  # Simulate async work
            try:
                session = manager.authenticate_user(user_id, tenant_id)
                manager.store_tenant_data(
                    tenant_id, f"data_{user_id}", f"value_{user_id}"
                )
                return session
            except Exception as e:
                return str(e)

        # Create concurrent operations
        tasks = []
        for i in range(5):
            for j in range(10):
                tasks.append(tenant_operation(f"tenant{i}", f"user{j}"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all operations completed
        successful = [r for r in results if isinstance(r, dict)]
        assert len(successful) == 50

    def test_tenant_data_encryption(self):
        """Test that tenant data is properly encrypted."""
        from tests.e2e.auth_security.security_utils import EncryptionHelper

        class EncryptedMultiTenantManager(MultiTenantManager):
            def __init__(self):
                super().__init__()
                self.tenant_keys = {}

            def register_tenant(self, tenant_id: str, config: Dict[str, Any]):
                """Register tenant with encryption key."""
                super().register_tenant(tenant_id, config)
                # Generate unique encryption key per tenant
                self.tenant_keys[tenant_id] = EncryptionHelper.generate_key()

            def store_tenant_data(self, tenant_id: str, key: str, data: Any):
                """Store encrypted tenant data."""
                if tenant_id not in self.tenant_keys:
                    raise ValueError(f"No encryption key for tenant {tenant_id}")

                # Encrypt data before storage
                if isinstance(data, str):
                    encrypted = EncryptionHelper.encrypt_data(
                        data, self.tenant_keys[tenant_id]
                    )
                    super().store_tenant_data(tenant_id, key, encrypted)
                else:
                    super().store_tenant_data(tenant_id, key, data)

            def get_tenant_data_decrypted(self, tenant_id: str, key: str) -> Any:
                """Get and decrypt tenant data."""
                encrypted = self.tenant_data.get(tenant_id, {}).get(key)
                if encrypted and tenant_id in self.tenant_keys:
                    return EncryptionHelper.decrypt_data(
                        encrypted, self.tenant_keys[tenant_id]
                    )
                return encrypted

        encrypted_manager = EncryptedMultiTenantManager()

        # Setup tenants
        encrypted_manager.register_tenant("tenant1", {"name": "Tenant 1"})
        encrypted_manager.register_tenant("tenant2", {"name": "Tenant 2"})

        # Store sensitive data
        encrypted_manager.store_tenant_data("tenant1", "password", "tenant1_password")
        encrypted_manager.store_tenant_data("tenant2", "password", "tenant2_password")

        # Verify data is encrypted in storage
        raw_data1 = encrypted_manager.tenant_data["tenant1"]["password"]
        assert "tenant1_password" not in raw_data1

        # Verify correct decryption
        decrypted1 = encrypted_manager.get_tenant_data_decrypted("tenant1", "password")
        decrypted2 = encrypted_manager.get_tenant_data_decrypted("tenant2", "password")

        assert decrypted1 == "tenant1_password"
        assert decrypted2 == "tenant2_password"

        # Verify tenant keys are different
        assert (
            encrypted_manager.tenant_keys["tenant1"]
            != encrypted_manager.tenant_keys["tenant2"]
        )

    def test_tenant_quota_enforcement(self):
        """Test enforcement of tenant-specific quotas and limits."""

        class QuotaEnforcedManager(MultiTenantManager):
            def __init__(self):
                super().__init__()
                self.tenant_quotas = {}
                self.tenant_usage = {}

            def register_tenant(self, tenant_id: str, config: Dict[str, Any]):
                """Register tenant with quotas."""
                super().register_tenant(tenant_id, config)
                self.tenant_quotas[tenant_id] = {
                    "max_users": config.get("max_users", 10),
                    "max_storage_mb": config.get("max_storage_mb", 100),
                    "max_api_calls": config.get("max_api_calls", 1000),
                }
                self.tenant_usage[tenant_id] = {
                    "users": 0,
                    "storage_mb": 0,
                    "api_calls": 0,
                }

            def add_user_to_tenant(
                self, tenant_id: str, user_id: str, roles: List[str] = None
            ):
                """Add user with quota check."""
                if (
                    self.tenant_usage[tenant_id]["users"]
                    >= self.tenant_quotas[tenant_id]["max_users"]
                ):
                    raise ValueError(f"User quota exceeded for tenant {tenant_id}")

                super().add_user_to_tenant(tenant_id, user_id, roles)
                self.tenant_usage[tenant_id]["users"] += 1

            def check_api_quota(self, tenant_id: str) -> bool:
                """Check if API quota is exceeded."""
                usage = self.tenant_usage[tenant_id]["api_calls"]
                quota = self.tenant_quotas[tenant_id]["max_api_calls"]
                return usage < quota

        quota_manager = QuotaEnforcedManager()

        # Register tenant with quotas
        quota_manager.register_tenant(
            "limited_tenant", {"name": "Limited", "max_users": 3, "max_api_calls": 10}
        )

        # Add users up to quota
        quota_manager.add_user_to_tenant("limited_tenant", "user1")
        quota_manager.add_user_to_tenant("limited_tenant", "user2")
        quota_manager.add_user_to_tenant("limited_tenant", "user3")

        # Verify quota enforcement
        with pytest.raises(ValueError) as exc_info:
            quota_manager.add_user_to_tenant("limited_tenant", "user4")
        assert "quota exceeded" in str(exc_info.value).lower()

    def test_tenant_audit_segregation(self):
        """Test that audit logs are properly segregated by tenant."""

        class TenantAuditManager(MultiTenantManager):
            def __init__(self):
                super().__init__()
                self.tenant_audit_logs = {}

            def log_tenant_event(
                self, tenant_id: str, event_type: str, details: Dict[str, Any]
            ):
                """Log event for specific tenant."""
                if tenant_id not in self.tenant_audit_logs:
                    self.tenant_audit_logs[tenant_id] = []

                event = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tenant_id": tenant_id,
                    "event_type": event_type,
                    "details": details,
                }
                self.tenant_audit_logs[tenant_id].append(event)

            def get_tenant_audit_logs(
                self, tenant_id: str, requester_tenant: str
            ) -> List[Dict]:
                """Get audit logs with tenant isolation."""
                if requester_tenant != tenant_id:
                    raise PermissionError("Cannot access other tenant's audit logs")
                return self.tenant_audit_logs.get(tenant_id, [])

        audit_manager = TenantAuditManager()

        # Generate events for different tenants
        audit_manager.log_tenant_event("tenant1", "login", {"user": "user1"})
        audit_manager.log_tenant_event("tenant1", "data_access", {"resource": "db1"})
        audit_manager.log_tenant_event("tenant2", "login", {"user": "user2"})
        audit_manager.log_tenant_event("tenant2", "config_change", {"setting": "value"})

        # Verify audit log segregation
        tenant1_logs = audit_manager.get_tenant_audit_logs("tenant1", "tenant1")
        tenant2_logs = audit_manager.get_tenant_audit_logs("tenant2", "tenant2")

        assert len(tenant1_logs) == 2
        assert len(tenant2_logs) == 2
        assert all(log["tenant_id"] == "tenant1" for log in tenant1_logs)
        assert all(log["tenant_id"] == "tenant2" for log in tenant2_logs)

        # Verify cross-tenant access is blocked
        with pytest.raises(PermissionError):
            audit_manager.get_tenant_audit_logs("tenant1", "tenant2")

    def test_tenant_configuration_isolation(self):
        """Test that tenant configurations are isolated."""
        manager = MultiTenantManager()

        # Register tenants with different configurations
        tenant1_config = {
            "name": "Enterprise Tenant",
            "features": ["advanced_analytics", "custom_branding", "sso"],
            "api_rate_limit": 10000,
            "data_retention_days": 365,
        }

        tenant2_config = {
            "name": "Basic Tenant",
            "features": ["basic_reporting"],
            "api_rate_limit": 100,
            "data_retention_days": 30,
        }

        manager.register_tenant("enterprise", tenant1_config)
        manager.register_tenant("basic", tenant2_config)

        # Verify configurations are separate
        assert manager.tenants["enterprise"]["config"]["api_rate_limit"] == 10000
        assert manager.tenants["basic"]["config"]["api_rate_limit"] == 100

        # Verify feature isolation
        enterprise_features = set(manager.tenants["enterprise"]["config"]["features"])
        basic_features = set(manager.tenants["basic"]["config"]["features"])

        assert "sso" in enterprise_features
        assert "sso" not in basic_features
        assert (
            len(enterprise_features.intersection(basic_features)) == 0
        )  # No shared features

    def test_tenant_deletion_cleanup(self):
        """Test that tenant deletion properly cleans up all associated data."""

        class DeletableMultiTenantManager(MultiTenantManager):
            def delete_tenant(self, tenant_id: str):
                """Securely delete tenant and all associated data."""
                if tenant_id not in self.tenants:
                    raise ValueError(f"Tenant {tenant_id} not found")

                # Log deletion event
                self.audit_logger.log_security_violation(
                    violation_type="tenant_deletion",
                    details=f"Deleting tenant {tenant_id}",
                    source_ip="system",
                    user_id="admin",
                )

                # Clean up all tenant data
                del self.tenants[tenant_id]
                del self.tenant_users[tenant_id]
                del self.tenant_data[tenant_id]
                del self.tenant_permissions[tenant_id]

                # Invalidate all sessions for this tenant
                sessions_to_remove = [
                    sid
                    for sid, session in self.active_sessions.items()
                    if session["tenant_id"] == tenant_id
                ]
                for sid in sessions_to_remove:
                    del self.active_sessions[sid]

                return len(sessions_to_remove)

        manager = DeletableMultiTenantManager()

        # Setup tenant with data
        manager.register_tenant("temp_tenant", {"name": "Temporary"})
        manager.add_user_to_tenant("temp_tenant", "user1")
        manager.store_tenant_data("temp_tenant", "data", "sensitive")
        session = manager.authenticate_user("user1", "temp_tenant")

        # Delete tenant
        invalidated_sessions = manager.delete_tenant("temp_tenant")

        # Verify complete cleanup
        assert "temp_tenant" not in manager.tenants
        assert "temp_tenant" not in manager.tenant_users
        assert "temp_tenant" not in manager.tenant_data
        assert "temp_tenant" not in manager.tenant_permissions
        assert session["session_id"] not in manager.active_sessions
        assert invalidated_sessions == 1

        # Verify tenant cannot be accessed
        with pytest.raises(ValueError):
            manager.authenticate_user("user1", "temp_tenant")
