"""
Tests for fidelity_calculator module.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.fidelity_calculator import FidelityCalculator, FidelityMetrics


class TestFidelityMetrics:
    """Test cases for FidelityMetrics class."""

    def test_metrics_initialization(self) -> None:
        """Test FidelityMetrics initialization."""
        metrics = FidelityMetrics(
            timestamp="2025-10-17T01:30:00Z",
            source_subscription_id="source-sub-id",
            target_subscription_id="target-sub-id",
            source_resources=1000,
            target_resources=800,
            source_relationships=3000,
            target_relationships=2400,
            source_resource_groups=50,
            target_resource_groups=40,
            source_resource_types=25,
            target_resource_types=20,
            overall_fidelity=80.0,
            fidelity_by_type={"Microsoft.Compute/virtualMachines": 85.0},
            missing_resources=200,
            objective_met=False,
            target_fidelity=95.0,
        )

        assert metrics.timestamp == "2025-10-17T01:30:00Z"
        assert metrics.source_subscription_id == "source-sub-id"
        assert metrics.target_subscription_id == "target-sub-id"
        assert metrics.source_resources == 1000
        assert metrics.target_resources == 800
        assert metrics.overall_fidelity == 80.0
        assert metrics.objective_met is False

    def test_metrics_to_dict(self) -> None:
        """Test FidelityMetrics to_dict conversion."""
        metrics = FidelityMetrics(
            timestamp="2025-10-17T01:30:00Z",
            source_subscription_id="source-sub-id",
            target_subscription_id="target-sub-id",
            source_resources=1000,
            target_resources=800,
            source_relationships=3000,
            target_relationships=2400,
            source_resource_groups=50,
            target_resource_groups=40,
            source_resource_types=25,
            target_resource_types=20,
            overall_fidelity=80.5,
            fidelity_by_type={"Microsoft.Compute/virtualMachines": 85.2},
            missing_resources=200,
            objective_met=False,
            target_fidelity=95.0,
        )

        result = metrics.to_dict()

        assert result["timestamp"] == "2025-10-17T01:30:00Z"
        assert result["source"]["subscription_id"] == "source-sub-id"
        assert result["source"]["resources"] == 1000
        assert result["target"]["subscription_id"] == "target-sub-id"
        assert result["target"]["resources"] == 800
        assert result["fidelity"]["overall"] == 80.5
        assert (
            result["fidelity"]["by_type"]["Microsoft.Compute/virtualMachines"] == 85.2
        )
        assert result["fidelity"]["missing_resources"] == 200
        assert result["fidelity"]["objective_met"] is False
        assert result["fidelity"]["target_fidelity"] == 95.0


class TestFidelityCalculator:
    """Test cases for FidelityCalculator class."""

    def test_initialization(self) -> None:
        """Test FidelityCalculator initialization."""
        with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )
            assert calculator.neo4j_uri == "bolt://localhost:7687"
            assert calculator.neo4j_user == "neo4j"
            assert calculator.neo4j_password == "password"
            mock_driver.assert_called_once_with(
                "bolt://localhost:7687", auth=("neo4j", "password")
            )

    def test_close(self) -> None:
        """Test FidelityCalculator close method."""
        with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
            mock_driver_instance = Mock()
            mock_driver.return_value = mock_driver_instance

            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )
            calculator.close()

            mock_driver_instance.close.assert_called_once()

    def test_calculate_fidelity_success(self) -> None:
        """Test successful fidelity calculation."""
        with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
            # Setup mock driver and session
            mock_driver_instance = MagicMock()
            mock_session = MagicMock()
            mock_driver.return_value = mock_driver_instance
            mock_driver_instance.session.return_value.__enter__.return_value = (
                mock_session
            )

            # Mock source metrics query results
            source_results = [
                Mock(single=Mock(return_value={"count": 1000})),  # check source exists
                Mock(single=Mock(return_value={"count": 1000})),  # resources
                Mock(single=Mock(return_value={"count": 3000})),  # relationships
                Mock(single=Mock(return_value={"count": 50})),  # resource groups
                Mock(single=Mock(return_value={"count": 25})),  # resource types
            ]

            # Mock target metrics query results
            target_results = [
                Mock(single=Mock(return_value={"count": 800})),  # check target exists
                Mock(single=Mock(return_value={"count": 800})),  # resources
                Mock(single=Mock(return_value={"count": 2400})),  # relationships
                Mock(single=Mock(return_value={"count": 40})),  # resource groups
                Mock(single=Mock(return_value={"count": 20})),  # resource types
            ]

            # Mock fidelity by type query results (iterator results)
            type_source = [
                {"type": "Microsoft.Compute/virtualMachines", "count": 100},
                {"type": "Microsoft.Network/virtualNetworks", "count": 50},
            ]
            type_target = [
                {"type": "Microsoft.Compute/virtualMachines", "count": 80},
                {"type": "Microsoft.Network/virtualNetworks", "count": 40},
            ]

            mock_session.run.side_effect = (
                source_results
                + target_results
                + [Mock(__iter__=lambda self: iter(type_source))]
                + [Mock(__iter__=lambda self: iter(type_target))]
            )

            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )
            metrics = calculator.calculate_fidelity(
                "source-sub-id", "target-sub-id", 95.0
            )

            assert metrics.source_subscription_id == "source-sub-id"
            assert metrics.target_subscription_id == "target-sub-id"
            assert metrics.source_resources == 1000
            assert metrics.target_resources == 800
            assert metrics.overall_fidelity == 80.0
            assert metrics.missing_resources == 200
            assert metrics.objective_met is False
            assert metrics.target_fidelity == 95.0

    def test_calculate_fidelity_source_not_found(self) -> None:
        """Test fidelity calculation when source subscription not found."""
        with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
            mock_driver_instance = MagicMock()
            mock_session = MagicMock()
            mock_driver.return_value = mock_driver_instance
            mock_driver_instance.session.return_value.__enter__.return_value = (
                mock_session
            )

            # Mock source not found (count = 0)
            mock_session.run.return_value.single.return_value = {"count": 0}

            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            with pytest.raises(ValueError, match="Source subscription not found"):
                calculator.calculate_fidelity("source-sub-id", "target-sub-id", 95.0)

    def test_calculate_fidelity_target_not_found(self) -> None:
        """Test fidelity calculation when target subscription not found."""
        with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
            mock_driver_instance = MagicMock()
            mock_session = MagicMock()
            mock_driver.return_value = mock_driver_instance
            mock_driver_instance.session.return_value.__enter__.return_value = (
                mock_session
            )

            # Mock source found, target not found
            source_results = [
                Mock(single=Mock(return_value={"count": 1000})),  # check source exists
                Mock(single=Mock(return_value={"count": 1000})),  # resources
                Mock(single=Mock(return_value={"count": 3000})),  # relationships
                Mock(single=Mock(return_value={"count": 50})),  # resource groups
                Mock(single=Mock(return_value={"count": 25})),  # resource types
            ]
            target_check = Mock(single=Mock(return_value={"count": 0}))

            mock_session.run.side_effect = source_results + [target_check]

            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            with pytest.raises(ValueError, match="Target subscription not found"):
                calculator.calculate_fidelity("source-sub-id", "target-sub-id", 95.0)

    def test_calculate_overall_fidelity(self) -> None:
        """Test overall fidelity calculation."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            source_metrics = {"resources": 1000}
            target_metrics = {"resources": 800}

            fidelity = calculator._calculate_overall_fidelity(
                source_metrics, target_metrics
            )
            assert fidelity == 80.0

            # Test with zero source resources
            source_metrics = {"resources": 0}
            fidelity = calculator._calculate_overall_fidelity(
                source_metrics, target_metrics
            )
            assert fidelity == 0.0

    def test_export_to_json(self) -> None:
        """Test JSON export functionality."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            metrics = FidelityMetrics(
                timestamp="2025-10-17T01:30:00Z",
                source_subscription_id="source-sub-id",
                target_subscription_id="target-sub-id",
                source_resources=1000,
                target_resources=800,
                source_relationships=3000,
                target_relationships=2400,
                source_resource_groups=50,
                target_resource_groups=40,
                source_resource_types=25,
                target_resource_types=20,
                overall_fidelity=80.0,
                fidelity_by_type={},
                missing_resources=200,
                objective_met=False,
                target_fidelity=95.0,
            )

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                calculator.export_to_json(metrics, "/tmp/fidelity.json")

                mock_open.assert_called_once_with("/tmp/fidelity.json", "w")
                # Verify JSON was written
                assert mock_file.write.called

    def test_track_fidelity(self) -> None:
        """Test fidelity tracking to JSONL file."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            metrics = FidelityMetrics(
                timestamp="2025-10-17T01:30:00Z",
                source_subscription_id="source-sub-id",
                target_subscription_id="target-sub-id",
                source_resources=1000,
                target_resources=800,
                source_relationships=3000,
                target_relationships=2400,
                source_resource_groups=50,
                target_resource_groups=40,
                source_resource_types=25,
                target_resource_types=20,
                overall_fidelity=80.0,
                fidelity_by_type={},
                missing_resources=200,
                objective_met=False,
                target_fidelity=95.0,
            )

            with patch("os.makedirs") as mock_makedirs:
                with patch("builtins.open", create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_open.return_value.__enter__.return_value = mock_file

                    calculator.track_fidelity(metrics, "demos/fidelity_history.jsonl")

                    mock_makedirs.assert_called_once_with("demos", exist_ok=True)
                    mock_open.assert_called_once_with(
                        "demos/fidelity_history.jsonl", "a"
                    )
                    # Verify JSONL line was written
                    assert mock_file.write.called

    def test_check_objective_success(self) -> None:
        """Test objective checking with valid OBJECTIVE.md."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            objective_content = """
            # OBJECTIVE

            The goal is to achieve 95% fidelity in the replication.
            """

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = objective_content
                mock_open.return_value.__enter__.return_value = mock_file

                objective_met, target_fidelity = calculator.check_objective(
                    "OBJECTIVE.md", 96.0
                )

                assert objective_met is True
                assert target_fidelity == 95.0

    def test_check_objective_not_met(self) -> None:
        """Test objective checking when fidelity not met."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            objective_content = """
            # OBJECTIVE

            Target fidelity: 95%
            """

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = objective_content
                mock_open.return_value.__enter__.return_value = mock_file

                objective_met, target_fidelity = calculator.check_objective(
                    "OBJECTIVE.md", 80.0
                )

                assert objective_met is False
                assert target_fidelity == 95.0

    def test_check_objective_default_target(self) -> None:
        """Test objective checking with no explicit target in file."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            objective_content = """
            # OBJECTIVE

            Some objective without explicit fidelity percentage.
            """

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = objective_content
                mock_open.return_value.__enter__.return_value = mock_file

                objective_met, target_fidelity = calculator.check_objective(
                    "OBJECTIVE.md", 96.0
                )

                assert objective_met is True
                assert target_fidelity == 95.0  # Default

    def test_check_objective_file_not_found(self) -> None:
        """Test objective checking when file doesn't exist."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(
                "bolt://localhost:7687", "neo4j", "password"
            )

            with patch("builtins.open", side_effect=OSError("File not found")):
                with pytest.raises(IOError):
                    calculator.check_objective("OBJECTIVE.md", 96.0)
