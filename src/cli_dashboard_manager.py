"""
CLI Dashboard Manager

Handles the Rich dashboard functionality for the CLI, including keypress handling
and build task coordination.
"""

import asyncio
import logging
import os
import queue
import sys
from typing import TYPE_CHECKING, Any

from src.rich_dashboard import RichDashboard

if TYPE_CHECKING:
    from src.azure_tenant_grapher import AzureTenantGrapher
    from src.config_manager import AzureTenantGrapherConfig


class DashboardExitException(Exception):
    """Exception raised to force immediate exit from dashboard context."""

    pass


class CLIDashboardManager:
    """Manages CLI dashboard interactions and build task coordination."""

    def __init__(self, dashboard: RichDashboard):
        self.dashboard = dashboard
        self.logger = logging.getLogger(__name__)

    async def run_with_file_keypress(
        self, build_task: asyncio.Task[Any], test_keypress_file: str
    ) -> None:
        """Run dashboard with file-based keypress simulation for testing."""

        async def check_exit_file():
            """Simple exit checker that looks for 'x' in the file."""
            while True:
                try:
                    if os.path.exists(test_keypress_file):
                        with open(test_keypress_file) as f:
                            content = f.read()
                            if "x" in content.lower():
                                with self.dashboard.lock:
                                    self.dashboard._should_exit = True  # type: ignore[attr-defined]
                                return
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"Error checking exit file: {e}")
                    await asyncio.sleep(0.1)

        # Start the exit checker as a background task
        exit_checker = asyncio.create_task(check_exit_file())

        try:
            with self.dashboard.live():
                self.dashboard.log_info("Press 'x' to exit the dashboard")
                # Use the same polling logic as other methods for consistency
                await self.poll_build_task(build_task)
        finally:
            # Clean up
            if not exit_checker.done():
                exit_checker.cancel()

    async def run_with_queue_keypress(self, build_task: asyncio.Task[Any]) -> None:
        """Run dashboard with queue-based keypress simulation for testing."""

        key_q = queue.Queue()
        self.dashboard._test_keypress_queue = key_q  # type: ignore[attr-defined]

        with self.dashboard.live(key_queue=key_q):
            self.dashboard.log_info("Press 'x' to exit the dashboard")
            await self.poll_build_task(build_task)

    async def run_normal(self, build_task: asyncio.Task[Any]) -> None:
        """Run dashboard with normal keyboard input."""

        try:
            with self.dashboard.live():
                self.dashboard.log_info("Press 'x' to exit the dashboard")
                await self.poll_build_task(build_task)
        except Exception as e:
            # Check if this is a dashboard exit from Rich dashboard
            if (
                "User pressed 'x' to exit" in str(e)
                or e.__class__.__name__ == "DashboardExit"
            ):
                self.logger.debug("Dashboard exit detected from Rich dashboard")
                raise DashboardExitException(
                    "User requested exit via 'x' keypress"
                ) from e
            raise

    async def poll_build_task(self, build_task: asyncio.Task[Any]) -> None:
        """Poll build task and handle early exit."""

        while not build_task.done() and not self.dashboard.should_exit:
            self.logger.debug(
                f"Polling: build_task.done={build_task.done()}, dashboard.should_exit={self.dashboard.should_exit}"
            )

            # Check exit flag more frequently
            if self.dashboard.should_exit:
                self.logger.debug("Exit flag detected during polling!")
                break

            await asyncio.sleep(0.1)

        if self.dashboard.should_exit and not build_task.done():
            self.logger.debug("Cancelling build task due to exit request")
            self.dashboard.add_error(
                "Dashboard exited before build completed. Cancelling build..."
            )
            build_task.cancel()
            try:
                await build_task
            except asyncio.CancelledError:
                # Expected when we cancel the task
                pass
            except Exception:
                # Any other unexpected exception
                pass

        # If exit was requested, exit the process immediately (forceful, but reliable)
        if self.dashboard.should_exit:
            self.logger.debug("IMMEDIATE EXIT - User pressed 'x'")
            sys.exit(0)

    def check_exit_condition(self) -> bool:
        """Check if user requested exit and handle accordingly."""

        if self.dashboard.should_exit:
            self.dashboard.log_info(
                "Dashboard exit requested by user (pressed 'x'). Exiting program."
            )
            return True
        return False

    async def handle_build_completion(
        self,
        build_task: asyncio.Task[Any],
        grapher: "AzureTenantGrapher",
        config: "AzureTenantGrapherConfig",
        generate_spec: bool = False,
        visualize: bool = False,
    ) -> None:
        """Handle build task completion and post-processing."""

        # After dashboard context exits, await the build if still running
        if not build_task.done():
            try:
                result = await build_task
            except Exception as build_e:
                self.dashboard.set_processing(False)
                self.dashboard.add_error(f"❌ Graph building failed: {build_e}")
                raise
        else:
            result = build_task.result()

        self.dashboard.set_processing(False)
        self.dashboard.log_info("🎉 Graph building completed successfully!")
        self.dashboard.log_info(f"Result: {result}")

        # Handle post-processing options (generate_spec, visualize) after build
        if generate_spec:
            self.dashboard.log_info("📋 Generating tenant specification...")
            try:
                await grapher.generate_tenant_specification()
                self.dashboard.log_info("✅ Tenant specification generated")
            except Exception as spec_e:
                self.dashboard.add_error(
                    f"❌ Tenant specification generation failed: {spec_e}"
                )

        if visualize:
            self.dashboard.log_info("🎨 Generating visualization...")
            try:
                from src.graph_visualizer import GraphVisualizer

                visualizer = GraphVisualizer(
                    config.neo4j.uri,
                    config.neo4j.user,
                    config.neo4j.password,
                )
                viz_path = visualizer.generate_html_visualization()
                self.dashboard.log_info(f"✅ Visualization saved to: {viz_path}")
            except Exception as viz_e:
                self.dashboard.add_error(f"⚠️ Visualization failed: {viz_e}")
