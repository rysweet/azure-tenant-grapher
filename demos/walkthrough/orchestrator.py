#!/usr/bin/env python3
"""
Azure Tenant Grapher Demo Orchestrator

Production-ready orchestrator using modular architecture with proper error handling,
health checks, and service management.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Import modular components
from modules import (
    ConfigManager,
    ConfigurationError,
    ErrorReporter,
    HealthChecker,
    ServiceManager,
    ScenarioRunner,
    ScenarioResult
)
from utils.screenshot_manager import ScreenshotManager
from utils.test_assertions import TestAssertions


class DemoOrchestrator:
    """
    Production-ready demo orchestrator with modular architecture.

    Uses self-contained modules for:
    - Configuration management
    - Health checking
    - Service lifecycle
    - Scenario execution
    - Error reporting
    """

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize orchestrator with modular components."""
        # Initialize core modules
        self.config_manager = ConfigManager(config_path)
        self.error_reporter = ErrorReporter()
        self.health_checker = None  # Initialized after config load
        self.service_manager = None  # Initialized after config load
        self.scenario_runner = None  # Initialized after config load

        # Playwright components
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Results tracking
        self.results: List[ScenarioResult] = []

        # Initialize after loading config
        self._initialize()

    def _initialize(self):
        """Initialize components after loading configuration."""
        try:
            # Load configuration
            self.config = self.config_manager.load_config()

            # Setup logging
            self.logger = self._setup_logging()

            # Initialize modules with config
            self.health_checker = HealthChecker(self.config)
            self.service_manager = ServiceManager(self.config.get("services", {}))
            self.scenario_runner = ScenarioRunner(self.config.get("scenarios", {}))

            # Initialize utilities
            self.screenshots = ScreenshotManager(self.config.get('screenshot', {}))
            self.assertions = TestAssertions()

            self.logger.info("Orchestrator initialized successfully")

        except ConfigurationError as e:
            print(f"Configuration Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Initialization Error: {e}")
            sys.exit(1)

    def _setup_logging(self) -> logging.Logger:
        """Setup logging with configuration."""
        log_config = self.config_manager.get_logging_config()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_config.get('file', 'logs/demo_{timestamp}.log').replace("{timestamp}", timestamp)

        # Create logs directory
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure handlers
        handlers = []
        if log_config.get('console', True):
            handlers.append(logging.StreamHandler())
        handlers.append(logging.FileHandler(log_file))

        # Set up logging
        log_level = log_config.get('level', 'info').upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

        return logging.getLogger(__name__)

    async def health_check(self) -> bool:
        """
        Perform comprehensive health checks before running demos.

        Returns:
            True if all health checks pass
        """
        self.logger.info("Running health checks...")

        try:
            # Run all health checks
            healthy = await self.health_checker.check_all()

            # Display summary
            summary = self.health_checker.get_summary()
            print(summary)

            if not healthy:
                # Get detailed failure information
                failed_checks = self.health_checker.get_failed_checks()

                for check in failed_checks:
                    # Report each failure with remediation
                    error = Exception(check.message)
                    report = self.error_reporter.report_error(error, check.details)
                    print(self.error_reporter.format_for_console(report))

                return False

            return True

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            report = self.error_reporter.report_error(e)
            print(self.error_reporter.format_for_console(report))
            return False

    async def start_services(self) -> bool:
        """
        Start required services based on configuration.

        Returns:
            True if all required services started
        """
        service_configs = self.config.get("services", {}).get("definitions", [])

        if not service_configs:
            self.logger.info("No services configured to start")
            return True

        self.logger.info("Starting services...")

        try:
            success = await self.service_manager.start_all(service_configs)

            if success:
                # Display service status
                status = self.service_manager.get_status()
                self.logger.info(f"Services started: {status['running']}/{status['total']}")
            else:
                self.logger.error("Failed to start required services")

            return success

        except Exception as e:
            self.logger.error(f"Service startup failed: {e}")
            report = self.error_reporter.report_error(e)
            print(self.error_reporter.format_for_console(report))
            return False

    async def setup_browser(self):
        """Setup Playwright browser with error handling."""
        self.logger.info("Setting up browser...")

        try:
            playwright = await async_playwright().start()
            browser_type = self.config_manager.get_browser()

            browser_config = {
                "headless": self.config_manager.is_headless(),
                "slow_mo": self.config_manager.get("test.slowMo", 0)
            }

            browser_instance = getattr(playwright, browser_type)
            self.browser = await browser_instance.launch(**browser_config)

            # Create context with viewport
            viewport = self.config_manager.get("test.viewport", {"width": 1920, "height": 1080})
            self.context = await self.browser.new_context(
                viewport=viewport,
                ignore_https_errors=True
            )

            self.page = await self.context.new_page()

            # Setup event handlers for debugging
            self.page.on("console", lambda msg: self.logger.debug(f"Browser console: {msg.text}"))
            self.page.on("pageerror", lambda err: self.logger.error(f"Browser error: {err}"))

            self.logger.info(f"Browser setup complete ({browser_type})")

        except Exception as e:
            self.logger.error(f"Browser setup failed: {e}")
            report = self.error_reporter.report_error(e, {"browser": browser_type})
            print(self.error_reporter.format_for_console(report))
            raise

    async def teardown_browser(self):
        """Cleanup browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            self.logger.info("Browser cleanup complete")
        except Exception as e:
            self.logger.warning(f"Browser cleanup warning: {e}")

    async def run_scenario(self, scenario_name: str) -> ScenarioResult:
        """
        Run a single scenario with full error handling.

        Args:
            scenario_name: Name of scenario to run

        Returns:
            ScenarioResult with execution details
        """
        self.logger.info(f"Running scenario: {scenario_name}")

        try:
            # Load scenario
            scenario = self.scenario_runner.load_scenario(scenario_name)

            # Set app URL if not in scenario
            if "url" not in scenario:
                scenario["url"] = self.config_manager.get_app_url()

            # Run scenario with screenshot callback
            result = await self.scenario_runner.run_scenario(
                scenario,
                self.page,
                screenshot_callback=self.screenshots.capture
            )

            # Log result
            if result.success:
                self.logger.info(f"Scenario '{scenario_name}' completed successfully")
            else:
                self.logger.error(f"Scenario '{scenario_name}' failed with {len(result.errors)} errors")

                # Report errors
                for error_msg in result.errors:
                    error = Exception(error_msg)
                    report = self.error_reporter.report_error(error, {"scenario": scenario_name})
                    print(self.error_reporter.format_for_console(report))

            return result

        except FileNotFoundError as e:
            self.logger.error(f"Scenario file not found: {e}")
            report = self.error_reporter.report_error(e, {"scenario": scenario_name})
            print(self.error_reporter.format_for_console(report))

            # Create empty result for consistency
            result = ScenarioResult(scenario_name)
            result.success = False
            result.errors.append(str(e))
            result.complete()
            return result

        except Exception as e:
            self.logger.error(f"Scenario execution failed: {e}")
            report = self.error_reporter.report_error(e, {"scenario": scenario_name})
            print(self.error_reporter.format_for_console(report))

            # Create error result
            result = ScenarioResult(scenario_name)
            result.success = False
            result.errors.append(str(e))
            result.complete()
            return result

    async def run_story(self, story_name: str) -> List[ScenarioResult]:
        """
        Run a story (collection of scenarios).

        Args:
            story_name: Name of story to run

        Returns:
            List of ScenarioResult objects
        """
        self.logger.info(f"Running story: {story_name}")

        story_path = Path("stories") / f"{story_name}.yaml"
        if not story_path.exists():
            raise FileNotFoundError(f"Story not found: {story_path}")

        import yaml
        with open(story_path, 'r') as f:
            story = yaml.safe_load(f)

        results = []
        stop_on_failure = story.get("stop_on_failure", False)

        for scenario_name in story.get("scenarios", []):
            result = await self.run_scenario(scenario_name)
            results.append(result)

            if not result.success and stop_on_failure:
                self.logger.warning(f"Stopping story due to scenario failure: {scenario_name}")
                break

        return results

    def generate_report(self, results: List[ScenarioResult]):
        """Generate comprehensive reports."""
        if not self.config.get('report', {}).get('generate', True):
            return

        self.logger.info("Generating reports...")

        report_dir = Path(self.config.get('report', {}).get('path', './reports'))
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate JSON report
        formats = self.config.get('report', {}).get('format', ['json'])

        if "json" in formats:
            json_path = report_dir / f"report_{timestamp}.json"
            with open(json_path, 'w') as f:
                json.dump([r.to_dict() for r in results], f, indent=2, default=str)
            self.logger.info(f"JSON report saved to: {json_path}")

        if "html" in formats:
            html_path = report_dir / f"report_{timestamp}.html"
            self._generate_html_report(results, html_path)
            self.logger.info(f"HTML report saved to: {html_path}")

        # Save error log if there were errors
        if self.error_reporter.has_errors():
            error_log_path = self.error_reporter.save_error_log(str(report_dir / f"errors_{timestamp}.json"))
            self.logger.info(f"Error log saved to: {error_log_path}")

    def _generate_html_report(self, results: List[ScenarioResult], output_path: Path):
        """Generate HTML report from results."""
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed

        scenarios_html = ""
        for result in results:
            status_class = "success" if result.success else "failure"
            error_section = ""

            if result.errors:
                error_list = "".join(f"<li>{e}</li>" for e in result.errors)
                error_section = f"<ul class='errors'>{error_list}</ul>"

            scenarios_html += f"""
            <div class="scenario {status_class}">
                <h3>{result.name}</h3>
                <p>Duration: {result.duration:.2f}s</p>
                <p>Steps: {len(result.steps)} (Passed: {sum(1 for s in result.steps if s.get('success'))})</p>
                {error_section}
            </div>
            """

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Azure Tenant Grapher Demo Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 10px;
        }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .scenario {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .scenario.success {{
            border-left: 4px solid #107c10;
        }}
        .scenario.failure {{
            border-left: 4px solid #d83b01;
        }}
        .errors {{
            color: #d83b01;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Azure Tenant Grapher Demo Report</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Total Scenarios: {total}</p>
            <p>✅ Passed: {passed}</p>
            <p>❌ Failed: {failed}</p>
        </div>
        {scenarios_html}
    </div>
</body>
</html>
        """

        with open(output_path, 'w') as f:
            f.write(html_content)

    async def generate_gallery(self):
        """Generate screenshot gallery."""
        self.logger.info("Generating screenshot gallery...")
        gallery_path = await self.screenshots.generate_gallery(self.config.get('gallery', {}))
        self.logger.info(f"Gallery saved to: {gallery_path}")
        return gallery_path

    async def run(
        self,
        story: Optional[str] = None,
        scenario: Optional[str] = None,
        gallery_only: bool = False,
        skip_health_check: bool = False,
        skip_services: bool = False
    ) -> List[ScenarioResult]:
        """
        Main execution method with comprehensive error handling.

        Args:
            story: Optional story name to run
            scenario: Optional single scenario to run
            gallery_only: Generate gallery without running scenarios
            skip_health_check: Skip health checks
            skip_services: Skip service startup

        Returns:
            List of ScenarioResult objects
        """
        if gallery_only:
            await self.generate_gallery()
            return []

        try:
            # Run health checks unless skipped
            if not skip_health_check:
                if not await self.health_check():
                    self.logger.error("Health checks failed. Use --skip-health-check to bypass.")
                    return []

            # Start services unless skipped
            if not skip_services:
                if not await self.start_services():
                    self.logger.error("Service startup failed. Use --skip-services to bypass.")
                    return []

            # Setup browser
            await self.setup_browser()

            # Execute scenarios
            if scenario:
                # Run single scenario
                result = await self.run_scenario(scenario)
                self.results = [result]
            elif story:
                # Run story
                self.results = await self.run_story(story)
            else:
                # Run default story
                default_story = self.config.get('stories', {}).get('default', 'quick_demo')
                self.results = await self.run_story(default_story)

            # Generate reports
            self.generate_report(self.results)

            # Generate gallery if screenshots were taken
            if any(r.screenshots for r in self.results):
                await self.generate_gallery()

            return self.results

        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            report = self.error_reporter.report_error(e)
            print(self.error_reporter.format_for_console(report))
            return []

        finally:
            # Cleanup
            await self.teardown_browser()

            if not skip_services:
                await self.service_manager.stop_all()

                # Export service logs
                if self.config.get('services', {}).get('export_logs', True):
                    log_files = self.service_manager.export_logs()
                    if log_files:
                        self.logger.info(f"Service logs exported: {log_files}")


