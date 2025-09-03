"""Deployment registry for tracking IaC deployments.

This module tracks all Infrastructure-as-Code deployments to enable
safe destruction and rollback capabilities.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Status of a deployment."""
    ACTIVE = "active"
    DESTROYED = "destroyed"
    FAILED = "failed"
    PARTIAL = "partial"


class DeploymentRegistry:
    """Manages deployment tracking and state."""
    
    def __init__(self, registry_dir: Path = Path(".deployments")):
        """Initialize the deployment registry.
        
        Args:
            registry_dir: Directory for storing deployment metadata
        """
        self.registry_dir = registry_dir
        self.registry_file = registry_dir / "registry.json"
        self.backups_dir = registry_dir / "backups"
        self.logs_dir = registry_dir / "logs"
        
        # Create directories if they don't exist
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize registry
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load the deployment registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    self.registry = json.load(f)
            except json.JSONDecodeError:
                logger.error("Failed to load registry, initializing new one")
                self.registry = {"deployments": []}
        else:
            self.registry = {"deployments": []}
    
    def _save_registry(self) -> None:
        """Save the deployment registry to disk."""
        with open(self.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2, default=str)
    
    def register_deployment(
        self,
        directory: str,
        tenant: str,
        resources: Dict[str, int],
        terraform_version: Optional[str] = None
    ) -> str:
        """Register a new deployment.
        
        Args:
            directory: IaC output directory path
            tenant: Target tenant identifier
            resources: Dictionary of resource types and counts
            terraform_version: Version of Terraform used
            
        Returns:
            Deployment ID
        """
        timestamp = datetime.now()
        deployment_id = f"deploy-{timestamp.strftime('%Y%m%d-%H%M%S')}"
        
        deployment = {
            "id": deployment_id,
            "directory": directory,
            "tenant": tenant,
            "status": DeploymentStatus.ACTIVE.value,
            "deployed_at": timestamp.isoformat(),
            "destroyed_at": None,
            "resources": resources,
            "terraform_version": terraform_version,
            "state_backup": None
        }
        
        self.registry["deployments"].append(deployment)
        self._save_registry()
        
        logger.info(f"Registered deployment {deployment_id} for tenant {tenant}")
        return deployment_id
    
    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Get a deployment by ID.
        
        Args:
            deployment_id: Deployment identifier
            
        Returns:
            Deployment record or None if not found
        """
        for deployment in self.registry["deployments"]:
            if deployment["id"] == deployment_id:
                return deployment
        return None
    
    def get_deployment_by_directory(self, directory: str) -> Optional[Dict[str, Any]]:
        """Get a deployment by directory path.
        
        Args:
            directory: IaC output directory path
            
        Returns:
            Deployment record or None if not found
        """
        # Normalize path for comparison
        normalized_dir = str(Path(directory).resolve())
        
        for deployment in self.registry["deployments"]:
            if str(Path(deployment["directory"]).resolve()) == normalized_dir:
                return deployment
        return None
    
    def list_deployments(
        self,
        tenant: Optional[str] = None,
        status: Optional[DeploymentStatus] = None
    ) -> List[Dict[str, Any]]:
        """List deployments with optional filters.
        
        Args:
            tenant: Filter by tenant
            status: Filter by status
            
        Returns:
            List of deployment records
        """
        deployments = self.registry["deployments"]
        
        if tenant:
            deployments = [d for d in deployments if d["tenant"] == tenant]
        
        if status:
            deployments = [d for d in deployments if d["status"] == status.value]
        
        # Sort by deployment time (newest first)
        deployments.sort(key=lambda x: x["deployed_at"], reverse=True)
        
        return deployments
    
    def mark_destroyed(
        self,
        deployment_id: str,
        backup_path: Optional[str] = None
    ) -> bool:
        """Mark a deployment as destroyed.
        
        Args:
            deployment_id: Deployment identifier
            backup_path: Path to state backup
            
        Returns:
            True if successful, False otherwise
        """
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return False
        
        deployment["status"] = DeploymentStatus.DESTROYED.value
        deployment["destroyed_at"] = datetime.now().isoformat()
        if backup_path:
            deployment["state_backup"] = backup_path
        
        self._save_registry()
        logger.info(f"Marked deployment {deployment_id} as destroyed")
        return True
    
    def mark_failed(
        self,
        deployment_id: str,
        error: str,
        remaining_resources: Optional[Dict[str, int]] = None
    ) -> bool:
        """Mark a deployment as failed.
        
        Args:
            deployment_id: Deployment identifier
            error: Error message
            remaining_resources: Resources that couldn't be destroyed
            
        Returns:
            True if successful, False otherwise
        """
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return False
        
        deployment["status"] = DeploymentStatus.FAILED.value
        deployment["error"] = error
        deployment["failed_at"] = datetime.now().isoformat()
        if remaining_resources:
            deployment["remaining_resources"] = remaining_resources
        
        self._save_registry()
        logger.error(f"Marked deployment {deployment_id} as failed: {error}")
        return True
    
    def backup_state(self, deployment_id: str, state_file: Path) -> Optional[Path]:
        """Backup Terraform state file for a deployment.
        
        Args:
            deployment_id: Deployment identifier
            state_file: Path to terraform.tfstate file
            
        Returns:
            Path to backup or None if failed
        """
        if not state_file.exists():
            logger.error(f"State file {state_file} does not exist")
            return None
        
        backup_dir = self.backups_dir / deployment_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_file = backup_dir / "terraform.tfstate"
        
        try:
            import shutil
            shutil.copy2(state_file, backup_file)
            
            # Also save metadata
            deployment = self.get_deployment(deployment_id)
            if deployment:
                metadata_file = backup_dir / "metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump({
                        "deployment": deployment,
                        "backup_time": datetime.now().isoformat(),
                        "original_path": str(state_file)
                    }, f, indent=2)
            
            logger.info(f"Backed up state for {deployment_id} to {backup_dir}")
            return backup_dir
            
        except Exception as e:
            logger.error(f"Failed to backup state: {e}")
            return None
    
    def get_active_deployments(self, tenant: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active deployments.
        
        Args:
            tenant: Optional tenant filter
            
        Returns:
            List of active deployment records
        """
        return self.list_deployments(tenant=tenant, status=DeploymentStatus.ACTIVE)