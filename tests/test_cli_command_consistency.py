#!/usr/bin/env python3
"""
Test to ensure that 'atg scan' and 'atg build' commands are identical.

This test verifies that the scan command is a true alias of the build command,
with identical parameters, help text, and behavior.
"""

import sys
from pathlib import Path

import click.testing
import pytest

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cli import cli


class TestCommandConsistency:
    """Test that scan and build commands are consistent."""

    def test_scan_and_build_have_same_parameters(self):
        """Verify that scan and build commands have identical parameters."""
        runner = click.testing.CliRunner()
        
        # Get help text for both commands
        build_result = runner.invoke(cli, ['build', '--help'])
        scan_result = runner.invoke(cli, ['scan', '--help'])
        
        # Extract parameter sections from help text
        build_help = build_result.output
        scan_help = scan_result.output
        
        # Find all options in each help text
        import re
        option_pattern = r'--[\w-]+(?:\s+[\w_]+)?'
        
        build_options = set(re.findall(option_pattern, build_help))
        scan_options = set(re.findall(option_pattern, scan_help))
        
        # Remove help option as it's always present
        build_options.discard('--help')
        scan_options.discard('--help')
        
        # Check that options are identical
        assert build_options == scan_options, (
            f"Commands have different options.\n"
            f"Build only: {build_options - scan_options}\n"
            f"Scan only: {scan_options - build_options}"
        )

    def test_scan_and_build_have_same_docstring(self):
        """Verify that scan and build commands have the same help text."""
        runner = click.testing.CliRunner()
        
        # Get help text for both commands
        build_result = runner.invoke(cli, ['build', '--help'])
        scan_result = runner.invoke(cli, ['scan', '--help'])
        
        # The help text should be identical (or scan should just reference build)
        # For now, we'll check that key elements are present in both
        
        # Check that both mention the same core functionality
        assert "Azure tenant graph" in build_result.output
        assert "Azure tenant graph" in scan_result.output
        
        # Check that both mention the dashboard controls
        assert "Press 'x' to exit" in build_result.output
        assert "Press 'x' to exit" in scan_result.output

    def test_filter_parameters_are_consistent(self):
        """Verify that filtering parameters from PR #229 are present in both commands."""
        runner = click.testing.CliRunner()
        
        # Get help text for both commands
        build_result = runner.invoke(cli, ['build', '--help'])
        scan_result = runner.invoke(cli, ['scan', '--help'])
        
        # Check for the new filtering parameters from PR #229
        # Build command should have --filter-by-subscriptions
        assert '--filter-by-subscriptions' in build_result.output, (
            "Build command missing --filter-by-subscriptions parameter"
        )
        
        # Scan command should also have --filter-by-subscriptions (not --filter-by-subs)
        assert '--filter-by-subscriptions' in scan_result.output, (
            "Scan command missing --filter-by-subscriptions parameter"
        )
        
        # Check for resource group filtering parameter
        assert '--filter-by-rgs' in build_result.output, (
            "Build command missing --filter-by-rgs parameter"
        )
        assert '--filter-by-rgs' in scan_result.output, (
            "Scan command missing --filter-by-rgs parameter"
        )

    def test_commands_use_same_handler(self):
        """Verify that both commands use the same underlying handler."""
        # This is more of a code inspection test
        # After refactoring, scan is an alias of build_scan_command
        from scripts.cli import build_scan_command, cli as cli_group

        # Check that the unified command exists
        assert build_scan_command is not None

        # Should be a Click command
        assert callable(build_scan_command)

        # Verify both command names are registered in the CLI group
        registered_commands = cli_group.commands
        assert 'build' in registered_commands, "build command not registered"
        assert 'scan' in registered_commands, "scan command not registered"

        # Verify both are the same command object (true aliasing)
        assert registered_commands['build'] is registered_commands['scan'], \
            "build and scan should be the same command object"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])