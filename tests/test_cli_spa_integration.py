"""
Tests for SPA CLI integration (start/stop commands).
"""

import os
import tempfile
from unittest.mock import MagicMock, patch, mock_open, ANY
import pytest
from click.testing import CliRunner

from src.cli_commands import spa_start, spa_stop


class TestSPACommands:
    """Test the SPA start/stop CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        # Create a temporary outputs directory
        self.temp_dir = tempfile.mkdtemp()
        self.pidfile = os.path.join(self.temp_dir, "spa_server.pid")
        
    def teardown_method(self):
        """Clean up after tests."""
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('src.cli_commands.SPA_PIDFILE', new='test_spa.pid')
    @patch('src.cli_commands.shutil.which')
    @patch('src.cli_commands.subprocess.Popen')
    @patch('src.cli_commands.os.path.exists')
    @patch('src.cli_commands.os.makedirs')
    def test_spa_start_success(self, mock_makedirs, mock_exists, mock_popen, mock_which):
        """Test successful SPA start."""
        
        # Mock npm available
        mock_which.return_value = '/usr/bin/npm'
        
        # Mock file existence checks - PID file doesn't exist, but package.json and node_modules do
        def exists_side_effect(path):
            if 'spa_server.pid' in str(path) or 'test_spa.pid' in str(path):
                return False  # PID file doesn't exist
            elif 'package.json' in str(path):
                return True   # package.json exists
            elif 'node_modules' in str(path):
                return True   # node_modules exists
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock successful process start
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = self.runner.invoke(spa_start)
            
            assert result.exit_code == 0
            assert "SPA started" in result.output
            assert "12345" in result.output
            mock_popen.assert_called_once()

    @patch('src.cli_commands.shutil.which')
    def test_spa_start_no_npm(self, mock_which):
        """Test SPA start when npm is not installed."""
        mock_which.return_value = None
        
        result = self.runner.invoke(spa_start)
        
        assert result.exit_code == 0
        assert "npm is not installed" in result.output

    @patch('src.cli_commands.shutil.which')
    @patch('src.cli_commands.os.path.exists')
    def test_spa_start_already_running(self, mock_exists, mock_which):
        """Test SPA start when already running."""
        mock_which.return_value = '/usr/bin/npm'
        mock_exists.return_value = True  # PID file exists
        
        result = self.runner.invoke(spa_start)
        
        assert result.exit_code == 0
        assert "SPA already running" in result.output

    @patch('src.cli_commands.shutil.which')
    @patch('src.cli_commands.os.path.exists')
    def test_spa_start_no_package_json(self, mock_exists, mock_which):
        """Test SPA start when package.json doesn't exist."""
        mock_which.return_value = '/usr/bin/npm'
        mock_exists.side_effect = lambda path: (
            False if 'package.json' in path else
            False  # Nothing exists
        )
        
        result = self.runner.invoke(spa_start)
        
        assert result.exit_code == 0
        assert "SPA not found" in result.output

    @patch('src.cli_commands.os.kill')
    def test_spa_stop_success(self, mock_kill):
        """Test successful SPA stop."""
        # Create a real temporary PID file
        test_pidfile = os.path.join(self.temp_dir, 'test_spa.pid')
        with open(test_pidfile, 'w') as f:
            f.write('12345')
        
        with patch('src.cli_commands.SPA_PIDFILE', new=test_pidfile):
            result = self.runner.invoke(spa_stop)
            
            assert result.exit_code == 0
            assert "Sent SIGTERM" in result.output
            assert "SPA stopped" in result.output
            
            # Check kill was called with correct PID and signal
            import signal
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)
            
            # Check file was removed
            assert not os.path.exists(test_pidfile)

    @patch('src.cli_commands.os.path.exists')
    def test_spa_stop_not_running(self, mock_exists):
        """Test SPA stop when not running."""
        mock_exists.return_value = False
        
        result = self.runner.invoke(spa_stop)
        
        assert result.exit_code == 0
        assert "SPA is not running" in result.output

    @patch('src.cli_commands.os.kill')
    def test_spa_stop_kill_error(self, mock_kill):
        """Test SPA stop when kill fails."""
        # Create a real temporary PID file
        test_pidfile = os.path.join(self.temp_dir, 'test_spa2.pid')
        with open(test_pidfile, 'w') as f:
            f.write('12345')
        
        mock_kill.side_effect = ProcessLookupError("No such process")
        
        with patch('src.cli_commands.SPA_PIDFILE', new=test_pidfile):
            result = self.runner.invoke(spa_stop)
            
            assert result.exit_code == 0
            assert "Could not terminate SPA process" in result.output
            assert "SPA stopped" in result.output
            
            # Check file was removed despite error
            assert not os.path.exists(test_pidfile)

    @patch('src.cli_commands.shutil.which')
    @patch('src.cli_commands.subprocess.run')
    @patch('src.cli_commands.subprocess.Popen')
    @patch('src.cli_commands.os.path.exists')
    @patch('src.cli_commands.os.makedirs')
    def test_spa_start_install_dependencies(self, mock_makedirs, mock_exists, 
                                           mock_popen, mock_run, mock_which):
        """Test SPA start installs dependencies if needed."""
        mock_which.return_value = '/usr/bin/npm'
        
        # Mock file existence: package.json exists, node_modules doesn't
        mock_exists.side_effect = lambda path: (
            True if 'package.json' in path else
            False if 'node_modules' in path else
            False  # PID file doesn't exist
        )
        
        # Mock successful npm install
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock successful process start
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        with patch('builtins.open', mock_open()):
            result = self.runner.invoke(spa_start)
            
            assert result.exit_code == 0
            assert "Installing SPA dependencies" in result.output
            assert "Dependencies installed successfully" in result.output
            assert "SPA started" in result.output
            mock_run.assert_called_once()
            mock_popen.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])