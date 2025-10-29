#!/usr/bin/env python3
"""
Scenario Runner Module

Purpose: Execute demo scenarios with proper error handling and retry logic
Contract: Run scenarios, handle failures, and provide execution results
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class ScenarioStep:
    """Represents a single step in a scenario."""

    def __init__(self, index: int, config: Dict[str, Any]):
        self.index = index
        self.description = config.get("description", f"Step {index}")
        self.action = config.get("action", "")
        self.selector = config.get("selector")
        self.value = config.get("value")
        self.url = config.get("url")
        self.key = config.get("key")
        self.timeout = config.get("timeout", 30000)
        self.wait_after = config.get("wait_after", 0)
        self.screenshot = config.get("screenshot", False)
        self.retry_count = config.get("retry", 3)
        self.optional = config.get("optional", False)
        self.config = config

    def should_retry(self, attempt: int) -> bool:
        """Check if step should be retried."""
        return attempt < self.retry_count


class ScenarioResult:
    """Result of scenario execution."""

    def __init__(self, name: str):
        self.name = name
        self.success = True
        self.steps: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.screenshots: List[str] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.duration = 0.0

    def add_step_result(self, step_result: Dict[str, Any]) -> None:
        """Add a step result."""
        self.steps.append(step_result)
        if not step_result.get("success", False):
            self.success = False
            if step_result.get("error"):
                self.errors.append(step_result["error"])

    def complete(self) -> None:
        """Mark scenario as complete."""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "success": self.success,
            "duration": self.duration,
            "steps": self.steps,
            "errors": self.errors,
            "screenshots": self.screenshots,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class ScenarioRunner:
    """
    Executes demo scenarios with error handling and retry logic.

    Public Interface:
        - load_scenario(path): Load scenario from file
        - run_scenario(scenario, page): Execute a scenario
        - run_step(step, page): Execute a single step
        - validate_scenario(scenario): Validate scenario configuration
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize scenario runner."""
        self.config = config or {}
        self.stop_on_failure = self.config.get("stop_on_failure", False)
        self.screenshot_on_failure = self.config.get("screenshot_on_failure", True)
        self.slow_mo = self.config.get("slow_mo", 0)
        self.default_timeout = self.config.get("timeout", 30000)
        self.screenshot_callback: Optional[Callable] = None

    def load_scenario(self, path: str) -> Dict[str, Any]:
        """
        Load scenario from YAML file.

        Args:
            path: Path to scenario file

        Returns:
            Scenario configuration

        Raises:
            FileNotFoundError: If scenario file not found
            ValueError: If scenario is invalid
        """
        scenario_path = Path(path)
        if not scenario_path.exists():
            # Try in scenarios directory
            scenario_path = Path("scenarios") / path
            if not scenario_path.suffix:
                scenario_path = scenario_path.with_suffix(".yaml")

        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario not found: {scenario_path}")

        try:
            with open(scenario_path) as f:
                scenario = yaml.safe_load(f)

            # Validate scenario
            self.validate_scenario(scenario)
            return scenario

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid scenario YAML: {e}")

    def validate_scenario(self, scenario: Dict[str, Any]) -> None:
        """
        Validate scenario configuration.

        Args:
            scenario: Scenario to validate

        Raises:
            ValueError: If scenario is invalid
        """
        if not scenario:
            raise ValueError("Scenario is empty")

        if "name" not in scenario:
            raise ValueError("Scenario missing 'name' field")

        if "steps" not in scenario or not scenario["steps"]:
            raise ValueError("Scenario has no steps")

        # Validate each step
        for i, step in enumerate(scenario["steps"]):
            if "action" not in step:
                raise ValueError(f"Step {i} missing 'action' field")

            action = step["action"]
            if action in ["click", "fill", "hover", "press"] and "selector" not in step:
                raise ValueError(f"Step {i} with action '{action}' missing 'selector'")

            if action == "fill" and "value" not in step:
                raise ValueError(f"Step {i} with action 'fill' missing 'value'")

            if action == "navigate" and "url" not in step:
                raise ValueError(f"Step {i} with action 'navigate' missing 'url'")

    async def run_scenario(
        self,
        scenario: Dict[str, Any],
        page: Page,
        screenshot_callback: Optional[Callable] = None,
    ) -> ScenarioResult:
        """
        Execute a scenario.

        Args:
            scenario: Scenario configuration
            page: Playwright page instance
            screenshot_callback: Optional callback for screenshots

        Returns:
            ScenarioResult with execution details
        """
        name = scenario.get("name", "unnamed")
        logger.info(f"Running scenario: {name}")

        result = ScenarioResult(name)
        self.screenshot_callback = screenshot_callback

        try:
            # Navigate if needed
            if scenario.get("navigate", True) and "url" in scenario:
                await page.goto(scenario["url"])
                await page.wait_for_load_state("networkidle")

            # Execute steps
            for i, step_config in enumerate(scenario.get("steps", [])):
                step = ScenarioStep(i, step_config)
                step_result = await self.run_step(step, page)

                result.add_step_result(step_result)

                # Handle screenshot
                if step.screenshot and screenshot_callback:
                    screenshot_path = await screenshot_callback(
                        page, name, i, step.description
                    )
                    if screenshot_path:
                        result.screenshots.append(screenshot_path)

                # Stop on failure if configured
                if not step_result["success"] and not step.optional:
                    if self.stop_on_failure:
                        logger.warning(
                            f"Stopping scenario due to step failure: {step.description}"
                        )
                        break

                    # Screenshot on failure
                    if self.screenshot_on_failure and screenshot_callback:
                        screenshot_path = await screenshot_callback(
                            page, name, f"error_{i}", "failure"
                        )
                        if screenshot_path:
                            result.screenshots.append(screenshot_path)

            # Run assertions
            for assertion in scenario.get("assertions", []):
                assertion_result = await self._run_assertion(page, assertion)
                if not assertion_result["success"]:
                    result.success = False
                    result.errors.append(assertion_result["message"])

        except Exception as e:
            logger.error(f"Scenario '{name}' failed: {e}")
            result.success = False
            result.errors.append(str(e))

            # Screenshot on error
            if self.screenshot_on_failure and screenshot_callback:
                try:
                    screenshot_path = await screenshot_callback(
                        page, name, "error", "exception"
                    )
                    if screenshot_path:
                        result.screenshots.append(screenshot_path)
                except Exception as e:
                    self.logger.debug(f"Cleanup error (non-critical): {e}")

        finally:
            result.complete()

        return result

    async def run_step(self, step: ScenarioStep, page: Page) -> Dict[str, Any]:
        """
        Execute a single step with retry logic.

        Args:
            step: Step to execute
            page: Playwright page instance

        Returns:
            Step execution result
        """
        logger.debug(f"Executing step {step.index}: {step.description}")

        result = {
            "index": step.index,
            "description": step.description,
            "action": step.action,
            "success": False,
            "attempts": 0,
            "duration": 0,
        }

        start_time = datetime.now()
        last_error = None

        for attempt in range(step.retry_count):
            result["attempts"] = attempt + 1

            try:
                # Add slow motion delay
                if self.slow_mo > 0:
                    await asyncio.sleep(self.slow_mo / 1000)

                # Execute action
                await self._execute_action(step, page)

                # Wait after action if specified
                if step.wait_after > 0:
                    await page.wait_for_timeout(step.wait_after)

                result["success"] = True
                logger.debug(f"Step {step.index} succeeded on attempt {attempt + 1}")
                break

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Step {step.index} failed on attempt {attempt + 1}: {e}"
                )

                if not step.should_retry(attempt + 1):
                    break

                # Wait before retry
                await asyncio.sleep(1)

        if not result["success"]:
            result["error"] = str(last_error)
            if not step.optional:
                logger.error(
                    f"Step {step.index} failed after {result['attempts']} attempts: {last_error}"
                )

        end_time = datetime.now()
        result["duration"] = (end_time - start_time).total_seconds()

        return result

    async def _execute_action(self, step: ScenarioStep, page: Page) -> None:
        """
        Execute a step action.

        Args:
            step: Step configuration
            page: Playwright page instance
        """
        action = step.action

        if action == "click":
            await page.click(step.selector, timeout=step.timeout)

        elif action == "fill":
            await page.fill(step.selector, step.value, timeout=step.timeout)

        elif action == "select":
            await page.select_option(step.selector, step.value, timeout=step.timeout)

        elif action == "wait":
            if step.selector:
                await page.wait_for_selector(step.selector, timeout=step.timeout)
            else:
                await page.wait_for_timeout(step.timeout)

        elif action == "navigate":
            await page.goto(step.url)
            await page.wait_for_load_state("networkidle")

        elif action == "hover":
            await page.hover(step.selector, timeout=step.timeout)

        elif action == "press":
            await page.press(step.selector, step.key, timeout=step.timeout)

        elif action == "scroll":
            position = step.config.get("position", "document.body.scrollHeight")
            await page.evaluate(f"window.scrollTo(0, {position})")

        elif action == "evaluate":
            code = step.config.get("code", "")
            await page.evaluate(code)

        elif action == "screenshot":
            # Handled separately
            pass

        elif action == "wait_for_load":
            state = step.config.get("state", "networkidle")
            await page.wait_for_load_state(state)

        elif action == "reload":
            await page.reload()
            await page.wait_for_load_state("networkidle")

        elif action == "go_back":
            await page.go_back()
            await page.wait_for_load_state("networkidle")

        elif action == "go_forward":
            await page.go_forward()
            await page.wait_for_load_state("networkidle")

        else:
            raise ValueError(f"Unknown action: {action}")

    async def _run_assertion(
        self, page: Page, assertion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run an assertion on the page.

        Args:
            page: Playwright page instance
            assertion: Assertion configuration

        Returns:
            Assertion result
        """
        result = {"success": False, "message": ""}

        try:
            assertion_type = assertion.get("type", "exists")
            selector = assertion.get("selector")

            if assertion_type == "exists":
                element = await page.query_selector(selector)
                if element:
                    result["success"] = True
                    result["message"] = f"Element exists: {selector}"
                else:
                    result["message"] = f"Element not found: {selector}"

            elif assertion_type == "visible":
                is_visible = await page.is_visible(selector)
                if is_visible:
                    result["success"] = True
                    result["message"] = f"Element visible: {selector}"
                else:
                    result["message"] = f"Element not visible: {selector}"

            elif assertion_type == "text":
                expected = assertion.get("value", "")
                actual = await page.text_content(selector)
                if expected in actual:
                    result["success"] = True
                    result["message"] = f"Text matches: {expected}"
                else:
                    result["message"] = (
                        f"Text mismatch. Expected: {expected}, Got: {actual}"
                    )

            elif assertion_type == "count":
                expected = assertion.get("value", 0)
                elements = await page.query_selector_all(selector)
                actual = len(elements)
                if actual == expected:
                    result["success"] = True
                    result["message"] = f"Element count matches: {expected}"
                else:
                    result["message"] = (
                        f"Count mismatch. Expected: {expected}, Got: {actual}"
                    )

            else:
                result["message"] = f"Unknown assertion type: {assertion_type}"

        except Exception as e:
            result["message"] = f"Assertion error: {e!s}"

        return result

    def get_scenario_list(self, directory: str = "scenarios") -> List[str]:
        """
        Get list of available scenarios.

        Args:
            directory: Directory to search for scenarios

        Returns:
            List of scenario names
        """
        scenario_dir = Path(directory)
        if not scenario_dir.exists():
            return []

        scenarios = []
        for file in scenario_dir.glob("*.yaml"):
            scenarios.append(file.stem)

        return sorted(scenarios)
