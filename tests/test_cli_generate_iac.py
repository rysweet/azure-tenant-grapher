"""Tests for generate-iac CLI command.

Tests the CLI integration for IaC generation functionality.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch


class TestGenerateIacCLI:
    """Test cases for generate-iac CLI command."""

    @patch("src.iac.cli_handler.get_neo4j_driver_from_config")
    @patch("src.utils.cli_installer.is_tool_installed", return_value=True)
    def test_generate_iac_dry_run_success(self, mock_is_tool, mock_get_driver) -> None:
        """Test generate-iac command with --dry-run flag exits with code 0."""
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []  # Empty result
        mock_get_driver.return_value = mock_driver

        result = subprocess.run(
            ["uv", "run", "scripts/cli.py", "generate-iac", "--dry-run"],
            capture_output=True,
            text=True,
        )

        # Should exit with code 0
        assert result.returncode == 0
        # Should contain JSON output in dry-run mode
        assert "resources" in result.stdout

    @patch("src.iac.cli_handler.get_neo4j_driver_from_config")
    @patch("src.utils.cli_installer.is_tool_installed", return_value=True)
    def test_generate_iac_with_format_option(
        self, mock_is_tool, mock_get_driver
    ) -> None:
        """Test generate-iac command with different format options."""
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []  # Empty result
        mock_get_driver.return_value = mock_driver

        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/cli.py",
                "generate-iac",
                "--format",
                "terraform",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Test that JSON contains format info
        if "resources" in result.stdout:
            # Try to parse JSON from output
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip().startswith("{"):
                    try:
                        data = json.loads(line)
                        if "format" in data:
                            assert data["format"] == "terraform"
                    except json.JSONDecodeError:
                        pass  # Not all lines will be JSON

    @patch("src.iac.cli_handler.get_neo4j_driver_from_config")
    @patch("src.utils.cli_installer.is_tool_installed", return_value=True)
    def test_generate_iac_with_resource_filters(
        self, mock_is_tool, mock_get_driver
    ) -> None:
        """Test generate-iac command with resource filters."""
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []  # Empty result
        mock_get_driver.return_value = mock_driver

        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/cli.py",
                "generate-iac",
                "--resource-filters",
                "Microsoft.Compute/virtualMachines,Microsoft.Storage/storageAccounts",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # NOTE: Can't check mock_session.run in subprocess, so only check output
        assert "resources" in result.stdout

    def test_generate_iac_invalid_format(self) -> None:
        """Test generate-iac command with invalid format option."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/cli.py",
                "generate-iac",
                "--format",
                "invalid-format",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )

        # Should fail with invalid choice
        assert result.returncode != 0
        assert (
            "Invalid value for '--format'" in result.stdout
            or "invalid choice" in result.stdout.lower()
        )

    def test_generate_iac_help(self) -> None:
        """Test generate-iac command help output."""
        result = subprocess.run(
            ["uv", "run", "scripts/cli.py", "generate-iac", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Generate Infrastructure-as-Code templates" in result.stdout
        assert "--format" in result.stdout
        assert "--dry-run" in result.stdout

    @patch("src.iac.cli_handler.get_neo4j_driver_from_config")
    @patch("src.utils.cli_installer.is_tool_installed", return_value=True)
    def test_generate_iac_with_domain_name_option(
        self, mock_is_tool, mock_get_driver
    ) -> None:
        """
        Test generate-iac command with --domain-name option sets userPrincipalName/email for user accounts.
        """
        # Mock the Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        # Return a sample user resource
        mock_session.run.return_value = [
            MagicMock(
                __getitem__=lambda self, key: {
                    "r": {
                        "id": "user-1",
                        "name": "alice",
                        "type": "user",
                        "relationships": [],
                    },
                    "rels": [],
                }[key],
                __contains__=lambda self, key: key in ["r", "rels"],
            )
        ]
        mock_get_driver.return_value = mock_driver

        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/cli.py",
                "generate-iac",
                "--domain-name",
                "example.com",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed and output should include the specified domain
        assert result.returncode == 0
        assert "example.com" in result.stdout
        assert "userPrincipalName" in result.stdout or "email" in result.stdout


class TestGenerateIacCLIIntegration:
    """Integration tests for generate-iac CLI command."""

    def test_cli_command_is_registered(self) -> None:
        """Test that generate-iac command is properly registered."""
        result = subprocess.run(
            ["uv", "run", "scripts/cli.py", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # The command should be listed in the help output
        assert "generate-iac" in result.stdout

    @patch("src.iac.cli_handler.get_neo4j_driver_from_config")
    @patch("src.utils.cli_installer.is_tool_installed", return_value=True)
    def test_command_dry_run_shows_sample_output(
        self, mock_is_tool, mock_get_driver
    ) -> None:
        """Test that dry-run mode shows sample JSON output."""
        # Mock the Neo4j driver to return sample data
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock a record with sample resource data
        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda key: {
            "r": {
                "id": "vm-1",
                "name": "test-vm",
                "type": "Microsoft.Compute/virtualMachines",
            },
            "rels": [],
        }[key]
        mock_record.__contains__.side_effect = lambda key: key in ["r", "rels"]

        mock_session.run.return_value = [mock_record]
        mock_get_driver.return_value = mock_driver

        result = subprocess.run(
            ["uv", "run", "scripts/cli.py", "generate-iac", "--dry-run"],
            capture_output=True,
            text=True,
        )

        # Should succeed and show JSON output
        assert result.returncode == 0

        # Look for JSON in output (check if the entire output can be parsed as JSON)
        has_json = False
        try:
            # Try to parse the entire output as JSON
            data = json.loads(result.stdout.strip())
            if "resources" in data:
                has_json = True
        except json.JSONDecodeError:
            # If that fails, look for JSON block in the output
            output_lines = result.stdout.strip().split("\n")
            json_start = -1
            for i, line in enumerate(output_lines):
                if line.strip().startswith("{"):
                    json_start = i
                    break

            if json_start >= 0:
                # Try to parse from the first { to the end
                json_text = "\n".join(output_lines[json_start:])
                try:
                    data = json.loads(json_text)
                    if "resources" in data:
                        has_json = True
                except json.JSONDecodeError:
                    pass

        assert has_json, f"Expected JSON output in dry-run mode, got: {result.stdout}"
