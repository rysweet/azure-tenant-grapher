"""CLI testing agent for command-line interface testing."""

import asyncio
import os
import shlex
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import CLIConfig
from ..models import CommandResult, TestStep
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CLIAgent:
    """Agent responsible for CLI testing."""

    def __init__(self, config: CLIConfig):
        """
        Initialize CLI testing agent.

        Args:
            config: CLI configuration
        """
        self.config = config
        self.base_command = config.base_command
        self.timeout = config.timeout
        self.env_vars = config.env_vars
        self.working_dir = Path(config.working_dir)

    async def execute_command(
        self,
        command: str,
        args: List[str],
        timeout: Optional[int] = None,
        input_text: Optional[str] = None,
    ) -> CommandResult:
        """
        Execute a CLI command and capture output.

        Args:
            command: Command to execute
            args: Command arguments
            timeout: Command timeout in seconds
            input_text: Optional input to send to command

        Returns:
            CommandResult with execution details
        """
        full_command = [*self.base_command, command, *args]
        cmd_str = " ".join(shlex.quote(str(arg)) for arg in full_command)

        logger.info(f"Executing: {cmd_str}")

        # Prepare environment
        env = {**os.environ, **self.env_vars}

        # Execute command
        start_time = time.time()
        try:
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=asyncio.subprocess.PIPE if input_text else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.working_dir,
            )

            # Send input if provided
            stdin_data = input_text.encode() if input_text else None

            # Wait for completion with timeout
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(input=stdin_data), timeout=timeout or self.timeout
            )

            duration = time.time() - start_time

            return CommandResult(
                command=command,
                args=args,
                stdout=stdout_data.decode("utf-8", errors="replace"),
                stderr=stderr_data.decode("utf-8", errors="replace"),
                returncode=process.returncode or 0,
                duration=duration,
                timestamp=datetime.now(),
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.error(f"Command timed out after {timeout}s: {cmd_str}")

            # Try to kill the process
            if "process" in locals():
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass

            return CommandResult(
                command=command,
                args=args,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                returncode=-1,
                duration=duration,
                timestamp=datetime.now(),
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Command execution failed: {e}")

            return CommandResult(
                command=command,
                args=args,
                stdout="",
                stderr=str(e),
                returncode=-1,
                duration=duration,
                timestamp=datetime.now(),
            )

    async def execute_test_step(self, step: TestStep) -> Dict[str, Any]:
        """
        Execute a single test step for CLI testing.

        Args:
            step: Test step to execute

        Returns:
            Result dictionary with execution details
        """
        if step.action == "execute":
            # Parse command and arguments
            parts = shlex.split(step.target)
            command = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []

            # Execute command
            result = await self.execute_command(
                command=command, args=args, timeout=step.timeout, input_text=step.value
            )

            # Verify expected result if specified
            success = True
            if step.expected is not None:
                if isinstance(step.expected, dict):
                    # Check specific fields
                    if "returncode" in step.expected:
                        success = success and (
                            result.returncode == step.expected["returncode"]
                        )
                    if "stdout_contains" in step.expected:
                        success = success and (
                            step.expected["stdout_contains"] in result.stdout
                        )
                    if "stderr_empty" in step.expected:
                        success = success and (
                            not result.stderr.strip()
                            if step.expected["stderr_empty"]
                            else True
                        )
                elif isinstance(step.expected, str):
                    # Check if expected string is in output
                    success = (
                        step.expected in result.stdout or step.expected in result.stderr
                    )
                else:
                    # Check return code
                    success = result.returncode == step.expected
            else:
                # Default: command should succeed
                success = result.success

            return {"success": success, "command_result": result, "step": step}

        elif step.action == "wait":
            # Wait for specified duration
            wait_time = float(step.value or 1)
            await asyncio.sleep(wait_time)
            return {"success": True, "step": step}

        else:
            logger.warning(f"Unsupported CLI action: {step.action}")
            return {
                "success": False,
                "error": f"Unsupported action: {step.action}",
                "step": step,
            }

    async def verify_cli_available(self) -> bool:
        """
        Verify that the CLI is installed and accessible.

        Returns:
            True if CLI is available
        """
        try:
            result = await self.execute_command("--version", [], timeout=10)
            return result.success and (
                "azure-tenant-grapher" in result.stdout.lower()
                or "atg" in result.stdout.lower()
            )
        except Exception as e:
            logger.error(f"CLI verification failed: {e}")
            return False

    async def get_command_help(self, command: str) -> str:
        """
        Get help text for a command.

        Args:
            command: Command name

        Returns:
            Help text
        """
        result = await self.execute_command(command, ["--help"], timeout=10)
        return result.stdout if result.success else result.stderr
