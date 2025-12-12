"""
Progress Display - Display progress for remote operations.

Philosophy:
- Simple rich console output
- Same UX as local mode
- Zero-BS implementation

Public API:
    RemoteProgressDisplay: Display progress for remote operations
"""

from types import TracebackType
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
)


class RemoteProgressDisplay:
    """
    Display progress for remote operations using Rich console.

    Philosophy:
    - Match existing ATG progress display style
    - Simple and clear progress updates
    - Handle errors gracefully
    """

    def __init__(self, show_progress: bool = True):
        """
        Initialize progress display.

        Args:
            show_progress: Whether to show progress (default: True)
        """
        self.show_progress = show_progress
        self.console = Console()
        self._progress: Optional[Progress] = None
        self._task_id: Optional[TaskID] = None

    def start(self, description: str = "Executing remote operation...") -> None:
        """
        Start progress display.

        Args:
            description: Initial progress description
        """
        if not self.show_progress:
            return

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        )

        self._progress.start()
        self._task_id = self._progress.add_task(description, total=100)

    def update(self, progress: float, message: str) -> None:
        """
        Update progress display.

        Args:
            progress: Progress percentage (0.0 to 100.0)
            message: Progress message
        """
        if not self.show_progress or not self._progress or self._task_id is None:
            return

        self._progress.update(self._task_id, completed=progress, description=message)

    def complete(self, message: str = "Operation complete") -> None:
        """
        Mark operation as complete.

        Args:
            message: Completion message
        """
        if not self.show_progress or not self._progress or self._task_id is None:
            return

        self._progress.update(
            self._task_id, completed=100, description=f"[green]✓ {message}"
        )

        self._progress.stop()

    def error(self, message: str) -> None:
        """
        Display error message.

        Args:
            message: Error message
        """
        if not self.show_progress:
            return

        if self._progress:
            self._progress.stop()

        self.console.print(f"[red]✗ Error: {message}")

    def info(self, message: str) -> None:
        """
        Display info message (without disrupting progress).

        Args:
            message: Info message
        """
        if not self.show_progress:
            return

        self.console.print(f"[cyan]i {message}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Context manager exit - cleanup progress display."""
        if self._progress:
            self._progress.stop()


def create_progress_callback(display: RemoteProgressDisplay):
    """
    Create a progress callback function for remote client.

    Args:
        display: Progress display instance

    Returns:
        Callback function(progress, message)
    """

    def callback(progress: float, message: str) -> None:
        """Progress callback for remote operations."""
        display.update(progress, message)

    return callback


__all__ = ["RemoteProgressDisplay", "create_progress_callback"]