async def main():
    """Enhanced CLI entry point with better error handling."""
    parser = argparse.ArgumentParser(
        description="Azure Tenant Grapher Demo Orchestrator - Production Ready",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run default story with health checks
  %(prog)s --scenario login         # Run single scenario
  %(prog)s --story full_walkthrough # Run specific story
  %(prog)s --health-check-only      # Only run health checks
  %(prog)s --skip-health-check      # Skip health checks (faster)
  %(prog)s --headless --debug        # Run headless with debug logging
        """
    )

    parser.add_argument("--config", default="config.yaml", help="Configuration file path")
    parser.add_argument("--story", help="Story to run (collection of scenarios)")
    parser.add_argument("--scenario", help="Individual scenario to run")
    parser.add_argument("--gallery", action="store_true", help="Generate gallery only")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip health checks")
    parser.add_argument("--skip-services", action="store_true", help="Skip service startup")
    parser.add_argument("--health-check-only", action="store_true", help="Run health checks only")
    parser.add_argument("--list-scenarios", action="store_true", help="List available scenarios")

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = DemoOrchestrator(args.config)

    # Handle list scenarios
    if args.list_scenarios:
        scenarios = orchestrator.scenario_runner.get_scenario_list()
        print("\nAvailable Scenarios:")
        for scenario in scenarios:
            print(f"  - {scenario}")
        return

    # Handle health check only
    if args.health_check_only:
        healthy = await orchestrator.health_check()
        sys.exit(0 if healthy else 1)

    # Override configuration from CLI
    if args.headless:
        orchestrator.config_manager.set('test.headless', True)
    if args.debug:
        orchestrator.config_manager.set('logging.level', 'debug')
        logging.getLogger().setLevel(logging.DEBUG)

    # Run demo
    results = await orchestrator.run(
        story=args.story,
        scenario=args.scenario,
        gallery_only=args.gallery,
        skip_health_check=args.skip_health_check,
        skip_services=args.skip_services
    )

    # Print summary
    if results:
        total = len(results)
        passed = sum(1 for r in results if r.success)

        print(f"\n{'='*60}")
        print(f"✨ Demo Execution Complete")
        print(f"{'='*60}")
        print(f"Total Scenarios: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {total - passed}")

        if orchestrator.error_reporter.has_errors():
            print(f"\n{orchestrator.error_reporter.get_summary()}")

        print(f"{'='*60}\n")

        # Exit with error if any tests failed
        sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())