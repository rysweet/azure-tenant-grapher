"""
Scrollable Log Widget for Rich CLI Dashboards

A custom Rich widget that provides scrollable log display with level filtering.
"""

from typing import List, Tuple

from rich.console import RenderableType
from rich.text import Text


class ScrollableLogWidget:
    """A custom widget for scrollable log display with level filtering."""

    def __init__(self, max_lines: int = 50):
        """
        Initialize the scrollable log widget.

        Args:
            max_lines: Maximum number of lines to display (default: 50)
        """
        self.max_lines = max_lines
        self.lines: List[Tuple[str, str, str]] = []  # (text, style, level)

    def add_line(self, text: str, style: str = "white", level: str = "info") -> None:
        """
        Add a line to the log widget.

        Args:
            text: The log message text
            style: Rich style for the text (default: "white")
            level: Log level (debug, info, warning) (default: "info")
        """
        self.lines.append((text, style, level))
        # Keep only the last max_lines * 2 to allow for filtering
        if len(self.lines) > self.max_lines * 2:
            self.lines = self.lines[-self.max_lines * 2 :]

    def get_filtered_lines(self, min_level: str = "info") -> List[Tuple[str, str]]:
        """
        Get lines filtered by minimum log level.

        Args:
            min_level: Minimum log level to display (debug, info, warning)

        Returns:
            List of (text, style) tuples for lines that meet the level criteria
        """
        level_order = {"debug": 0, "info": 1, "warning": 2}
        min_level_value = level_order.get(min_level, 1)

        def level_from_style(style: str) -> str:
            """Infer log level from Rich style."""
            if "red" in style:
                return "warning"
            if "green" in style:
                return "info"
            return "debug"

        filtered = []
        for text, style, level in self.lines:
            # Use the explicit level if provided, otherwise infer from style
            actual_level = level if level in level_order else level_from_style(style)
            if level_order.get(actual_level, 0) >= min_level_value:
                filtered.append((text, style))

        # Return only the last max_lines after filtering
        return filtered[-self.max_lines :]

    def __rich__(self) -> RenderableType:
        """
        Render the scrollable log widget.

        Note: This is a fallback render method. The dashboard should call
        get_filtered_lines() directly for proper level filtering.

        Returns:
            Rich renderable object
        """
        lines = [(text, style) for text, style, _ in self.lines[-self.max_lines :]]

        if not lines:
            return Text("Waiting for logs...", style="dim")

        # Create a Text object with all lines
        result = Text()
        for line_text, style in lines:
            result.append(line_text + "\n", style=style)

        return result
