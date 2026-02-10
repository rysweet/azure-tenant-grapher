"""
Unit tests for PR #902 Bug #2 and #4: Session Manager Connection Fixes.

Bug #2: Changed from `async with Neo4jSessionManager(...)` to regular instantiation
Bug #4: Added `session_manager.connect()` call before use

This module provides focused unit tests for the session manager usage pattern fixes.

Testing pyramid distribution: 60% unit tests
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestSessionManagerInstantiationPattern:
    """Test Bug #2: Session manager instantiation pattern (not async context manager)."""

    @pytest.mark.asyncio
    async def test_session_manager_instantiated_not_async_with(self):
        """Verify Neo4jSessionManager is instantiated, not used with 'async with'."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        with patch("src.commands.fidelity.Neo4jConfig"):
                            # Create mock session manager instance
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock()
                            MockSessionManager.return_value = mock_session_manager

                            # Create mock calculator
                            from src.validation.resource_fidelity_calculator import (
                                FidelityResult,
                                ResourceFidelityMetrics,
                            )

                            mock_calculator = Mock()
                            mock_result = FidelityResult(
                                classifications=[],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=0,
                                    exact_match=0,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=0.0,
                                ),
                            )
                            mock_calculator.calculate_fidelity.return_value = mock_result
                            MockCalculator.return_value = mock_calculator

                            from src.commands.fidelity import fidelity_resource_level_handler

                            # Execute handler
                            await fidelity_resource_level_handler(
                                source_subscription="source-123",
                                target_subscription="target-123",
                                no_container=True,
                            )

                            # Verify instantiation was called (not async with)
                            MockSessionManager.assert_called_once()

                            # Verify it was NOT used as context manager
                            # (if it were, __aenter__ would be called)
                            assert not hasattr(mock_session_manager, "__aenter__") or \
                                   not mock_session_manager.__aenter__.called, \
                                "Session manager should not be used as async context manager (Bug #2)"

    @pytest.mark.asyncio
    async def test_session_manager_created_with_neo4j_config(self):
        """Verify session manager is created with proper Neo4j config."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("neo4j://localhost", "neo4j", "password")):
                        with patch("src.commands.fidelity.Neo4jConfig") as MockConfig:
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock()
                            MockSessionManager.return_value = mock_session_manager

                            from src.validation.resource_fidelity_calculator import (
                                FidelityResult,
                                ResourceFidelityMetrics,
                            )

                            mock_calculator = Mock()
                            mock_result = FidelityResult(
                                classifications=[],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=0,
                                    exact_match=0,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=0.0,
                                ),
                            )
                            mock_calculator.calculate_fidelity.return_value = mock_result
                            MockCalculator.return_value = mock_calculator

                            from src.commands.fidelity import fidelity_resource_level_handler

                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                            # Verify Neo4jConfig was created
                            MockConfig.assert_called_once()
                            call_kwargs = MockConfig.call_args[1]
                            assert call_kwargs["uri"] == "neo4j://localhost"
                            assert call_kwargs["user"] == "neo4j"
                            assert call_kwargs["password"] == "password"


class TestSessionManagerConnectionCall:
    """Test Bug #4: session_manager.connect() is called before use."""

    @pytest.mark.asyncio
    async def test_connect_called_on_session_manager(self):
        """Verify session_manager.connect() is called."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        with patch("src.commands.fidelity.Neo4jConfig"):
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock()
                            MockSessionManager.return_value = mock_session_manager

                            from src.validation.resource_fidelity_calculator import (
                                FidelityResult,
                                ResourceFidelityMetrics,
                            )

                            mock_calculator = Mock()
                            mock_result = FidelityResult(
                                classifications=[],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=0,
                                    exact_match=0,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=0.0,
                                ),
                            )
                            mock_calculator.calculate_fidelity.return_value = mock_result
                            MockCalculator.return_value = mock_calculator

                            from src.commands.fidelity import fidelity_resource_level_handler

                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                            # Verify connect() was called (Bug #4 fix)
                            mock_session_manager.connect.assert_called_once(), \
                                "session_manager.connect() must be called before use (Bug #4)"

    @pytest.mark.asyncio
    async def test_connect_called_before_calculator_creation(self):
        """Verify connect() is called BEFORE calculator is created."""
        call_order = []

        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        with patch("src.commands.fidelity.Neo4jConfig"):
                            # Track call order
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock(side_effect=lambda: call_order.append("connect"))
                            MockSessionManager.return_value = mock_session_manager

                            def mock_calculator_constructor(*args, **kwargs):
                                call_order.append("calculator_init")
                                from src.validation.resource_fidelity_calculator import (
                                    FidelityResult,
                                    ResourceFidelityMetrics,
                                )

                                mock_calc = Mock()
                                mock_result = FidelityResult(
                                    classifications=[],
                                    metrics=ResourceFidelityMetrics(
                                        total_resources=0,
                                        exact_match=0,
                                        drifted=0,
                                        missing_target=0,
                                        missing_source=0,
                                        match_percentage=0.0,
                                    ),
                                )
                                mock_calc.calculate_fidelity.return_value = mock_result
                                return mock_calc

                            MockCalculator.side_effect = mock_calculator_constructor

                            from src.commands.fidelity import fidelity_resource_level_handler

                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                            # Verify order: connect() before calculator creation
                            assert call_order == ["connect", "calculator_init"], \
                                f"connect() must be called before calculator creation. Got: {call_order}"

    @pytest.mark.asyncio
    async def test_connect_called_only_once(self):
        """Verify connect() is called exactly once, not multiple times."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        with patch("src.commands.fidelity.Neo4jConfig"):
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock()
                            MockSessionManager.return_value = mock_session_manager

                            from src.validation.resource_fidelity_calculator import (
                                FidelityResult,
                                ResourceFidelityMetrics,
                            )

                            mock_calculator = Mock()
                            mock_result = FidelityResult(
                                classifications=[],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=0,
                                    exact_match=0,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=0.0,
                                ),
                            )
                            mock_calculator.calculate_fidelity.return_value = mock_result
                            MockCalculator.return_value = mock_calculator

                            from src.commands.fidelity import fidelity_resource_level_handler

                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                            # Verify connect() called exactly once
                            assert mock_session_manager.connect.call_count == 1, \
                                "connect() should be called exactly once"


