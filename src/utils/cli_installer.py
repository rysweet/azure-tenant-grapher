import platform
import shlex
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


def _is_interactive_mode() -> bool:
    """Check if we're in interactive mode (has TTY)."""
    import sys

    try:
        return sys.stdin.isatty()
    except (AttributeError, OSError):
        # If stdin doesn't have isatty or raises an error, assume non-interactive
        return False


def _run_command_safely(cmd_string: str) -> None:
    """Run a command string safely without shell=True.

    Handles commands with && by splitting and running sequentially.
    Uses shlex.split() to parse command arguments safely.

    Args:
        cmd_string: Command string from trusted registry (NOT user input)

    Raises:
        subprocess.CalledProcessError: If any command fails
    """
    # Split on && to handle chained commands (e.g., "apt update && apt install")
    # This is safe because commands come from our trusted TOOL_REGISTRY
    commands = [c.strip() for c in cmd_string.split("&&")]

    for cmd in commands:
        if not cmd:
            continue
        # Use shlex.split to properly parse the command into arguments
        args = shlex.split(cmd)
        subprocess.run(args, check=True)


def install_tool(tool: str, non_interactive: bool = False) -> bool:
    """Prompt user to install the tool using the detected package manager.
    Returns True if install attempted, False if declined or not possible.

    Args:
        tool: Name of the tool to install
        non_interactive: If True, skip interactive prompt and return False
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
    print(str(f"Installing {tool} using {installer}: {cmd}"))

    # Check if running in non-interactive mode
    is_non_interactive = non_interactive or not _is_interactive_mode()

    if is_non_interactive:
        print("Non-interactive mode detected. Skipping installation prompt.")
        print(str(f"Please install {tool} manually using: {cmd}"))
        return False

    proceed = input("Proceed? [y/N] ").strip().lower()
    if proceed == "y":
        print(cmd)
        try:
            # Use _run_command_safely to avoid shell=True (Issue #477)
            _run_command_safely(cmd)
            print(str(f"Successfully installed {tool}."))
        except subprocess.CalledProcessError:
            print(str(f"Failed to install {tool}."))
        return True
    else:
        print("Installation cancelled.")
        return False


def ensure_tool(
    tool: str, auto_prompt: bool = True, non_interactive: bool = False
) -> None:
    """
    Ensure the given CLI tool is installed (by name, must be registered).
    If not installed and auto_prompt is True, prompt to install.
    If user declines, aborts the command with a message.

    Args:
        tool: Name of the tool to check/install
        auto_prompt: If True, prompt user to install if missing
        non_interactive: If True, skip interactive prompts (for background/CI mode)
    """
    import sys

    if tool not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool}' is not registered in TOOL_REGISTRY.")
    if is_tool_installed(tool):
        return

    # Detect non-interactive mode
    is_non_interactive = non_interactive or not _is_interactive_mode()

    if auto_prompt and not is_non_interactive:
        installed = install_tool(tool, non_interactive=False)
        if not installed:
            print(f"Aborting: '{tool}' is required but was not installed.", flush=True)
            sys.exit(1)
    else:
        if is_non_interactive:
            print(
                f"Error: '{tool}' is required but not installed (non-interactive mode).",
                flush=True,
            )
            print(
                f"Please install {tool} manually before running this command.",
                flush=True,
            )
        else:
            print(f"Aborting: '{tool}' is required but was not installed.", flush=True)
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
