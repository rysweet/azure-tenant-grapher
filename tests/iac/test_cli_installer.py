import types

import pytest

import src.utils.cli_installer as cli_installer


@pytest.mark.parametrize(
    "tool,which_result,expected",
    [
        ("terraform", "/usr/local/bin/terraform", True),
        ("az", None, False),
    ],
)
def test_is_tool_installed(monkeypatch, tool, which_result, expected):
    monkeypatch.setattr(
        cli_installer.shutil,
        "which",
        lambda name: which_result if name == tool else None,
    )
    assert cli_installer.is_tool_installed(tool) is expected


@pytest.mark.parametrize(
    "system,which_map,expected",
    [
        ("Darwin", {"brew": "/usr/local/bin/brew"}, "brew"),
        ("Linux", {"apt": "/usr/bin/apt"}, "apt"),
        ("Windows", {"winget": "C:\\winget.exe"}, "winget"),
        ("Windows", {"winget": None, "choco": "C:\\choco.exe"}, "choco"),
        ("Linux", {"apt": None}, None),
    ],
)
def test_detect_installer(monkeypatch, system, which_map, expected):
    monkeypatch.setattr(cli_installer.platform, "system", lambda: system)

    def fake_which(name):
        return which_map.get(name)

    monkeypatch.setattr(cli_installer.shutil, "which", fake_which)
    assert cli_installer.detect_installer() == expected


@pytest.mark.parametrize(
    "tool_name",
    list(cli_installer.TOOL_REGISTRY.keys()),
)
@pytest.mark.parametrize(
    "installer",
    ["brew", "apt", "winget", "choco"],
)
def test_install_tool_runs(monkeypatch, tool_name, installer, capsys):
    # Get the tool object and its installer command for this package manager
    tool_obj = cli_installer.TOOL_REGISTRY[tool_name]
    cmd = tool_obj.installers.get(installer)
    if not cmd:
        pytest.skip(f"{tool_name} does not support installer {installer}")
    # Patch detect_installer to return the desired installer
    monkeypatch.setattr(cli_installer, "detect_installer", lambda: installer)
    # Patch _is_interactive_mode to return True (simulate interactive terminal)
    monkeypatch.setattr(cli_installer, "_is_interactive_mode", lambda: True)
    # Patch input to simulate user confirmation
    monkeypatch.setattr("builtins.input", lambda _: "y")
    # Patch subprocess.run to check the command
    # Note: After Issue #477 fix, commands are passed as lists without shell=True
    called_commands = []

    def fake_run(command, check=False):
        called_commands.append(command)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_installer.subprocess, "run", fake_run)
    cli_installer.install_tool(tool_name)
    out = capsys.readouterr().out
    assert cmd in out
    # Verify command was called as a list (Issue #477 security fix)
    assert len(called_commands) >= 1
    # For chained commands (e.g., "cmd1 && cmd2"), multiple calls are made
    for called_cmd in called_commands:
        assert isinstance(called_cmd, list), "Commands should be passed as lists, not strings"


