"""Main entry point for the Agentic Testing System."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import TestConfig
from .orchestrator import ATGTestingOrchestrator
from .utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Agentic Testing System for Azure Tenant Grapher"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="agentic_testing/config.yaml",
        help="Path to configuration file",
    )

    parser.add_argument(
        "--suite",
        type=str,
        choices=["smoke", "full", "regression"],
        default="smoke",
        help="Test suite to run",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Perform dry run without executing tests"
    )

    parser.add_argument(
        "--no-issues", action="store_true", help="Skip GitHub issue creation"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    parser.add_argument(
        "--output", type=str, help="Output file for results (JSON format)"
    )

    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_arguments()

    # Setup logging
    setup_logging(args.log_level)

    logger.info("Starting Agentic Testing System")
    logger.info(f"Configuration: {args.config}")
    logger.info(f"Test suite: {args.suite}")

    try:
        # Load configuration
        if Path(args.config).exists():
            config = TestConfig.from_yaml(args.config)
        else:
            logger.warning(f"Config file not found: {args.config}, using defaults")
            config = TestConfig()

        # Override with command line arguments
        if args.no_issues:
            config.github_config.create_issues = False

        config.log_level = args.log_level

        # Create orchestrator
        orchestrator = ATGTestingOrchestrator(config)

        if args.dry_run:
            logger.info("DRY RUN MODE - Not executing tests")
            # In dry run, just discover scenarios
            scenarios = await orchestrator._discover_and_generate_scenarios()
            scenarios = orchestrator._filter_scenarios_for_suite(scenarios, args.suite)

            print(f"\nWould execute {len(scenarios)} scenarios:")
            for scenario in scenarios:
                print(
                    f"  - [{scenario.interface.value}] {scenario.id}: {scenario.name}"
                )

            return 0

        # Run test session
        session = await orchestrator.run(suite=args.suite)

        # Display results
        print("\n" + "=" * 60)
        print("TEST SESSION RESULTS")
        print("=" * 60)
        print(f"Session ID: {session.id}")
        print(f"Duration: {session.metrics.get('duration', 0):.2f} seconds")
        print(f"Total Tests: {session.metrics.get('total_tests', 0)}")
        print(f"Passed: {session.metrics.get('passed', 0)}")
        print(f"Failed: {session.metrics.get('failed', 0)}")
        print(f"Skipped: {session.metrics.get('skipped', 0)}")
        print(f"Pass Rate: {session.metrics.get('pass_rate', 0):.1f}%")
        print(f"Issues Created: {len(session.issues_created)}")

        if session.issues_created:
            print("\nCreated Issues:")
            for issue_num in session.issues_created:
                print(f"  - #{issue_num}")

        # Save results if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            results_data = {
                "session_id": session.id,
                "suite": args.suite,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "metrics": session.metrics,
                "scenarios_executed": session.scenarios_executed,
                "issues_created": session.issues_created,
            }

            with open(output_path, "w") as f:
                json.dump(results_data, f, indent=2)

            print(f"\nResults saved to: {output_path}")

        # Return exit code based on failures
        if session.metrics.get("failed", 0) > 0:
            return 1
        return 0

    except Exception as e:
        logger.error(f"Testing system failed: {e}", exc_info=True)
        return 1


def run():
    """Run the main async function."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Testing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
