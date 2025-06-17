import shutil
import platform
import subprocess
from typing import Literal, Optional, Dict
from dataclasses import dataclass, field

# Tool registry modularization for CLI dependencies.
# Example:
# register_tool(Tool(
#     name="bicep",
#     test_cmd="bicep --version",
#     installers={"brew": "brew install bicep", "apt": "...", "winget": "...", "choco": "..."}
# ))

@dataclass
class Tool:
    name: str
    test_cmd: str
    installers: Dict[str, str] = field(default_factory=dict)

TOOL_REGISTRY: Dict[str, Tool] = {}

def register_tool(tool: Tool) -> None:
    """Register a CLI tool in the global registry."""
    TOOL_REGISTRY[tool.name] = tool

def is_tool_installed(name: str) -> bool:
    """Check if a CLI tool is installed and available in PATH."""
    return shutil.which(name) is not None

def detect_installer() -> Optional[Literal["brew", "apt", "winget", "choco"]]:
    """Detect the system's package manager."""
    system = platform.system()
    if system == "Darwin":
        if shutil.which("brew"):
            return "brew"
    elif system == "Linux":
        if shutil.which("apt"):
            return "apt"
    elif system == "Windows":
        if shutil.which("winget"):
            return "winget"
        if shutil.which("choco"):
            return "choco"
    return None

def install_tool(tool: str) -> bool:
    """Prompt user to install the tool using the detected package manager.
    Returns True if install attempted, False if declined or not possible.
    """
    if tool not in TOOL_REGISTRY:
        print(f"Tool '{tool}' is not registered. Please register it before use.")
        print("Run `atg doctor` for more details.")
        return False
    tool_obj = TOOL_REGISTRY[tool]
    installer = detect_installer()
    if installer is None:
        print(f"No supported package manager detected. Please install '{tool}' manually.")
        print("Run `atg doctor` for more details.")
        return False
    if installer not in tool_obj.installers:
        print(f"No install command available for {tool} with {installer}.")
        print("Run `atg doctor` for more details.")
        return False
    cmd = tool_obj.installers[installer]
    print(f"Install command for {tool}:")
    print(f"  {cmd}")
    proceed = input("Proceed? [y/N] ").strip().lower()
    if proceed == "y":
        try:
            subprocess.run(cmd, shell=True, check=True)
            print(f"{tool} installation attempted. Please verify installation.")
        except subprocess.CalledProcessError as e:
            print(f"Installation failed: {e}")
        print("Run `atg doctor` for more details.")
        return True
    else:
        print("Installation cancelled.")
        print("Run `atg doctor` for more details.")
        return False

def ensure_tool(tool: str, auto_prompt: bool = True) -> None:
    """
    Ensure the given CLI tool is installed (by name, must be registered).
    If not installed and auto_prompt is True, prompt to install.
    If user declines, aborts the command with a message.
    """
    if tool not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool}' is not registered in TOOL_REGISTRY.")
    if is_tool_installed(tool):
        return
    if auto_prompt:
        installed = install_tool(tool)
        if not installed:
            print(f"Aborting: '{tool}' is required but was not installed.")
            import sys
            sys.exit(1)
    else:
        print(f"Required tool '{tool}' is not installed.")
        import sys
        sys.exit(1)

# Pre-register core tools
register_tool(Tool(
    name="terraform",
    test_cmd="terraform --version",
    installers={
        "brew": "brew install terraform",
        "apt": "sudo apt-get update && sudo apt-get install -y terraform",
        "winget": "winget install HashiCorp.Terraform",
        "choco": "choco install terraform -y",
    }
))
register_tool(Tool(
    name="az",
    test_cmd="az --version",
    installers={
        "brew": "brew install azure-cli",
        "apt": "sudo apt-get update && sudo apt-get install -y azure-cli",
        "winget": "winget install Microsoft.AzureCLI",
        "choco": "choco install azure-cli -y",
    }
))