"""
ATG Remote Server Services.

Philosophy:
- WRAP existing ATG services, don't duplicate
- Single responsibility per service
- Clear dependency injection patterns
- Working implementations only (no stubs)

Services:
    ProgressTracker: Progress tracking and WebSocket publishing
    JobStorage: Job metadata storage in Neo4j
    OperationsService: Wraps ATG scan/generate operations
    FileGenerator: Output file generation and management
    BackgroundExecutor: Background task execution
"""

from .executor import BackgroundExecutor
from .file_generator import FileGenerator
from .job_storage import JobStorage
from .operations import OperationsService
from .progress import ProgressTracker

__all__ = [
    "BackgroundExecutor",
    "FileGenerator",
    "JobStorage",
    "OperationsService",
    "ProgressTracker",
]
