import threading
from typing import Any, Dict, List

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


class RichDashboard:
    def __init__(self, config: Dict[str, Any], batch_size: int, total_threads: int):
        self.console = Console()
        self.layout = Layout()
        self.config = config
        self.batch_size = batch_size
        self.total_threads = total_threads

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
        self.errors: List[tuple[str, str]] = []  # (message, style)
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
        self.layout["logs"].update(self._render_error_panel())
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
        table.add_row("Batch", f"{stats['batch']}/{stats['total_batches']}")
        table.add_row("Processed", f"{stats['processed']}/{stats['total']}")
        table.add_row("Successful", str(stats["successful"]))
        table.add_row("Failed", str(stats["failed"]))
        table.add_row("Skipped", str(stats["skipped"]))
        table.add_row("LLM Generated", str(stats["llm_generated"]))
        table.add_row("LLM Skipped", str(stats["llm_skipped"]))
        table.add_row("LLM In-Flight", str(stats.get("llm_in_flight", 0)))
        table.add_row("Threads", str(self.total_threads))
        # Add spinner and label at the bottom if processing
        if self.processing:
            spinner = Spinner("dots", text="processing...", style="green")
            group = Group(table, Align.center(spinner))
            return Panel(group, title="Progress", border_style="blue", height=15)
        else:
            return Panel(table, title="Progress", border_style="blue", height=15)

    def _render_error_panel(self):
        # Show only the last 40 lines, and join with newlines, with color
        error_lines = self.errors[-40:] if self.errors else [("No errors.", "white")]
        text = Text()
        for msg, style in error_lines:
            text.append(msg + "\n", style=style)
        return Panel(
            Align.left(text),
            title="Errors / Logs",
            border_style="green",
            padding=(0, 1),
        )

    def update_progress(self, **kwargs: Any):
        with self.lock:
            self.progress_stats.update(kwargs)
            self.layout["progress"].update(self._render_progress_panel())

    def add_error(self, error: str):
        with self.lock:
            self.errors.append((error, "red"))
            self.layout["logs"].update(self._render_error_panel())

    def log_info(self, info: str):
        with self.lock:
            self.errors.append((info, "green"))
            self.layout["logs"].update(self._render_error_panel())

    def set_processing(self, processing: bool):
        with self.lock:
            self.processing = processing
            self.layout["progress"].update(self._render_progress_panel())

    def live(self):
        return Live(self.layout, refresh_per_second=4, console=self.console)
