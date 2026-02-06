#!/usr/bin/env python3
"""
Auto-Improving Upweight Factor Test Script

Tests the effectiveness of rare_boost_factor parameter in architecture-based replication
by measuring node coverage differences between baseline (1.0) and boosted (5.0) values.
If coverage difference is below threshold, automatically tries improvement strategies
to modify the boost multipliers and thresholds in the source code.

Architecture:
    Layer 1: Safety & State Management (TestSession)
    Layer 2: Core Testing (test_rare_boost_factor, compute_coverage_difference)
    Layer 3: Improvement Strategies (STRATEGIES, apply_strategy, reload_replicator)
    Layer 4: Orchestration (run_improvement_loop, main)

Usage:
    # Run full improvement loop
    python scripts/test_rare_boost_factor.py

    # Test baseline only (no modifications)
    python scripts/test_rare_boost_factor.py --dry-run

    # Test single strategy
    python scripts/test_rare_boost_factor.py --strategy 0
"""

import argparse
import importlib
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# Layer 1: Safety & State Management
# =============================================================================


@dataclass
class IterationResult:
    """Result from a single improvement iteration."""

    strategy_name: str
    coverage_diff: float
    metrics_1_0: Dict[str, Any]
    metrics_5_0: Dict[str, Any]
    success: bool
    error: Optional[str] = None


@dataclass
class TestSession:
    """
    Manages test session state, backup/restore, and iteration tracking.

    Responsibilities:
    - Create backup of target file before modifications
    - Track iteration results
    - Restore original code on exit
    - Generate test report
    """

    target_file: Path
    backup_file: Path = field(init=False)
    iterations: List[IterationResult] = field(default_factory=list)
    original_content: str = field(init=False)

    def __post_init__(self):
        """Create backup immediately after initialization."""
        if not self.target_file.exists():
            raise FileNotFoundError(f"Target file not found: {self.target_file}")

        self.original_content = self.target_file.read_text()
        self.backup_file = self.target_file.with_suffix(".py.backup")

        # Create backup
        self.backup_file.write_text(self.original_content)
        logger.info(f"Created backup: {self.backup_file}")

    def record_iteration(
        self,
        strategy_name: str,
        coverage_diff: float,
        metrics_1_0: Dict[str, Any],
        metrics_5_0: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record results from an improvement iteration."""
        result = IterationResult(
            strategy_name=strategy_name,
            coverage_diff=coverage_diff,
            metrics_1_0=metrics_1_0,
            metrics_5_0=metrics_5_0,
            success=success,
            error=error,
        )
        self.iterations.append(result)
        logger.info(
            f"Iteration {len(self.iterations)}: {strategy_name} → "
            f"coverage_diff={coverage_diff:.2f}% (success={success})"
        )

    def restore(self) -> None:
        """Restore original code from backup."""
        self.target_file.write_text(self.original_content)
        logger.info(f"Restored original code to {self.target_file}")

        # Clean up backup file
        if self.backup_file.exists():
            self.backup_file.unlink()
            logger.info(f"Removed backup: {self.backup_file}")

    def save_report(self, output_path: Path) -> None:
        """Generate JSON report of test session."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "target_file": str(self.target_file),
            "iterations": [
                {
                    "strategy_name": it.strategy_name,
                    "coverage_diff": it.coverage_diff,
                    "success": it.success,
                    "error": it.error,
                    "metrics_1_0": it.metrics_1_0,
                    "metrics_5_0": it.metrics_5_0,
                }
                for it in self.iterations
            ],
            "best_strategy": self._find_best_strategy(),
        }

        output_path.write_text(json.dumps(report, indent=2))
        logger.info(f"Saved report: {output_path}")

    def _find_best_strategy(self) -> Optional[Dict[str, Any]]:
        """Find strategy with highest coverage difference."""
        if not self.iterations:
            return None

        best = max(self.iterations, key=lambda it: it.coverage_diff)
        return {
            "strategy_name": best.strategy_name,
            "coverage_diff": best.coverage_diff,
            "success": best.success,
        }


