"""
Operations Service for ATG Remote Execution.

Philosophy:
- WRAP existing ATG services, don't duplicate
- Publish progress to ProgressTracker
- Handle errors gracefully
- Use existing ATG configuration

This service wraps the existing ATG CLI functionality for remote execution.
It delegates to AzureTenantGrapher for scan operations and IaC generation.

Public API:
    OperationsService: Main operations coordinator
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

from ....azure_tenant_grapher import AzureTenantGrapher
from ....config_manager import (
    create_config_from_env,
)
from ....iac.cli_handler import (
    default_timestamped_dir,
)
from ...db.connection_manager import ConnectionManager
from .progress import ProgressTracker

logger = logging.getLogger(__name__)


class OperationsService:
    """
    Execute ATG operations by wrapping existing services.

    Coordinates scan and IaC generation operations, publishing progress
    updates through the ProgressTracker.

    Attributes:
        connection_manager: Neo4j connection manager
        progress_tracker: Progress tracking service
        output_dir: Base directory for operation outputs
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        progress_tracker: ProgressTracker,
        output_dir: Path = Path("outputs"),
    ):
        """
        Initialize operations service.

        Args:
            connection_manager: Neo4j connection manager
            progress_tracker: Progress tracking service
            output_dir: Base directory for outputs (default: outputs/)
        """
        self.connection_manager = connection_manager
        self.progress_tracker = progress_tracker
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def execute_scan(
        self,
        job_id: str,
        tenant_id: str,
        subscription_id: Optional[str] = None,
        resource_limit: Optional[int] = None,
    ) -> Dict:
        """
        Execute Azure tenant scan operation.

        Wraps the existing AzureTenantGrapher scan functionality with
        progress tracking.

        Args:
            job_id: Unique job identifier for progress tracking
            tenant_id: Azure tenant ID to scan
            subscription_id: Optional subscription ID filter
            resource_limit: Optional limit on resources to scan

        Returns:
            Dictionary with scan results

        Raises:
            Exception: If scan fails

        Example:
            >>> service = OperationsService(conn_mgr, progress_tracker)
            >>> result = await service.execute_scan(
            ...     "scan-abc123",
            ...     "tenant-123"
            ... )
        """
        try:
            await self.progress_tracker.publish(
                job_id,
                "starting",
                f"Starting scan for tenant {tenant_id}",
                {"tenant_id": tenant_id},
            )

            # Create ATG configuration from environment
            # This uses existing config management
            config = create_config_from_env()

            # Override tenant ID
            config.azure_config.tenant_id = tenant_id
            if subscription_id:
                config.azure_config.subscription_id = subscription_id
            if resource_limit:
                config.processing.resource_limit = resource_limit

            # Initialize AzureTenantGrapher (wraps existing service)
            grapher = AzureTenantGrapher(config)

            await self.progress_tracker.publish(
                job_id,
                "progress",
                "Initializing Azure connection",
            )

            # Execute discovery using existing service
            # This wraps discovery_service.discover_all_resources()
            loop = asyncio.get_event_loop()

            def run_scan():
                """Sync wrapper for ATG scan (which may be sync or async)."""
                # The actual scan process
                resources = asyncio.run(
                    grapher.discovery_service.discover_all_resources()
                )
                return resources

            # Run in executor to avoid blocking
            resources = await loop.run_in_executor(None, run_scan)

            await self.progress_tracker.publish(
                job_id,
                "progress",
                f"Discovered {len(resources)} resources",
                {"resource_count": len(resources)},
            )

            # Process resources using existing service
            def process_resources():
                """Sync wrapper for resource processing."""
                return asyncio.run(
                    grapher.processing_service.process_resources(resources)
                )

            await loop.run_in_executor(None, process_resources)

            await self.progress_tracker.publish(
                job_id,
                "complete",
                f"Scan complete - processed {len(resources)} resources",
                {"resource_count": len(resources)},
            )

            return {
                "status": "complete",
                "resource_count": len(resources),
                "tenant_id": tenant_id,
            }

        except Exception as e:
            logger.exception(f"Scan failed for job {job_id}: {e}")
            await self.progress_tracker.publish(
                job_id,
                "error",
                f"Scan failed: {e!s}",
                {"error": str(e)},
            )
            raise

    async def execute_generate_iac(
        self,
        job_id: str,
        tenant_id: str,
        output_format: str = "terraform",
        output_path: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        auto_import: bool = False,
    ) -> Dict:
        """
        Execute IaC generation operation.

        Wraps the existing IaC generation functionality with progress tracking.

        Args:
            job_id: Unique job identifier
            tenant_id: Source tenant ID
            output_format: Output format (terraform, arm, bicep)
            output_path: Optional custom output path
            target_tenant_id: Optional target tenant for cross-tenant deployment
            auto_import: Generate Terraform import blocks

        Returns:
            Dictionary with generation results including output path

        Raises:
            Exception: If generation fails

        Example:
            >>> result = await service.execute_generate_iac(
            ...     "gen-abc123",
            ...     "tenant-123",
            ...     output_format="terraform"
            ... )
        """
        try:
            await self.progress_tracker.publish(
                job_id,
                "starting",
                f"Starting IaC generation for tenant {tenant_id}",
                {"tenant_id": tenant_id, "format": output_format},
            )

            # Determine output directory
            if output_path:
                outdir = Path(output_path)
            else:
                outdir = default_timestamped_dir()

            outdir.mkdir(parents=True, exist_ok=True)

            await self.progress_tracker.publish(
                job_id,
                "progress",
                f"Generating {output_format} templates",
            )

            # Use existing IaC generation (wraps generate_iac_command)
            # This is the actual ATG IaC generation logic
            loop = asyncio.get_event_loop()

            def run_generation():
                """Sync wrapper for IaC generation."""
                # Call the existing CLI handler
                # (This wraps GraphTraverser, TransformationEngine, etc.)
                from src.iac.cli_handler import generate_iac_command

                result = generate_iac_command(
                    tenant_id=tenant_id,
                    output_format=output_format,
                    output_dir=str(outdir),
                    target_tenant_id=target_tenant_id,
                    auto_import_existing=auto_import,
                )
                return result

            await loop.run_in_executor(None, run_generation)

            # Count generated files
            generated_files = list(outdir.glob("**/*.tf"))
            file_count = len(generated_files)

            await self.progress_tracker.publish(
                job_id,
                "complete",
                f"Generated {file_count} files in {outdir}",
                {"file_count": file_count, "output_dir": str(outdir)},
            )

            return {
                "status": "complete",
                "output_dir": str(outdir),
                "file_count": file_count,
                "format": output_format,
            }

        except Exception as e:
            logger.exception(f"IaC generation failed for job {job_id}: {e}")
            await self.progress_tracker.publish(
                job_id,
                "error",
                f"Generation failed: {e!s}",
                {"error": str(e)},
            )
            raise

    async def execute_generate_spec(
        self,
        job_id: str,
        tenant_id: str,
        output_path: Optional[str] = None,
    ) -> Dict:
        """
        Execute tenant specification generation operation.

        Wraps the existing tenant spec generation functionality with progress tracking.

        Args:
            job_id: Unique job identifier
            tenant_id: Source tenant ID (unused but kept for consistency)
            output_path: Optional custom output path

        Returns:
            Dictionary with generation results including spec path

        Raises:
            Exception: If generation fails

        Example:
            >>> result = await service.execute_generate_spec(
            ...     "spec-abc123",
            ...     "tenant-123"
            ... )
        """
        try:
            await self.progress_tracker.publish(
                job_id,
                "starting",
                "Starting tenant specification generation",
                {"tenant_id": tenant_id},
            )

            # Determine output path
            if output_path:
                outpath = Path(output_path)
            else:
                from datetime import datetime, timezone

                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                outpath = self.output_dir / f"{ts}_tenant_spec.md"

            outpath.parent.mkdir(parents=True, exist_ok=True)

            await self.progress_tracker.publish(
                job_id,
                "progress",
                "Generating tenant specification",
            )

            # Use existing spec generation
            loop = asyncio.get_event_loop()

            def run_generation():
                """Sync wrapper for spec generation."""
                from src.config_manager import SpecificationConfig
                from src.tenant_spec_generator import (
                    ResourceAnonymizer,
                    TenantSpecificationGenerator,
                )

                # Get Neo4j connection details from connection manager

                # Create anonymizer with default seed
                spec_config = SpecificationConfig()
                anonymizer = ResourceAnonymizer(seed=spec_config.anonymization_seed)

                # Create generator (uses Neo4j URI from connection manager)
                generator = TenantSpecificationGenerator(
                    neo4j_uri=self.connection_manager.uri,
                    neo4j_user=self.connection_manager.user,
                    neo4j_password=self.connection_manager.password,
                    anonymizer=anonymizer,
                    config=spec_config,
                )

                # Generate specification
                generated_path = generator.generate_specification(
                    output_path=str(outpath)
                )
                return generated_path

            spec_path = await loop.run_in_executor(None, run_generation)

            await self.progress_tracker.publish(
                job_id,
                "complete",
                f"Generated specification at {spec_path}",
                {"spec_path": str(spec_path)},
            )

            return {
                "status": "complete",
                "spec_path": str(spec_path),
            }

        except Exception as e:
            logger.exception(f"Spec generation failed for job {job_id}: {e}")
            await self.progress_tracker.publish(
                job_id,
                "error",
                f"Generation failed: {e!s}",
                {"error": str(e)},
            )
            raise


__all__ = ["OperationsService"]