def test_install_tool_cancel(monkeypatch, capsys):
    monkeypatch.setattr(cli_installer, "detect_installer", lambda: "brew")
    # Patch _is_interactive_mode to return True (simulate interactive terminal)
    monkeypatch.setattr(cli_installer, "_is_interactive_mode", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    called = {}
    monkeypatch.setattr(
        cli_installer.subprocess,
        "run",
        lambda *a, **k: called.setdefault("called", True),
    )
    cli_installer.install_tool("terraform")
    out = capsys.readouterr().out
    assert "Installation cancelled." in out
    assert "called" not in called


def test_install_tool_no_installer(monkeypatch, capsys):
    monkeypatch.setattr(cli_installer, "detect_installer", lambda: None)
    cli_installer.install_tool("terraform")
    out = capsys.readouterr().out
    assert "No supported package manager detected" in out


def test_install_tool_unknown_tool(monkeypatch, capsys):
    monkeypatch.setattr(cli_installer, "detect_installer", lambda: "brew")
    cli_installer.install_tool("notarealtool")
    out = capsys.readouterr().out
    assert "is not registered" in out


def test_doctor_checks_all_registered_tools(monkeypatch, capsys):
    # Import the doctor command from scripts.cli
    import importlib

    cli_mod = importlib.import_module("scripts.cli")

    # Prepare a fake TOOL_REGISTRY with 3 tools
    class FakeTool:
        def __init__(self, name):
            self.name = name

    fake_tools = {
        "foo": FakeTool("foo"),
        "bar": FakeTool("bar"),
        "baz": FakeTool("baz"),
    }

    # Patch TOOL_REGISTRY in src.utils.cli_installer
    monkeypatch.setattr(cli_mod, "is_tool_installed", lambda name: name == "bar")
    monkeypatch.setattr(
        cli_mod, "install_tool", lambda name: print(f"install_tool({name}) called")
    )
    # Patch TOOL_REGISTRY import in doctor
    import src.utils.cli_installer as cli_installer_mod

    monkeypatch.setattr(cli_installer_mod, "TOOL_REGISTRY", dict(fake_tools))

    # Patch import in doctor to return our fake registry
    def fake_import(name, *args, **kwargs):
        if name == "src.utils.cli_installer":
            return cli_installer_mod
        return importlib.import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    # Patch print to capture output
    # (but capsys should capture stdout)
    cli_mod.doctor.callback()
    out = capsys.readouterr().out

    # Check that all tools were checked and correct status printed
    assert "Checking for 'foo' CLI..." in out
    assert "Checking for 'bar' CLI..." in out
    assert "Checking for 'baz' CLI..." in out
    assert "✅ bar is installed." in out
    assert "❌ foo is NOT installed." in out
    assert "❌ baz is NOT installed." in out
    assert "install_tool(foo) called" in out
    assert "install_tool(baz) called" in out
    assert "Doctor check complete." in out


def test_bicep_install_commands():
    """Test that Bicep tool has correct install commands for each platform."""
    bicep_tool = cli_installer.TOOL_REGISTRY["bicep"]

    # Test macOS Homebrew command (with tap)
    assert "brew" in bicep_tool.installers
    assert bicep_tool.installers["brew"] == "brew tap azure/bicep && brew install bicep"

    # Test Linux command (manual download)
    assert "apt" in bicep_tool.installers
    expected_linux = "curl -Lo bicep https://github.com/Azure/bicep/releases/latest/download/bicep-linux-x64 && chmod +x ./bicep && sudo mv ./bicep /usr/local/bin/bicep"
    assert bicep_tool.installers["apt"] == expected_linux

    # Test Windows winget command (with --id flag)
    assert "winget" in bicep_tool.installers
    assert bicep_tool.installers["winget"] == "winget install -e --id Microsoft.Bicep"

    # Test Windows choco command
    assert "choco" in bicep_tool.installers
    assert bicep_tool.installers["choco"] == "choco install bicep"


@pytest.mark.parametrize(
    "installer,expected_cmd",
    [
        ("brew", "brew tap azure/bicep && brew install bicep"),
        (
            "apt",
            "curl -Lo bicep https://github.com/Azure/bicep/releases/latest/download/bicep-linux-x64 && chmod +x ./bicep && sudo mv ./bicep /usr/local/bin/bicep",
        ),
        ("winget", "winget install -e --id Microsoft.Bicep"),
        ("choco", "choco install bicep"),
    ],
)
def test_bicep_install_command_selection(monkeypatch, installer, expected_cmd, capsys):
    """Test that the correct Bicep install command is selected for each platform.

    Note: After Issue #477 fix, commands are passed as lists without shell=True.
    Chained commands (with &&) are split and executed separately.
    """
    # Patch detect_installer to return the specific installer
    monkeypatch.setattr(cli_installer, "detect_installer", lambda: installer)
    # Patch _is_interactive_mode to return True (simulate interactive terminal)
    monkeypatch.setattr(cli_installer, "_is_interactive_mode", lambda: True)
    # Patch input to simulate user confirmation
    monkeypatch.setattr("builtins.input", lambda _: "y")
    # Patch subprocess.run to capture the command
    # Note: After Issue #477 fix, commands are passed as lists without shell=True
    called_commands = []

    def fake_run(command, check=False):
        called_commands.append(command)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_installer.subprocess, "run", fake_run)

    # Run the install_tool function for bicep
    cli_installer.install_tool("bicep")

    # Verify command was called as a list (Issue #477 security fix)
    assert len(called_commands) >= 1
    for called_cmd in called_commands:
        assert isinstance(called_cmd, list), "Commands should be passed as lists, not strings"

    # Also verify the command appears in the output
    out = capsys.readouterr().out
    assert expected_cmd in out
