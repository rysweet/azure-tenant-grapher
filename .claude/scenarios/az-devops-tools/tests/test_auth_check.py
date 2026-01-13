"""Tests for auth_check module."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from ..auth_check import (
    AuthStatus,
    check_auth,
    check_az_cli_installed,
    check_devops_extension,
    check_logged_in,
)
from ..common import ExitCode


class TestAuthStatus:
    """Test AuthStatus dataclass."""

    def test_init_defaults(self):
        """Test AuthStatus initializes with defaults."""
        status = AuthStatus()
        assert status.errors == []
        assert status.warnings == []
        assert not status.is_ready

    def test_is_ready_all_true(self):
        """Test is_ready when all checks pass."""
        status = AuthStatus(
            az_cli_installed=True,
            logged_in=True,
            devops_extension_installed=True,
            org_configured=True,
            project_configured=True,
            org_accessible=True,
            project_accessible=True,
        )
        assert status.is_ready

    def test_is_ready_missing_requirement(self):
        """Test is_ready fails if any check fails."""
        status = AuthStatus(
            az_cli_installed=True,
            logged_in=False,  # Missing this
            devops_extension_installed=True,
            org_configured=True,
            project_configured=True,
            org_accessible=True,
            project_accessible=True,
        )
        assert not status.is_ready


class TestCheckFunctions:
    """Test individual check functions."""

    @patch("shutil.which")
    def test_check_az_cli_installed_success(self, mock_which):
        """Test az CLI check when installed."""
        mock_which.return_value = "/usr/bin/az"
        installed, error = check_az_cli_installed()
        assert installed is True
        assert error is None

    @patch("shutil.which")
    def test_check_az_cli_installed_missing(self, mock_which):
        """Test az CLI check when not installed."""
        mock_which.return_value = None
        installed, error = check_az_cli_installed()
        assert installed is False
        assert "Azure CLI" in error
        assert "install" in error.lower()

    @patch("subprocess.run")
    def test_check_logged_in_success(self, mock_run):
        """Test login check when logged in."""
        mock_run.return_value = Mock(returncode=0, stdout='{"name": "test"}')
        logged_in, error = check_logged_in()
        assert logged_in is True
        assert error is None

    @patch("subprocess.run")
    def test_check_logged_in_not_logged_in(self, mock_run):
        """Test login check when not logged in."""
        mock_run.return_value = Mock(returncode=1, stderr="Please run 'az login'")
        logged_in, error = check_logged_in()
        assert logged_in is False
        assert error is not None

    @patch("subprocess.run")
    def test_check_devops_extension_installed(self, mock_run):
        """Test DevOps extension check."""
        mock_run.return_value = Mock(returncode=0, stdout="azure-devops")
        installed, error = check_devops_extension()
        assert installed is True
        assert error is None

    @patch("subprocess.run")
    def test_check_devops_extension_missing(self, mock_run):
        """Test DevOps extension check when missing."""
        mock_run.return_value = Mock(returncode=0, stdout="")
        installed, error = check_devops_extension()
        assert installed is False
        assert "extension" in error.lower()


class TestCheckAuth:
    """Test main check_auth function."""

    @patch("..auth_check.check_az_cli_installed")
    @patch("..auth_check.check_logged_in")
    @patch("..auth_check.check_devops_extension")
    def test_check_auth_all_pass(
        self, mock_ext, mock_login, mock_cli
    ):
        """Test check_auth when all checks pass."""
        mock_cli.return_value = (True, None)
        mock_login.return_value = (True, None)
        mock_ext.return_value = (True, None)

        status = check_auth(org="https://dev.azure.com/test", project="TestProject")
        assert status.az_cli_installed
        assert status.logged_in
        assert status.devops_extension_installed

    @patch("..auth_check.check_az_cli_installed")
    def test_check_auth_cli_missing(self, mock_cli):
        """Test check_auth when CLI missing."""
        mock_cli.return_value = (False, "CLI not found")

        status = check_auth()
        assert not status.az_cli_installed
        assert not status.is_ready
        assert len(status.errors) > 0
