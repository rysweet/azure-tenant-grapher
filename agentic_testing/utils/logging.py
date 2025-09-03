"""Logging utilities for the Agentic Testing System."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure logging for the testing system.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class TestRunLogger:
    """Context manager for test run logging."""

    def __init__(self, test_id: str, output_dir: str = "outputs/logs"):
        self.test_id = test_id
        self.output_dir = Path(output_dir)
        self.log_file = None
        self.file_handler = None

    def __enter__(self):
        """Start logging for test run."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.output_dir / f"test_{self.test_id}_{timestamp}.log"

        self.file_handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.file_handler.setFormatter(formatter)

        logger = logging.getLogger(f"test.{self.test_id}")
        logger.addHandler(self.file_handler)

        return self.log_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop logging for test run."""
        if self.file_handler:
            logger = logging.getLogger(f"test.{self.test_id}")
            logger.removeHandler(self.file_handler)
            self.file_handler.close()
