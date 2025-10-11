"""Integration with cleanup script for Azure resource cleanup.

This module provides a Python wrapper for the bash cleanup script,
allowing programmatic invocation from the IaC generation workflow.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class CleanupScriptError(Exception):
    """Raised when cleanup script execution fails."""

    pass


def invoke_cleanup_script(
    subscription_id: str,
    dry_run: bool = True,
    force: bool = False,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """Invoke cleanup script from Python code.

    Args:
        subscription_id: Target subscription ID
        dry_run: If True, run in dry-run mode (default)
        force: If True, skip confirmation prompts
        timeout: Timeout in seconds (default: 600 = 10 minutes)

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        CleanupScriptError: If script not found or execution fails
    """
    # Find cleanup script relative to this file
    script_path = (
        Path(__file__).parent.parent.parent
        / "scripts"
        / "cleanup_target_subscription.sh"
    )

    if not script_path.exists():
        raise CleanupScriptError(f"Cleanup script not found: {script_path}")

    # Build command arguments
    args = [str(script_path), subscription_id]

    if dry_run:
        args.append("--dry-run")
    else:
        args.append("--execute")

    if force:
        args.append("--force")

    logger.info(f"Running cleanup script: {' '.join(args)}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )

        # Log output
        if result.stdout:
            logger.debug(f"Cleanup stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"Cleanup stderr: {result.stderr}")

        return result

    except subprocess.TimeoutExpired as e:
        logger.error(f"Cleanup script timed out after {timeout} seconds")
        raise CleanupScriptError(
            f"Cleanup script timed out after {timeout} seconds"
        ) from e
    except Exception as e:
        logger.error(f"Cleanup script execution failed: {e}")
        raise CleanupScriptError(f"Cleanup script execution failed: {e}") from e


def parse_cleanup_result(result: subprocess.CompletedProcess) -> dict:
    """Parse cleanup script output into structured result.

    Args:
        result: CompletedProcess from invoke_cleanup_script

    Returns:
        Dict with keys: success, resources_deleted, errors
    """
    success = result.returncode == 0
    resources_deleted = []
    errors = []

    # Parse stdout for deleted resources (basic parsing)
    if result.stdout:
        for line in result.stdout.splitlines():
            if "Deleted" in line or "deleted" in line.lower():
                resources_deleted.append(line.strip())
            if "Error" in line or "Failed" in line:
                errors.append(line.strip())

    # Parse stderr for errors
    if result.stderr:
        for line in result.stderr.splitlines():
            if line.strip() and not line.startswith("#"):
                errors.append(line.strip())

    return {
        "success": success,
        "resources_deleted": resources_deleted,
        "errors": errors,
        "returncode": result.returncode,
    }
