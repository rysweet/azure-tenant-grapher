"""CLI commands for fidelity calculation and tracking.

This module re-exports fidelity command from src.commands.fidelity for backward
compatibility with existing CLI structure.

Public API:
    fidelity: Main fidelity command with resource-level validation support
    ResourceFidelityCalculator: Calculator class for testing patches
"""

from src.commands.fidelity import fidelity, fidelity_command, fidelity_command_handler, fidelity_resource_level_handler
from src.validation.resource_fidelity_calculator import ResourceFidelityCalculator

__all__ = [
    "fidelity",
    "fidelity_command",
    "fidelity_command_handler",
    "fidelity_resource_level_handler",
    "ResourceFidelityCalculator",
]
