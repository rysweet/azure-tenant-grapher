"""Testing agents for the Agentic Testing System."""

from .cli_agent import CLIAgent
from .comprehension_agent import ComprehensionAgent
from .issue_reporter import IssueReporter
from .priority_agent import PriorityAgent

# Optional import for Electron UI agent (requires playwright)
try:
    from .electron_ui_agent import ElectronUIAgent

    __all__ = [
        "CLIAgent",
        "ComprehensionAgent",
        "ElectronUIAgent",
        "IssueReporter",
        "PriorityAgent",
    ]
except ImportError:
    # Playwright not installed, UI testing unavailable
    __all__ = [
        "CLIAgent",
        "ComprehensionAgent",
        "IssueReporter",
        "PriorityAgent",
    ]
