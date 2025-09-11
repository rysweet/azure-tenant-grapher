"""Test that scan and build commands have identical options."""

import click
from click.testing import CliRunner
from scripts.cli import cli


class TestScanBuildConsistency:
    """Test that scan and build commands are consistent."""
    
    def test_scan_and_build_have_same_options(self):
        """Verify that scan and build commands have identical options."""
        # Get the commands from the CLI group
        build_cmd = cli.commands.get('build')
        scan_cmd = cli.commands.get('scan')
        
        assert build_cmd is not None, "build command not found"
        assert scan_cmd is not None, "scan command not found"
        
        # Get option names for each command
        build_options = {param.name for param in build_cmd.params if isinstance(param, click.Option)}
        scan_options = {param.name for param in scan_cmd.params if isinstance(param, click.Option)}
        
        # Check that both commands have the same options
        missing_in_scan = build_options - scan_options
        missing_in_build = scan_options - build_options
        
        assert missing_in_scan == set(), f"Options in build but not in scan: {missing_in_scan}"
        assert missing_in_build == set(), f"Options in scan but not in build: {missing_in_build}"
        
    def test_scan_accepts_filter_options(self):
        """Test that scan command accepts filter options added in PR #229."""
        runner = CliRunner()
        
        # Test --filter-by-subscriptions
        result = runner.invoke(cli, ['scan', '--help'])
        assert result.exit_code == 0
        assert '--filter-by-subscriptions' in result.output, "scan command missing --filter-by-subscriptions option"
        
        # Test --filter-by-rgs  
        assert '--filter-by-rgs' in result.output, "scan command missing --filter-by-rgs option"
        
    def test_build_accepts_filter_options(self):
        """Test that build command has filter options from PR #229."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ['build', '--help'])
        assert result.exit_code == 0
        assert '--filter-by-subscriptions' in result.output, "build command missing --filter-by-subscriptions option"
        assert '--filter-by-rgs' in result.output, "build command missing --filter-by-rgs option"
        
    def test_scan_and_build_help_text_consistency(self):
        """Test that help text is consistent between scan and build."""
        runner = CliRunner()
        
        build_result = runner.invoke(cli, ['build', '--help'])
        scan_result = runner.invoke(cli, ['scan', '--help'])
        
        # Both should mention filtering
        assert 'filter' in build_result.output.lower() or 'subscription' in build_result.output.lower()
        assert 'filter' in scan_result.output.lower() or 'subscription' in scan_result.output.lower()
        
        # Both should have dashboard options
        assert '--no-dashboard' in build_result.output
        assert '--no-dashboard' in scan_result.output