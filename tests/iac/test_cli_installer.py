import sys
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
    monkeypatch.setattr(cli_installer.shutil, "which", lambda name: which_result if name == tool else None)
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

import copy

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
    # Patch input to simulate user confirmation
    monkeypatch.setattr("builtins.input", lambda _: "y")
    # Patch subprocess.run to check the command
    called = {}
    def fake_run(command, shell, check):
        called["cmd"] = command
        called["shell"] = shell
        called["check"] = check
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(cli_installer.subprocess, "run", fake_run)
    cli_installer.install_tool(tool_name)
    out = capsys.readouterr().out
    assert cmd in out
    assert called["cmd"] == cmd
    assert called["shell"] is True
    assert called["check"] is True

def test_install_tool_cancel(monkeypatch, capsys):
    monkeypatch.setattr(cli_installer, "detect_installer", lambda: "brew")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    called = {}
    monkeypatch.setattr(cli_installer.subprocess, "run", lambda *a, **k: called.setdefault("called", True))
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