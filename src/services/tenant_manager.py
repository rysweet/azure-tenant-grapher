"""
Tenant Manager Service

This module provides multi-tenant support for Azure Tenant Grapher,
managing tenant registration, switching, and configuration persistence.

Following the project's philosophy of ruthless simplicity, this implementation
uses file-based JSON storage initially, with the ability to enhance later.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    Uses file-based storage in .atg/tenants/ directory for simplicity.
    """
    
    _instance: Optional["TenantManager"] = None
    _initialized: bool = False
    
    def __new__(cls, base_dir: Optional[Path] = None) -> "TenantManager":
        """Implement singleton pattern with support for base_dir parameter."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """
        Initialize the TenantManager.
        
        Args:
            base_dir: Base directory for tenant storage. Defaults to .atg/tenants
        """
        # Handle singleton initialization
        if TenantManager._initialized and base_dir is None:
            return
        
        # Allow re-initialization with a different base_dir for testing
        if base_dir is not None:
            TenantManager._initialized = False
            
        if TenantManager._initialized:
            return
            
        self.base_dir = base_dir or Path.home() / ".atg" / "tenants"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_tenant_id: Optional[str] = None
        self._tenant_cache: Dict[str, Tenant] = {}
        
        # Load existing tenants on initialization
        self._load_tenants()
        
        # Load current tenant from state file if exists
        self._load_current_tenant()
        
        TenantManager._initialized = True
        logger.info(f"TenantManager initialized with base directory: {self.base_dir}")
    
    def _get_tenant_file_path(self, tenant_id: str) -> Path:
        """Get the file path for a specific tenant configuration."""
        return self.base_dir / f"{tenant_id}.json"
    
    def _get_state_file_path(self) -> Path:
        """Get the file path for the manager state."""
        return self.base_dir / "_state.json"
    
    def _load_tenants(self) -> None:
        """Load all tenant configurations from disk."""
        self._tenant_cache.clear()
        
        for tenant_file in self.base_dir.glob("*.json"):
            # Skip the state file
            if tenant_file.name == "_state.json":
                continue
                
            try:
                with open(tenant_file, 'r') as f:
                    data = json.load(f)
                    tenant = Tenant.from_dict(data)
                    self._tenant_cache[tenant.tenant_id] = tenant
                    logger.debug(f"Loaded tenant: {tenant.tenant_id}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load tenant from {tenant_file}: {e}")
    
    def _load_current_tenant(self) -> None:
        """Load the current tenant from state file."""
        state_file = self._get_state_file_path()
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self._current_tenant_id = state.get("current_tenant_id")
                    logger.debug(f"Loaded current tenant: {self._current_tenant_id}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load state: {e}")
    
    def _save_tenant(self, tenant: Tenant) -> None:
        """Save a tenant configuration to disk."""
        tenant_file = self._get_tenant_file_path(tenant.tenant_id)
        with open(tenant_file, 'w') as f:
            json.dump(tenant.to_dict(), f, indent=2)
        logger.debug(f"Saved tenant: {tenant.tenant_id}")
    
    def _save_state(self) -> None:
        """Save the manager state to disk."""
        state_file = self._get_state_file_path()
        state = {
            "current_tenant_id": self._current_tenant_id,
            "last_updated": datetime.utcnow().isoformat()
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state with current tenant: {self._current_tenant_id}")
    
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
        
        # Remove file
        tenant_file = self._get_tenant_file_path(tenant_id)
        if tenant_file.exists():
            tenant_file.unlink()
        
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
            # Clear existing cache
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
def get_tenant_manager() -> TenantManager:
    """Get the singleton TenantManager instance."""
    return TenantManager()


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