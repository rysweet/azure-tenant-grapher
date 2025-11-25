"""Tests for Scale Validation Utilities.

This test suite validates the scale operation validation utilities that
ensure proper dual-graph architecture integrity.
"""

from unittest.mock import MagicMock

import pytest

from src.services.scale_validation import ScaleValidation


class TestScaleValidation:
    """Test suite for ScaleValidation utilities."""

    @pytest.fixture
    def mock_session(self):
        """Provide a mock Neo4j session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_check_no_original_contamination_pass(self, mock_session):
        """Test validation passes when no Original nodes exist."""
        # Mock query result: no contaminated nodes
        result_mock = MagicMock()
        record_mock = {"contaminated_count": 0}
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_no_original_contamination(
            mock_session, operation_id
        )

        assert is_valid is True
        assert "passed" in message.lower()
        assert "no original layer contamination" in message.lower()

        # Verify query
        mock_session.run.assert_called_once()
        call_args, call_kwargs = mock_session.run.call_args
        assert "MATCH (r:Resource:Original)" in call_args[0]
        # Parameters are passed as keyword arguments in the second parameter (a dict)
        assert call_args[1]["operation_id"] == operation_id

    @pytest.mark.asyncio
    async def test_check_no_original_contamination_fail(self, mock_session):
        """Test validation fails when Original nodes found."""
        # Mock query result: contaminated nodes found
        result_mock = MagicMock()
        record_mock = {"contaminated_count": 5}
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_no_original_contamination(
            mock_session, operation_id
        )

        assert is_valid is False
        assert "failed" in message.lower()
        assert "5" in message
        assert "original layer" in message.lower()

    @pytest.mark.asyncio
    async def test_check_no_scan_source_links_pass(self, mock_session):
        """Test validation passes when no SCAN_SOURCE_NODE links exist."""
        # Mock query result: no invalid links
        result_mock = MagicMock()
        record_mock = {"invalid_links": 0}
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_no_scan_source_links(
            mock_session, operation_id
        )

        assert is_valid is True
        assert "passed" in message.lower()
        assert "no scan_source_node relationships" in message.lower()

        # Verify query
        mock_session.run.assert_called_once()
        call_args, call_kwargs = mock_session.run.call_args
        assert "MATCH (r:Resource)-[rel:SCAN_SOURCE_NODE]->" in call_args[0]
        # Parameters are passed as keyword arguments in the second parameter (a dict)
        assert call_args[1]["operation_id"] == operation_id

    @pytest.mark.asyncio
    async def test_check_no_scan_source_links_fail(self, mock_session):
        """Test validation fails when SCAN_SOURCE_NODE links found."""
        # Mock query result: invalid links found
        result_mock = MagicMock()
        record_mock = {"invalid_links": 3}
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_no_scan_source_links(
            mock_session, operation_id
        )

        assert is_valid is False
        assert "failed" in message.lower()
        assert "3" in message
        assert "scan_source_node" in message.lower()

    @pytest.mark.asyncio
    async def test_check_synthetic_markers_pass(self, mock_session):
        """Test validation passes when all markers are present."""
        # Mock query result: all markers present
        result_mock = MagicMock()
        record_mock = {
            "total_resources": 50,
            "missing_synthetic_count": 0,
            "missing_operation_id_count": 0,
            "missing_strategy_count": 0,
            "missing_timestamp_count": 0,
        }
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_synthetic_markers(
            mock_session, operation_id
        )

        assert is_valid is True
        assert "passed" in message.lower()
        assert "50" in message
        assert "required markers" in message.lower()

    @pytest.mark.asyncio
    async def test_check_synthetic_markers_fail_synthetic(self, mock_session):
        """Test validation fails when synthetic marker missing."""
        # Mock query result: missing synthetic marker
        result_mock = MagicMock()
        record_mock = {
            "total_resources": 50,
            "missing_synthetic_count": 5,
            "missing_operation_id_count": 0,
            "missing_strategy_count": 0,
            "missing_timestamp_count": 0,
        }
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_synthetic_markers(
            mock_session, operation_id
        )

        assert is_valid is False
        assert "failed" in message.lower()
        assert "5 missing 'synthetic' marker" in message

    @pytest.mark.asyncio
    async def test_check_synthetic_markers_fail_multiple(self, mock_session):
        """Test validation fails when multiple markers missing."""
        # Mock query result: multiple missing markers
        result_mock = MagicMock()
        record_mock = {
            "total_resources": 50,
            "missing_synthetic_count": 5,
            "missing_operation_id_count": 3,
            "missing_strategy_count": 7,
            "missing_timestamp_count": 2,
        }
        result_mock.single.return_value = record_mock
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_synthetic_markers(
            mock_session, operation_id
        )

        assert is_valid is False
        assert "failed" in message.lower()
        assert "5 missing 'synthetic' marker" in message
        assert "3 missing 'scale_operation_id' marker" in message
        assert "7 missing 'generation_strategy' marker" in message
        assert "2 missing 'generation_timestamp' marker" in message

    @pytest.mark.asyncio
    async def test_check_synthetic_markers_no_resources(self, mock_session):
        """Test validation warning when no resources found."""
        # Mock query result: no resources
        result_mock = MagicMock()
        result_mock.single.return_value = None
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.check_synthetic_markers(
            mock_session, operation_id
        )

        assert is_valid is True  # No resources is valid (warning case)
        assert "warning" in message.lower()
        assert "no resources found" in message.lower()

    @pytest.mark.asyncio
    async def test_validate_operation_all_pass(self, mock_session):
        """Test complete validation when all checks pass."""
        # Mock all checks to pass
        result_mock = MagicMock()
        result_mock.single.return_value = {
            "contaminated_count": 0,
            "invalid_links": 0,
            "total_resources": 50,
            "missing_synthetic_count": 0,
            "missing_operation_id_count": 0,
            "missing_strategy_count": 0,
            "missing_timestamp_count": 0,
        }
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.validate_operation(
            mock_session, operation_id
        )

        assert is_valid is True
        assert "all validations passed" in message.lower()

        # Should have run 3 queries (one for each check)
        assert mock_session.run.call_count == 3

    @pytest.mark.asyncio
    async def test_validate_operation_some_fail(self, mock_session):
        """Test complete validation when some checks fail."""
        # Mock checks: contamination fails, others pass
        call_count = 0

        def mock_run_side_effect(query, params):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            if "Resource:Original" in query:
                # Contamination check fails
                result.single.return_value = {"contaminated_count": 5}
            elif "SCAN_SOURCE_NODE" in query:
                # No SCAN_SOURCE_NODE links
                result.single.return_value = {"invalid_links": 0}
            else:
                # All markers present
                result.single.return_value = {
                    "total_resources": 50,
                    "missing_synthetic_count": 0,
                    "missing_operation_id_count": 0,
                    "missing_strategy_count": 0,
                    "missing_timestamp_count": 0,
                }

            return result

        mock_session.run.side_effect = mock_run_side_effect

        operation_id = "scale-20250110T123045-a1b2c3d4"
        is_valid, message = await ScaleValidation.validate_operation(
            mock_session, operation_id
        )

        assert is_valid is False
        assert "some validations failed" in message.lower()
        assert "5" in message  # Contamination count

    @pytest.mark.asyncio
    async def test_validation_queries_exclude_original_layer(self, mock_session):
        """Test that validation queries properly filter by Original layer."""
        result_mock = MagicMock()
        result_mock.single.return_value = {"contaminated_count": 0}
        mock_session.run.return_value = result_mock

        operation_id = "scale-20250110T123045-a1b2c3d4"

        # Check contamination query
        await ScaleValidation.check_no_original_contamination(
            mock_session, operation_id
        )
        call_args = mock_session.run.call_args[0][0]
        assert ":Original" in call_args

        # Check SCAN_SOURCE_NODE query
        await ScaleValidation.check_no_scan_source_links(mock_session, operation_id)
        call_args = mock_session.run.call_args[0][0]
        assert ":Original" in call_args  # Target of relationship

        # Check synthetic markers query
        result_mock.single.return_value = {
            "total_resources": 0,
            "missing_synthetic_count": 0,
            "missing_operation_id_count": 0,
            "missing_strategy_count": 0,
            "missing_timestamp_count": 0,
        }
        await ScaleValidation.check_synthetic_markers(mock_session, operation_id)
        call_args = mock_session.run.call_args[0][0]
        assert "NOT r:Original" in call_args

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, mock_session):
        """Test validation handles database errors gracefully."""
        # Mock query to raise exception
        mock_session.run.side_effect = Exception("Database connection error")

        operation_id = "scale-20250110T123045-a1b2c3d4"

        # Each validation should handle errors and return False
        is_valid, message = await ScaleValidation.check_no_original_contamination(
            mock_session, operation_id
        )
        assert is_valid is False
        assert "validation error" in message.lower()

        is_valid, message = await ScaleValidation.check_no_scan_source_links(
            mock_session, operation_id
        )
        assert is_valid is False
        assert "validation error" in message.lower()

        is_valid, message = await ScaleValidation.check_synthetic_markers(
            mock_session, operation_id
        )
        assert is_valid is False
        assert "validation error" in message.lower()
