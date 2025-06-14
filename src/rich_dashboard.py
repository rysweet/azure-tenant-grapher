import asyncio
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from .cli_dashboard_widgets import ScrollableLogWidget


class RichDashboard:
    def __init__(self, config: Dict[str, Any], batch_size: int, total_threads: int):
        self.console = Console()
        self.layout = Layout()
        self.config = config
        self.batch_size = batch_size
        self.total_threads = total_threads
        self.log_level = "info"  # "info", "debug", "warning"
        self._should_exit = False  # Set to True when user presses "x"

        # Create timestamped log file in tmp directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = (
            f"{tempfile.gettempdir()}/azure_tenant_grapher_{timestamp}.log"
        )

        # Update config to include log file path for display
        self.config = dict(config)  # Make a copy
        self.config["log_file"] = self.log_file_path

        self.progress_stats = {
            "batch": 0,
            "total_batches": 0,
            "processed": 0,
            "total": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "llm_generated": 0,
            "llm_skipped": 0,
            "llm_in_flight": 0,
        }

        # Use the new scrollable log widget
        self.log_widget = ScrollableLogWidget(max_lines=50)
        self.lock = threading.Lock()
        self.processing = True  # Show spinner by default

        # Layout: top margin, then config/progress, then logs
        self.layout.split(
            Layout(name="top_margin", size=4),
            Layout(name="top", size=15),
            Layout(name="logs"),
        )
        self.layout["top"].split_row(
            Layout(name="config", ratio=2), Layout(name="progress", ratio=1)
        )
        self.layout["config"].update(self._render_config_panel())
        self.layout["progress"].update(self._render_progress_panel())
        self.layout["logs"].update(self._render_log_panel())
        self.layout["top_margin"].update(Text(""))

    def _render_config_panel(self):
        table = Table.grid(expand=True)
        table.add_column(justify="right", style="cyan", no_wrap=True)
        table.add_column()
        for k, v in self.config.items():
            table.add_row(str(k), str(v))
        table.add_row("Batch Size", str(self.batch_size))
        table.add_row("Threads", str(self.total_threads))
        return Panel(
            table, title="Config / Parameters", border_style="green", height=15
        )

    def _render_progress_panel(self):
        stats = self.progress_stats
        table = Table.grid(expand=True)
        table.add_column("Metric", style="magenta")
        table.add_column("Value", style="bold")
        # Removed Batch row
        table.add_row("Processed", f"{stats['processed']}/{stats['total']}")
        table.add_row("Successful", str(stats["successful"]))
        table.add_row("Failed", str(stats["failed"]))
        table.add_row("Skipped", str(stats["skipped"]))
        table.add_row("LLM Generated", str(stats["llm_generated"]))
        table.add_row("LLM Skipped", str(stats["llm_skipped"]))
        table.add_row("LLM In-Flight", str(stats.get("llm_in_flight", 0)))
        table.add_row("Threads", str(self.total_threads))
        # Add spinner and label at the bottom if processing
        hint = Align.center(Text("Press 'x' to exit.", style="yellow"))
        log_label = Align.center(
            Text(
                f"Log level: {self.log_level.upper()}  (press i=INFO, d=DEBUG, w=WARNING)",
                style="bold green",
            )
        )
        if self.processing:
            spinner = Spinner("dots", text="processing...", style="green")
            group = Group(table, hint, log_label, Align.center(spinner))
            return Panel(group, title="Progress", border_style="blue", height=15)
        else:
            group = Group(table, hint, log_label)
            return Panel(group, title="Progress", border_style="blue", height=15)

    def _render_log_panel(self):
        # Get filtered lines based on current log level
        filtered_lines = self.log_widget.get_filtered_lines(self.log_level)

        if not filtered_lines:
            text = Text("Waiting for logs...", style="dim")
        else:
            text = Text()
            for line_text, style in filtered_lines:
                text.append(line_text + "\n", style=style)

            # Add indicator if there are more logs available
            total_lines = len(self.log_widget.lines)
            visible_lines = len(filtered_lines)
            if total_lines > visible_lines:
                text.append(
                    f"... ({total_lines - visible_lines} more logs at other levels)\n",
                    style="dim",
                )

        return Panel(
            text,
            title=f"Logs (Level: {self.log_level.upper()}) - {len(self.log_widget.lines)} total, {len(filtered_lines)} visible",
            border_style="green",
            padding=(0, 1),
        )

    def update_progress(self, **kwargs: Any):
        with self.lock:
            self.progress_stats.update(kwargs)
            self.layout["progress"].update(self._render_progress_panel())

    def add_error(self, error: str):
        with self.lock:
            self.log_widget.add_line(error, "red", "warning")
            self.layout["logs"].update(self._render_log_panel())

    def log_info(self, info: str):
        with self.lock:
            self.log_widget.add_line(info, "green", "info")
            self.layout["logs"].update(self._render_log_panel())

    def set_processing(self, processing: bool):
        with self.lock:
            self.processing = processing
            self.layout["progress"].update(self._render_progress_panel())

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def live(self):
        """
        Async context manager for running the dashboard live.
        Allows user to press 'X' to exit safely and [i|d|w] to set log level.
        """
        import readchar

        stop_event = threading.Event()
        self._should_exit = False  # Reset on entry
        key_task = None

        async def _key_loop():
            while not stop_event.is_set():
                key = await asyncio.to_thread(readchar.readkey)
                if key.lower() == "x":
                    self.set_processing(False)
                    self.add_error("Exiting dashboard (user pressed X)")
                    self._should_exit = True
                    stop_event.set()
                    break
                elif key.lower() in ("i", "d", "w"):
                    self.log_level = {"i": "info", "d": "debug", "w": "warning"}[
                        key.lower()
                    ]
                    self.add_error(f"Log level set to {self.log_level.upper()}")
                    self.layout["progress"].update(self._render_progress_panel())

        try:
            with Live(self.layout, refresh_per_second=4, console=self.console):
                key_task = asyncio.create_task(_key_loop())
                try:
                    yield
                finally:
                    stop_event.set()
                    await key_task
        except KeyboardInterrupt:
            self.set_processing(False)
            self.add_error("Exiting dashboard (KeyboardInterrupt)")
        finally:
            self.set_processing(False)

    @property
    def should_exit(self) -> bool:
        """True if the user pressed 'x' to exit the dashboard."""
        return self._should_exit
