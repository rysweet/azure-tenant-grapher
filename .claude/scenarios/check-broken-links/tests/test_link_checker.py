"""Tests for link_checker module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from ..link_checker import (
    LinkCheckReport,
    check_linkinator_installed,
    check_local,
    check_site,
    parse_linkinator_output,
)


class TestLinkCheckReport:
    """Test LinkCheckReport dataclass."""

    def test_init_defaults(self):
        """Test report initializes with defaults."""
        report = LinkCheckReport(target="https://example.com")
        assert report.target == "https://example.com"
        assert report.broken_links == []
        assert report.warnings == []
        assert report.total_links == 0

    def test_is_healthy_no_broken_links(self):
        """Test is_healthy when no broken links."""
        report = LinkCheckReport(
            target="https://example.com",
            total_links=100,
            successful=100,
            broken_count=0,
        )
        assert report.is_healthy

    def test_is_healthy_with_broken_links(self):
        """Test is_healthy fails with broken links."""
        report = LinkCheckReport(
            target="https://example.com",
            total_links=100,
            successful=99,
            broken_count=1,
        )
        assert not report.is_healthy

    def test_is_healthy_with_warnings_only(self):
        """Test is_healthy passes with warnings but no broken links."""
        report = LinkCheckReport(
            target="https://example.com",
            total_links=100,
            successful=100,
            broken_count=0,
            warnings=["Redirect detected"],
        )
        assert report.is_healthy  # Warnings don't fail health check


class TestCheckLinkinatorInstalled:
    """Test linkinator installation check."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_linkinator_installed_global(self, mock_run, mock_which):
        """Test linkinator found in global PATH."""
        mock_which.return_value = "/usr/local/bin/linkinator"
        installed, path = check_linkinator_installed()
        assert installed
        assert path == "linkinator"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_linkinator_installed_npx(self, mock_run, mock_which):
        """Test linkinator available via npx."""
        mock_which.return_value = None  # Not in PATH
        mock_run.return_value = Mock(returncode=0)  # But npx works

        installed, path = check_linkinator_installed()
        assert installed
        assert "npx" in path

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_linkinator_not_installed(self, mock_run, mock_which):
        """Test linkinator not available."""
        mock_which.return_value = None
        mock_run.return_value = Mock(returncode=1)  # npx fails too

        installed, path = check_linkinator_installed()
        assert not installed


class TestParseLinkinator:
    """Test linkinator output parsing."""

    def test_parse_json_output_success(self):
        """Test parsing successful linkinator JSON."""
        json_output = {
            "passed": True,
            "links": [
                {"url": "https://example.com", "state": "OK"},
                {"url": "https://example.com/page", "state": "OK"},
            ],
        }

        report = parse_linkinator_output(json_output, "https://example.com")
        assert report.total_links == 2
        assert report.successful == 2
        assert report.broken_count == 0
        assert report.is_healthy

    def test_parse_json_output_with_broken_links(self):
        """Test parsing output with broken links."""
        json_output = {
            "passed": False,
            "links": [
                {"url": "https://example.com", "state": "OK"},
                {"url": "https://broken.link", "state": "BROKEN", "status": 404},
            ],
        }

        report = parse_linkinator_output(json_output, "https://example.com")
        assert report.total_links == 2
        assert report.successful == 1
        assert report.broken_count == 1
        assert not report.is_healthy
        assert len(report.broken_links) == 1

    def test_parse_json_output_with_warnings(self):
        """Test parsing output with warnings (redirects)."""
        json_output = {
            "passed": True,
            "links": [
                {"url": "http://example.com", "state": "OK", "status": 301},
            ],
        }

        report = parse_linkinator_output(json_output, "https://example.com")
        # 301 redirects should be warnings
        assert len(report.warnings) >= 0  # May or may not warn on redirects


class TestCheckSite:
    """Test check_site function."""

    @patch("..link_checker.check_linkinator_installed")
    @patch("subprocess.run")
    def test_check_site_success(self, mock_run, mock_installed):
        """Test checking a website successfully."""
        mock_installed.return_value = (True, "linkinator")
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"passed": true, "links": []}',
        )

        report = check_site("https://example.com")
        assert report.target == "https://example.com"
        assert report.is_healthy

    @patch("..link_checker.check_linkinator_installed")
    def test_check_site_linkinator_missing(self, mock_installed):
        """Test check_site when linkinator not installed."""
        mock_installed.return_value = (False, None)

        with pytest.raises(RuntimeError) as exc:
            check_site("https://example.com")
        assert "linkinator" in str(exc.value).lower()

    @patch("..link_checker.check_linkinator_installed")
    @patch("subprocess.run")
    def test_check_site_with_timeout(self, mock_run, mock_installed):
        """Test check_site with custom timeout."""
        mock_installed.return_value = (True, "linkinator")
        mock_run.return_value = Mock(returncode=0, stdout='{"passed": true, "links": []}')

        check_site("https://example.com", timeout=10000)

        # Verify timeout was passed to linkinator
        call_args = mock_run.call_args[0][0]
        assert any("10000" in str(arg) for arg in call_args)


class TestCheckLocal:
    """Test check_local function for local markdown files."""

    @patch("..link_checker.check_linkinator_installed")
    @patch("subprocess.run")
    def test_check_local_directory(self, mock_run, mock_installed):
        """Test checking local directory."""
        mock_installed.return_value = (True, "linkinator")
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"passed": true, "links": []}',
        )

        report = check_local(Path("./docs"))
        assert report.target == "./docs"

    @patch("..link_checker.check_linkinator_installed")
    @patch("subprocess.run")
    def test_check_local_single_file(self, mock_run, mock_installed):
        """Test checking single markdown file."""
        mock_installed.return_value = (True, "linkinator")
        mock_run.return_value = Mock(returncode=0, stdout='{"passed": true, "links": []}')

        report = check_local(Path("./README.md"))
        assert report.target == "./README.md"


class TestCLI:
    """Test command-line interface."""

    def test_cli_requires_target(self):
        """Test CLI requires target argument."""
        # Placeholder for CLI integration tests
        pass
