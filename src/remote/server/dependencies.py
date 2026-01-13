"""
FastAPI Dependencies for ATG Remote Service.

Philosophy:
- Centralized dependency injection
- Avoid circular imports
- Clear access to global state

This module provides dependency functions for FastAPI endpoints.
"""

from pathlib import Path
from typing import Optional

from ..db.connection_manager import ConnectionManager
from .config import ATGServerConfig
from .services import (
    BackgroundExecutor,
    FileGenerator,
    JobStorage,
    OperationsService,
    ProgressTracker,
)

# Global state (set during app startup)
_connection_manager: Optional[ConnectionManager] = None
_config: Optional[ATGServerConfig] = None
_progress_tracker: Optional[ProgressTracker] = None
_job_storage: Optional[JobStorage] = None
_operations_service: Optional[OperationsService] = None
_file_generator: Optional[FileGenerator] = None
_background_executor: Optional[BackgroundExecutor] = None


def set_connection_manager(manager: ConnectionManager) -> None:
    """Set the global connection manager."""
    global _connection_manager
    _connection_manager = manager


def set_config(config: ATGServerConfig) -> None:
    """Set the global configuration."""
    global _config
    _config = config


def initialize_services(
    connection_manager: ConnectionManager,
    output_dir: Path = Path("outputs"),
) -> None:
    """
    Initialize all services during app startup.

    Args:
        connection_manager: Neo4j connection manager
        output_dir: Base directory for outputs
    """
    global _progress_tracker, _job_storage, _operations_service
    global _file_generator, _background_executor

    # Create service instances
    _progress_tracker = ProgressTracker()
    _job_storage = JobStorage(connection_manager)
    _operations_service = OperationsService(
        connection_manager,
        _progress_tracker,
        output_dir,
    )
    _file_generator = FileGenerator(output_dir)
    _background_executor = BackgroundExecutor(
        _job_storage,
        _operations_service,
        _progress_tracker,
        _file_generator,
    )


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager (FastAPI dependency)."""
    if _connection_manager is None:
        raise RuntimeError("Connection manager not initialized")
    return _connection_manager


def get_config() -> ATGServerConfig:
    """Get the global configuration (FastAPI dependency)."""
    if _config is None:
        raise RuntimeError("Configuration not loaded")
    return _config


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker (FastAPI dependency)."""
    if _progress_tracker is None:
        raise RuntimeError("Progress tracker not initialized")
    return _progress_tracker


def get_job_storage() -> JobStorage:
    """Get the global job storage (FastAPI dependency)."""
    if _job_storage is None:
        raise RuntimeError("Job storage not initialized")
    return _job_storage


def get_operations_service() -> OperationsService:
    """Get the global operations service (FastAPI dependency)."""
    if _operations_service is None:
        raise RuntimeError("Operations service not initialized")
    return _operations_service


def get_file_generator() -> FileGenerator:
    """Get the global file generator (FastAPI dependency)."""
    if _file_generator is None:
        raise RuntimeError("File generator not initialized")
    return _file_generator


def get_background_executor() -> BackgroundExecutor:
    """Get the global background executor (FastAPI dependency)."""
    if _background_executor is None:
        raise RuntimeError("Background executor not initialized")
    return _background_executor


__all__ = [
    "get_background_executor",
    "get_config",
    "get_connection_manager",
    "get_file_generator",
    "get_job_storage",
    "get_operations_service",
    "get_progress_tracker",
    "initialize_services",
    "set_config",
    "set_connection_manager",
]
