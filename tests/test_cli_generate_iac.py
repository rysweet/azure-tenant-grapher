"""Tests for generate-iac CLI command.

Tests the CLI integration for IaC generation functionality.
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from scripts.cli import cli


class TestGenerateIacCLI:
    """Test cases for generate-iac CLI command."""
    
    @patch('src.iac.cli_handler.get_neo4j_driver_from_config')
    def test_generate_iac_dry_run_success(self, mock_get_driver) -> None:
        """Test generate-iac command with --dry-run flag exits with code 0."""
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []  # Empty result
        mock_get_driver.return_value = mock_driver
        
        runner = CliRunner()
        
        # Run with dry-run flag
        result = runner.invoke(cli, [
            'generate-iac',
            '--dry-run'
        ])
        
        # Should exit with code 0
        assert result.exit_code == 0
        # Should contain JSON output in dry-run mode
        assert "resources" in result.output
    
    @patch('src.iac.cli_handler.get_neo4j_driver_from_config')
    def test_generate_iac_with_format_option(self, mock_get_driver) -> None:
        """Test generate-iac command with different format options."""
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []  # Empty result
        mock_get_driver.return_value = mock_driver
        
        runner = CliRunner()
        
        # Test terraform format
        result = runner.invoke(cli, [
            'generate-iac',
            '--format', 'terraform',
            '--dry-run'
        ])
        assert result.exit_code == 0
        
        # Test that JSON contains format info
        if "resources" in result.output:
            # Try to parse JSON from output
            lines = result.output.strip().split('\n')
            for line in lines:
                if line.strip().startswith('{'):
                    try:
                        data = json.loads(line)
                        if "format" in data:
                            assert data["format"] == "terraform"
                    except json.JSONDecodeError:
                        pass  # Not all lines will be JSON
    
    @patch('src.iac.cli_handler.get_neo4j_driver_from_config')
    def test_generate_iac_with_resource_filters(self, mock_get_driver) -> None:
        """Test generate-iac command with resource filters."""
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []  # Empty result
        mock_get_driver.return_value = mock_driver
        
        runner = CliRunner()
        
        result = runner.invoke(cli, [
            'generate-iac',
            '--resource-filters', 'Microsoft.Compute/virtualMachines,Microsoft.Storage/storageAccounts',
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        # Verify that a custom filter query was used
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args[0]
        assert len(call_args) > 0
        query = call_args[0]
        assert "WHERE" in query  # Should contain WHERE clause for filtering
    
    def test_generate_iac_invalid_format(self) -> None:
        """Test generate-iac command with invalid format option."""
        runner = CliRunner()
        
        result = runner.invoke(cli, [
            'generate-iac',
            '--format', 'invalid-format',
            '--dry-run'
        ])
        
        # Should fail with invalid choice
        assert result.exit_code != 0
        assert "Invalid value for '--format'" in result.output or "invalid choice" in result.output.lower()
    
    def test_generate_iac_help(self) -> None:
        """Test generate-iac command help output."""
        runner = CliRunner()
        
        result = runner.invoke(cli, [
            'generate-iac',
            '--help'
        ])
        
        assert result.exit_code == 0
        assert "Generate Infrastructure-as-Code templates" in result.output
        assert "--format" in result.output
        assert "--dry-run" in result.output


class TestGenerateIacCLIIntegration:
    """Integration tests for generate-iac CLI command."""
    
    def test_cli_command_is_registered(self) -> None:
        """Test that generate-iac command is properly registered."""
        runner = CliRunner()
        
        # Get main help to see if command is listed
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        # The command should be listed in the help output
        assert "generate-iac" in result.output
    
    @patch('src.iac.cli_handler.get_neo4j_driver_from_config')
    def test_command_dry_run_shows_sample_output(self, mock_get_driver) -> None:
        """Test that dry-run mode shows sample JSON output."""
        # Mock the Neo4j driver to return sample data
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Mock a record with sample resource data
        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": {"id": "vm-1", "name": "test-vm", "type": "Microsoft.Compute/virtualMachines"},
            "rels": []
        }[key]
        mock_record.__contains__.side_effect = lambda key: key in ["r", "rels"]
        
        mock_session.run.return_value = [mock_record]
        mock_get_driver.return_value = mock_driver
        
        runner = CliRunner()
        
        # Run dry-run command
        result = runner.invoke(cli, ['generate-iac', '--dry-run'])
        
        # Should succeed and show JSON output
        assert result.exit_code == 0
        
        # Look for JSON in output (check if the entire output can be parsed as JSON)
        has_json = False
        try:
            # Try to parse the entire output as JSON
            data = json.loads(result.output.strip())
            if "resources" in data:
                has_json = True
        except json.JSONDecodeError:
            # If that fails, look for JSON block in the output
            output_lines = result.output.strip().split('\n')
            json_start = -1
            for i, line in enumerate(output_lines):
                if line.strip().startswith('{'):
                    json_start = i
                    break
            
            if json_start >= 0:
                # Try to parse from the first { to the end
                json_text = '\n'.join(output_lines[json_start:])
                try:
                    data = json.loads(json_text)
                    if "resources" in data:
                        has_json = True
                except json.JSONDecodeError:
                    pass
        
        assert has_json, f"Expected JSON output in dry-run mode, got: {result.output}"