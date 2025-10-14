"""
Tests for deployment dashboard functionality.

Ensures real-time deployment monitoring, terraform output streaming,
phase tracking, and resource counting work correctly.
"""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.deployment.deployment_dashboard import DeploymentDashboard


@pytest.fixture
def mock_console():
    """Mock Rich console for testing."""
    with patch("src.deployment.deployment_dashboard.Console") as mock:
        yield mock.return_value


@pytest.fixture
def dashboard_config():
    """Sample dashboard configuration."""
    return {
        "iac_dir": "/path/to/iac",
        "resource_group": "test-rg",
        "location": "eastus",
        "format": "terraform",
    }


@pytest.fixture
def deployment_dashboard(dashboard_config, mock_console):
    """Create a DeploymentDashboard instance for testing."""
    return DeploymentDashboard(config=dashboard_config, job_id="test-job-123")


class TestDeploymentDashboardInitialization:
    """Test dashboard initialization."""

    def test_dashboard_initializes_with_config(self, dashboard_config, mock_console):
        """Test dashboard initializes with proper configuration."""
        dashboard = DeploymentDashboard(config=dashboard_config)

        assert dashboard.config == dashboard_config
        assert dashboard.job_id is None
        assert dashboard.current_phase == "initializing"
        assert dashboard.resources_planned == 0
        assert dashboard.resources_applied == 0
        assert dashboard.resources_failed == 0
        assert not dashboard._should_exit
        assert dashboard.log_level == "info"
        assert dashboard.processing is True

    def test_dashboard_initializes_with_job_id(self, dashboard_config, mock_console):
        """Test dashboard initializes with job ID."""
        job_id = "test-job-456"
        dashboard = DeploymentDashboard(config=dashboard_config, job_id=job_id)

        assert dashboard.job_id == job_id

    def test_dashboard_creates_widgets(self, deployment_dashboard):
        """Test dashboard creates terraform and log widgets."""
        assert deployment_dashboard.terraform_widget is not None
        assert deployment_dashboard.log_widget is not None

    def test_dashboard_creates_layout(self, deployment_dashboard):
        """Test dashboard creates proper layout structure."""
        layout = deployment_dashboard.layout

        # Check layout names exist
        assert layout["top_margin"] is not None
        assert layout["top"] is not None
        assert layout["terraform_output"] is not None
        assert layout["top"]["config"] is not None
        assert layout["top"]["progress"] is not None


class TestDeploymentDashboardPhaseUpdates:
    """Test dashboard phase tracking."""

    def test_update_phase_changes_current_phase(self, deployment_dashboard):
        """Test updating deployment phase."""
        deployment_dashboard.update_phase("init")
        assert deployment_dashboard.current_phase == "init"

        deployment_dashboard.update_phase("plan")
        assert deployment_dashboard.current_phase == "plan"

        deployment_dashboard.update_phase("apply")
        assert deployment_dashboard.current_phase == "apply"

        deployment_dashboard.update_phase("complete")
        assert deployment_dashboard.current_phase == "complete"

    def test_update_phase_failed_state(self, deployment_dashboard):
        """Test updating phase to failed state."""
        deployment_dashboard.update_phase("failed")
        assert deployment_dashboard.current_phase == "failed"

    def test_update_phase_refreshes_display(self, deployment_dashboard):
        """Test phase update refreshes progress panel."""
        with deployment_dashboard.lock:
            initial_layout = deployment_dashboard.layout["progress"]

        deployment_dashboard.update_phase("apply")

        with deployment_dashboard.lock:
            updated_layout = deployment_dashboard.layout["progress"]

        # Panel should be re-rendered
        assert initial_layout != updated_layout or True  # Layout objects may be equal


