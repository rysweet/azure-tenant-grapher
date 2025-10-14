"""
Deployment Job Tracker

Manages tracking of IaC deployment jobs in Neo4j, including job lifecycle,
status transitions, and relationships between deployment iterations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from neo4j.exceptions import Neo4jError

from src.exceptions import Neo4jQueryError, wrap_neo4j_exception
from src.utils.session_manager import Neo4jSessionManager

logger = structlog.get_logger(__name__)


class DeploymentJobTracker:
    """
    Tracks deployment jobs in Neo4j graph database.

    Provides methods for creating, updating, and querying deployment jobs
    with support for iteration tracking and resource relationships.
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the deployment job tracker.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        self.session_manager = session_manager
        self._logger = logger.bind(component="DeploymentJobTracker")

    def create_job(
        self,
        tenant_id: str,
        format_type: str,
        status: str = "pending",
        parent_job_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Create a new deployment job in Neo4j.

        Args:
            tenant_id: Azure tenant ID for this deployment
            format_type: IaC format (terraform, arm, bicep)
            status: Initial job status (default: pending)
            parent_job_id: Optional parent job ID for iteration tracking
            metadata: Optional additional metadata for the job

        Returns:
            str: The generated job_id

        Raises:
            Neo4jConnectionError: If database connection fails
            Neo4jQueryError: If job creation query fails
        """
        job_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        job_properties: dict[str, Any] = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "format": format_type,
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
        }

        # Add optional metadata fields
        if metadata:
            job_properties["metadata"] = metadata

        self._logger.info(
            "Creating deployment job",
            job_id=job_id,
            tenant_id=tenant_id,
            format=format_type,
            status=status,
        )

        try:
            with self.session_manager.session() as session:
                # Create the job node
                create_query = """
                CREATE (job:DeploymentJob $properties)
                RETURN job.job_id as job_id
                """
                result = session.run(create_query, parameters={"properties": job_properties})
                record = result.single()

                if not record:
                    raise Neo4jQueryError(
                        "Failed to create deployment job - no result returned",
                        query=create_query,
                        parameters={"properties": job_properties},
                    )

                # If parent_job_id is provided, create ITERATION_OF relationship
                if parent_job_id:
                    iteration_query = """
                    MATCH (new_job:DeploymentJob {job_id: $new_job_id})
                    MATCH (parent_job:DeploymentJob {job_id: $parent_job_id})
                    CREATE (new_job)-[:ITERATION_OF]->(parent_job)
                    RETURN new_job.job_id as job_id
                    """
                    iter_result = session.run(
                        iteration_query,
                        parameters={
                            "new_job_id": job_id,
                            "parent_job_id": parent_job_id,
                        },
                    )
                    iter_record = iter_result.single()

                    if not iter_record:
                        self._logger.warning(
                            "Failed to create ITERATION_OF relationship",
                            new_job_id=job_id,
                            parent_job_id=parent_job_id,
                        )
                    else:
                        self._logger.info(
                            "Created ITERATION_OF relationship",
                            new_job_id=job_id,
                            parent_job_id=parent_job_id,
                        )

                self._logger.info("Successfully created deployment job", job_id=job_id)
                return job_id

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "create_job",
                    "tenant_id": tenant_id,
                    "format": format_type,
                },
            ) from e
        except Exception as e:
            self._logger.exception("Unexpected error creating deployment job", error=str(e))
            # Provide a default query string for the error case
            error_query = "CREATE (job:DeploymentJob $properties) RETURN job.job_id as job_id"
            raise Neo4jQueryError(
                f"Failed to create deployment job: {e}",
                query=error_query,
                parameters={"properties": job_properties},
                cause=e,
            ) from e

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        output_path: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Update an existing deployment job.

        Args:
            job_id: Job ID to update
            status: New status (if changing)
            output_path: Path to generated IaC output
            error_message: Error message if job failed
            metadata: Additional metadata to merge

        Returns:
            bool: True if update successful, False otherwise

        Raises:
            Neo4jQueryError: If update query fails
        """
        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}

        if status is not None:
            updates["status"] = status
        if output_path is not None:
            updates["output_path"] = output_path
        if error_message is not None:
            updates["error_message"] = error_message
        if metadata is not None:
            updates["metadata"] = metadata

        self._logger.info("Updating deployment job", job_id=job_id, updates=updates)

        try:
            with self.session_manager.session() as session:
                # Build SET clause dynamically
                set_clauses = [f"job.{key} = ${key}" for key in updates.keys()]
                set_clause = ", ".join(set_clauses)

                query = f"""
                MATCH (job:DeploymentJob {{job_id: $job_id}})
                SET {set_clause}
                RETURN job.job_id as job_id
                """

                parameters = {"job_id": job_id, **updates}
                result = session.run(query, parameters=parameters)  # type: ignore[arg-type]
                record = result.single()

                if not record:
                    self._logger.warning(
                        "Job not found for update",
                        job_id=job_id,
                    )
                    return False

                self._logger.info("Successfully updated deployment job", job_id=job_id)
                return True

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "update_job",
                    "job_id": job_id,
                },
            ) from e
        except Exception as e:
            self._logger.exception("Unexpected error updating deployment job", error=str(e))
            raise Neo4jQueryError(
                f"Failed to update deployment job: {e}",
                query="update_job",
                parameters={"job_id": job_id, **updates},
                cause=e,
            ) from e

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve a deployment job by ID.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Optional[dict]: Job properties if found, None otherwise

        Raises:
            Neo4jQueryError: If query fails
        """
        self._logger.debug("Retrieving deployment job", job_id=job_id)

        try:
            with self.session_manager.session() as session:
                query = """
                MATCH (job:DeploymentJob {job_id: $job_id})
                RETURN job
                """
                result = session.run(query, parameters={"job_id": job_id})
                record = result.single()

                if not record:
                    self._logger.debug("Job not found", job_id=job_id)
                    return None

                # Convert Neo4j node to dict
                job_node = record["job"]
                job_dict = dict(job_node.items())

                self._logger.debug("Retrieved deployment job", job_id=job_id)
                return job_dict

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "get_job",
                    "job_id": job_id,
                },
            ) from e
        except Exception as e:
            self._logger.exception("Unexpected error retrieving deployment job", error=str(e))
            raise Neo4jQueryError(
                f"Failed to retrieve deployment job: {e}",
                query="get_job",
                parameters={"job_id": job_id},
                cause=e,
            ) from e

    def link_deployed_resources(
        self, job_id: str, resource_ids: list[str]
    ) -> int:
        """
        Create DEPLOYED relationships between a job and resources.

        Args:
            job_id: Job ID that deployed the resources
            resource_ids: List of resource IDs that were deployed

        Returns:
            int: Number of relationships created

        Raises:
            Neo4jQueryError: If relationship creation fails
        """
        if not resource_ids:
            self._logger.debug("No resources to link", job_id=job_id)
            return 0

        self._logger.info(
            "Linking deployed resources",
            job_id=job_id,
            resource_count=len(resource_ids),
        )

        try:
            with self.session_manager.session() as session:
                query = """
                MATCH (job:DeploymentJob {job_id: $job_id})
                UNWIND $resource_ids as resource_id
                MATCH (resource:Resource {id: resource_id})
                MERGE (job)-[:DEPLOYED]->(resource)
                RETURN count(*) as relationships_created
                """
                result = session.run(
                    query,
                    parameters={
                        "job_id": job_id,
                        "resource_ids": resource_ids,
                    },
                )
                record = result.single()

                relationships_created = record["relationships_created"] if record else 0

                self._logger.info(
                    "Successfully linked deployed resources",
                    job_id=job_id,
                    relationships_created=relationships_created,
                )
                return relationships_created

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "link_deployed_resources",
                    "job_id": job_id,
                    "resource_count": len(resource_ids),
                },
            ) from e
        except Exception as e:
            self._logger.exception(
                "Unexpected error linking deployed resources", error=str(e)
            )
            raise Neo4jQueryError(
                f"Failed to link deployed resources: {e}",
                query="link_deployed_resources",
                parameters={"job_id": job_id, "resource_ids": resource_ids},
                cause=e,
            ) from e

    def get_job_history(
        self, tenant_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get deployment job history for a tenant.

        Args:
            tenant_id: Tenant ID to query
            limit: Maximum number of jobs to return

        Returns:
            list[dict]: List of job records, ordered by created_at DESC

        Raises:
            Neo4jQueryError: If query fails
        """
        self._logger.debug(
            "Retrieving job history", tenant_id=tenant_id, limit=limit
        )

        try:
            with self.session_manager.session() as session:
                query = """
                MATCH (job:DeploymentJob {tenant_id: $tenant_id})
                RETURN job
                ORDER BY job.created_at DESC
                LIMIT $limit
                """
                result = session.run(
                    query, parameters={"tenant_id": tenant_id, "limit": limit}
                )

                jobs = []
                for record in result:
                    job_node = record["job"]
                    job_dict = dict(job_node.items())
                    jobs.append(job_dict)

                self._logger.debug(
                    "Retrieved job history",
                    tenant_id=tenant_id,
                    job_count=len(jobs),
                )
                return jobs

        except Neo4jError as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "get_job_history",
                    "tenant_id": tenant_id,
                },
            ) from e
        except Exception as e:
            self._logger.exception("Unexpected error retrieving job history", error=str(e))
            raise Neo4jQueryError(
                f"Failed to retrieve job history: {e}",
                query="get_job_history",
                parameters={"tenant_id": tenant_id, "limit": limit},
                cause=e,
            ) from e
