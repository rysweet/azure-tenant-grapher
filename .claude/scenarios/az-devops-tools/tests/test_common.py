"""Tests for common utilities module."""

from unittest.mock import Mock, patch

import pytest

from ..common import (
    AzCliWrapper,
    CommandResult,
    ExitCode,
    format_table,
    load_config,
    parse_work_item_id,
)


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_command_result_success(self):
        """Test successful command result."""
        result = CommandResult(
            returncode=0,
            stdout="output",
            stderr="",
            success=True,
        )
        assert result.success
        assert result.returncode == 0

    def test_command_result_failure(self):
        """Test failed command result."""
        result = CommandResult(
            returncode=1,
            stdout="",
            stderr="error",
            success=False,
        )
        assert not result.success
        assert result.returncode == 1


class TestParseWorkItemId:
    """Test work item ID parsing."""

    def test_parse_valid_id(self):
        """Test parsing valid work item ID."""
        assert parse_work_item_id("12345") == 12345
        assert parse_work_item_id("1") == 1

    def test_parse_invalid_id_negative(self):
        """Test parsing negative ID raises error."""
        with pytest.raises(ValueError) as exc:
            parse_work_item_id("-1")
        assert "positive" in str(exc.value).lower()

    def test_parse_invalid_id_zero(self):
        """Test parsing zero raises error."""
        with pytest.raises(ValueError) as exc:
            parse_work_item_id("0")
        assert "positive" in str(exc.value).lower()

    def test_parse_invalid_id_non_numeric(self):
        """Test parsing non-numeric ID raises error."""
        with pytest.raises(ValueError) as exc:
            parse_work_item_id("abc")
        assert "Invalid work item ID" in str(exc.value)

    def test_parse_invalid_id_empty(self):
        """Test parsing empty ID raises error."""
        with pytest.raises(ValueError):
            parse_work_item_id("")


class TestFormatTable:
    """Test table formatting."""

    def test_format_table_basic(self):
        """Test basic table formatting."""
        headers = ["ID", "Title", "State"]
        rows = [
            ["1", "First Item", "Active"],
            ["2", "Second Item", "Closed"],
        ]
        result = format_table(headers, rows)

        assert "ID" in result
        assert "Title" in result
        assert "First Item" in result
        assert "Second Item" in result

    def test_format_table_empty(self):
        """Test table with no rows."""
        headers = ["ID", "Title"]
        rows = []
        result = format_table(headers, rows)

        assert "ID" in result
        assert "Title" in result

    def test_format_table_alignment(self):
        """Test table column alignment."""
        headers = ["Short", "Very Long Header"]
        rows = [["a", "b"]]
        result = format_table(headers, rows)

        # Should handle column width properly
        assert len(result) > 0


class TestLoadConfig:
    """Test configuration loading."""

    def test_load_config_from_args(self):
        """Test config loaded from arguments."""
        config = load_config(org="https://dev.azure.com/test", project="TestProject")
        assert config["org"] == "https://dev.azure.com/test"
        assert config["project"] == "TestProject"

    @patch.dict("os.environ", {"AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/env-org"})
    def test_load_config_from_env(self):
        """Test config loaded from environment."""
        config = load_config()
        assert config.get("org") == "https://dev.azure.com/env-org"

    def test_load_config_args_override_env(self):
        """Test args override environment variables."""
        with patch.dict("os.environ", {"AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/env-org"}):
            config = load_config(org="https://dev.azure.com/arg-org")
            assert config["org"] == "https://dev.azure.com/arg-org"


class TestAzCliWrapper:
    """Test AzCliWrapper class."""

    def test_init(self):
        """Test wrapper initialization."""
        wrapper = AzCliWrapper(org="https://dev.azure.com/test", project="TestProject")
        assert wrapper.org == "https://dev.azure.com/test"
        assert wrapper.project == "TestProject"

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        wrapper = AzCliWrapper()
        result = wrapper.run_command(["az", "version"])

        assert result.success
        assert result.returncode == 0
        assert result.stdout == "output"

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test failed command execution."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error",
        )

        wrapper = AzCliWrapper()
        result = wrapper.run_command(["az", "invalid"])

        assert not result.success
        assert result.returncode == 1

    def test_devops_command(self):
        """Test DevOps command construction."""
        wrapper = AzCliWrapper(org="https://dev.azure.com/test", project="TestProject")

        with patch.object(wrapper, "run_command") as mock_run:
            mock_run.return_value = CommandResult(0, "", "", True)
            wrapper.devops_command(["work-item", "list"])

            # Should construct correct command
            call_args = mock_run.call_args[0][0]
            assert "az" in call_args
            assert "boards" in call_args or "devops" in call_args