# =============================================================================
# Layer 2: Core Testing
# =============================================================================


def test_rare_boost_factor(
    replicator: Any, rare_boost_factor: float, test_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Test replicator with specific rare_boost_factor and extract metrics.

    Args:
        replicator: ArchitecturePatternReplicator instance
        rare_boost_factor: Upweight factor value to test
        test_params: Fixed parameters (target_instance_count, max_samples, etc.)

    Returns:
        Dictionary with metrics (node_coverage, instance_count, etc.)
    """
    logger.info(f"Testing rare_boost_factor={rare_boost_factor}")

    try:
        # generate_replication_plan returns (pattern_instances, spectral_history, distribution_metadata)
        # Now uses recommended defaults; only override what's needed for testing
        pattern_instances, spectral_history, distribution_metadata = replicator.generate_replication_plan(
            target_instance_count=test_params["target_instance_count"],
            spectral_weight=0.1,  # Override to match old notebook behavior
            max_config_samples=test_params["max_config_samples"],
            rare_boost_factor=rare_boost_factor,
            missing_type_threshold=test_params["missing_type_threshold"],
        )

        # Extract metrics
        source_nodes = set(replicator.source_pattern_graph.nodes())
        target_nodes = set()

        # pattern_instances is a list of (pattern_name, instances) tuples
        for pattern_name, instances in pattern_instances:
            for instance in instances:
                for resource in instance:
                    target_nodes.add(resource["type"])

        # Compute node coverage
        covered_nodes = target_nodes & source_nodes
        node_coverage = (
            (len(covered_nodes) / len(source_nodes) * 100) if source_nodes else 0.0
        )

        # Count total instances
        total_instances = sum(len(instances) for _, instances in pattern_instances)

        metrics = {
            "rare_boost_factor": rare_boost_factor,
            "instance_count": total_instances,
            "source_nodes": len(source_nodes),
            "target_nodes": len(target_nodes),
            "covered_nodes": len(covered_nodes),
            "node_coverage": node_coverage,
        }

        logger.info(
            f"  instance_count={metrics['instance_count']}, "
            f"node_coverage={node_coverage:.2f}%"
        )

        return metrics

    except Exception as e:
        logger.error(f"Test failed for rare_boost_factor={rare_boost_factor}: {e}")
        raise


def compute_coverage_difference(
    metrics_1_0: Dict[str, Any], metrics_5_0: Dict[str, Any]
) -> float:
    """
    Compute percentage difference in node coverage between two test runs.

    Args:
        metrics_1_0: Metrics from rare_boost_factor=1.0 test
        metrics_5_0: Metrics from rare_boost_factor=5.0 test

    Returns:
        Percentage point difference (metrics_5_0 - metrics_1_0)
    """
    cov_1_0 = metrics_1_0["node_coverage"]
    cov_5_0 = metrics_5_0["node_coverage"]
    diff = cov_5_0 - cov_1_0

    logger.info(
        f"Coverage difference: {cov_5_0:.2f}% - {cov_1_0:.2f}% = {diff:.2f} percentage points"
    )

    return diff


# =============================================================================
# Layer 3: Improvement Strategies
# =============================================================================

# Strategy definitions
STRATEGIES = [
    # Boost multiplier strategies
    {
        "name": "boost_8_4",
        "type": "boost_multipliers",
        "orphaned": 8.0,
        "missing": 4.0,
        "description": "Increase missing boost to 8x, underrepresented to 4x",
    },
    {
        "name": "boost_10_5",
        "type": "boost_multipliers",
        "orphaned": 10.0,
        "missing": 5.0,
        "description": "Increase missing boost to 10x, underrepresented to 5x",
    },
    {
        "name": "boost_12_6",
        "type": "boost_multipliers",
        "orphaned": 12.0,
        "missing": 6.0,
        "description": "Increase missing boost to 12x, underrepresented to 6x",
    },
    # Threshold strategies
    {
        "name": "threshold_0.05",
        "type": "threshold",
        "threshold": 0.05,
        "description": "Lower threshold to 0.05 (more aggressive underrepresented detection)",
    },
    {
        "name": "threshold_0.15",
        "type": "threshold",
        "threshold": 0.15,
        "description": "Raise threshold to 0.15 (less aggressive underrepresented detection)",
    },
]


def apply_strategy(session: TestSession, strategy: Dict[str, Any]) -> None:
    """
    Apply improvement strategy by modifying source code.

    Modifies architecture_based_replicator.py based on strategy type:
    - boost_multipliers: Change hardcoded boost values (6.0, 3.0)
    - threshold: Change missing_type_threshold default (0.1)

    Args:
        session: TestSession with target file
        strategy: Strategy dictionary with type and parameters

    Raises:
        SyntaxError: If modified code has syntax errors
        ValueError: If strategy type is unknown
    """
    logger.info(f"Applying strategy: {strategy['name']} ({strategy['description']})")

    content = session.target_file.read_text()
    original_content = content

    try:
        if strategy["type"] == "boost_multipliers":
            # Replace hardcoded boost multipliers
            # Line 2214: return 6.0 * rare_boost_factor  (missing/orphaned)
            # Line 2220: return 3.0 * rare_boost_factor  (underrepresented)

            orphaned_boost = strategy["orphaned"]
            missing_boost = strategy["missing"]

            # Replace missing boost (line 2214)
            content = content.replace(
                "return 6.0 * rare_boost_factor", f"return {orphaned_boost} * rare_boost_factor"
            )

            # Replace underrepresented boost (line 2220)
            content = content.replace(
                "return 3.0 * rare_boost_factor", f"return {missing_boost} * rare_boost_factor"
            )

            logger.info(
                f"  Modified boost multipliers: missing={orphaned_boost}, underrepresented={missing_boost}"
            )

        elif strategy["type"] == "threshold":
            # Replace missing_type_threshold default value
            # Multiple function signatures have this parameter
            threshold = strategy["threshold"]

            # Replace all instances of missing_type_threshold: float = 0.1
            content = content.replace(
                "missing_type_threshold: float = 0.1",
                f"missing_type_threshold: float = {threshold}",
            )

            logger.info(f"  Modified threshold default: {threshold}")

        else:
            raise ValueError(f"Unknown strategy type: {strategy['type']}")

        # Validate syntax before writing
        compile(content, session.target_file, "exec")

        # Write modified content
        session.target_file.write_text(content)
        logger.info(f"  Successfully modified {session.target_file}")

    except SyntaxError as e:
        # Restore original content on syntax error
        session.target_file.write_text(original_content)
        logger.error(f"  Syntax error after modification: {e}")
        raise

    except Exception as e:
        # Restore original content on any error
        session.target_file.write_text(original_content)
        logger.error(f"  Error applying strategy: {e}")
        raise


def reload_replicator() -> Any:
    """
    Reload ArchitecturePatternReplicator module after code modification.

    Returns:
        Fresh ArchitecturePatternReplicator class

    Raises:
        ImportError: If module reload fails
    """
    try:
        # Remove cached module
        if "src.architecture_based_replicator" in sys.modules:
            del sys.modules["src.architecture_based_replicator"]

        # Reimport module
        module = importlib.import_module("src.architecture_based_replicator")
        logger.info("Successfully reloaded ArchitecturePatternReplicator module")

        return module.ArchitecturePatternReplicator

    except ImportError as e:
        logger.error(f"Failed to reload module: {e}")
        raise


# =============================================================================
# Layer 4: Orchestration
# =============================================================================


def run_improvement_loop(
    session: TestSession,
    replicator_class: Any,
    neo4j_config: Dict[str, str],
    test_params: Dict[str, Any],
    max_iterations: int = 10,
    success_threshold: float = 5.0,
) -> Dict[str, Any]:
    """
    Run improvement loop: test strategies until success or max iterations.

    Iterations:
    1. Test baseline (rare_boost_factor=1.0 and 5.0)
    2. If coverage_diff < success_threshold, try improvement strategies
    3. For each strategy: apply → reload → test → record
    4. Stop on success (coverage_diff >= success_threshold) or max iterations

    Args:
        session: TestSession for state management
        replicator_class: ArchitecturePatternReplicator class
        neo4j_config: Neo4j connection configuration
        test_params: Fixed test parameters
        max_iterations: Maximum number of strategies to try
        success_threshold: Minimum coverage difference for success (percentage points)

    Returns:
        Dictionary with final results and best strategy
    """
    logger.info("=" * 80)
    logger.info("Starting improvement loop")
    logger.info(f"Success threshold: {success_threshold} percentage points")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info("=" * 80)

    # Baseline test (iteration 0)
    logger.info("\n[Iteration 0] Baseline test")
    try:
        replicator = replicator_class(**neo4j_config)

        # Analyze source tenant first (required)
        logger.info("Analyzing source tenant...")
        replicator.analyze_source_tenant(
            use_configuration_coherence=True,
            coherence_threshold=0.5
        )
        logger.info(f"Source tenant has {replicator.source_pattern_graph.number_of_nodes()} resource types")

        metrics_1_0 = test_rare_boost_factor(replicator, 1.0, test_params)
        metrics_5_0 = test_rare_boost_factor(replicator, 5.0, test_params)
        coverage_diff = compute_coverage_difference(metrics_1_0, metrics_5_0)

        session.record_iteration(
            strategy_name="baseline",
            coverage_diff=coverage_diff,
            metrics_1_0=metrics_1_0,
            metrics_5_0=metrics_5_0,
            success=(coverage_diff >= success_threshold),
        )

        if coverage_diff >= success_threshold:
            logger.info(f"\n✓ Baseline already meets success threshold ({coverage_diff:.2f}% >= {success_threshold}%)")
            logger.info("No improvement needed.")
            return {"success": True, "iterations": 1, "best_strategy": "baseline"}

        logger.info(
            f"\n✗ Baseline below threshold ({coverage_diff:.2f}% < {success_threshold}%)"
        )
        logger.info("Trying improvement strategies...")

    except Exception as e:
        logger.error(f"Baseline test failed: {e}")
        session.record_iteration(
            strategy_name="baseline",
            coverage_diff=0.0,
            metrics_1_0={},
            metrics_5_0={},
            success=False,
            error=str(e),
        )
        return {"success": False, "iterations": 1, "error": str(e)}

    # Improvement iterations
    for iteration in range(1, min(max_iterations + 1, len(STRATEGIES) + 1)):
        strategy = STRATEGIES[iteration - 1]

        logger.info(f"\n[Iteration {iteration}] Testing strategy: {strategy['name']}")
        logger.info(f"  {strategy['description']}")

        try:
            # Apply strategy
            apply_strategy(session, strategy)

            # Reload module
            replicator_class = reload_replicator()

            # Test with new code
            replicator = replicator_class(**neo4j_config)

            # Analyze source tenant first (required)
            logger.info("Analyzing source tenant...")
            replicator.analyze_source_tenant(
                use_configuration_coherence=True,
                coherence_threshold=0.5
            )

            metrics_1_0 = test_rare_boost_factor(replicator, 1.0, test_params)
            metrics_5_0 = test_rare_boost_factor(replicator, 5.0, test_params)
            coverage_diff = compute_coverage_difference(metrics_1_0, metrics_5_0)

            success = coverage_diff >= success_threshold
            session.record_iteration(
                strategy_name=strategy["name"],
                coverage_diff=coverage_diff,
                metrics_1_0=metrics_1_0,
                metrics_5_0=metrics_5_0,
                success=success,
            )

            if success:
                logger.info(
                    f"\n✓ SUCCESS! Strategy '{strategy['name']}' achieves "
                    f"{coverage_diff:.2f}% coverage difference (>= {success_threshold}%)"
                )
                logger.info(
                    f"\nRecommendation: Apply '{strategy['name']}' permanently"
                )
                logger.info(f"  {strategy['description']}")
                return {
                    "success": True,
                    "iterations": iteration + 1,
                    "best_strategy": strategy["name"],
                }

            # Restore for next iteration
            session.restore()
            session.original_content = session.target_file.read_text()

        except Exception as e:
            logger.error(f"Strategy '{strategy['name']}' failed: {e}")
            session.record_iteration(
                strategy_name=strategy["name"],
                coverage_diff=0.0,
                metrics_1_0={},
                metrics_5_0={},
                success=False,
                error=str(e),
            )

            # Restore on error
            session.restore()
            session.original_content = session.target_file.read_text()

            # Reload clean module
            try:
                replicator_class = reload_replicator()
            except ImportError:
                logger.error("Failed to reload module after error, stopping")
                return {
                    "success": False,
                    "iterations": iteration + 1,
                    "error": "Module reload failed",
                }

    # Max iterations reached without success
    logger.info(f"\n✗ Max iterations ({max_iterations}) reached without success")

    # Find best strategy (highest coverage_diff)
    best = session._find_best_strategy()
    if best:
        logger.info(f"\nBest strategy: {best['strategy_name']} ({best['coverage_diff']:.2f}%)")

    return {
        "success": False,
        "iterations": len(session.iterations),
        "best_strategy": best["strategy_name"] if best else None,
    }


def main(args: argparse.Namespace) -> int:
    """
    Main entry point with CLI argument handling.

    Modes:
    - No args: Run full improvement loop
    - --dry-run: Test baseline only (no modifications)
    - --strategy N: Test single strategy (0-based index)

    Returns:
        Exit code (0 = success, 1 = error)
    """
    # Configuration
    project_root = Path(__file__).parent.parent
    target_file = project_root / "src" / "architecture_based_replicator.py"

    # Neo4j configuration from environment
    import os

    neo4j_config = {
        "neo4j_uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
        "neo4j_password": os.getenv("NEO4J_PASSWORD", "password"),
    }

    # Fixed test parameters (matching notebook configuration)
    test_params = {
        "target_instance_count": 500,  # Match notebook baseline
        "max_config_samples": 500,      # Allow sufficient sampling
        "missing_type_threshold": 0.1,
    }

    # Safety check: ensure we're in a git repository
    git_dir = project_root / ".git"
    if not git_dir.exists():
        logger.error("Not in a git repository. Refusing to modify code.")
        return 1

    # Check git status
    import subprocess

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            logger.warning("Git working directory has uncommitted changes")
            logger.warning("Recommendation: commit or stash changes before running")
            if not args.yes:
                response = input("Continue anyway? [y/N]: ")
                if response.lower() != "y":
                    logger.info("Aborted")
                    return 0
            else:
                logger.info("Continuing with uncommitted changes (--yes flag)")
    except subprocess.CalledProcessError:
        logger.warning("Could not check git status")

    # Import replicator class
    try:
        sys.path.insert(0, str(project_root))
        from src.architecture_based_replicator import ArchitecturePatternReplicator

        logger.info(f"Loaded ArchitecturePatternReplicator from {target_file}")
    except ImportError as e:
        logger.error(f"Failed to import ArchitecturePatternReplicator: {e}")
        return 1

    # Create test session
    session = TestSession(target_file=target_file)

    try:
        if args.dry_run:
            # Dry run mode: test baseline only
            logger.info("DRY RUN MODE: Testing baseline only (no modifications)")
            logger.info("=" * 80)

            replicator = ArchitecturePatternReplicator(**neo4j_config)

            # Analyze source tenant first (required)
            logger.info("Analyzing source tenant...")
            replicator.analyze_source_tenant(
                use_configuration_coherence=True,
                coherence_threshold=0.5
            )
            logger.info(f"Source tenant has {replicator.source_pattern_graph.number_of_nodes()} resource types")

            metrics_1_0 = test_rare_boost_factor(replicator, 1.0, test_params)
            metrics_5_0 = test_rare_boost_factor(replicator, 5.0, test_params)
            coverage_diff = compute_coverage_difference(metrics_1_0, metrics_5_0)

            session.record_iteration(
                strategy_name="baseline",
                coverage_diff=coverage_diff,
                metrics_1_0=metrics_1_0,
                metrics_5_0=metrics_5_0,
                success=(coverage_diff >= 5.0),
            )

            print("\n" + "=" * 80)
            print("DRY RUN RESULTS")
            print("=" * 80)
            print(f"Coverage difference: {coverage_diff:.2f} percentage points")
            print(f"Baseline (upweight=1.0): {metrics_1_0['node_coverage']:.2f}%")
            print(f"Boosted (upweight=5.0):  {metrics_5_0['node_coverage']:.2f}%")
            print("=" * 80)

        elif args.strategy is not None:
            # Single strategy mode
            if args.strategy < 0 or args.strategy >= len(STRATEGIES):
                logger.error(
                    f"Invalid strategy index: {args.strategy} (must be 0-{len(STRATEGIES)-1})"
                )
                return 1

            strategy = STRATEGIES[args.strategy]
            logger.info(f"SINGLE STRATEGY MODE: Testing {strategy['name']}")
            logger.info("=" * 80)

            # Apply strategy
            apply_strategy(session, strategy)

            # Reload and test
            replicator_class = reload_replicator()
            replicator = replicator_class(**neo4j_config)

            # Analyze source tenant first (required)
            logger.info("Analyzing source tenant...")
            replicator.analyze_source_tenant(
                use_configuration_coherence=True,
                coherence_threshold=0.5
            )

            metrics_1_0 = test_rare_boost_factor(replicator, 1.0, test_params)
            metrics_5_0 = test_rare_boost_factor(replicator, 5.0, test_params)
            coverage_diff = compute_coverage_difference(metrics_1_0, metrics_5_0)

            session.record_iteration(
                strategy_name=strategy["name"],
                coverage_diff=coverage_diff,
                metrics_1_0=metrics_1_0,
                metrics_5_0=metrics_5_0,
                success=(coverage_diff >= 5.0),
            )

            print("\n" + "=" * 80)
            print(f"STRATEGY TEST RESULTS: {strategy['name']}")
            print("=" * 80)
            print(f"Coverage difference: {coverage_diff:.2f} percentage points")
            print(f"Baseline (upweight=1.0): {metrics_1_0['node_coverage']:.2f}%")
            print(f"Boosted (upweight=5.0):  {metrics_5_0['node_coverage']:.2f}%")
            print("=" * 80)

        else:
            # Full improvement loop mode
            result = run_improvement_loop(
                session=session,
                replicator_class=ArchitecturePatternReplicator,
                neo4j_config=neo4j_config,
                test_params=test_params,
                max_iterations=10,
                success_threshold=5.0,
            )

            print("\n" + "=" * 80)
            print("IMPROVEMENT LOOP RESULTS")
            print("=" * 80)
            print(f"Success: {result['success']}")
            print(f"Iterations: {result['iterations']}")
            if result.get("best_strategy"):
                print(f"Best strategy: {result['best_strategy']}")
            print("=" * 80)

            # Save report
            report_path = project_root / "upweight_test_report.json"
            session.save_report(report_path)

            return 0 if result["success"] else 1

    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    finally:
        # Always restore original code
        session.restore()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Auto-improving upweight factor test script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full improvement loop (default)
  python scripts/test_rare_boost_factor.py

  # Test baseline only (no modifications)
  python scripts/test_rare_boost_factor.py --dry-run

  # Test single strategy
  python scripts/test_rare_boost_factor.py --strategy 0
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test baseline only without modifications",
    )

    parser.add_argument(
        "--strategy",
        type=int,
        metavar="N",
        help=f"Test single strategy by index (0-{len(STRATEGIES)-1})",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip all prompts and assume yes (non-interactive mode)",
    )

    args = parser.parse_args()

    sys.exit(main(args))
