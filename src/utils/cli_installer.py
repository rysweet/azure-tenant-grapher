import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

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
        print(f"Tool '{tool}' is not registered in the tool registry.")
        return False
    tool_obj = TOOL_REGISTRY[tool]
    installer = detect_installer()
    if installer is None:
        print("No supported package manager detected on this system.")
        return False
    if installer not in tool_obj.installers:
        print(f"Tool '{tool}' does not support installer '{installer}'.")
        return False
    cmd = tool_obj.installers[installer]
    print(f"Installing {tool} using {installer}: {cmd}")
    proceed = input("Proceed? [y/N] ").strip().lower()
    if proceed == "y":
        print(cmd)
        try:
            subprocess.run(cmd, shell=True, check=True)
            print(f"Successfully installed {tool}.")
        except subprocess.CalledProcessError:
            print(f"Failed to install {tool}.")
        return True
    else:
        print("Installation cancelled.")
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
            print(f"Aborting: '{tool}' is required but was not installed.", flush=True)
            import sys

            sys.exit(1)
    else:
        print(f"Aborting: '{tool}' is required but was not installed.", flush=True)
        import sys

        sys.exit(1)


# Pre-register core tools
register_tool(
    Tool(
        name="terraform",
        test_cmd="terraform --version",
        installers={
            "brew": "brew install terraform",
            "apt": "sudo apt-get update && sudo apt-get install -y terraform",
            "winget": "winget install HashiCorp.Terraform",
            "choco": "choco install terraform -y",
        },
    )
)
register_tool(
    Tool(
        name="az",
        test_cmd="az --version",
        installers={
            "brew": "brew install azure-cli",
            "apt": "sudo apt-get update && sudo apt-get install -y azure-cli",
            "winget": "winget install Microsoft.AzureCLI",
            "choco": "choco install azure-cli -y",
        },
    )
)

register_tool(
    Tool(
        name="bicep",
        test_cmd="bicep --version",
        installers={
            "brew": "brew tap azure/bicep && brew install bicep",
            "apt": "curl -Lo bicep https://github.com/Azure/bicep/releases/latest/download/bicep-linux-x64 && chmod +x ./bicep && sudo mv ./bicep /usr/local/bin/bicep",
            "winget": "winget install -e --id Microsoft.Bicep",
            "choco": "choco install bicep",
        },
    )
)
