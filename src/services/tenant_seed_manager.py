"""
Tenant Seed Manager - Dual Graph Architecture (Issue #420)

This service manages per-tenant abstraction seeds used for deterministic ID generation
in the dual-graph architecture. Each tenant gets a unique, persistent seed that enables
reproducible abstraction of resource IDs while maintaining tenant isolation.

Key Features:
- Per-tenant seed isolation
- Persistent storage in Neo4j Tenant nodes
- Automatic seed generation on first use
- Seed retrieval for existing tenants
- Cryptographically secure seed generation
- Seed immutability (once created, never changed)
- Thread-safe operations using Neo4j transactions

Security Note:
Seeds are sensitive values that control ID abstraction. They should not be
logged or exposed in plain text unless necessary for debugging.
"""

import logging
import secrets
import string
from typing import Any, Optional

from neo4j.exceptions import Neo4jError

from ..exceptions import Neo4jConnectionError, wrap_neo4j_exception
from ..utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class TenantSeedError(Exception):
    """Base exception for tenant seed operations."""

    pass


class InvalidSeedError(TenantSeedError):
    """Raised when a seed fails validation."""

    pass


class TenantSeedManager:
    """
    Manages abstraction seeds for tenants in the dual-graph architecture.

    This service ensures each tenant has a unique, persistent seed for ID abstraction.
    Seeds are stored on Tenant nodes in Neo4j and automatically generated on first access.

    The seed is stored as a property 'abstraction_seed' on Tenant nodes in Neo4j
    and is immutable once created to ensure ID consistency across operations.

    Examples:
        >>> from src.utils.session_manager import Neo4jSessionManager
        >>> session_manager = Neo4jSessionManager(neo4j_config)
        >>> seed_manager = TenantSeedManager(session_manager)
        >>> seed = seed_manager.get_or_create_seed("tenant-id-123")
        >>> print(len(seed))  # 64 characters (32 bytes hex-encoded)
        64
    """

    # Seed configuration
    SEED_LENGTH = 32  # Minimum secure length (in bytes, becomes 64 hex chars)
    SEED_CHARSET = string.ascii_letters + string.digits  # For alphanumeric seeds

    def __init__(self, session_manager: Neo4jSessionManager):
        """
        Initialize the Tenant Seed Manager.

        Args:
            session_manager: Neo4jSessionManager instance for database operations

        Raises:
            Neo4jConnectionError: If connection to Neo4j fails
        """
        self.session_manager = session_manager

        # Ensure connection to Neo4j
        try:
            self.session_manager.ensure_connection()
            logger.debug("TenantSeedManager initialized with Neo4j backend")
        except Exception as e:
            raise Neo4jConnectionError(
                f"Failed to connect to Neo4j: {e}",
                context={"operation": "initialize", "service": "TenantSeedManager"},
            ) from e

    def get_or_create_seed(self, tenant_id: str) -> str:
        """
        Get the existing abstraction seed for a tenant, or create a new one.

        This method is idempotent: calling it multiple times for the same tenant
        will always return the same seed. Seeds are stored on Tenant nodes in Neo4j.

        The operation is atomic and thread-safe using Neo4j's MERGE operation
        with ON CREATE to ensure seeds are immutable once created.

        Args:
            tenant_id: Tenant ID (Azure tenant GUID or management group ID)

        Returns:
            str: Abstraction seed (64-character hex string)

        Raises:
            ValueError: If tenant_id is empty or invalid
            Neo4jConnectionError: If database operation fails
            TenantSeedError: If seed generation or storage fails

        Examples:
            >>> seed_manager = TenantSeedManager(session_manager)
            >>> seed1 = seed_manager.get_or_create_seed("tenant-123")
            >>> seed2 = seed_manager.get_or_create_seed("tenant-123")
            >>> seed1 == seed2
            True
        """
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")

        # First, try to get existing seed
        existing_seed = self.get_seed(tenant_id)
        if existing_seed:
            logger.debug(
                f"Retrieved existing seed for tenant {tenant_id} (length: {len(existing_seed)})"
            )
            return existing_seed

        # Generate new seed
        new_seed = self.generate_secure_seed()

        # Validate before storing
        if not self.validate_seed(new_seed):
            raise TenantSeedError(
                f"Generated seed failed validation for tenant {tenant_id}"
            )

        # Store seed atomically using MERGE with ON CREATE
        # This ensures seed immutability - existing seeds are not overwritten
        query = """
        MERGE (t:Tenant {id: $tenant_id})
        ON CREATE SET t.abstraction_seed = $seed,
                      t.created_at = datetime(),
                      t.seed_algorithm = 'secrets.token_hex'
        ON MATCH SET t.abstraction_seed = COALESCE(t.abstraction_seed, $seed)
        RETURN t.abstraction_seed as seed
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, tenant_id=tenant_id, seed=new_seed)
                record = result.single()

                if not record:
                    raise TenantSeedError(
                        f"Failed to create or retrieve seed for tenant {tenant_id}"
                    )

                stored_seed = record["seed"]

                # Log seed creation (without exposing the seed value)
                if stored_seed == new_seed:
                    logger.info(
                        f"Created new abstraction seed for tenant {tenant_id} "
                        f"(length: {len(stored_seed)})"
                    )
                else:
                    logger.debug(
                        f"Retrieved existing seed for tenant {tenant_id} "
                        f"(length: {len(stored_seed)})"
                    )

                return stored_seed

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                {"operation": "get_or_create_seed", "tenant_id": tenant_id},
            ) from e
        except Exception as e:
            raise TenantSeedError(
                f"Unexpected error creating seed for tenant {tenant_id}: {e}"
            ) from e

    def get_seed(self, tenant_id: str) -> Optional[str]:
        """
        Get the abstraction seed for a tenant (without creating if missing).

        This method only retrieves an existing seed and returns None if the
        tenant doesn't have a seed yet.

        Args:
            tenant_id: Tenant ID

        Returns:
            Optional[str]: Abstraction seed if exists, None otherwise

        Raises:
            ValueError: If tenant_id is empty or invalid
            Neo4jConnectionError: If database operation fails

        Examples:
            >>> seed_manager = TenantSeedManager(session_manager)
            >>> seed = seed_manager.get_seed("nonexistent-tenant")
            >>> seed is None
            True
        """
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")

        query = """
        MATCH (t:Tenant {id: $tenant_id})
        RETURN t.abstraction_seed as seed
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, tenant_id=tenant_id)
                record = result.single()

                if record and record["seed"]:
                    seed = record["seed"]
                    logger.debug(
                        f"Found seed for tenant {tenant_id} (length: {len(seed)})"
                    )
                    return seed

                logger.debug(str(f"No seed found for tenant {tenant_id}"))
                return None

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                {"operation": "get_seed", "tenant_id": tenant_id},
            ) from e

    def set_seed(self, tenant_id: str, seed: str) -> bool:
        """
        Set/update seed for tenant.

        WARNING: This method should be used with caution. Changing a tenant's seed
        will cause all future ID abstractions to be different, breaking consistency
        with previously abstracted IDs. This is primarily intended for:
        - Initial seed setup during migration
        - Disaster recovery scenarios
        - Testing purposes

        In production, seeds should be immutable once created. Use get_or_create_seed
        instead for normal operations.

        Args:
            tenant_id: Unique Azure tenant ID
            seed: Seed string to set (must pass validation)

        Returns:
            True if seed was set successfully

        Raises:
            ValueError: If tenant_id or seed is invalid
            InvalidSeedError: If seed fails validation
            Neo4jConnectionError: If database operation fails

        Examples:
            >>> manager = TenantSeedManager(session_manager)
            >>> success = manager.set_seed("tenant-123", "a" * 64)
            >>> assert success is True
        """
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")

        if not seed:
            raise ValueError("seed must be a non-empty string")

        # Validate seed before storing
        if not self.validate_seed(seed):
            raise InvalidSeedError(
                "Seed validation failed: must be 64+ characters (hex) or 32+ characters (alphanumeric)"
            )

        query = """
        MERGE (t:Tenant {id: $tenant_id})
        SET t.abstraction_seed = $seed,
            t.updated_at = datetime()
        RETURN t.abstraction_seed as seed
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, tenant_id=tenant_id, seed=seed)
                record = result.single()

                if not record:
                    raise TenantSeedError(f"Failed to set seed for tenant {tenant_id}")

                logger.warning(
                    f"Seed updated for tenant {tenant_id} - "
                    f"this may break ID consistency with existing abstractions"
                )
                return True

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                {"operation": "set_seed", "tenant_id": tenant_id},
            ) from e

    def delete_seed(self, tenant_id: str) -> bool:
        """
        Delete the abstraction seed for a tenant.

        This removes the seed from the Tenant node. Use with caution as this
        will orphan all abstracted nodes for this tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            bool: True if successful, False otherwise
        """
        if not tenant_id:
            raise ValueError("tenant_id cannot be empty")

        try:
            with self.session_manager.session() as session:
                session.run(
                    """
                    MATCH (t:Tenant {id: $tenant_id})
                    REMOVE t.abstraction_seed,
                           t.seed_created_at,
                           t.seed_updated_at,
                           t.seed_algorithm
                    SET t.updated_at = datetime()
                    """,
                    tenant_id=tenant_id,
                )

            logger.warning(str(f"Deleted abstraction seed for tenant {tenant_id}"))
            return True

        except Exception:
            logger.exception(f"Error deleting seed for tenant {tenant_id}")
            return False

    def generate_secure_seed(self) -> str:
        """
        Generate a cryptographically secure random seed.

        Uses Python's secrets module to generate a random string suitable for
        cryptographic use. The seed is composed of hex characters only
        to ensure compatibility with various storage and transmission systems.

        Generates 32 bytes (256 bits) of random data, hex-encoded to 64 characters.

        Returns:
            Cryptographically secure random seed string (64 characters, lowercase hex)

        Examples:
            >>> manager = TenantSeedManager(session_manager)
            >>> seed1 = manager.generate_secure_seed()
            >>> seed2 = manager.generate_secure_seed()
            >>> assert len(seed1) == 64
            >>> assert seed1 != seed2  # Very high probability
            >>> assert all(c in '0123456789abcdef' for c in seed1)
        """
        # Generate 32 bytes of cryptographically strong random data
        # Hex-encode to 64 characters (each byte = 2 hex digits)
        seed = secrets.token_hex(self.SEED_LENGTH)

        logger.debug(
            f"Generated secure seed (length: {len(seed)}, "
            f"entropy: ~{self.SEED_LENGTH * 8} bits)"
        )

        return seed

    def validate_seed(self, seed: str) -> bool:
        """
        Validate seed format and security requirements.

        A valid seed must:
        1. Be a non-empty string
        2. Be at least 64 characters long for hex seeds (32 bytes)
        3. Be at least 32 characters long for non-hex seeds
        4. Contain only valid characters (hex: 0-9a-f, or alphanumeric)

        Args:
            seed: Seed string to validate

        Returns:
            True if seed is valid, False otherwise

        Examples:
            >>> manager = TenantSeedManager(session_manager)
            >>> assert manager.validate_seed("a" * 64) is True
            >>> assert manager.validate_seed("0123456789abcdef" * 4) is True
            >>> assert manager.validate_seed("a" * 16) is False  # Too short
            >>> assert manager.validate_seed("a" * 64 + "!") is False  # Invalid char
        """
        if not seed:
            logger.debug("Seed validation failed: empty string")
            return False

        # Check if it's a hex seed (all characters are 0-9a-f)
        is_hex = all(c in "0123456789abcdef" for c in seed.lower())

        if is_hex:
            # Hex seeds should be 64 characters (32 bytes)
            if len(seed) < 64:
                logger.debug(
                    f"Seed validation failed: hex seed length {len(seed)} < 64"
                )
                return False
        else:
            # Non-hex seeds should be at least 32 characters
            if len(seed) < 32:
                logger.debug(
                    str(f"Seed validation failed: seed length {len(seed)} < 32")
                )
                return False

            # Check character set (alphanumeric only for non-hex)
            if not all(c in self.SEED_CHARSET for c in seed):
                logger.debug("Seed validation failed: contains invalid characters")
                return False

        return True

    def list_tenants_with_seeds(self) -> dict[str, dict[str, Any]]:
        """
        List all tenants that have abstraction seeds.

        This is useful for administrative purposes and migration scenarios.

        Returns:
            Dictionary mapping tenant_id to metadata (seed length, created_at, etc.)
            Note: Actual seed values are NOT returned for security reasons.

        Raises:
            Neo4jConnectionError: If database operation fails

        Examples:
            >>> manager = TenantSeedManager(session_manager)
            >>> tenants = manager.list_tenants_with_seeds()
            >>> # Returns: {"tenant-123": {"seed_length": 64, "created_at": "..."}}
        """
        query = """
        MATCH (t:Tenant)
        WHERE t.abstraction_seed IS NOT NULL
        RETURN t.id as tenant_id,
               t.abstraction_seed as seed,
               t.created_at as created_at
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query)

                tenants: dict[str, dict[str, Any]] = {}
                for record in result:
                    tenant_id = record["tenant_id"]
                    seed = record["seed"]
                    created_at = record["created_at"]

                    tenants[tenant_id] = {
                        "seed_length": len(seed) if seed else 0,
                        "created_at": str(created_at) if created_at else None,
                        "has_seed": bool(seed),
                    }

                logger.debug(str(f"Found {len(tenants)} tenants with seeds"))
                return tenants

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                {"operation": "list_tenants_with_seeds"},
            ) from e


def get_tenant_seed_manager(session_manager: Neo4jSessionManager) -> TenantSeedManager:
    """
    Factory function to create a TenantSeedManager instance.

    Args:
        session_manager: Neo4jSessionManager instance

    Returns:
        TenantSeedManager instance
    """
    return TenantSeedManager(session_manager)


# Convenience function for common use case
def get_tenant_seed(session_manager: Neo4jSessionManager, tenant_id: str) -> str:
    """
    Convenience function to get or create a tenant seed.

    This is a shorthand for creating a TenantSeedManager and calling
    get_or_create_seed, useful for one-off operations.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Unique Azure tenant ID

    Returns:
        The tenant's abstraction seed

    Examples:
        >>> from src.services.tenant_seed_manager import get_tenant_seed
        >>> seed = get_tenant_seed(session_manager, "tenant-123")
    """
    manager = TenantSeedManager(session_manager)
    return manager.get_or_create_seed(tenant_id)
