"""
Tenant Manager Service

This module provides multi-tenant support for Azure Tenant Grapher,
managing tenant registration, switching, and configuration persistence.

Following the project's philosophy of ruthless simplicity, this implementation
uses Neo4j for tenant storage, leveraging the existing graph database.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config_manager import Neo4jConfig
from ..utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


# Custom Exceptions
class TenantNotFoundError(Exception):
    """Raised when a requested tenant is not found in the registry."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the TenantNotFoundError.
        
        Args:
            message: Error message describing what went wrong
            context: Optional dictionary with additional error context
        """
        self.message = message
        self.context = context or {}
        super().__init__(self.message)


class InvalidTenantConfigError(Exception):
    """Raised when tenant configuration is invalid or corrupted."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the InvalidTenantConfigError.
        
        Args:
            message: Error message describing the configuration issue
            context: Optional dictionary with additional error context
        """
        self.message = message
        self.context = context or {}
        super().__init__(self.message)


class TenantSwitchError(Exception):
    """Raised when switching between tenants fails."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the TenantSwitchError.
        
        Args:
            message: Error message describing the switch failure
            context: Optional dictionary with additional error context
        """
        self.message = message
        self.context = context or {}
        super().__init__(self.message)


@dataclass
class Tenant:
    """
    Represents a single Azure tenant with its configuration.
    
    Attributes:
        tenant_id: Unique identifier for the Azure tenant
        display_name: Human-readable name for the tenant
        subscription_ids: List of Azure subscription IDs associated with this tenant
        created_at: ISO format timestamp when tenant was registered
        last_accessed: ISO format timestamp of last access
        is_active: Whether this tenant is currently active
        configuration: Additional tenant-specific configuration metadata
    """
    tenant_id: str
    display_name: str
    subscription_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_active: bool = True
    configuration: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tenant to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tenant":
        """Create tenant from dictionary."""
        return cls(**data)
    
    def update_last_accessed(self) -> None:
        """Update the last accessed timestamp to current time."""
        self.last_accessed = datetime.utcnow().isoformat()


class TenantManager:
    """
    Singleton manager for multi-tenant operations.
    
    This class provides centralized management of multiple Azure tenants,
    including registration, switching, and configuration persistence.
    Uses Neo4j graph database for tenant storage.
    """
    
    _instance: Optional["TenantManager"] = None
    _initialized: bool = False
    
    def __new__(cls, session_manager: Optional[Neo4jSessionManager] = None) -> "TenantManager":
        """Implement singleton pattern with support for session_manager parameter."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, session_manager: Optional[Neo4jSessionManager] = None) -> None:
        """
        Initialize the TenantManager.
        
        Args:
            session_manager: Optional Neo4j session manager. If not provided, creates one.
        """
        # Handle singleton initialization
        if TenantManager._initialized and session_manager is None:
            return
        
        # Allow re-initialization with a different session_manager for testing
        if session_manager is not None:
            TenantManager._initialized = False
            
        if TenantManager._initialized:
            return
            
        # Initialize Neo4j session manager
        if session_manager:
            self.session_manager = session_manager
        else:
            # Create default session manager with config from environment
            neo4j_config = Neo4jConfig()
            self.session_manager = Neo4jSessionManager(neo4j_config)
            
        self._current_tenant_id: Optional[str] = None
        self._tenant_cache: Dict[str, Tenant] = {}
        
        # Ensure connection to Neo4j
        self.session_manager.ensure_connection()
        
        # Load existing tenants on initialization
        self._load_tenants()
        
        # Load current tenant from Neo4j
        self._load_current_tenant()
        
        TenantManager._initialized = True
        logger.info("TenantManager initialized with Neo4j backend")
    
    def _load_tenants(self) -> None:
        """Load all tenant configurations from Neo4j."""
        self._tenant_cache.clear()
        
        query = """
        MATCH (t:TenantConfig)
        RETURN t.tenant_id as tenant_id,
               t.display_name as display_name,
               t.subscription_ids as subscription_ids,
               t.created_at as created_at,
               t.last_accessed as last_accessed,
               t.is_active as is_active,
               t.configuration as configuration
        """
        
        try:
            with self.session_manager.session() as session:
                result = session.run(query)
                for record in result:
                    tenant_data = {
                        "tenant_id": record["tenant_id"],
                        "display_name": record["display_name"],
                        "subscription_ids": json.loads(record["subscription_ids"]) if record["subscription_ids"] else [],
                        "created_at": record["created_at"],
                        "last_accessed": record["last_accessed"],
                        "is_active": record["is_active"],
                        "configuration": json.loads(record["configuration"]) if record["configuration"] else {}
                    }
                    tenant = Tenant.from_dict(tenant_data)
                    self._tenant_cache[tenant.tenant_id] = tenant
                    logger.debug(f"Loaded tenant: {tenant.tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to load tenants from Neo4j: {e}")
    
    def _load_current_tenant(self) -> None:
        """Load the current tenant from Neo4j."""
        query = """
        MATCH (t:TenantConfig {is_current: true})
        RETURN t.tenant_id as tenant_id
        LIMIT 1
        """
        
        try:
            with self.session_manager.session() as session:
                result = session.run(query)
                record = result.single()
                if record:
                    self._current_tenant_id = record["tenant_id"]
                    logger.debug(f"Loaded current tenant: {self._current_tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to load current tenant from Neo4j: {e}")
    
    def _save_tenant(self, tenant: Tenant) -> None:
        """Save a tenant configuration to Neo4j."""
        query = """
        MERGE (t:TenantConfig {tenant_id: $tenant_id})
        SET t.display_name = $display_name,
            t.subscription_ids = $subscription_ids,
            t.created_at = $created_at,
            t.last_accessed = $last_accessed,
            t.is_active = $is_active,
            t.configuration = $configuration
        """
        
        try:
            with self.session_manager.session() as session:
                session.run(query,
                    tenant_id=tenant.tenant_id,
                    display_name=tenant.display_name,
                    subscription_ids=json.dumps(tenant.subscription_ids),
                    created_at=tenant.created_at,
                    last_accessed=tenant.last_accessed,
                    is_active=tenant.is_active,
                    configuration=json.dumps(tenant.configuration)
                )
            logger.debug(f"Saved tenant: {tenant.tenant_id}")
        except Exception as e:
            logger.error(f"Failed to save tenant to Neo4j: {e}")
            raise
    
    def _save_state(self) -> None:
        """Save the manager state to Neo4j."""
        # First, clear any existing current tenant
        clear_query = """
        MATCH (t:TenantConfig {is_current: true})
        SET t.is_current = false
        """
        
        # Then set the new current tenant
        set_query = """
        MATCH (t:TenantConfig {tenant_id: $tenant_id})
        SET t.is_current = true
        """
        
        try:
            with self.session_manager.session() as session:
                session.run(clear_query)
                if self._current_tenant_id:
                    session.run(set_query, tenant_id=self._current_tenant_id)
            logger.debug(f"Saved state with current tenant: {self._current_tenant_id}")
        except Exception as e:
            logger.error(f"Failed to save state to Neo4j: {e}")
            raise
    
    def register_tenant(
        self,
        tenant_id: str,
        display_name: str,
        config: Optional[Dict[str, Any]] = None,
        subscription_ids: Optional[List[str]] = None
    ) -> Tenant:
        """
        Register a new tenant or update an existing one.
        
        Args:
            tenant_id: Unique identifier for the Azure tenant
            display_name: Human-readable name for the tenant
            config: Optional tenant-specific configuration
            subscription_ids: Optional list of Azure subscription IDs
            
        Returns:
            The registered Tenant object
            
        Raises:
            InvalidTenantConfigError: If tenant configuration is invalid
        """
        if not tenant_id or not display_name:
            raise InvalidTenantConfigError("Tenant ID and display name are required")
        
        # Check if tenant already exists
        if tenant_id in self._tenant_cache:
            logger.info(f"Updating existing tenant: {tenant_id}")
            tenant = self._tenant_cache[tenant_id]
            tenant.display_name = display_name
            if config:
                tenant.configuration.update(config)
            if subscription_ids:
                tenant.subscription_ids = subscription_ids
            tenant.update_last_accessed()
        else:
            logger.info(f"Registering new tenant: {tenant_id}")
            tenant = Tenant(
                tenant_id=tenant_id,
                display_name=display_name,
                configuration=config or {},
                subscription_ids=subscription_ids or []
            )
            self._tenant_cache[tenant_id] = tenant
        
        # Save to disk
        self._save_tenant(tenant)
        
        # If this is the first tenant, make it current
        if self._current_tenant_id is None:
            self.switch_tenant(tenant_id)
        
        return tenant
    
    def get_current_tenant(self) -> Optional[Tenant]:
        """
        Get the currently active tenant.
        
        Returns:
            The current Tenant object or None if no tenant is active
        """
        if self._current_tenant_id:
            return self._tenant_cache.get(self._current_tenant_id)
        return None
    
    def switch_tenant(self, tenant_id: str) -> Tenant:
        """
        Switch to a different tenant.
        
        Args:
            tenant_id: ID of the tenant to switch to
            
        Returns:
            The newly active Tenant object
            
        Raises:
            TenantNotFoundError: If the tenant doesn't exist
            TenantSwitchError: If the switch operation fails
        """
        if tenant_id not in self._tenant_cache:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        try:
            # Update last accessed time for the tenant
            tenant = self._tenant_cache[tenant_id]
            tenant.update_last_accessed()
            self._save_tenant(tenant)
            
            # Update current tenant
            self._current_tenant_id = tenant_id
            self._save_state()
            
            logger.info(f"Switched to tenant: {tenant.display_name} ({tenant_id})")
            return tenant
            
        except Exception as e:
            raise TenantSwitchError(f"Failed to switch to tenant {tenant_id}: {e}")
    
    def list_tenants(self, active_only: bool = False) -> List[Tenant]:
        """
        List all registered tenants.
        
        Args:
            active_only: If True, only return active tenants
            
        Returns:
            List of Tenant objects
        """
        tenants = list(self._tenant_cache.values())
        
        if active_only:
            tenants = [t for t in tenants if t.is_active]
        
        # Sort by last accessed time (most recent first)
        tenants.sort(key=lambda t: t.last_accessed, reverse=True)
        
        return tenants
    
    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get configuration for a specific tenant.
        
        Args:
            tenant_id: ID of the tenant
            
        Returns:
            Dictionary containing tenant configuration
            
        Raises:
            TenantNotFoundError: If the tenant doesn't exist
        """
        if tenant_id not in self._tenant_cache:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        tenant = self._tenant_cache[tenant_id]
        return tenant.configuration.copy()
    
    def update_tenant_config(self, tenant_id: str, config: Dict[str, Any]) -> None:
        """
        Update configuration for a specific tenant.
        
        Args:
            tenant_id: ID of the tenant
            config: Configuration updates to apply
            
        Raises:
            TenantNotFoundError: If the tenant doesn't exist
        """
        if tenant_id not in self._tenant_cache:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        tenant = self._tenant_cache[tenant_id]
        tenant.configuration.update(config)
        tenant.update_last_accessed()
        self._save_tenant(tenant)
        
        logger.info(f"Updated configuration for tenant: {tenant_id}")
    
    def remove_tenant(self, tenant_id: str) -> None:
        """
        Remove a tenant from the registry.
        
        Args:
            tenant_id: ID of the tenant to remove
            
        Raises:
            TenantNotFoundError: If the tenant doesn't exist
        """
        if tenant_id not in self._tenant_cache:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        # Remove from cache
        del self._tenant_cache[tenant_id]
        
        # Remove from Neo4j
        query = """
        MATCH (t:TenantConfig {tenant_id: $tenant_id})
        DELETE t
        """
        
        try:
            with self.session_manager.session() as session:
                session.run(query, tenant_id=tenant_id)
        except Exception as e:
            logger.error(f"Failed to remove tenant from Neo4j: {e}")
            raise
        
        # If this was the current tenant, clear it
        if self._current_tenant_id == tenant_id:
            self._current_tenant_id = None
            self._save_state()
        
        logger.info(f"Removed tenant: {tenant_id}")
    
    def deactivate_tenant(self, tenant_id: str) -> None:
        """
        Deactivate a tenant without removing it.
        
        Args:
            tenant_id: ID of the tenant to deactivate
            
        Raises:
            TenantNotFoundError: If the tenant doesn't exist
        """
        if tenant_id not in self._tenant_cache:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        tenant = self._tenant_cache[tenant_id]
        tenant.is_active = False
        self._save_tenant(tenant)
        
        logger.info(f"Deactivated tenant: {tenant_id}")
    
    def activate_tenant(self, tenant_id: str) -> None:
        """
        Activate a previously deactivated tenant.
        
        Args:
            tenant_id: ID of the tenant to activate
            
        Raises:
            TenantNotFoundError: If the tenant doesn't exist
        """
        if tenant_id not in self._tenant_cache:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        tenant = self._tenant_cache[tenant_id]
        tenant.is_active = True
        tenant.update_last_accessed()
        self._save_tenant(tenant)
        
        logger.info(f"Activated tenant: {tenant_id}")
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """
        Get a specific tenant by ID.
        
        Args:
            tenant_id: ID of the tenant to retrieve
            
        Returns:
            Tenant object or None if not found
        """
        return self._tenant_cache.get(tenant_id)
    
    def tenant_exists(self, tenant_id: str) -> bool:
        """
        Check if a tenant exists in the registry.
        
        Args:
            tenant_id: ID of the tenant to check
            
        Returns:
            True if tenant exists, False otherwise
        """
        return tenant_id in self._tenant_cache
    
    def get_tenant_count(self, active_only: bool = False) -> int:
        """
        Get the count of registered tenants.
        
        Args:
            active_only: If True, only count active tenants
            
        Returns:
            Number of tenants
        """
        if active_only:
            return sum(1 for t in self._tenant_cache.values() if t.is_active)
        return len(self._tenant_cache)
    
    def export_tenants(self) -> Dict[str, Any]:
        """
        Export all tenants as a dictionary for backup or migration.
        
        Returns:
            Dictionary containing all tenant data and current state
        """
        # Reload from Neo4j to ensure we have the latest data
        self._load_tenants()
        self._load_current_tenant()
        
        return {
            "tenants": {
                tid: tenant.to_dict() 
                for tid, tenant in self._tenant_cache.items()
            },
            "current_tenant_id": self._current_tenant_id,
            "exported_at": datetime.utcnow().isoformat()
        }
    
    def import_tenants(self, data: Dict[str, Any]) -> None:
        """
        Import tenants from an exported dictionary.
        
        Args:
            data: Dictionary containing tenant data to import
            
        Raises:
            InvalidTenantConfigError: If import data is invalid
        """
        try:
            # Clear existing tenants in Neo4j
            clear_query = """
            MATCH (t:TenantConfig)
            DELETE t
            """
            
            with self.session_manager.session() as session:
                session.run(clear_query)
            
            # Clear cache
            self._tenant_cache.clear()
            
            # Import tenants
            for tenant_id, tenant_data in data.get("tenants", {}).items():
                tenant = Tenant.from_dict(tenant_data)
                self._tenant_cache[tenant_id] = tenant
                self._save_tenant(tenant)
            
            # Set current tenant
            self._current_tenant_id = data.get("current_tenant_id")
            self._save_state()
            
            logger.info(f"Imported {len(self._tenant_cache)} tenants")
            
        except Exception as e:
            raise InvalidTenantConfigError(f"Failed to import tenants: {e}")


# Module-level convenience functions
def get_tenant_manager(session_manager: Optional[Neo4jSessionManager] = None) -> TenantManager:
    """
    Get the singleton TenantManager instance.
    
    Args:
        session_manager: Optional Neo4j session manager. If not provided, creates one.
    """
    if session_manager is None:
        # Create default session manager from environment
        from ..config_manager import create_neo4j_config_from_env
        neo4j_config = create_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(neo4j_config.neo4j)
    return TenantManager(session_manager)


def get_current_tenant() -> Optional[Tenant]:
    """Get the currently active tenant."""
    return get_tenant_manager().get_current_tenant()


def switch_tenant(tenant_id: str) -> Tenant:
    """Switch to a different tenant."""
    return get_tenant_manager().switch_tenant(tenant_id)


def register_tenant(
    tenant_id: str,
    display_name: str,
    config: Optional[Dict[str, Any]] = None,
    subscription_ids: Optional[List[str]] = None
) -> Tenant:
    """Register a new tenant."""
    return get_tenant_manager().register_tenant(
        tenant_id, display_name, config, subscription_ids
    )