"""
Background Executor Service for ATG Remote Operations.

Philosophy:
- Execute long-running operations in background
- Coordinate between JobStorage, OperationsService, and ProgressTracker
- Handle errors gracefully
- Update job status throughout execution

Public API:
    BackgroundExecutor: Background task orchestrator
"""

import logging
from typing import Optional

from fastapi import BackgroundTasks

from .file_generator import FileGenerator
from .job_storage import JobStorage
from .operations import OperationsService
from .progress import ProgressTracker

logger = logging.getLogger(__name__)


class BackgroundExecutor:
    """
    Execute ATG operations in background tasks.

    Orchestrates JobStorage, OperationsService, ProgressTracker, and
    FileGenerator to execute long-running operations.

    Attributes:
        job_storage: Job metadata storage
        operations_service: Operations execution service
        progress_tracker: Progress tracking service
        file_generator: File generation service
    """

    def __init__(
        self,
        job_storage: JobStorage,
        operations_service: OperationsService,
        progress_tracker: ProgressTracker,
        file_generator: FileGenerator,
    ):
        """
        Initialize background executor.

        Args:
            job_storage: Job metadata storage
            operations_service: Operations execution service
            progress_tracker: Progress tracking service
            file_generator: File generation service
        """
        self.job_storage = job_storage
        self.operations_service = operations_service
        self.progress_tracker = progress_tracker
        self.file_generator = file_generator

    async def submit_scan(
        self,
        background_tasks: BackgroundTasks,
        job_id: str,
        tenant_id: str,
        subscription_id: Optional[str] = None,
        resource_limit: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Submit scan operation to background.

        Args:
            background_tasks: FastAPI background tasks
            job_id: Unique job identifier
            tenant_id: Azure tenant ID
            subscription_id: Optional subscription filter
            resource_limit: Optional resource limit
            user_id: Optional user identifier

        Returns:
            Dictionary with job_id and status

        Example:
            >>> executor = BackgroundExecutor(storage, ops, tracker, files)
            >>> result = await executor.submit_scan(
            ...     background_tasks,
            ...     "scan-abc123",
            ...     "tenant-123"
            ... )
        """
        # Create job record
        await self.job_storage.create_job(
            job_id=job_id,
            operation_type="scan",
            params={
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "resource_limit": resource_limit,
            },
            user_id=user_id,
        )

        # Submit to background
        background_tasks.add_task(
            self._execute_scan,
            job_id,
            tenant_id,
            subscription_id,
            resource_limit,
        )

        logger.info(f"Submitted scan job {job_id} for tenant {tenant_id}")

        return {
            "job_id": job_id,
            "status": "queued",
        }

    async def submit_generate_iac(
        self,
        background_tasks: BackgroundTasks,
        job_id: str,
        tenant_id: str,
        output_format: str = "terraform",
        output_path: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        auto_import: bool = False,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Submit IaC generation operation to background.

        Args:
            background_tasks: FastAPI background tasks
            job_id: Unique job identifier
            tenant_id: Source tenant ID
            output_format: Output format (terraform, arm, bicep)
            output_path: Optional custom output path
            target_tenant_id: Optional target tenant
            auto_import: Generate import blocks
            user_id: Optional user identifier

        Returns:
            Dictionary with job_id and status
        """
        # Create job record
        await self.job_storage.create_job(
            job_id=job_id,
            operation_type="generate-iac",
            params={
                "tenant_id": tenant_id,
                "output_format": output_format,
                "output_path": output_path,
                "target_tenant_id": target_tenant_id,
                "auto_import": auto_import,
            },
            user_id=user_id,
        )

        # Submit to background
        background_tasks.add_task(
            self._execute_generate_iac,
            job_id,
            tenant_id,
            output_format,
            output_path,
            target_tenant_id,
            auto_import,
        )

        logger.info(f"Submitted generate-iac job {job_id} for tenant {tenant_id}")

        return {
            "job_id": job_id,
            "status": "queued",
        }

    async def submit_generate_spec(
        self,
        background_tasks: BackgroundTasks,
        job_id: str,
        tenant_id: str,
        output_path: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Submit spec generation operation to background.

        Args:
            background_tasks: FastAPI background tasks
            job_id: Unique job identifier
            tenant_id: Source tenant ID
            output_path: Optional custom output path
            user_id: Optional user identifier

        Returns:
            Dictionary with job_id and status
        """
        # Create job record
        await self.job_storage.create_job(
            job_id=job_id,
            operation_type="generate-spec",
            params={
                "tenant_id": tenant_id,
                "output_path": output_path,
            },
            user_id=user_id,
        )

        # Submit to background
        background_tasks.add_task(
            self._execute_generate_spec,
            job_id,
            tenant_id,
            output_path,
        )

        logger.info(f"Submitted generate-spec job {job_id} for tenant {tenant_id}")

        return {
            "job_id": job_id,
            "status": "queued",
        }

    async def _execute_scan(
        self,
        job_id: str,
        tenant_id: str,
        subscription_id: Optional[str] = None,
        resource_limit: Optional[int] = None,
    ) -> None:
        """
        Execute scan in background (internal).

        Args:
            job_id: Job identifier
            tenant_id: Tenant to scan
            subscription_id: Optional subscription filter
            resource_limit: Optional resource limit
        """
        try:
            # Update to running
            await self.job_storage.update_status(job_id, "running")

            # Execute scan
            result = await self.operations_service.execute_scan(
                job_id=job_id,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                resource_limit=resource_limit,
            )

            # Update to completed
            await self.job_storage.update_status(
                job_id,
                "completed",
                result=result,
            )

            logger.info(f"Scan job {job_id} completed successfully")

        except Exception as e:
            logger.exception(f"Scan job {job_id} failed: {e}")

            # Update to failed
            await self.job_storage.update_status(
                job_id,
                "failed",
                error=str(e),
            )

    async def _execute_generate_iac(
        self,
        job_id: str,
        tenant_id: str,
        output_format: str = "terraform",
        output_path: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        auto_import: bool = False,
    ) -> None:
        """
        Execute IaC generation in background (internal).

        Args:
            job_id: Job identifier
            tenant_id: Source tenant ID
            output_format: Output format
            output_path: Optional output path
            target_tenant_id: Optional target tenant
            auto_import: Generate import blocks
        """
        try:
            # Update to running
            await self.job_storage.update_status(job_id, "running")

            # Execute generation
            result = await self.operations_service.execute_generate_iac(
                job_id=job_id,
                tenant_id=tenant_id,
                output_format=output_format,
                output_path=output_path,
                target_tenant_id=target_tenant_id,
                auto_import=auto_import,
            )

            # Create ZIP archive of outputs
            if result.get("output_dir"):
                try:
                    # Copy outputs to job directory
                    import shutil
                    from pathlib import Path

                    source_dir = Path(result["output_dir"])
                    job_dir = self.file_generator.get_job_output_dir(job_id)
                    job_dir.mkdir(parents=True, exist_ok=True)

                    # Copy all files
                    for item in source_dir.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(source_dir)
                            dest_path = job_dir / rel_path
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest_path)

                    # Create ZIP archive
                    zip_path = self.file_generator.create_zip_archive(job_id)
                    result["zip_path"] = str(zip_path)

                except Exception as e:
                    logger.warning(f"Failed to create ZIP for job {job_id}: {e}")

            # Update to completed
            await self.job_storage.update_status(
                job_id,
                "completed",
                result=result,
            )

            logger.info(f"Generate-iac job {job_id} completed successfully")

        except Exception as e:
            logger.exception(f"Generate-iac job {job_id} failed: {e}")

            # Update to failed
            await self.job_storage.update_status(
                job_id,
                "failed",
                error=str(e),
            )

    async def _execute_generate_spec(
        self,
        job_id: str,
        tenant_id: str,
        output_path: Optional[str] = None,
    ) -> None:
        """
        Execute spec generation in background (internal).

        Args:
            job_id: Job identifier
            tenant_id: Source tenant ID
            output_path: Optional output path
        """
        try:
            # Update to running
            await self.job_storage.update_status(job_id, "running")

            # Execute spec generation
            result = await self.operations_service.execute_generate_spec(
                job_id=job_id,
                tenant_id=tenant_id,
                output_path=output_path,
            )

            # Create ZIP archive if spec file was generated
            if result.get("spec_path"):
                try:
                    import shutil
                    from pathlib import Path

                    spec_file = Path(result["spec_path"])
                    job_dir = self.file_generator.get_job_output_dir(job_id)
                    job_dir.mkdir(parents=True, exist_ok=True)

                    # Copy spec file to job directory
                    dest_path = job_dir / spec_file.name
                    shutil.copy2(spec_file, dest_path)

                    # Create ZIP archive
                    zip_path = self.file_generator.create_zip_archive(job_id)
                    result["zip_path"] = str(zip_path)

                except Exception as e:
                    logger.warning(f"Failed to create ZIP for job {job_id}: {e}")

            # Update to completed
            await self.job_storage.update_status(
                job_id,
                "completed",
                result=result,
            )

            logger.info(f"Generate-spec job {job_id} completed successfully")

        except Exception as e:
            logger.exception(f"Generate-spec job {job_id} failed: {e}")

            # Update to failed
            await self.job_storage.update_status(
                job_id,
                "failed",
                error=str(e),
            )


__all__ = ["BackgroundExecutor"]
