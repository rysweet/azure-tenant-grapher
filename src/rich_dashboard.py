import sys
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


class DashboardExit(Exception):
    """Raised to force exit from the dashboard context."""

    pass


class RichDashboard:
    def __init__(self, config: Dict[str, Any], batch_size: int, total_threads: int):
        self.console = Console()
        self.layout = Layout()
        self.config = config
        self.batch_size = batch_size
        self.total_threads = total_threads

        # Add log_file_path for CLI compatibility
        import tempfile
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = (
            f"{tempfile.gettempdir()}/azure_tenant_grapher_{timestamp}.log"
        )
        self._should_exit = False
        self.log_level = "info"

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
        table.add_row("Processed", f"{stats['processed']}/{stats['total']}")
        table.add_row("Successful", str(stats["successful"]))
        table.add_row("Failed", str(stats["failed"]))
        table.add_row("Skipped", str(stats["skipped"]))
        table.add_row("LLM Generated", str(stats["llm_generated"]))
        table.add_row("LLM Skipped", str(stats["llm_skipped"]))
        table.add_row("LLM In-Flight", str(stats.get("llm_in_flight", 0)))
        table.add_row("Threads", str(self.total_threads))
        # Add spinner and label at the bottom if processing
        exit_label = Text("Press 'x' to exit", style="yellow")
        if self.processing:
            spinner = Spinner("dots", text="processing...", style="green")
            group = Group(table, exit_label, Align.center(spinner))
            return Panel(group, title="Progress", border_style="blue", height=15)
        else:
            group = Group(table, exit_label)
            return Panel(group, title="Progress", border_style="blue", height=15)

    def _render_error_panel(self):
        # Show only the last 40 lines, and join with newlines, with color
        error_lines = self.errors[-40:] if self.errors else [("No errors.", "white")]
        text = Text()
        for msg, style in error_lines:
            text.append(msg + "\n", style=style)
        log_level_label = f"Log Level: {self.log_level.upper()}; Press 'i' for INFO, 'd' for DEBUG, 'w' for WARN"
        return Panel(
            Align.left(text),
            title=log_level_label,
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

    @contextmanager
    def live(
        self,
        key_handler: Optional[Callable[[], None]] = None,
        key_queue: Optional[Any] = None,
    ):
        import readchar

        stop_event = threading.Event()
        self._should_exit = False

        def default_key_loop():
            import queue

            # If not a TTY and no key_queue, create a stdin reader thread to feed a queue
            local_queue = key_queue
            stdin_reader_thread = None
            if not sys.stdin.isatty() and key_queue is None:
                local_queue = queue.Queue()

                def stdin_reader(
                    q: "queue.Queue[str]", stop_event: threading.Event
                ) -> None:
                    while not stop_event.is_set():
                        ch = sys.stdin.read(1)
                        if ch:
                            q.put(ch)

                stdin_reader_thread = threading.Thread(
                    target=stdin_reader, args=(local_queue, stop_event), daemon=True
                )
                stdin_reader_thread.start()
                with self.lock:
                    self.errors.append(
                        (
                            "STDIN fallback: using stdin reader thread for keypresses.",
                            "yellow",
                        )
                    )
                    self.layout["logs"].update(self._render_error_panel())
            else:
                with self.lock:
                    self.errors.append(
                        (
                            "Keypress thread started. Waiting for 'x', 'i', 'd', 'w'...",
                            "yellow",
                        )
                    )
                    self.layout["logs"].update(self._render_error_panel())
            while not stop_event.is_set():
                try:
                    if local_queue is not None:
                        key = local_queue.get(timeout=1)
                    else:
                        key = readchar.readkey()
                except Exception as e:
                    with self.lock:
                        self.errors.append((f"Keypress error: {e}", "red"))
                        self.layout["logs"].update(self._render_error_panel())
                    continue
                with self.lock:
                    self.errors.append((f"Keypress received: {key!r}", "yellow"))
                    self.layout["logs"].update(self._render_error_panel())
                if key and key.lower() == "x":
                    sys.exit(0)
                elif key and key.lower() in ("i", "d", "w"):
                    level = {"i": "info", "d": "debug", "w": "warning"}[key.lower()]
                    with self.lock:
                        self.log_level = level
                        # Update all loggers' and handlers' levels
                        import logging

                        level_map = {
                            "debug": logging.DEBUG,
                            "info": logging.INFO,
                            "warning": logging.WARNING,
                        }
                        new_level = level_map.get(self.log_level, logging.INFO)
                        root_logger = logging.getLogger()
                        root_logger.setLevel(new_level)

                        # Set all handler levels for all loggers
                        def set_all_handler_levels(
                            logger: logging.Logger, level: int
                        ) -> None:
                            for handler in getattr(logger, "handlers", []):
                                handler.setLevel(level)

                        set_all_handler_levels(root_logger, new_level)
                        for name in logging.root.manager.loggerDict:
                            # Preserve specific logger configurations (httpx, azure, openai should stay at WARNING)
                            if name in ["httpx", "azure", "openai"]:
                                continue
                            logger = logging.getLogger(name)
                            logger.setLevel(new_level)
                            set_all_handler_levels(logger, new_level)
                        self.errors.append(
                            (f"Log level set to {self.log_level.upper()}", "yellow")
                        )
                        self.layout["logs"].update(self._render_error_panel())
            if stdin_reader_thread is not None:
                stop_event.set()
                stdin_reader_thread.join(timeout=1)

        key_loop = key_handler if key_handler is not None else default_key_loop

        key_thread = threading.Thread(target=key_loop, daemon=True)
        key_thread.start()
        try:
            with Live(self.layout, refresh_per_second=4, console=self.console) as live:
                # Monitor for exit in a background thread
                import time

                def monitor_exit():
                    while not stop_event.is_set():
                        if self._should_exit:
                            live.stop()
                            stop_event.set()  # Signal all threads to stop
                            # (Revert: do NOT call os._exit or raise here)
                        time.sleep(0.05)

                monitor_thread = threading.Thread(target=monitor_exit, daemon=True)
                monitor_thread.start()

                try:
                    yield
                finally:
                    stop_event.set()
                    monitor_thread.join(timeout=1)
        finally:
            stop_event.set()
            key_thread.join(timeout=2)

    @property
    def should_exit(self):
        return self._should_exit
