"""
Job Storage Service for ATG Remote Operations.

Philosophy:
- Store job metadata in Neo4j
- Simple CRUD operations
- Clear error handling
- Support job listing and filtering

Public API:
    JobStorage: Job metadata storage service
"""

import json
import logging
from typing import Dict, List, Optional

from ...db.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class JobStorage:
    """
    Store and retrieve job metadata in Neo4j.

    Handles CRUD operations for ATG remote operation jobs.

    Attributes:
        connection_manager: Neo4j connection manager
    """

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize job storage.

        Args:
            connection_manager: Neo4j connection manager
        """
        self.connection_manager = connection_manager

    async def create_job(
        self,
        job_id: str,
        operation_type: str,
        params: Dict,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Create a new job record in Neo4j.

        Args:
            job_id: Unique job identifier
            operation_type: Type of operation (scan, generate-iac, etc.)
            params: Operation parameters
            user_id: Optional user identifier

        Returns:
            Created job record

        Example:
            >>> storage = JobStorage(connection_manager)
            >>> job = await storage.create_job(
            ...     "scan-abc123",
            ...     "scan",
            ...     {"tenant_id": "tenant-123"}
            ... )
        """
        async with self.connection_manager.session() as session:
            query = """
            CREATE (j:Job {
                id: $job_id,
                operation_type: $operation_type,
                params: $params,
                status: 'queued',
                created_at: datetime(),
                updated_at: datetime()
            })
            SET j.user_id = $user_id
            RETURN j
            """

            result = await session.run(
                query,
                job_id=job_id,
                operation_type=operation_type,
                params=json.dumps(params),
                user_id=user_id,
            )

            record = await result.single()
            if record is None:
                raise RuntimeError(f"Failed to create job {job_id}")

            job = dict(record["j"])
            logger.info(f"Created job {job_id} of type {operation_type}")
            return self._format_job(job)

    async def update_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        result: Optional[Dict] = None,
    ) -> Dict:
        """
        Update job status.

        Args:
            job_id: Job identifier
            status: New status (queued, running, completed, failed, cancelled)
            error: Optional error message if failed
            result: Optional result data if completed

        Returns:
            Updated job record

        Raises:
            ValueError: If job not found
        """
        async with self.connection_manager.session() as session:
            query = """
            MATCH (j:Job {id: $job_id})
            SET j.status = $status,
                j.updated_at = datetime()
            """

            params = {"job_id": job_id, "status": status}

            if error:
                query += ", j.error = $error"
                params["error"] = error

            if result:
                query += ", j.result = $result"
                params["result"] = json.dumps(result)

            query += " RETURN j"

            query_result = await session.run(query, **params)
            record = await query_result.single()

            if record is None:
                raise ValueError(f"Job {job_id} not found")

            job = dict(record["j"])
            logger.info(f"Updated job {job_id} status to {status}")
            return self._format_job(job)

    async def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Retrieve job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job record or None if not found
        """
        async with self.connection_manager.session() as session:
            result = await session.run(
                """
                MATCH (j:Job {id: $job_id})
                RETURN j
                """,
                job_id=job_id,
            )

            record = await result.single()
            if record is None:
                return None

            job = dict(record["j"])
            return self._format_job(job)

    async def list_jobs(
        self,
        status_filter: Optional[str] = None,
        operation_type: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """
        List jobs with optional filtering.

        Args:
            status_filter: Filter by status
            operation_type: Filter by operation type
            user_id: Filter by user
            limit: Maximum results (default: 50)
            offset: Pagination offset (default: 0)

        Returns:
            List of job records
        """
        conditions = []
        params: Dict = {"limit": limit, "offset": offset}

        if status_filter:
            conditions.append("j.status = $status")
            params["status"] = status_filter

        if operation_type:
            conditions.append("j.operation_type = $operation_type")
            params["operation_type"] = operation_type

        if user_id:
            conditions.append("j.user_id = $user_id")
            params["user_id"] = user_id

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (j:Job)
        {where_clause}
        RETURN j
        ORDER BY j.created_at DESC
        SKIP $offset
        LIMIT $limit
        """

        async with self.connection_manager.session() as session:
            result = await session.run(query, **params)
            records = await result.data()

            jobs = [dict(record["j"]) for record in records]
            return [self._format_job(job) for job in jobs]

    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job record.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        async with self.connection_manager.session() as session:
            result = await session.run(
                """
                MATCH (j:Job {id: $job_id})
                DELETE j
                RETURN count(j) as deleted
                """,
                job_id=job_id,
            )

            record = await result.single()
            if record is None:
                return False

            deleted = record["deleted"]
            if deleted > 0:
                logger.info(f"Deleted job {job_id}")
                return True
            return False

    def _format_job(self, job: Dict) -> Dict:
        """
        Format job record for API response.

        Handles Neo4j datetime conversion and JSON deserialization.

        Args:
            job: Raw Neo4j job record

        Returns:
            Formatted job dictionary
        """
        formatted = {
            "id": job["id"],
            "operation_type": job["operation_type"],
            "status": job["status"],
            "created_at": (
                job["created_at"].isoformat()
                if hasattr(job["created_at"], "isoformat")
                else str(job["created_at"])
            ),
            "updated_at": (
                job["updated_at"].isoformat()
                if hasattr(job["updated_at"], "isoformat")
                else str(job["updated_at"])
            ),
        }

        # Deserialize params
        if "params" in job:
            try:
                formatted["params"] = json.loads(job["params"])
            except (json.JSONDecodeError, TypeError):
                formatted["params"] = {}

        # Include optional fields
        if job.get("user_id"):
            formatted["user_id"] = job["user_id"]

        if job.get("error"):
            formatted["error"] = job["error"]

        if job.get("result"):
            try:
                formatted["result"] = json.loads(job["result"])
            except (json.JSONDecodeError, TypeError):
                formatted["result"] = {}

        return formatted


__all__ = ["JobStorage"]
