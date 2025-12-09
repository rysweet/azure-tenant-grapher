"""SPA/Electron dashboard commands.

This module provides commands for the SPA/Electron dashboard:
- 'start': Start the SPA/Electron dashboard and MCP server
- 'stop': Stop the SPA/Electron dashboard and MCP server

Issue #482: CLI Modularization
"""

import os
import shutil
import signal
import subprocess
import sys

import click

SPA_PIDFILE = os.path.join("outputs", "spa_server.pid")
MCP_PIDFILE = os.path.join("outputs", "mcp_server.pid")


@click.command("start")
def spa_start() -> None:
    """Start the local SPA/Electron dashboard and MCP server."""
    # Check for stale PID file
    if os.path.exists(SPA_PIDFILE):
        try:
            with open(SPA_PIDFILE) as f:
                pid = int(f.read().strip())
            # Check if process is actually running
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                click.echo(
                    f"SPA already running (PID: {pid}). Use 'atg stop' first.",
                    err=True,
                )
                return
            except ProcessLookupError:
                # Process not running, clean up stale PID file
                click.echo(
                    f"INFO: Cleaning up stale PID file (process {pid} not found)"
                )
                os.remove(SPA_PIDFILE)
        except (OSError, ValueError) as e:
            # Invalid PID file, remove it
            click.echo(f"INFO: Removing invalid PID file: {e}")
            os.remove(SPA_PIDFILE)

    # Check if npm is available
    if not shutil.which("npm"):
        click.echo(
            "npm is not installed. Please install Node.js and npm first.", err=True
        )
        return

    try:
        # Change to the spa directory
        spa_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "spa"
        )

        # Check if package.json exists
        if not os.path.exists(os.path.join(spa_dir, "package.json")):
            click.echo(
                "SPA not found. Please ensure the spa directory exists with package.json",
                err=True,
            )
            return

        # Check if node_modules exists, if not, install dependencies
        if not os.path.exists(os.path.join(spa_dir, "node_modules")):
            click.echo("Installing SPA dependencies...")
            install_proc = subprocess.run(
                ["npm", "install"], cwd=spa_dir, capture_output=True, text=True
            )
            if install_proc.returncode != 0:
                click.echo(
                    f"Failed to install dependencies: {install_proc.stderr}",
                    err=True,
                )
                return
            click.echo("Dependencies installed successfully")

        # Always build the app to ensure latest code is used
        click.echo("Building Electron app with latest code...")
        build_proc = subprocess.run(
            ["npm", "run", "build"], cwd=spa_dir, capture_output=True, text=True
        )
        if build_proc.returncode != 0:
            click.echo(
                f"Failed to build app: {build_proc.stderr}",
                err=True,
            )
            return

        # Verify the build created the main entry point
        main_entry = os.path.join(spa_dir, "dist", "main", "index.js")
        if not os.path.exists(main_entry):
            click.echo(
                "Build completed but main entry point not found. Check build configuration.",
                err=True,
            )
            return
        click.echo("Electron app built successfully")

        # Start the MCP server
        click.echo("Starting MCP server...")
        _start_mcp_server()

        # Start the Electron app
        spa_proc = subprocess.Popen(
            ["npm", "run", "start"],
            cwd=spa_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Save the PID
        os.makedirs("outputs", exist_ok=True)
        with open(SPA_PIDFILE, "w") as f:
            f.write(str(spa_proc.pid))

        click.echo("SPA started. The Electron app should open shortly.")
        click.echo(f"(PID: {spa_proc.pid} | pidfile: {SPA_PIDFILE})")
        click.echo("Use 'atg stop' to shut down the SPA and MCP server when done.")
    except Exception as e:
        click.echo(f"Failed to start SPA: {e}", err=True)


def _start_mcp_server() -> None:
    """Start the MCP server in the background."""
    try:
        # Check if MCP server is already running
        mcp_needs_start = True
        if os.path.exists(MCP_PIDFILE):
            # Check if it's a stale PID file
            try:
                with open(MCP_PIDFILE) as f:
                    mcp_pid = int(f.read().strip())
                try:
                    os.kill(mcp_pid, 0)  # Check if process exists
                    click.echo(
                        f"MCP server already running (PID: {mcp_pid}), skipping..."
                    )
                    mcp_needs_start = False
                except ProcessLookupError:
                    # Process not running, clean up stale PID file
                    click.echo(
                        f"INFO: Cleaning up stale MCP PID file (process {mcp_pid} not found)"
                    )
                    os.remove(MCP_PIDFILE)
            except (OSError, ValueError) as e:
                # Invalid PID file, remove it
                click.echo(f"INFO: Removing invalid MCP PID file: {e}")
                os.remove(MCP_PIDFILE)

        if mcp_needs_start:
            # Start MCP server in the background
            src_dir = os.path.dirname(os.path.dirname(__file__))
            mcp_proc = subprocess.Popen(
                [sys.executable, "-m", "src.mcp_server"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={
                    **os.environ,
                    "PYTHONPATH": src_dir,
                },
            )

            # Save MCP PID
            os.makedirs("outputs", exist_ok=True)
            with open(MCP_PIDFILE, "w") as f:
                f.write(str(mcp_proc.pid))

            click.echo(f"MCP server started (PID: {mcp_proc.pid})")
    except Exception as e:
        click.echo(f"Failed to start MCP server: {e}")
        # Continue even if MCP fails to start


@click.command("stop")
def spa_stop() -> None:
    """Stop the local SPA/Electron dashboard and MCP server."""
    spa_stopped = False
    mcp_stopped = False

    # Stop SPA
    if os.path.exists(SPA_PIDFILE):
        try:
            with open(SPA_PIDFILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                click.echo("Sent SIGTERM to SPA process.")
                spa_stopped = True
            except Exception as e:
                click.echo(f"Could not terminate SPA process: {e}", err=True)
            os.remove(SPA_PIDFILE)
        except Exception as e:
            click.echo(f"Failed to stop SPA: {e}", err=True)
    else:
        click.echo("[INFO] No SPA process running.")

    # Stop MCP server
    if os.path.exists(MCP_PIDFILE):
        try:
            with open(MCP_PIDFILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                click.echo("Sent SIGTERM to MCP server.")
                mcp_stopped = True
            except Exception as e:
                click.echo(f"Could not terminate MCP server: {e}", err=True)
            os.remove(MCP_PIDFILE)
        except Exception as e:
            click.echo(f"Failed to stop MCP server: {e}", err=True)
    else:
        click.echo("[INFO] No MCP server running.")

    if spa_stopped or mcp_stopped:
        click.echo("Services stopped successfully.")
    else:
        click.echo("[INFO] No services were running.")


# For backward compatibility
start = spa_start
stop = spa_stop

__all__ = ["spa_start", "spa_stop", "start", "stop"]
