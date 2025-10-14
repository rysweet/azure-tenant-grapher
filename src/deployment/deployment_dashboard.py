"""
Deployment Dashboard

Real-time deployment monitoring dashboard for IaC deployments.
Provides 3-panel layout with config, progress, and terraform output streaming.
"""

import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from src.cli_dashboard_widgets.scrollable_log_widget import ScrollableLogWidget
from src.rich_dashboard import RichDashboard


class DeploymentDashboard:
    """
    Dashboard for real-time deployment monitoring.

    Extends/wraps RichDashboard to provide deployment-specific visualizations:
    - Configuration panel showing deployment parameters
    - Progress panel with phase tracking and resource counts
    - Terraform output panel with real-time streaming
    """

    def __init__(
        self,
        config: Dict[str, Any],
        job_id: Optional[str] = None,
    ):
        """
        Initialize the deployment dashboard.

        Args:
            config: Deployment configuration parameters
            job_id: Optional deployment job ID for tracking
        """
        self.console = Console()
        self.layout = Layout()
        self.config = config
        self.job_id = job_id
        self.lock = threading.Lock()

        # Dashboard state
        self._should_exit = False
        self.log_level = "info"
        self.processing = True

        # Deployment-specific state
        self.current_phase = "initializing"  # init, plan, apply, complete
        self.resources_planned = 0
        self.resources_applied = 0
        self.resources_failed = 0

        # Log widgets for terraform output and general logs
        self.terraform_widget = ScrollableLogWidget(max_lines=30)
        self.log_widget = ScrollableLogWidget(max_lines=20)

        # Setup 3-panel layout
        self._setup_layout()

    def _setup_layout(self):
        """Setup the 3-panel dashboard layout."""
        # Main split: top section and logs
        self.layout.split(
            Layout(name="top_margin", size=2),
            Layout(name="top", size=15),
            Layout(name="terraform_output", size=18),
        )

        # Top section split into config and progress
        self.layout["top"].split_row(
            Layout(name="config", ratio=2),
            Layout(name="progress", ratio=1),
        )

        # Initialize panels
        self.layout["top_margin"].update(Text(""))
        self.layout["config"].update(self._render_config_panel())
        self.layout["progress"].update(self._render_progress_panel())
        self.layout["terraform_output"].update(self._render_terraform_panel())

    def _render_config_panel(self) -> Panel:
        """Render the configuration panel."""
        table = Table.grid(expand=True)
        table.add_column(justify="right", style="cyan", no_wrap=True)
        table.add_column()

        for key, value in self.config.items():
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 60:
                value_str = value_str[:57] + "..."
            table.add_row(key, value_str)

        if self.job_id:
            table.add_row("Job ID", self.job_id)

        return Panel(
            table,
            title="Deployment Configuration",
            border_style="green",
            height=15,
        )

    def _render_progress_panel(self) -> Panel:
        """Render the progress panel with phase tracking."""
        table = Table.grid(expand=True)
        table.add_column("Metric", style="magenta")
        table.add_column("Value", style="bold")

        # Phase indicator
        phase_style = "yellow"
        if self.current_phase == "complete":
            phase_style = "green"
        elif self.current_phase == "failed":
            phase_style = "red"

        phase_display = self.current_phase.upper()
        table.add_row("Phase", Text(phase_display, style=phase_style))
        table.add_row("", "")  # Spacer

        # Resource counters
        if self.current_phase in ("plan", "apply", "complete"):
            table.add_row("Resources Planned", str(self.resources_planned))

        if self.current_phase in ("apply", "complete"):
            table.add_row("Resources Applied", str(self.resources_applied))
            if self.resources_failed > 0:
                table.add_row(
                    "Resources Failed",
                    Text(str(self.resources_failed), style="red"),
                )

        # Exit instructions
        exit_label = Text(
            "Press 'x' to exit | Press 'i/d/w' for log levels",
            style="yellow",
        )

        # Add spinner if processing
        if self.processing and self.current_phase not in ("complete", "failed"):
            spinner = Spinner("dots", text="Deploying...", style="green")
            group = Group(table, exit_label, Align.center(spinner))
        else:
            group = Group(table, exit_label)

        title = "Deployment Progress"
        if self.current_phase == "complete":
            title += " - Complete"
        elif self.current_phase == "failed":
            title += " - Failed"

        return Panel(
            group,
            title=title,
            border_style="blue",
            height=15,
        )

    def _render_terraform_panel(self) -> Panel:
        """Render the terraform output panel."""
        log_level_label = (
            f"Terraform Output | Log Level: {self.log_level.upper()}"
        )

        # Get filtered lines based on current log level
        filtered_lines = self.terraform_widget.get_filtered_lines(self.log_level)

        if not filtered_lines:
            content = Text("Waiting for terraform output...", style="dim")
        else:
            content = Text()
            for line_text, style in filtered_lines:
                content.append(line_text + "\n", style=style)

        return Panel(
            Align.left(content),
            title=log_level_label,
            border_style="cyan",
            padding=(0, 1),
        )

    def update_phase(self, phase: str):
        """
        Update the current deployment phase.

        Args:
            phase: Phase name (init, plan, apply, complete, failed)
        """
        with self.lock:
            self.current_phase = phase
            self.layout["progress"].update(self._render_progress_panel())

    def update_resource_counts(
        self,
        planned: Optional[int] = None,
        applied: Optional[int] = None,
        failed: Optional[int] = None,
    ):
        """
        Update resource counters.

        Args:
            planned: Number of resources planned
            applied: Number of resources applied
            failed: Number of resources failed
        """
        with self.lock:
            if planned is not None:
                self.resources_planned = planned
            if applied is not None:
                self.resources_applied = applied
            if failed is not None:
                self.resources_failed = failed
            self.layout["progress"].update(self._render_progress_panel())

    def stream_terraform_output(self, line: str, level: str = "info"):
        """
        Stream a line of terraform output to the dashboard.

        Args:
            line: Output line from terraform
            level: Log level (debug, info, warning)
        """
        with self.lock:
            # Determine style based on content
            style = "white"
            if "error" in line.lower() or "failed" in line.lower():
                style = "red"
                level = "warning"
            elif "warning" in line.lower():
                style = "yellow"
                level = "warning"
            elif "creating" in line.lower() or "created" in line.lower():
                style = "green"
            elif "plan:" in line.lower() or "apply complete!" in line.lower():
                style = "bold green"

            self.terraform_widget.add_line(line.rstrip(), style=style, level=level)
            self.layout["terraform_output"].update(self._render_terraform_panel())

    def add_error(self, error: str):
        """
        Add an error message to the dashboard.

        Args:
            error: Error message
        """
        with self.lock:
            self.terraform_widget.add_line(error, style="red", level="warning")
            self.layout["terraform_output"].update(self._render_terraform_panel())

    def log_info(self, info: str):
        """
        Add an info message to the dashboard.

        Args:
            info: Info message
        """
        with self.lock:
            self.terraform_widget.add_line(info, style="green", level="info")
            self.layout["terraform_output"].update(self._render_terraform_panel())

    def set_processing(self, processing: bool):
        """
        Set the processing state.

        Args:
            processing: Whether deployment is actively processing
        """
        with self.lock:
            self.processing = processing
            self.layout["progress"].update(self._render_progress_panel())

    @contextmanager
    def live(self):
        """
        Context manager for live dashboard display with keyboard handling.

        Yields:
            None
        """
        import sys

        import readchar

        stop_event = threading.Event()
        self._should_exit = False

        def key_loop():
            """Handle keyboard input."""
            while not stop_event.is_set():
                try:
                    if not sys.stdin.isatty():
                        # Non-TTY mode, just wait
                        import time

                        time.sleep(0.5)
                        continue

                    key = readchar.readkey()
                except Exception:
                    continue

                if key and key.lower() == "x":
                    with self.lock:
                        self._should_exit = True
                    break
                elif key and key.lower() in ("i", "d", "w"):
                    level_map = {"i": "info", "d": "debug", "w": "warning"}
                    with self.lock:
                        self.log_level = level_map[key.lower()]
                        self.log_info(
                            f"Log level set to {self.log_level.upper()}"
                        )
                        # Update terraform panel to reflect new filter
                        self.layout["terraform_output"].update(
                            self._render_terraform_panel()
                        )

        key_thread = threading.Thread(target=key_loop, daemon=True)
        key_thread.start()

        try:
            with Live(
                self.layout, refresh_per_second=4, console=self.console
            ):
                yield
        finally:
            stop_event.set()
            key_thread.join(timeout=2)

    @property
    def should_exit(self) -> bool:
        """Check if user requested exit."""
        return self._should_exit

    def as_rich_dashboard(self) -> RichDashboard:
        """
        Convert to RichDashboard for compatibility with CLIDashboardManager.

        Returns:
            RichDashboard instance with shared state
        """
        # Create a minimal RichDashboard for compatibility
        dashboard = RichDashboard(self.config)
        dashboard._should_exit = self._should_exit
        dashboard.log_level = self.log_level
        dashboard.processing = self.processing
        return dashboard
