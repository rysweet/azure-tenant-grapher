"""
Scale Validation Utilities

This module provides validation utilities for scale operations to ensure:
1. No contamination of the Original layer (:Resource:Original nodes)
2. No SCAN_SOURCE_NODE relationships for synthetic data
3. Proper synthetic markers on all synthetic resources
4. Data integrity during scale operations

All validations operate ONLY on the abstracted graph layer.
"""

import logging
from typing import Any, Tuple

from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class ScaleValidation:
    """
    Validation utilities for scale operations.

    These validators ensure that scale operations maintain the integrity
    of the dual-graph architecture by verifying that synthetic resources
    exist only in the abstracted layer and are properly marked.
    """

    @staticmethod
    async def check_no_original_contamination(
        session: Any, operation_id: str
    ) -> Tuple[bool, str]:
        """
        Verify no :Original nodes were created during a scale operation.

        This is a critical validation - synthetic resources should NEVER
        exist in the Original layer as they have no Azure counterpart.

        Args:
            session: Neo4j session for database queries
            operation_id: Scale operation ID to validate

        Returns:
            Tuple[bool, str]: (is_valid, message)
                - is_valid: True if no Original nodes found, False otherwise
                - message: Human-readable validation result

        Example:
            >>> is_valid, msg = await ScaleValidation.check_no_original_contamination(
            ...     session, "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(msg)
            'Validation passed: No Original layer contamination detected'
        """
        query = """
        MATCH (r:Resource:Original)
        WHERE r.scale_operation_id = $operation_id
        RETURN count(r) as contaminated_count
        """

        try:
            result = session.run(query, {"operation_id": operation_id})
            record = result.single()
            contaminated_count = record["contaminated_count"] if record else 0

            if contaminated_count > 0:
                message = (
                    f"Validation FAILED: Found {contaminated_count} synthetic resources "
                    f"in Original layer for operation {operation_id}. "
                    f"Synthetic resources must only exist in abstracted layer."
                )
                logger.error(message)
                return False, message

            message = (
                f"Validation passed: No Original layer contamination detected "
                f"for operation {operation_id}"
            )
            logger.info(message)
            return True, message

        except (Neo4jError, ValueError) as e:
            message = (
                f"Validation error: Failed to check Original layer contamination: {e}"
            )
            logger.exception(message)
            return False, message
        except Exception as e:
            message = (
                f"Unexpected error checking Original layer contamination: {e}"
            )
            logger.exception(message)
            return False, f"Validation error: {e}"

    @staticmethod
    async def check_no_scan_source_links(
        session: Any, operation_id: str
    ) -> Tuple[bool, str]:
        """
        Verify no SCAN_SOURCE_NODE relationships exist for synthetic data.

        SCAN_SOURCE_NODE relationships link abstracted nodes to their
        Original counterparts. Synthetic resources have no Original
        counterparts, so these relationships must not exist.

        Args:
            session: Neo4j session for database queries
            operation_id: Scale operation ID to validate

        Returns:
            Tuple[bool, str]: (is_valid, message)
                - is_valid: True if no SCAN_SOURCE_NODE links found, False otherwise
                - message: Human-readable validation result

        Example:
            >>> is_valid, msg = await ScaleValidation.check_no_scan_source_links(
            ...     session, "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(msg)
            'Validation passed: No SCAN_SOURCE_NODE relationships found'
        """
        query = """
        MATCH (r:Resource)-[rel:SCAN_SOURCE_NODE]->(orig:Resource:Original)
        WHERE r.scale_operation_id = $operation_id
        RETURN count(rel) as invalid_links
        """

        try:
            result = session.run(query, {"operation_id": operation_id})
            record = result.single()
            invalid_links = record["invalid_links"] if record else 0

            if invalid_links > 0:
                message = (
                    f"Validation FAILED: Found {invalid_links} SCAN_SOURCE_NODE relationships "
                    f"for synthetic resources in operation {operation_id}. "
                    f"Synthetic resources must not link to Original layer."
                )
                logger.error(message)
                return False, message

            message = (
                f"Validation passed: No SCAN_SOURCE_NODE relationships found "
                f"for operation {operation_id}"
            )
            logger.info(message)
            return True, message

        except (Neo4jError, ValueError) as e:
            message = f"Validation error: Failed to check SCAN_SOURCE_NODE links: {e}"
            logger.exception(message)
            return False, message
        except Exception as e:
            message = f"Unexpected error checking SCAN_SOURCE_NODE links: {e}"
            logger.exception(message)
            return False, f"Validation error: {e}"

    @staticmethod
    async def check_synthetic_markers(
        session: Any, operation_id: str
    ) -> Tuple[bool, str]:
        """
        Verify all synthetic nodes have required markers.

        Required markers:
        - synthetic: true
        - scale_operation_id: matches operation_id
        - generation_strategy: non-empty string
        - generation_timestamp: ISO 8601 timestamp

        Args:
            session: Neo4j session for database queries
            operation_id: Scale operation ID to validate

        Returns:
            Tuple[bool, str]: (is_valid, message)
                - is_valid: True if all markers are valid, False otherwise
                - message: Human-readable validation result

        Example:
            >>> is_valid, msg = await ScaleValidation.check_synthetic_markers(
            ...     session, "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(msg)
            'Validation passed: All 50 synthetic resources have required markers'
        """
        # Query to find resources with the operation_id but missing markers
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.scale_operation_id = $operation_id
        WITH r,
             CASE WHEN r.synthetic IS NULL OR r.synthetic <> true THEN 1 ELSE 0 END as missing_synthetic,
             CASE WHEN r.scale_operation_id IS NULL OR r.scale_operation_id = '' THEN 1 ELSE 0 END as missing_operation_id,
             CASE WHEN r.generation_strategy IS NULL OR r.generation_strategy = '' THEN 1 ELSE 0 END as missing_strategy,
             CASE WHEN r.generation_timestamp IS NULL OR r.generation_timestamp = '' THEN 1 ELSE 0 END as missing_timestamp
        RETURN
            count(r) as total_resources,
            sum(missing_synthetic) as missing_synthetic_count,
            sum(missing_operation_id) as missing_operation_id_count,
            sum(missing_strategy) as missing_strategy_count,
            sum(missing_timestamp) as missing_timestamp_count
        """

        try:
            result = session.run(query, {"operation_id": operation_id})
            record = result.single()

            if not record:
                message = f"Validation warning: No resources found for operation {operation_id}"
                logger.warning(message)
                return True, message

            total_resources = record["total_resources"]
            missing_synthetic = record["missing_synthetic_count"]
            missing_operation_id = record["missing_operation_id_count"]
            missing_strategy = record["missing_strategy_count"]
            missing_timestamp = record["missing_timestamp_count"]

            errors = []
            if missing_synthetic > 0:
                errors.append(f"{missing_synthetic} missing 'synthetic' marker")
            if missing_operation_id > 0:
                errors.append(
                    f"{missing_operation_id} missing 'scale_operation_id' marker"
                )
            if missing_strategy > 0:
                errors.append(
                    f"{missing_strategy} missing 'generation_strategy' marker"
                )
            if missing_timestamp > 0:
                errors.append(
                    f"{missing_timestamp} missing 'generation_timestamp' marker"
                )

            if errors:
                message = (
                    f"Validation FAILED for operation {operation_id}: "
                    f"{', '.join(errors)} out of {total_resources} resources. "
                    f"All synthetic resources must have: synthetic=true, "
                    f"scale_operation_id, generation_strategy, generation_timestamp."
                )
                logger.error(message)
                return False, message

            message = (
                f"Validation passed: All {total_resources} synthetic resources "
                f"have required markers for operation {operation_id}"
            )
            logger.info(message)
            return True, message

        except (Neo4jError, ValueError) as e:
            message = f"Validation error: Failed to check synthetic markers: {e}"
            logger.exception(message)
            return False, message
        except Exception as e:
            message = f"Unexpected error checking synthetic markers: {e}"
            logger.exception(message)
            return False, f"Validation error: {e}"

    @staticmethod
    async def validate_operation(session: Any, operation_id: str) -> Tuple[bool, str]:
        """
        Run all validations for a scale operation.

        This is a convenience method that runs all validation checks
        and returns a combined result.

        Args:
            session: Neo4j session for database queries
            operation_id: Scale operation ID to validate

        Returns:
            Tuple[bool, str]: (is_valid, message)
                - is_valid: True if all validations pass, False otherwise
                - message: Combined validation results

        Example:
            >>> is_valid, msg = await ScaleValidation.validate_operation(
            ...     session, "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> if is_valid:
            ...     print("All validations passed!")
            ... else:
            ...     print(f"Validation failures: {msg}")
        """
        logger.info(f"Running all validations for operation {operation_id}")

        results = []

        # Check 1: No Original contamination
        is_valid_1, msg_1 = await ScaleValidation.check_no_original_contamination(
            session, operation_id
        )
        results.append((is_valid_1, msg_1))

        # Check 2: No SCAN_SOURCE_NODE links
        is_valid_2, msg_2 = await ScaleValidation.check_no_scan_source_links(
            session, operation_id
        )
        results.append((is_valid_2, msg_2))

        # Check 3: Synthetic markers
        is_valid_3, msg_3 = await ScaleValidation.check_synthetic_markers(
            session, operation_id
        )
        results.append((is_valid_3, msg_3))

        # Combine results
        all_valid = all(is_valid for is_valid, _ in results)
        messages = [msg for _, msg in results]
        combined_message = "\n".join(messages)

        if all_valid:
            final_message = (
                f"All validations PASSED for operation {operation_id}\n"
                f"{combined_message}"
            )
            logger.info(final_message)
        else:
            final_message = (
                f"Some validations FAILED for operation {operation_id}\n"
                f"{combined_message}"
            )
            logger.error(final_message)

        return all_valid, final_message