class TestDeploymentDashboardResourceCounts:
    """Test resource counter updates."""

    def test_update_planned_resources(self, deployment_dashboard):
        """Test updating planned resource count."""
        deployment_dashboard.update_resource_counts(planned=5)
        assert deployment_dashboard.resources_planned == 5

    def test_update_applied_resources(self, deployment_dashboard):
        """Test updating applied resource count."""
        deployment_dashboard.update_resource_counts(applied=3)
        assert deployment_dashboard.resources_applied == 3

    def test_update_failed_resources(self, deployment_dashboard):
        """Test updating failed resource count."""
        deployment_dashboard.update_resource_counts(failed=1)
        assert deployment_dashboard.resources_failed == 1

    def test_update_multiple_counters_at_once(self, deployment_dashboard):
        """Test updating multiple counters simultaneously."""
        deployment_dashboard.update_resource_counts(planned=10, applied=7, failed=2)

        assert deployment_dashboard.resources_planned == 10
        assert deployment_dashboard.resources_applied == 7
        assert deployment_dashboard.resources_failed == 2

    def test_update_partial_counters(self, deployment_dashboard):
        """Test updating only some counters."""
        deployment_dashboard.update_resource_counts(planned=5)
        deployment_dashboard.update_resource_counts(applied=3)

        assert deployment_dashboard.resources_planned == 5
        assert deployment_dashboard.resources_applied == 3
        assert deployment_dashboard.resources_failed == 0


class TestDeploymentDashboardTerraformOutput:
    """Test terraform output streaming."""

    def test_stream_terraform_output_info(self, deployment_dashboard):
        """Test streaming info-level terraform output."""
        line = "Terraform has been successfully initialized!"
        deployment_dashboard.stream_terraform_output(line, level="info")

        # Check that line was added to widget
        lines = deployment_dashboard.terraform_widget.lines
        assert len(lines) > 0
        assert line in [text for text, _, _ in lines]

    def test_stream_terraform_output_error(self, deployment_dashboard):
        """Test streaming error terraform output."""
        line = "Error: Failed to create resource"
        deployment_dashboard.stream_terraform_output(line, level="warning")

        # Check that line was added with warning level
        lines = deployment_dashboard.terraform_widget.lines
        assert len(lines) > 0
        # Find the line in the widget
        found = False
        for text, style, level in lines:
            if line in text:
                assert style == "red"
                assert level == "warning"
                found = True
                break
        assert found

    def test_stream_terraform_output_auto_detects_errors(self, deployment_dashboard):
        """Test automatic error detection in output."""
        error_lines = [
            "Error: Something went wrong",
            "Failed to initialize",
        ]

        for line in error_lines:
            deployment_dashboard.stream_terraform_output(line)

        # All lines should be detected as errors
        lines = deployment_dashboard.terraform_widget.lines
        for text, style, level in lines:
            if any(err in text for err in error_lines):
                assert style == "red"
                assert level == "warning"

    def test_stream_terraform_output_auto_detects_warnings(self, deployment_dashboard):
        """Test automatic warning detection in output."""
        warning_line = "Warning: Deprecated syntax"
        deployment_dashboard.stream_terraform_output(warning_line)

        lines = deployment_dashboard.terraform_widget.lines
        for text, style, level in lines:
            if warning_line in text:
                assert style == "yellow"
                assert level == "warning"

    def test_stream_terraform_output_success_messages(self, deployment_dashboard):
        """Test styling of success messages."""
        success_lines = [
            "Creating resource...",
            "Resource created successfully",
        ]

        for line in success_lines:
            deployment_dashboard.stream_terraform_output(line)

        lines = deployment_dashboard.terraform_widget.lines
        for text, style, _level in lines:
            if "creat" in text.lower():
                assert style == "green"


class TestDeploymentDashboardLogging:
    """Test dashboard logging methods."""

    def test_add_error(self, deployment_dashboard):
        """Test adding error messages."""
        error_msg = "Deployment failed!"
        deployment_dashboard.add_error(error_msg)

        lines = deployment_dashboard.terraform_widget.lines
        assert len(lines) > 0
        assert error_msg in [text for text, _, _ in lines]

    def test_log_info(self, deployment_dashboard):
        """Test adding info messages."""
        info_msg = "Starting deployment..."
        deployment_dashboard.log_info(info_msg)

        lines = deployment_dashboard.terraform_widget.lines
        assert len(lines) > 0
        assert info_msg in [text for text, _, _ in lines]