class TestConnectionErrorHandling:
    """Test error handling when session manager connection fails."""

    @pytest.mark.asyncio
    async def test_connection_failure_raises_exception(self):
        """Verify connection failure raises exception."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                    with patch("src.commands.fidelity.Neo4jConfig"):
                        mock_session_manager = Mock()
                        # Simulate connection failure
                        mock_session_manager.connect = Mock(side_effect=Exception("Connection refused"))
                        MockSessionManager.return_value = mock_session_manager

                        from src.commands.fidelity import fidelity_resource_level_handler

                        # Should raise exception on connection failure
                        with pytest.raises(Exception) as exc_info:
                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                        assert "Connection refused" in str(exc_info.value) or \
                               "connection" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connection_timeout_handled(self):
        """Verify connection timeout is handled gracefully."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                    with patch("src.commands.fidelity.Neo4jConfig"):
                        mock_session_manager = Mock()
                        mock_session_manager.connect = Mock(side_effect=TimeoutError("Connection timeout"))
                        MockSessionManager.return_value = mock_session_manager

                        from src.commands.fidelity import fidelity_resource_level_handler

                        with pytest.raises((Exception, TimeoutError)):
                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

    @pytest.mark.asyncio
    async def test_authentication_failure_handled(self):
        """Verify authentication failure is handled gracefully."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "wrongpass")):
                    with patch("src.commands.fidelity.Neo4jConfig"):
                        mock_session_manager = Mock()
                        mock_session_manager.connect = Mock(side_effect=Exception("Authentication failed"))
                        MockSessionManager.return_value = mock_session_manager

                        from src.commands.fidelity import fidelity_resource_level_handler

                        with pytest.raises(Exception) as exc_info:
                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                        assert "Authentication" in str(exc_info.value) or \
                               "auth" in str(exc_info.value).lower()


class TestSessionManagerPassedToCalculator:
    """Test that connected session manager is passed to calculator."""

    @pytest.mark.asyncio
    async def test_session_manager_passed_to_calculator(self):
        """Verify connected session manager is passed to ResourceFidelityCalculator."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        with patch("src.commands.fidelity.Neo4jConfig"):
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock()
                            MockSessionManager.return_value = mock_session_manager

                            from src.validation.resource_fidelity_calculator import (
                                FidelityResult,
                                ResourceFidelityMetrics,
                            )

                            mock_calculator = Mock()
                            mock_result = FidelityResult(
                                classifications=[],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=0,
                                    exact_match=0,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=0.0,
                                ),
                            )
                            mock_calculator.calculate_fidelity.return_value = mock_result
                            MockCalculator.return_value = mock_calculator

                            from src.commands.fidelity import fidelity_resource_level_handler

                            await fidelity_resource_level_handler(
                                source_subscription="source",
                                target_subscription="target",
                                no_container=True,
                            )

                            # Verify calculator was created with session_manager
                            MockCalculator.assert_called_once()
                            call_kwargs = MockCalculator.call_args[1]
                            assert "session_manager" in call_kwargs, \
                                "Calculator must receive session_manager parameter"
                            assert call_kwargs["session_manager"] is mock_session_manager, \
                                "Calculator must receive the connected session manager instance"


class TestRegressionPreventionSessionManager:
    """Regression tests to ensure session manager fixes persist."""

    def test_no_async_with_pattern_in_fidelity_handler(self):
        """Ensure 'async with Neo4jSessionManager' pattern is not used."""
        from src.commands import fidelity
        import inspect

        source = inspect.getsource(fidelity.fidelity_resource_level_handler)

        # Check for problematic pattern
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "async with" in line and "Neo4jSessionManager" in line:
                pytest.fail(
                    f"Line {i+1} uses 'async with Neo4jSessionManager' pattern (Bug #2 regression)\n"
                    f"Line: {line.strip()}\n"
                    f"Use regular instantiation + .connect() instead"
                )

    def test_connect_call_present_in_handler(self):
        """Ensure session_manager.connect() call is present in handler."""
        from src.commands import fidelity
        import inspect

        source = inspect.getsource(fidelity.fidelity_resource_level_handler)

        # Check for connect() call
        assert ".connect()" in source, \
            "fidelity_resource_level_handler must call session_manager.connect() (Bug #4)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
