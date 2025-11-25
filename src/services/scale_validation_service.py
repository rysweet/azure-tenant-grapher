"""
Scale Validation Service for Azure Tenant Grapher

This service provides comprehensive validation operations for synthetic data
created during scale operations. It ensures the integrity of the dual-graph
architecture and provides auto-fix capabilities for common issues.

Key Features:
- Validate no Original contamination
- Validate no SCAN_SOURCE_NODE for synthetic resources
- Validate synthetic markers present and correct
- Validate graph structure integrity
- Auto-fix capabilities for validation issues
- Batch processing for large validations

All operations respect the dual-graph architecture.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.services.base_scale_service import BaseScaleService
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class ScaleValidationService(BaseScaleService):
    """
    Service for validating synthetic data created during scale operations.

    This service provides comprehensive validation capabilities with support
    for auto-fixing common issues. It ensures that synthetic resources
    maintain the integrity of the dual-graph architecture.

    All operations:
    - Validate abstracted layer integrity
    - Check for contamination of Original layer
    - Verify relationship correctness
    - Support auto-fix for common issues
    - Provide detailed issue reporting
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        batch_size: int = 1000,
    ) -> None:
        """
        Initialize the scale validation service.

        Args:
            session_manager: Neo4j session manager for database operations
            batch_size: Number of resources to process per batch (default: 1000)
        """
        super().__init__(session_manager)
        self.batch_size = batch_size

    async def validate_graph(
        self,
        tenant_id: str,
        check_type: str = "all",
        auto_fix: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Validate graph integrity for a tenant's synthetic data.

        This method runs comprehensive validation checks on synthetic resources
        to ensure they maintain the integrity of the dual-graph architecture.

        Args:
            tenant_id: Azure tenant ID to validate
            check_type: Type of validation to run:
                - "all": Run all validation checks (default)
                - "original": Check for Original layer contamination
                - "scan_links": Check for invalid SCAN_SOURCE_NODE relationships
                - "markers": Check for missing/invalid synthetic markers
                - "structure": Check graph structure integrity
            auto_fix: If True, attempt to automatically fix issues (default: False)
            progress_callback: Optional callback(message, current, total)

        Returns:
            Dict[str, Any]: Validation results including:
                - success: Whether all validations passed
                - tenant_id: Azure tenant ID
                - check_type: Type of validation run
                - checks_run: List of check names executed
                - checks_passed: List of checks that passed
                - checks_failed: List of checks that failed
                - issues: List of validation issues found
                - auto_fix_applied: Whether auto-fix was run
                - fixes_applied: Number of fixes applied (if auto_fix=True)
                - duration_seconds: Validation duration

        Raises:
            ValueError: If tenant doesn't exist or check_type is invalid
            Exception: If validation fails

        Example:
            >>> result = await service.validate_graph(
            ...     tenant_id="abc123",
            ...     check_type="all",
            ...     auto_fix=False
            ... )
            >>> if not result['success']:
            ...     print(f"Found {len(result['issues'])} issues")
            ...     for issue in result['issues']:
            ...         print(f"  - {issue['type']}: {issue['message']}")
        """
        start_time = datetime.now()

        self.logger.info(
            f"Starting validation for tenant {tenant_id}: "
            f"check_type={check_type}, auto_fix={auto_fix}"
        )

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # Validate check_type
        valid_check_types = ["all", "original", "scan_links", "markers", "structure"]
        if check_type not in valid_check_types:
            raise ValueError(
                f"Invalid check_type: {check_type}. Must be one of: {valid_check_types}"
            )

        checks_run: List[str] = []
        checks_passed: List[str] = []
        checks_failed: List[str] = []
        issues: List[Dict[str, Any]] = []

        # Determine which checks to run
        run_all = check_type == "all"

        try:
            # Check 1: Original layer contamination
            if run_all or check_type == "original":
                if progress_callback:
                    progress_callback(
                        "Checking Original layer contamination...", 0, 100
                    )

                check_name = "original_contamination"
                checks_run.append(check_name)
                original_issues = await self._check_original_contamination(tenant_id)

                if original_issues:
                    checks_failed.append(check_name)
                    issues.extend(original_issues)
                else:
                    checks_passed.append(check_name)

            # Check 2: Invalid SCAN_SOURCE_NODE relationships
            if run_all or check_type == "scan_links":
                if progress_callback:
                    progress_callback("Checking SCAN_SOURCE_NODE links...", 25, 100)

                check_name = "scan_source_links"
                checks_run.append(check_name)
                scan_link_issues = await self._check_scan_source_links(tenant_id)

                if scan_link_issues:
                    checks_failed.append(check_name)
                    issues.extend(scan_link_issues)
                else:
                    checks_passed.append(check_name)

            # Check 3: Missing/invalid synthetic markers
            if run_all or check_type == "markers":
                if progress_callback:
                    progress_callback("Checking synthetic markers...", 50, 100)

                check_name = "synthetic_markers"
                checks_run.append(check_name)
                marker_issues = await self._check_synthetic_markers(tenant_id)

                if marker_issues:
                    checks_failed.append(check_name)
                    issues.extend(marker_issues)
                else:
                    checks_passed.append(check_name)

            # Check 4: Graph structure integrity
            if run_all or check_type == "structure":
                if progress_callback:
                    progress_callback("Checking graph structure...", 75, 100)

                check_name = "graph_structure"
                checks_run.append(check_name)
                structure_issues = await self._check_graph_structure(tenant_id)

                if structure_issues:
                    checks_failed.append(check_name)
                    issues.extend(structure_issues)
                else:
                    checks_passed.append(check_name)

            # Apply auto-fixes if requested
            fixes_applied = 0
            if auto_fix and issues:
                if progress_callback:
                    progress_callback("Applying auto-fixes...", 90, 100)

                fixes_applied = await self._apply_auto_fixes(tenant_id, issues)

            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "success": len(checks_failed) == 0,
                "tenant_id": tenant_id,
                "check_type": check_type,
                "checks_run": checks_run,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "issues": issues,
                "issue_count": len(issues),
                "auto_fix_applied": auto_fix,
                "fixes_applied": fixes_applied,
                "duration_seconds": duration,
            }

            if progress_callback:
                progress_callback("Validation complete!", 100, 100)

            if result["success"]:
                self.logger.info(
                    f"Validation PASSED: All {len(checks_run)} checks passed "
                    f"in {duration:.2f}s"
                )
            else:
                self.logger.warning(
                    f"Validation FAILED: {len(checks_failed)} of {len(checks_run)} "
                    f"checks failed, {len(issues)} issues found in {duration:.2f}s"
                )

            return result

        except (Neo4jError, ValueError, RuntimeError) as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Validation failed with error: {e}")

            return {
                "success": False,
                "tenant_id": tenant_id,
                "check_type": check_type,
                "checks_run": checks_run,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "issues": issues,
                "issue_count": len(issues),
                "auto_fix_applied": auto_fix,
                "fixes_applied": 0,
                "duration_seconds": duration,
                "error_message": str(e),
            }
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Unexpected error during validation: {e}")

            return {
                "success": False,
                "tenant_id": tenant_id,
                "check_type": check_type,
                "checks_run": checks_run,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "issues": issues,
                "issue_count": len(issues),
                "auto_fix_applied": auto_fix,
                "fixes_applied": 0,
                "duration_seconds": duration,
                "error_message": str(e),
            }

    async def fix_validation_issues(
        self,
        tenant_id: str,
        issues: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Manually fix validation issues.

        This method applies fixes to specific validation issues provided
        by a previous validate_graph() call.

        Args:
            tenant_id: Azure tenant ID
            issues: List of issues from validate_graph() to fix
            progress_callback: Optional callback(message, current, total)

        Returns:
            Dict[str, Any]: Fix results including:
                - success: Whether all fixes succeeded
                - tenant_id: Azure tenant ID
                - issues_provided: Number of issues provided
                - fixes_attempted: Number of fixes attempted
                - fixes_succeeded: Number of fixes that succeeded
                - fixes_failed: Number of fixes that failed
                - fix_details: List of fix results

        Raises:
            ValueError: If tenant doesn't exist or issues list is invalid
            Exception: If fixing fails

        Example:
            >>> validation_result = await service.validate_graph("abc123")
            >>> if validation_result['issues']:
            ...     fix_result = await service.fix_validation_issues(
            ...         "abc123",
            ...         validation_result['issues']
            ...     )
            ...     print(f"Fixed {fix_result['fixes_succeeded']} issues")
        """
        start_time = datetime.now()

        self.logger.info(
            f"Fixing {len(issues)} validation issues for tenant {tenant_id}"
        )

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        if not issues:
            raise ValueError("Issues list cannot be empty")

        fixes_attempted = 0
        fixes_succeeded = 0
        fixes_failed = 0
        fix_details: List[Dict[str, Any]] = []

        try:
            for i, issue in enumerate(issues):
                if progress_callback:
                    progress_callback(
                        f"Fixing issue {i + 1}/{len(issues)}...", i, len(issues)
                    )

                issue_type = issue.get("type", "unknown")
                fixes_attempted += 1

                try:
                    if issue_type == "missing_marker":
                        await self._fix_missing_marker(issue)
                        fixes_succeeded += 1
                        fix_details.append(
                            {
                                "issue": issue,
                                "success": True,
                                "message": "Marker added successfully",
                            }
                        )
                    elif issue_type == "invalid_scan_link":
                        await self._fix_invalid_scan_link(issue)
                        fixes_succeeded += 1
                        fix_details.append(
                            {
                                "issue": issue,
                                "success": True,
                                "message": "Invalid link removed",
                            }
                        )
                    elif issue_type == "original_contamination":
                        await self._fix_original_contamination(issue)
                        fixes_succeeded += 1
                        fix_details.append(
                            {
                                "issue": issue,
                                "success": True,
                                "message": "Original node removed",
                            }
                        )
                    else:
                        fixes_failed += 1
                        fix_details.append(
                            {
                                "issue": issue,
                                "success": False,
                                "message": f"Unknown issue type: {issue_type}",
                            }
                        )

                except (Neo4jError, ValueError, RuntimeError) as fix_error:
                    fixes_failed += 1
                    fix_details.append(
                        {
                            "issue": issue,
                            "success": False,
                            "message": f"Fix failed: {fix_error!s}",
                        }
                    )
                    self.logger.error(f"Failed to fix issue {issue}: {fix_error}")
                except Exception as unexpected_error:
                    fixes_failed += 1
                    fix_details.append(
                        {
                            "issue": issue,
                            "success": False,
                            "message": f"Unexpected error during fix: {unexpected_error!s}",
                        }
                    )
                    self.logger.exception(f"Unexpected error fixing issue {issue}: {unexpected_error}")

            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "success": fixes_failed == 0,
                "tenant_id": tenant_id,
                "issues_provided": len(issues),
                "fixes_attempted": fixes_attempted,
                "fixes_succeeded": fixes_succeeded,
                "fixes_failed": fixes_failed,
                "fix_details": fix_details,
                "duration_seconds": duration,
            }

            if progress_callback:
                progress_callback("Fixes complete!", len(issues), len(issues))

            self.logger.info(
                f"Fixing complete: {fixes_succeeded}/{fixes_attempted} succeeded "
                f"in {duration:.2f}s"
            )

            return result

        except (Neo4jError, ValueError, RuntimeError) as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Fixing failed: {e}")

            return {
                "success": False,
                "tenant_id": tenant_id,
                "issues_provided": len(issues),
                "fixes_attempted": fixes_attempted,
                "fixes_succeeded": fixes_succeeded,
                "fixes_failed": fixes_failed,
                "fix_details": fix_details,
                "duration_seconds": duration,
                "error_message": str(e),
            }
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Unexpected error during fixing: {e}")

            return {
                "success": False,
                "tenant_id": tenant_id,
                "issues_provided": len(issues),
                "fixes_attempted": fixes_attempted,
                "fixes_succeeded": fixes_succeeded,
                "fixes_failed": fixes_failed,
                "fix_details": fix_details,
                "duration_seconds": duration,
                "error_message": str(e),
            }

    # =========================================================================
    # Private Validation Methods
    # =========================================================================

    async def _check_original_contamination(
        self, tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Check for synthetic resources in Original layer."""
        query = """
        MATCH (r:Resource:Original)
        WHERE r.tenant_id = $tenant_id
          AND r.synthetic = true
        RETURN r.id as resource_id,
               r.type as resource_type,
               r.scale_operation_id as operation_id
        LIMIT 1000
        """

        issues: List[Dict[str, Any]] = []

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})

                for record in result:
                    issues.append(
                        {
                            "type": "original_contamination",
                            "severity": "critical",
                            "resource_id": record["resource_id"],
                            "resource_type": record["resource_type"],
                            "operation_id": record["operation_id"],
                            "message": (
                                f"Synthetic resource {record['resource_id']} found in "
                                f"Original layer. Synthetic resources must only exist "
                                f"in abstracted layer."
                            ),
                        }
                    )

            if issues:
                self.logger.warning(
                    f"Found {len(issues)} Original contamination issues"
                )

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to check Original contamination: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error checking Original contamination: {e}")
            raise

        return issues

    async def _check_scan_source_links(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Check for invalid SCAN_SOURCE_NODE relationships on synthetic resources."""
        query = """
        MATCH (r:Resource)-[rel:SCAN_SOURCE_NODE]->(orig:Resource:Original)
        WHERE r.tenant_id = $tenant_id
          AND r.synthetic = true
        RETURN r.id as resource_id,
               r.type as resource_type,
               r.scale_operation_id as operation_id,
               orig.id as original_id
        LIMIT 1000
        """

        issues: List[Dict[str, Any]] = []

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})

                for record in result:
                    issues.append(
                        {
                            "type": "invalid_scan_link",
                            "severity": "high",
                            "resource_id": record["resource_id"],
                            "resource_type": record["resource_type"],
                            "operation_id": record["operation_id"],
                            "original_id": record["original_id"],
                            "message": (
                                f"Synthetic resource {record['resource_id']} has "
                                f"SCAN_SOURCE_NODE link to {record['original_id']}. "
                                f"Synthetic resources should not link to Original layer."
                            ),
                        }
                    )

            if issues:
                self.logger.warning(
                    f"Found {len(issues)} invalid SCAN_SOURCE_NODE links"
                )

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to check SCAN_SOURCE_NODE links: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error checking SCAN_SOURCE_NODE links: {e}")
            raise

        return issues

    async def _check_synthetic_markers(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Check for missing or invalid synthetic markers."""
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND r.synthetic = true
        WITH r,
             CASE WHEN r.scale_operation_id IS NULL OR r.scale_operation_id = ''
                  THEN 'missing_operation_id' ELSE null END as missing_op,
             CASE WHEN r.generation_strategy IS NULL OR r.generation_strategy = ''
                  THEN 'missing_strategy' ELSE null END as missing_strategy,
             CASE WHEN r.generation_timestamp IS NULL OR r.generation_timestamp = ''
                  THEN 'missing_timestamp' ELSE null END as missing_timestamp
        WHERE missing_op IS NOT NULL OR missing_strategy IS NOT NULL OR missing_timestamp IS NOT NULL
        RETURN r.id as resource_id,
               r.type as resource_type,
               missing_op, missing_strategy, missing_timestamp
        LIMIT 1000
        """

        issues: List[Dict[str, Any]] = []

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})

                for record in result:
                    missing_markers = []
                    if record["missing_op"]:
                        missing_markers.append("scale_operation_id")
                    if record["missing_strategy"]:
                        missing_markers.append("generation_strategy")
                    if record["missing_timestamp"]:
                        missing_markers.append("generation_timestamp")

                    issues.append(
                        {
                            "type": "missing_marker",
                            "severity": "medium",
                            "resource_id": record["resource_id"],
                            "resource_type": record["resource_type"],
                            "missing_markers": missing_markers,
                            "message": (
                                f"Resource {record['resource_id']} is missing markers: "
                                f"{', '.join(missing_markers)}"
                            ),
                        }
                    )

            if issues:
                self.logger.warning(f"Found {len(issues)} marker issues")

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to check synthetic markers: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error checking synthetic markers: {e}")
            raise

        return issues

    async def _check_graph_structure(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Check graph structure integrity (orphaned nodes, cycles, etc)."""
        issues: List[Dict[str, Any]] = []

        # Check 1: Orphaned synthetic nodes (no incoming or outgoing relationships)
        orphan_query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND r.synthetic = true
        WHERE NOT (r)-[]-()
        RETURN r.id as resource_id,
               r.type as resource_type,
               r.scale_operation_id as operation_id
        LIMIT 100
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(orphan_query, {"tenant_id": tenant_id})

                for record in result:
                    issues.append(
                        {
                            "type": "orphaned_node",
                            "severity": "low",
                            "resource_id": record["resource_id"],
                            "resource_type": record["resource_type"],
                            "operation_id": record["operation_id"],
                            "message": (
                                f"Resource {record['resource_id']} is orphaned "
                                f"(no relationships). This may be intentional."
                            ),
                        }
                    )

            if issues:
                self.logger.info(f"Found {len(issues)} orphaned nodes (low severity)")

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to check graph structure: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error checking graph structure: {e}")
            raise

        return issues

    # =========================================================================
    # Private Fix Methods
    # =========================================================================

    async def _apply_auto_fixes(
        self, tenant_id: str, issues: List[Dict[str, Any]]
    ) -> int:
        """Apply automatic fixes to issues that can be safely resolved."""
        fixes_applied = 0

        for issue in issues:
            issue_type = issue.get("type")

            try:
                # Only auto-fix safe issue types
                if issue_type == "invalid_scan_link":
                    await self._fix_invalid_scan_link(issue)
                    fixes_applied += 1
                elif issue_type == "original_contamination":
                    # Critical issue - log but don't auto-fix without explicit confirmation
                    self.logger.warning(
                        f"Original contamination detected but not auto-fixed: {issue}"
                    )
            except (Neo4jError, ValueError, RuntimeError) as e:
                self.logger.error(f"Auto-fix failed for issue {issue}: {e}")
            except Exception as e:
                self.logger.exception(f"Unexpected error during auto-fix for issue {issue}: {e}")
                # Don't raise here - continue with other fixes

        return fixes_applied

    async def _fix_missing_marker(self, issue: Dict[str, Any]) -> None:
        """Fix missing synthetic markers by adding them."""
        resource_id = issue["resource_id"]
        missing_markers = issue.get("missing_markers", [])

        # Build SET clause for missing markers
        set_clauses = []
        params = {"resource_id": resource_id}

        if "scale_operation_id" in missing_markers:
            set_clauses.append("r.scale_operation_id = $operation_id")
            params["operation_id"] = "unknown-operation"

        if "generation_strategy" in missing_markers:
            set_clauses.append("r.generation_strategy = $strategy")
            params["strategy"] = "unknown"

        if "generation_timestamp" in missing_markers:
            set_clauses.append("r.generation_timestamp = $timestamp")
            params["timestamp"] = datetime.now().isoformat()

        if not set_clauses:
            return

        query = f"""
        MATCH (r:Resource {{id: $resource_id}})
        WHERE NOT r:Original
        SET {", ".join(set_clauses)}
        """

        with self.session_manager.session() as session:
            session.run(query, params)

        self.logger.info(f"Fixed missing markers for resource {resource_id}")

    async def _fix_invalid_scan_link(self, issue: Dict[str, Any]) -> None:
        """Fix invalid SCAN_SOURCE_NODE relationship by removing it."""
        resource_id = issue["resource_id"]

        query = """
        MATCH (r:Resource {id: $resource_id})-[rel:SCAN_SOURCE_NODE]->()
        WHERE NOT r:Original
        DELETE rel
        """

        with self.session_manager.session() as session:
            session.run(query, {"resource_id": resource_id})

        self.logger.info(f"Removed invalid SCAN_SOURCE_NODE link from {resource_id}")

    async def _fix_original_contamination(self, issue: Dict[str, Any]) -> None:
        """Fix Original contamination by removing synthetic resource from Original layer."""
        resource_id = issue["resource_id"]

        # Remove :Original label and SCAN_SOURCE_NODE relationships
        query = """
        MATCH (r:Resource:Original {id: $resource_id})
        OPTIONAL MATCH (r)-[rel:SCAN_SOURCE_NODE]->()
        DELETE rel
        REMOVE r:Original
        """

        with self.session_manager.session() as session:
            session.run(query, {"resource_id": resource_id})

        self.logger.info(
            f"Removed Original label from synthetic resource {resource_id}"
        )