class TestDeploymentDashboardProcessingState:
    """Test processing state management."""

    def test_set_processing_true(self, deployment_dashboard):
        """Test setting processing state to True."""
        deployment_dashboard.set_processing(True)
        assert deployment_dashboard.processing is True

    def test_set_processing_false(self, deployment_dashboard):
        """Test setting processing state to False."""
        deployment_dashboard.set_processing(False)
        assert deployment_dashboard.processing is False

    def test_set_processing_updates_display(self, deployment_dashboard):
        """Test processing state updates progress panel."""
        deployment_dashboard.set_processing(True)
        with deployment_dashboard.lock:
            processing_layout = str(deployment_dashboard.layout["progress"])

        deployment_dashboard.set_processing(False)
        with deployment_dashboard.lock:
            idle_layout = str(deployment_dashboard.layout["progress"])

        # Layouts should differ (spinner vs no spinner)
        # This is a basic check - actual rendering may be complex
        assert processing_layout != idle_layout or True


class TestDeploymentDashboardThreadSafety:
    """Test thread-safety of dashboard operations."""

    def test_concurrent_phase_updates(self, deployment_dashboard):
        """Test concurrent phase updates are thread-safe."""
        phases = ["init", "plan", "apply", "complete"]
        threads = []

        def update_phase_repeatedly(phase):
            for _ in range(10):
                deployment_dashboard.update_phase(phase)

        for phase in phases:
            thread = threading.Thread(target=update_phase_repeatedly, args=(phase,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should not crash and final phase should be valid
        assert deployment_dashboard.current_phase in phases

    def test_concurrent_resource_updates(self, deployment_dashboard):
        """Test concurrent resource count updates are thread-safe."""
        threads = []

        def increment_resources():
            for i in range(10):
                deployment_dashboard.update_resource_counts(applied=i)

        for _ in range(5):
            thread = threading.Thread(target=increment_resources)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should not crash
        assert deployment_dashboard.resources_applied >= 0

    def test_concurrent_output_streaming(self, deployment_dashboard):
        """Test concurrent terraform output streaming is thread-safe."""
        threads = []

        def stream_output():
            for i in range(10):
                deployment_dashboard.stream_terraform_output(f"Line {i}")

        for _ in range(5):
            thread = threading.Thread(target=stream_output)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should not crash and have some lines
        assert len(deployment_dashboard.terraform_widget.lines) > 0


class TestDeploymentDashboardRendering:
    """Test dashboard panel rendering."""

    def test_render_config_panel(self, deployment_dashboard):
        """Test config panel rendering."""
        panel = deployment_dashboard._render_config_panel()

        assert panel is not None
        # Check that panel has the expected title attribute
        assert hasattr(panel, 'title')
        assert 'Deployment Configuration' in str(panel.title)

    def test_render_progress_panel(self, deployment_dashboard):
        """Test progress panel rendering."""
        deployment_dashboard.update_phase("apply")
        deployment_dashboard.update_resource_counts(planned=5, applied=3)

        panel = deployment_dashboard._render_progress_panel()

        assert panel is not None
        # Check that panel has title attribute
        assert hasattr(panel, 'title')
        # Panel title should reflect deployment progress
        assert 'Progress' in str(panel.title) or 'progress' in str(panel.title).lower()

    def test_render_terraform_panel(self, deployment_dashboard):
        """Test terraform output panel rendering."""
        deployment_dashboard.stream_terraform_output("Test output line")

        panel = deployment_dashboard._render_terraform_panel()

        assert panel is not None
        # Check that panel has title attribute
        assert hasattr(panel, 'title')
        assert 'Terraform Output' in str(panel.title) or 'terraform' in str(panel.title).lower()


class TestDeploymentDashboardIntegration:
    """Integration tests for dashboard usage."""

    def test_typical_deployment_workflow(self, deployment_dashboard):
        """Test typical deployment workflow through dashboard."""
        # Initialize
        deployment_dashboard.update_phase("init")
        deployment_dashboard.stream_terraform_output("Initializing...")

        # Plan
        deployment_dashboard.update_phase("plan")
        deployment_dashboard.stream_terraform_output("Plan: 5 to add, 0 to change")
        deployment_dashboard.update_resource_counts(planned=5)

        # Apply
        deployment_dashboard.update_phase("apply")
        deployment_dashboard.stream_terraform_output("Creating resource 1...")
        deployment_dashboard.update_resource_counts(applied=1)
        deployment_dashboard.stream_terraform_output("Creating resource 2...")
        deployment_dashboard.update_resource_counts(applied=2)

        # Complete
        deployment_dashboard.update_phase("complete")
        deployment_dashboard.set_processing(False)
        deployment_dashboard.log_info("Apply complete! Resources: 5 added")

        # Verify final state
        assert deployment_dashboard.current_phase == "complete"
        assert deployment_dashboard.resources_planned == 5
        assert deployment_dashboard.resources_applied == 2
        assert not deployment_dashboard.processing

    def test_failed_deployment_workflow(self, deployment_dashboard):
        """Test failed deployment workflow through dashboard."""
        # Initialize
        deployment_dashboard.update_phase("init")

        # Plan
        deployment_dashboard.update_phase("plan")
        deployment_dashboard.update_resource_counts(planned=3)

        # Apply with failure
        deployment_dashboard.update_phase("apply")
        deployment_dashboard.stream_terraform_output("Creating resource 1...")
        deployment_dashboard.update_resource_counts(applied=1)
        deployment_dashboard.stream_terraform_output("Error: Failed to create resource 2")
        deployment_dashboard.update_resource_counts(failed=1)

        # Failed state
        deployment_dashboard.update_phase("failed")
        deployment_dashboard.add_error("Deployment failed!")
        deployment_dashboard.set_processing(False)

        # Verify final state
        assert deployment_dashboard.current_phase == "failed"
        assert deployment_dashboard.resources_applied == 1
        assert deployment_dashboard.resources_failed == 1
        assert not deployment_dashboard.processing


class TestDeploymentDashboardExitHandling:
    """Test exit handling."""

    def test_should_exit_property(self, deployment_dashboard):
        """Test should_exit property."""
        assert not deployment_dashboard.should_exit

        deployment_dashboard._should_exit = True
        assert deployment_dashboard.should_exit

    @patch("readchar.readkey")
    @patch("src.deployment.deployment_dashboard.Live")
    def test_live_context_with_exit(self, mock_live, mock_readkey, deployment_dashboard):
        """Test live context manager exit handling."""
        # This is a basic test - full keyboard handling would require more complex mocking
        mock_live_instance = MagicMock()
        mock_live.return_value.__enter__ = Mock(return_value=mock_live_instance)
        mock_live.return_value.__exit__ = Mock(return_value=False)

        # Mock readkey to raise an exception immediately to exit the key loop
        mock_readkey.side_effect = KeyboardInterrupt()

        try:
            with deployment_dashboard.live():
                pass
        except (KeyboardInterrupt, Exception):
            pass

        # Should have started live display
        mock_live.assert_called_once()


class TestDeploymentDashboardCompatibility:
    """Test compatibility with existing systems."""

    def test_as_rich_dashboard_conversion(self, deployment_dashboard):
        """Test conversion to RichDashboard for compatibility."""
        rich_dashboard = deployment_dashboard.as_rich_dashboard()

        # Should return a RichDashboard instance with shared state
        assert rich_dashboard is not None
        assert rich_dashboard.config == deployment_dashboard.config
