#!/usr/bin/env python3
"""
Azure Tenant Grapher Demo Orchestrator

Main entry point for running demo walkthroughs and generating documentation.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from demos.walkthrough.utils.screenshot_manager import ScreenshotManager
from demos.walkthrough.utils.test_assertions import TestAssertions


class DemoOrchestrator:
    """Orchestrates demo scenarios and stories."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the orchestrator with configuration."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.screenshots = ScreenshotManager(self.config['screenshot'])
        self.assertions = TestAssertions()
        self.logger = self._setup_logging()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.results: List[Dict[str, Any]] = []

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Expand environment variables
        config = self._expand_env_vars(config)
        return config

    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, obj)
        return obj

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_config = self.config['logging']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_config['file'].replace("{timestamp}", timestamp)

        # Create logs directory if needed
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure logging
        handlers = []
        if log_config['console']:
            handlers.append(logging.StreamHandler())
        handlers.append(logging.FileHandler(log_file))

        logging.basicConfig(
            level=getattr(logging, log_config['level'].upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

        return logging.getLogger(__name__)

    async def setup_browser(self):
        """Setup Playwright browser instance."""
        self.logger.info("Setting up browser...")

        playwright = await async_playwright().start()
        browser_type = getattr(playwright, self.config['test']['browser'])

        self.browser = await browser_type.launch(
            headless=self.config['test']['headless'],
            slow_mo=self.config['test']['slowMo']
        )

        self.context = await self.browser.new_context(
            viewport=self.config['test']['viewport'],
            ignore_https_errors=True
        )

        self.page = await self.context.new_page()

        # Setup page event handlers
        self.page.on("console", lambda msg: self.logger.debug(f"Browser console: {msg.text}"))
        self.page.on("pageerror", lambda err: self.logger.error(f"Browser error: {err}"))

    async def teardown_browser(self):
        """Cleanup browser resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def run_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Run a single scenario."""
        self.logger.info(f"Running scenario: {scenario_name}")

        scenario_path = Path("scenarios") / f"{scenario_name}.yaml"
        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario not found: {scenario_path}")

        with open(scenario_path, 'r') as f:
            scenario = yaml.safe_load(f)

        result = {
            "name": scenario_name,
            "description": scenario.get("description", ""),
            "steps": [],
            "success": True,
            "duration": 0,
            "screenshots": []
        }

        start_time = datetime.now()

        try:
            # Navigate to app if needed
            if scenario.get("navigate", True):
                await self.page.goto(self.config['app']['url'])
                await self.page.wait_for_load_state("networkidle")

            # Execute steps
            for i, step in enumerate(scenario.get("steps", [])):
                step_result = await self._execute_step(step, scenario_name, i)
                result["steps"].append(step_result)

                if not step_result["success"] and self.config['scenarios']['stop_on_failure']:
                    result["success"] = False
                    break

                # Take screenshot if configured
                if step.get("screenshot", self.config['screenshot']['enabled']):
                    screenshot_path = await self.screenshots.capture(
                        self.page,
                        scenario_name,
                        i,
                        step.get("description", f"step_{i}")
                    )
                    result["screenshots"].append(screenshot_path)

            # Run assertions
            for assertion in scenario.get("assertions", []):
                assertion_result = await self.assertions.run(self.page, assertion)
                if not assertion_result["success"]:
                    result["success"] = False
                    self.logger.error(f"Assertion failed: {assertion_result['message']}")

        except Exception as e:
            self.logger.error(f"Scenario failed: {e}")
            result["success"] = False
            result["error"] = str(e)

            if self.config['scenarios']['screenshot_on_failure']:
                await self.screenshots.capture(
                    self.page,
                    scenario_name,
                    "error",
                    "failure"
                )

        finally:
            end_time = datetime.now()
            result["duration"] = (end_time - start_time).total_seconds()

        return result

    async def _execute_step(self, step: Dict[str, Any], scenario: str, index: int) -> Dict[str, Any]:
        """Execute a single step within a scenario."""
        self.logger.debug(f"Executing step {index}: {step.get('description', 'unnamed')}")

        result = {
            "index": index,
            "description": step.get("description", ""),
            "action": step.get("action", ""),
            "success": True,
            "duration": 0
        }

        start_time = datetime.now()

        try:
            action = step.get("action", "")

            if action == "click":
                await self.page.click(step["selector"])

            elif action == "fill":
                await self.page.fill(step["selector"], step["value"])

            elif action == "select":
                await self.page.select_option(step["selector"], step["value"])

            elif action == "wait":
                if "selector" in step:
                    await self.page.wait_for_selector(step["selector"], timeout=step.get("timeout", 30000))
                else:
                    await self.page.wait_for_timeout(step.get("timeout", 1000))

            elif action == "navigate":
                await self.page.goto(step["url"])
                await self.page.wait_for_load_state("networkidle")

            elif action == "hover":
                await self.page.hover(step["selector"])

            elif action == "press":
                await self.page.press(step["selector"], step["key"])

            elif action == "scroll":
                await self.page.evaluate(f"window.scrollTo(0, {step.get('position', 'document.body.scrollHeight')})")

            elif action == "evaluate":
                await self.page.evaluate(step["code"])

            elif action == "screenshot":
                await self.screenshots.capture(
                    self.page,
                    scenario,
                    index,
                    step.get("description", f"step_{index}")
                )

            # Wait after action if specified
            if "wait_after" in step:
                await self.page.wait_for_timeout(step["wait_after"])

        except Exception as e:
            self.logger.error(f"Step failed: {e}")
            result["success"] = False
            result["error"] = str(e)

        finally:
            end_time = datetime.now()
            result["duration"] = (end_time - start_time).total_seconds()

        return result

    async def run_story(self, story_name: str) -> List[Dict[str, Any]]:
        """Run a story (collection of scenarios)."""
        self.logger.info(f"Running story: {story_name}")

        story_path = Path("stories") / f"{story_name}.yaml"
        if not story_path.exists():
            raise FileNotFoundError(f"Story not found: {story_path}")

        with open(story_path, 'r') as f:
            story = yaml.safe_load(f)

        results = []

        for scenario_name in story.get("scenarios", []):
            try:
                result = await self.run_scenario(scenario_name)
                results.append(result)

                if not result["success"] and story.get("stop_on_failure", False):
                    self.logger.warning(f"Stopping story due to scenario failure: {scenario_name}")
                    break

            except Exception as e:
                self.logger.error(f"Failed to run scenario {scenario_name}: {e}")
                if story.get("stop_on_failure", False):
                    break

        return results

    def generate_report(self, results: List[Dict[str, Any]]):
        """Generate test report in various formats."""
        if not self.config['report']['generate']:
            return

        self.logger.info("Generating reports...")

        report_dir = Path(self.config['report']['path'])
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate JSON report
        if "json" in self.config['report']['format']:
            json_path = report_dir / f"report_{timestamp}.json"
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            self.logger.info(f"JSON report saved to: {json_path}")

        # Generate HTML report
        if "html" in self.config['report']['format']:
            html_path = report_dir / f"report_{timestamp}.html"
            self._generate_html_report(results, html_path)
            self.logger.info(f"HTML report saved to: {html_path}")

        # Generate JUnit XML report
        if "junit" in self.config['report']['format']:
            junit_path = report_dir / f"junit_{timestamp}.xml"
            self._generate_junit_report(results, junit_path)
            self.logger.info(f"JUnit report saved to: {junit_path}")

    def _generate_html_report(self, results: List[Dict[str, Any]], output_path: Path):
        """Generate HTML report from results."""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Azure Tenant Grapher Demo Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 10px;
        }
        .summary {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .scenario {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .success {
            color: #107c10;
        }
        .failure {
            color: #d83b01;
        }
        .step {
            padding: 10px;
            margin: 5px 0;
            background: #f8f8f8;
            border-left: 3px solid #0078d4;
        }
        .screenshot {
            max-width: 100%;
            margin: 10px 0;
            border: 1px solid #ddd;
        }
        .duration {
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Azure Tenant Grapher Demo Report</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p>Generated: {timestamp}</p>
            <p>Total Scenarios: {total}</p>
            <p class="success">Passed: {passed}</p>
            <p class="failure">Failed: {failed}</p>
        </div>
        {scenarios}
    </div>
</body>
</html>
        """

        total = len(results)
        passed = sum(1 for r in results if r.get("success", False))
        failed = total - passed

        scenarios_html = ""
        for result in results:
            status_class = "success" if result.get("success") else "failure"
            scenarios_html += f"""
            <div class="scenario">
                <h3 class="{status_class}">{result.get('name', 'Unknown')}</h3>
                <p>{result.get('description', '')}</p>
                <p class="duration">Duration: {result.get('duration', 0):.2f}s</p>
            </div>
            """

        html = html_content.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total=total,
            passed=passed,
            failed=failed,
            scenarios=scenarios_html
        )

        with open(output_path, 'w') as f:
            f.write(html)

    def _generate_junit_report(self, results: List[Dict[str, Any]], output_path: Path):
        """Generate JUnit XML report from results."""
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom

        testsuites = Element("testsuites")
        testsuite = SubElement(testsuites, "testsuite")
        testsuite.set("name", "Azure Tenant Grapher Demo")
        testsuite.set("tests", str(len(results)))
        testsuite.set("failures", str(sum(1 for r in results if not r.get("success", False))))
        testsuite.set("time", str(sum(r.get("duration", 0) for r in results)))

        for result in results:
            testcase = SubElement(testsuite, "testcase")
            testcase.set("name", result.get("name", "Unknown"))
            testcase.set("classname", "DemoScenario")
            testcase.set("time", str(result.get("duration", 0)))

            if not result.get("success", False):
                failure = SubElement(testcase, "failure")
                failure.set("message", result.get("error", "Test failed"))
                failure.text = str(result)

        # Pretty print XML
        rough_string = tostring(testsuites, 'utf-8')
        reparsed = minidom.parseString(rough_string)

        with open(output_path, 'w') as f:
            f.write(reparsed.toprettyxml(indent="  "))

    async def generate_gallery(self):
        """Generate HTML gallery from screenshots."""
        self.logger.info("Generating screenshot gallery...")
        gallery_path = await self.screenshots.generate_gallery(self.config['gallery'])
        self.logger.info(f"Gallery saved to: {gallery_path}")
        return gallery_path

    async def run(self, story: Optional[str] = None, scenario: Optional[str] = None,
                  gallery_only: bool = False) -> List[Dict[str, Any]]:
        """Main execution method."""
        if gallery_only:
            await self.generate_gallery()
            return []

        try:
            await self.setup_browser()

            if scenario:
                # Run single scenario
                result = await self.run_scenario(scenario)
                self.results = [result]
            elif story:
                # Run story
                self.results = await self.run_story(story)
            else:
                # Run default story
                default_story = self.config['stories']['default']
                self.results = await self.run_story(default_story)

            # Generate reports
            self.generate_report(self.results)

            # Generate gallery if screenshots were taken
            if any(r.get("screenshots") for r in self.results):
                await self.generate_gallery()

            return self.results

        finally:
            await self.teardown_browser()


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Azure Tenant Grapher Demo Orchestrator")
    parser.add_argument("--config", default="config.yaml", help="Configuration file path")
    parser.add_argument("--story", help="Story to run")
    parser.add_argument("--scenario", help="Individual scenario to run")
    parser.add_argument("--gallery", action="store_true", help="Generate gallery only")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = DemoOrchestrator(args.config)

    # Override config if needed
    if args.headless:
        orchestrator.config['test']['headless'] = True
    if args.debug:
        orchestrator.config['logging']['level'] = 'debug'

    # Run demo
    results = await orchestrator.run(
        story=args.story,
        scenario=args.scenario,
        gallery_only=args.gallery
    )

    # Print summary
    if results:
        total = len(results)
        passed = sum(1 for r in results if r.get("success", False))
        print(f"\n{'='*50}")
        print(f"Demo Execution Complete")
        print(f"{'='*50}")
        print(f"Total Scenarios: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"{'='*50}\n")

        # Exit with error if any tests failed
        if passed < total:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())