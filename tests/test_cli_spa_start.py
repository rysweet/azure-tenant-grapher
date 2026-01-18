"""Test the atg start command for launching the SPA."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.commands.spa import spa_start


class TestSpaStartCommand:
    """Test suite for the SPA start command."""

    def test_spa_start_builds_if_dist_missing(self, tmp_path):
        """Test that spa_start builds the app if dist/ doesn't exist."""
        # Create a mock spa directory
        spa_dir = tmp_path / "spa"
        spa_dir.mkdir()

        # Create a minimal package.json
        package_json = {
            "name": "test-spa",
            "main": "dist/main/index.js",
            "scripts": {
                "build:main": "echo 'Building main'",
                "build:renderer": "echo 'Building renderer'",
                "build": "echo 'Building all'",
                "start": "electron .",
            },
        }

        import json

        with open(spa_dir / "package.json", "w") as f:
            json.dump(package_json, f)

        # Create node_modules to simulate installed deps
        (spa_dir / "node_modules").mkdir()

        runner = CliRunner()

        # Patch the PID file location to avoid conflicts
        with patch("src.cli_commands.SPA_PIDFILE", str(tmp_path / "spa.pid")):
            with patch("src.cli_commands.os.path.dirname") as mock_dirname:
                # First call returns parent of __file__, second call returns parent of that
                mock_dirname.side_effect = [str(tmp_path / "src"), str(tmp_path)]

                with patch("src.cli_commands.subprocess.run") as mock_run:
                    # First build call succeeds and creates the dist/main/index.js file
                    def side_effect(*args, **kwargs):
                        if args and "build" in str(args[0]):
                            # Create the expected build output
                            dist_main = spa_dir / "dist" / "main"
                            dist_main.mkdir(parents=True, exist_ok=True)
                            (dist_main / "index.js").write_text("// Built")
                        return MagicMock(returncode=0, stdout="Built successfully")

                    mock_run.side_effect = side_effect

                    with patch("src.cli_commands.subprocess.Popen") as mock_popen:
                        mock_proc = MagicMock()
                        mock_proc.pid = 12345
                        mock_popen.return_value = mock_proc

                        result = runner.invoke(spa_start, catch_exceptions=False)

                        # Print debug info
                        print(f"Result output: {result.output}")
                        print(f"Result exit code: {result.exit_code}")
                        print(f"Mock run calls: {mock_run.call_args_list}")

                        # Should call build before starting
                        build_calls = [
                            call
                            for call in mock_run.call_args_list
                            if any("build" in str(arg) for arg in call[0][0])
                        ]
                        assert len(build_calls) > 0, (
                            f"Should run build command when dist doesn't exist. Calls: {mock_run.call_args_list}"
                        )

                        assert result.exit_code == 0
                        assert "Building Electron app" in result.output

    def test_spa_start_checks_for_main_entry_point(self, tmp_path):
        """Test that spa_start verifies the main entry point exists after build."""
        spa_dir = tmp_path / "spa"
        spa_dir.mkdir()

        # Create package.json with main entry
        package_json = {
            "name": "test-spa",
            "main": "dist/main/index.js",
            "scripts": {"build": "echo 'Building'", "start": "electron ."},
        }

        import json

        with open(spa_dir / "package.json", "w") as f:
            json.dump(package_json, f)

        (spa_dir / "node_modules").mkdir()

        # Create the dist directory but NOT the main entry file
        (spa_dir / "dist" / "main").mkdir(parents=True)
        # Don't create index.js to simulate failed build

        runner = CliRunner()

        # Patch the PID file location to avoid conflicts
        with patch("src.cli_commands.SPA_PIDFILE", str(tmp_path / "spa.pid")):
            with patch("src.cli_commands.os.path.dirname") as mock_dirname:
                mock_dirname.side_effect = [str(tmp_path / "src"), str(tmp_path)]

                with patch("src.cli_commands.subprocess.run") as mock_run:
                    # Simulate build completing
                    mock_run.return_value = MagicMock(returncode=0)

                    with patch("src.cli_commands.subprocess.Popen"):
                        # This should not be called if main entry doesn't exist
                        result = runner.invoke(spa_start, catch_exceptions=False)

                        # Should fail because main entry doesn't exist
                        assert (
                            result.exit_code != 0
                            or "not found" in result.output.lower()
                            or "doesn't exist" in result.output.lower()
                        ), "Should fail when main entry point doesn't exist after build"

    def test_spa_start_skips_build_if_dist_exists(self, tmp_path):
        """Test that spa_start skips build if dist/main/index.js already exists."""
        spa_dir = tmp_path / "spa"
        spa_dir.mkdir()

        package_json = {
            "name": "test-spa",
            "main": "dist/main/index.js",
            "scripts": {"start": "electron ."},
        }

        import json

        with open(spa_dir / "package.json", "w") as f:
            json.dump(package_json, f)

        # Create the built files
        (spa_dir / "node_modules").mkdir()
        (spa_dir / "dist" / "main").mkdir(parents=True)
        (spa_dir / "dist" / "main" / "index.js").write_text("// Main process")

        runner = CliRunner()

        # Patch the PID file location to avoid conflicts
        with patch("src.cli_commands.SPA_PIDFILE", str(tmp_path / "spa.pid")):
            with patch("src.cli_commands.os.path.dirname") as mock_dirname:
                mock_dirname.side_effect = [str(tmp_path / "src"), str(tmp_path)]

                with patch("src.cli_commands.subprocess.run") as mock_run:
                    with patch("src.cli_commands.subprocess.Popen") as mock_popen:
                        mock_proc = MagicMock()
                        mock_proc.pid = 12345
                        mock_popen.return_value = mock_proc

                        result = runner.invoke(spa_start, catch_exceptions=False)

                        # Should NOT call build
                        assert not any(
                            "build" in str(call) for call in mock_run.call_args_list
                        ), "Should not run build when dist/main/index.js exists"

                        assert result.exit_code == 0

    def test_spa_start_installs_deps_if_needed(self, tmp_path):
        """Test that spa_start installs dependencies if node_modules is missing."""
        spa_dir = tmp_path / "spa"
        spa_dir.mkdir()

        package_json = {
            "name": "test-spa",
            "main": "dist/main/index.js",
            "scripts": {"start": "electron ."},
        }

        import json

        with open(spa_dir / "package.json", "w") as f:
            json.dump(package_json, f)

        # Don't create node_modules to trigger install

        runner = CliRunner()

        # Patch the PID file location to avoid conflicts
        with patch("src.cli_commands.SPA_PIDFILE", str(tmp_path / "spa.pid")):
            with patch("src.cli_commands.os.path.dirname") as mock_dirname:
                mock_dirname.side_effect = [str(tmp_path / "src"), str(tmp_path)]

                with patch("src.cli_commands.subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    with patch("src.cli_commands.subprocess.Popen") as mock_popen:
                        mock_proc = MagicMock()
                        mock_proc.pid = 12345
                        mock_popen.return_value = mock_proc

                        # Create dist/main/index.js after "build" and node_modules after "install"
                        def side_effect(*args, **kwargs):
                            if "install" in str(args):
                                (spa_dir / "node_modules").mkdir(exist_ok=True)
                            elif "build" in str(args):
                                (spa_dir / "dist" / "main").mkdir(
                                    parents=True, exist_ok=True
                                )
                                (spa_dir / "dist" / "main" / "index.js").write_text(
                                    "// Main"
                                )
                            return MagicMock(returncode=0)

                        mock_run.side_effect = side_effect

                        result = runner.invoke(spa_start, catch_exceptions=False)

                        # Should call npm install
                        assert any(
                            "install" in str(call) for call in mock_run.call_args_list
                        ), "Should run npm install when node_modules doesn't exist"

                        assert result.exit_code == 0


class TestElectronAppIntegration:
    """Integration tests for the Electron app."""

    def test_electron_main_process_exists(self):
        """Verify the Electron main process file exists."""
        spa_dir = Path(__file__).parent.parent / "spa"
        main_file = spa_dir / "main" / "index.ts"

        assert main_file.exists(), f"Electron main process not found at {main_file}"

    def test_package_json_has_correct_main_entry(self):
        """Verify package.json points to the correct main entry."""
        spa_dir = Path(__file__).parent.parent / "spa"
        package_json_file = spa_dir / "package.json"

        assert package_json_file.exists(), "package.json not found"

        import json

        with open(package_json_file) as f:
            package = json.load(f)

        assert "main" in package, "package.json missing 'main' entry"
        assert package["main"] == "dist/main/index.js", (
            f"Expected main to be 'dist/main/index.js', got '{package['main']}'"
        )

    def test_build_scripts_exist(self):
        """Verify necessary build scripts exist in package.json."""
        spa_dir = Path(__file__).parent.parent / "spa"
        package_json_file = spa_dir / "package.json"

        import json

        with open(package_json_file) as f:
            package = json.load(f)

        required_scripts = ["build", "build:main", "build:renderer", "start"]

        for script in required_scripts:
            assert script in package.get("scripts", {}), (
                f"Missing required script '{script}' in package.json"
            )
