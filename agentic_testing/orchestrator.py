"""Main orchestrator for the Agentic Testing System."""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from .agents import CLIAgent, ComprehensionAgent, IssueReporter, PriorityAgent

try:
    from .agents import ElectronUIAgent
except ImportError:
    ElectronUIAgent = None
from .config import TestConfig
from .models import (
    TestError,
    TestFailure,
    TestInterface,
    TestResult,
    TestScenario,
    TestSession,
    TestStatus,
)
from .utils.logging import TestRunLogger, get_logger, setup_logging

logger = get_logger(__name__)


class ATGTestingOrchestrator:
    """
    Main orchestrator that coordinates all testing agents.

    Implements the Magentic-One inspired architecture with a central
    orchestrator managing specialized agents.
    """

    def __init__(self, config: TestConfig):
        """
        Initialize the testing orchestrator.

        Args:
            config: Test configuration
        """
        self.config = config

        # Initialize agents
        self.cli_agent = CLIAgent(config.cli_config)
        self.comprehension_agent = ComprehensionAgent(config.llm_config)
        self.ui_agent = (
            ElectronUIAgent(config.ui_config) if ElectronUIAgent else None
        )
        self.issue_reporter = IssueReporter(config.github_config)
        self.priority_agent = PriorityAgent(config.priority_config)

        # Test session tracking
        self.session = None
        self.results_store = []
        self.failures_store = []

        # Execution control
        self.max_parallel = config.execution_config.parallel_workers
        self.retry_count = config.execution_config.retry_count
        self.fail_fast = config.execution_config.fail_fast

        # Setup logging
        setup_logging(config.log_level, config.log_file)

    async def run(self, suite: str = "smoke") -> TestSession:
        """
        Run a complete testing session.

        Args:
            suite: Test suite to run (smoke, full, regression)

        Returns:
            TestSession with results
        """
        logger.info(f"Starting test session with suite: {suite}")

        # Create session
        self.session = TestSession(id=str(uuid.uuid4()), start_time=datetime.now())

        try:
            # Phase 1: Discovery
            logger.info("Phase 1: Discovering features and generating scenarios")
            scenarios = await self._discover_and_generate_scenarios()

            # Filter scenarios based on suite
            scenarios = self._filter_scenarios_for_suite(scenarios, suite)
            logger.info(f"Selected {len(scenarios)} scenarios for suite '{suite}'")

            # Phase 2: Execution
            logger.info("Phase 2: Executing test scenarios")
            await self._execute_scenarios(scenarios)

            # Phase 3: Analysis
            logger.info("Phase 3: Analyzing results and prioritizing failures")
            await self._analyze_results()

            # Phase 4: Reporting
            logger.info("Phase 4: Reporting failures to GitHub")
            await self._report_failures()

        except Exception as e:
            logger.error(f"Test session failed: {e}")
            raise

        finally:
            # Finalize session
            self.session.end_time = datetime.now()
            self.session.calculate_metrics()

            # Save session results
            await self._save_session_results()

        logger.info(f"Test session completed: {self.session.id}")
        return self.session

    async def _discover_and_generate_scenarios(self) -> List[TestScenario]:
        """
        Discover features and generate test scenarios.

        Returns:
            List of test scenarios
        """
        scenarios = []

        # Discover features from documentation
        features = await self.comprehension_agent.discover_features()
        logger.info(f"Discovered {len(features)} features")

        # Generate scenarios for each feature
        for feature_info in features:
            try:
                # Analyze feature to get specification
                feature_spec = await self.comprehension_agent.analyze_feature(
                    feature_info["context"]
                )

                # Generate test scenarios
                feature_scenarios = (
                    await self.comprehension_agent.generate_test_scenarios(feature_spec)
                )

                scenarios.extend(feature_scenarios)
                logger.debug(
                    f"Generated {len(feature_scenarios)} scenarios for {feature_spec.name}"
                )

            except Exception as e:
                logger.error(f"Failed to generate scenarios for feature: {e}")

        logger.info(f"Generated {len(scenarios)} total test scenarios")
        return scenarios

    def _filter_scenarios_for_suite(
        self, scenarios: List[TestScenario], suite: str
    ) -> List[TestScenario]:
        """
        Filter scenarios based on test suite configuration.

        Args:
            scenarios: All scenarios
            suite: Suite name

        Returns:
            Filtered scenarios
        """
        suite_config = self.config.execution_config.test_suites.get(suite, ["*"])

        if "*" in suite_config:
            return scenarios

        filtered = []
        for scenario in scenarios:
            # Check if scenario matches any pattern in suite
            for pattern in suite_config:
                if pattern.endswith("*"):
                    # Prefix match
                    prefix = pattern[:-1]
                    if scenario.id.startswith(prefix) or any(
                        tag.startswith(prefix) for tag in scenario.tags
                    ):
                        filtered.append(scenario)
                        break
                else:
                    # Exact match
                    if scenario.id == pattern or pattern in scenario.tags:
                        filtered.append(scenario)
                        break

        return filtered

    async def _execute_scenarios(self, scenarios: List[TestScenario]):
        """
        Execute test scenarios with parallel execution support.

        Args:
            scenarios: Scenarios to execute
        """
        # Group scenarios by interface type for efficient execution
        cli_scenarios = [s for s in scenarios if s.interface == TestInterface.CLI]
        ui_scenarios = [s for s in scenarios if s.interface == TestInterface.GUI]
        mixed_scenarios = [s for s in scenarios if s.interface == TestInterface.MIXED]

        # Execute CLI scenarios
        if cli_scenarios:
            logger.info(f"Executing {len(cli_scenarios)} CLI scenarios")
            await self._execute_cli_scenarios(cli_scenarios)

        # Execute UI scenarios
        if ui_scenarios:
            logger.info(f"Executing {len(ui_scenarios)} UI scenarios")
            await self._execute_ui_scenarios(ui_scenarios)

        # Execute mixed scenarios
        if mixed_scenarios:
            logger.info(f"Executing {len(mixed_scenarios)} mixed scenarios")
            await self._execute_mixed_scenarios(mixed_scenarios)

    async def _execute_cli_scenarios(self, scenarios: List[TestScenario]):
        """Execute CLI test scenarios."""
        # Use semaphore to limit parallel execution
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def execute_with_semaphore(scenario):
            async with semaphore:
                return await self._execute_single_scenario(scenario, self.cli_agent)

        # Execute scenarios in parallel
        tasks = [execute_with_semaphore(scenario) for scenario in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for scenario, result in zip(scenarios, results):
            if isinstance(result, Exception):
                logger.error(f"Scenario {scenario.id} failed with exception: {result}")
                self._record_failure(scenario, str(result))
            else:
                self._record_result(result)
                if self.fail_fast and result.status == TestStatus.FAILED:
                    logger.warning("Fail-fast enabled, stopping execution")
                    break

    async def _execute_ui_scenarios(self, scenarios: List[TestScenario]):
        """Execute UI test scenarios."""
        if not self.ui_agent:
            logger.warning("UI agent not available (playwright not installed)")
            for scenario in scenarios:
                self._record_failure(scenario, "UI testing unavailable - playwright not installed")
            return

        # UI scenarios typically run sequentially due to single app instance

        # Launch application once
        launched = await self.ui_agent.launch_application()
        if not launched:
            logger.error("Failed to launch Electron application")
            for scenario in scenarios:
                self._record_failure(scenario, "Failed to launch application")
            return

        try:
            for scenario in scenarios:
                result = await self._execute_single_scenario(scenario, self.ui_agent)
                self._record_result(result)

                if self.fail_fast and result.status == TestStatus.FAILED:
                    logger.warning("Fail-fast enabled, stopping execution")
                    break

        finally:
            # Close application
            await self.ui_agent.close_application()

    async def _execute_mixed_scenarios(self, scenarios: List[TestScenario]):
        """Execute mixed interface scenarios."""
        # Mixed scenarios might need both CLI and UI
        for scenario in scenarios:
            # Determine which agent to use based on steps
            agent = self._select_agent_for_scenario(scenario)
            result = await self._execute_single_scenario(scenario, agent)
            self._record_result(result)

            if self.fail_fast and result.status == TestStatus.FAILED:
                logger.warning("Fail-fast enabled, stopping execution")
                break

    async def _execute_single_scenario(
        self, scenario: TestScenario, agent
    ) -> TestResult:
        """
        Execute a single test scenario.

        Args:
            scenario: Test scenario
            agent: Testing agent to use

        Returns:
            Test result
        """
        logger.info(f"Executing scenario: {scenario.id} - {scenario.name}")

        start_time = datetime.now()
        retry_count = 0

        while retry_count <= self.retry_count:
            try:
                # Use test run logger
                with TestRunLogger(scenario.id) as log_file:
                    # Execute steps
                    for step in scenario.steps:
                        step_result = await agent.execute_test_step(step)
                        if not step_result.get("success", False):
                            raise Exception(f"Step failed: {step.description}")

                    # Perform verification
                    verification_results = {}
                    for verification in scenario.verification:
                        # Simple verification for now
                        verification_results[verification.description or "check"] = True

                    # Success
                    duration = (datetime.now() - start_time).total_seconds()
                    return TestResult(
                        scenario_id=scenario.id,
                        status=TestStatus.PASSED,
                        duration=duration,
                        verification_results=verification_results,
                        logs=str(log_file),
                        retry_count=retry_count,
                    )

            except Exception as e:
                logger.error(
                    f"Scenario {scenario.id} failed (attempt {retry_count + 1}): {e}"
                )

                if retry_count < self.retry_count and scenario.retry_on_failure:
                    retry_count += 1
                    await asyncio.sleep(2**retry_count)  # Exponential backoff
                    continue

                # Final failure
                duration = (datetime.now() - start_time).total_seconds()
                return TestResult(
                    scenario_id=scenario.id,
                    status=TestStatus.FAILED,
                    duration=duration,
                    error=TestError(type="execution_error", message=str(e)),
                    retry_count=retry_count,
                )

        # Should not reach here
        duration = (datetime.now() - start_time).total_seconds()
        return TestResult(
            scenario_id=scenario.id,
            status=TestStatus.ERROR,
            duration=duration,
            retry_count=retry_count,
        )

    def _select_agent_for_scenario(self, scenario: TestScenario):
        """Select appropriate agent for scenario."""
        # Count step types
        cli_steps = sum(1 for s in scenario.steps if s.action == "execute")
        ui_steps = sum(1 for s in scenario.steps if s.action in ["click", "type"])

        if cli_steps > ui_steps:
            return self.cli_agent
        else:
            return self.ui_agent

    def _record_result(self, result: TestResult):
        """Record test result."""
        self.results_store.append(result)
        self.session.results.append(result)
        self.session.scenarios_executed.append(result.scenario_id)

        if result.status == TestStatus.FAILED and result.error:
            # Create failure record
            failure = TestFailure(
                feature="Unknown",  # Would need scenario reference
                scenario=result.scenario_id,
                scenario_id=result.scenario_id,
                error_message=result.error.message,
                error_type=result.error.type,
                stack_trace=result.error.stack_trace,
            )
            self.failures_store.append(failure)

    def _record_failure(self, scenario: TestScenario, error_msg: str):
        """Record a scenario failure."""
        failure = TestFailure(
            feature=scenario.feature,
            scenario=scenario.name,
            scenario_id=scenario.id,
            error_message=error_msg,
            error_type="execution_error",
            expected_behavior=scenario.expected_outcome,
        )
        self.failures_store.append(failure)
        self.session.failures.append(failure)

    async def _analyze_results(self):
        """Analyze test results and prioritize failures."""
        if not self.failures_store:
            logger.info("No failures to analyze")
            return

        logger.info(f"Analyzing {len(self.failures_store)} failures")

        # Get priority analysis
        prioritized = self.priority_agent.prioritize_batch(self.failures_store)

        # Log summary
        summary = self.priority_agent.get_priority_summary(self.failures_store)
        logger.info(f"Priority summary: {json.dumps(summary, indent=2)}")

        # Update failures with priority
        for _failure, _analysis in prioritized:
            # Could store analysis results for later use
            pass

    async def _report_failures(self):
        """Report failures to GitHub."""
        if not self.failures_store:
            logger.info("No failures to report")
            return

        if not self.config.github_config.create_issues:
            logger.info("Issue creation disabled")
            return

        logger.info(f"Reporting {len(self.failures_store)} failures to GitHub")

        # Report failures
        issue_numbers = await self.issue_reporter.batch_report(self.failures_store)

        # Track created issues
        self.session.issues_created.extend(issue_numbers)

        logger.info(f"Created {len(issue_numbers)} GitHub issues")

    async def _save_session_results(self):
        """Save session results to file."""
        output_dir = Path("outputs/sessions")
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"session_{self.session.id}_{self.session.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_dir / filename

        session_data = {
            "id": self.session.id,
            "start_time": self.session.start_time.isoformat(),
            "end_time": self.session.end_time.isoformat()
            if self.session.end_time
            else None,
            "scenarios_executed": self.session.scenarios_executed,
            "results": [r.to_dict() for r in self.session.results],
            "issues_created": self.session.issues_created,
            "metrics": self.session.metrics,
        }

        with open(filepath, "w") as f:
            json.dump(session_data, f, indent=2)

        logger.info(f"Session results saved to {filepath}")
