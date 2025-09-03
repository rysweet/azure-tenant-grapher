"""Priority agent for analyzing and prioritizing test failures."""

from typing import Any, Dict, List, Tuple

from ..config import PriorityConfig
from ..models import Priority, TestFailure
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PriorityAgent:
    """Agent responsible for prioritizing test failures and issues."""

    def __init__(self, config: PriorityConfig):
        """
        Initialize priority agent.

        Args:
            config: Priority configuration
        """
        self.config = config
        self.impact_weights = config.impact_weights
        self.auto_prioritize = config.auto_prioritize

        # Keywords for impact analysis
        self.critical_keywords = [
            "crash",
            "fatal",
            "critical",
            "security",
            "data loss",
            "corruption",
            "vulnerability",
            "authentication",
            "authorization",
        ]

        self.high_keywords = [
            "error",
            "fail",
            "broken",
            "cannot",
            "unable",
            "blocked",
            "missing",
            "incorrect",
            "wrong",
            "bug",
        ]

        self.medium_keywords = [
            "slow",
            "performance",
            "warning",
            "deprecated",
            "issue",
            "problem",
            "unexpected",
            "inconsistent",
        ]

        self.low_keywords = [
            "typo",
            "spelling",
            "formatting",
            "cosmetic",
            "ui",
            "minor",
            "enhancement",
            "suggestion",
        ]

    def analyze_failure(self, failure: TestFailure) -> Dict[str, Any]:
        """
        Analyze a test failure to determine its impact and priority.

        Args:
            failure: Test failure to analyze

        Returns:
            Analysis results with priority and reasoning
        """
        analysis = {
            "failure_id": failure.scenario_id,
            "feature": failure.feature,
            "impact_scores": {},
            "priority": Priority.MEDIUM,
            "reasoning": [],
            "recommendations": [],
        }

        # Calculate impact scores
        scores = self._calculate_impact_scores(failure)
        analysis["impact_scores"] = scores

        # Determine priority based on scores
        total_score = sum(scores.values())

        if total_score >= 4.0:
            analysis["priority"] = Priority.CRITICAL
            analysis["reasoning"].append(
                "High total impact score indicates critical issue"
            )
        elif total_score >= 2.5:
            analysis["priority"] = Priority.HIGH
            analysis["reasoning"].append(
                "Significant impact across multiple dimensions"
            )
        elif total_score >= 1.5:
            analysis["priority"] = Priority.MEDIUM
            analysis["reasoning"].append("Moderate impact on system functionality")
        else:
            analysis["priority"] = Priority.LOW
            analysis["reasoning"].append("Low impact on system functionality")

        # Add specific reasoning based on highest scores
        for dimension, score in sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        ):
            if score >= 0.8:
                analysis["reasoning"].append(f"High {dimension} impact ({score:.2f})")

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(failure, analysis)

        return analysis

    def _calculate_impact_scores(self, failure: TestFailure) -> Dict[str, float]:
        """
        Calculate impact scores for different dimensions.

        Args:
            failure: Test failure

        Returns:
            Dictionary of impact scores
        """
        scores = {}

        # Critical path impact
        scores["critical_path"] = self._score_critical_path(failure)

        # Security impact
        scores["security"] = self._score_security(failure)

        # Data loss impact
        scores["data_loss"] = self._score_data_loss(failure)

        # Frequency impact (how often this might occur)
        scores["frequency"] = self._score_frequency(failure)

        # User experience impact
        scores["ux"] = self._score_ux(failure)

        # Apply configured weights
        for dimension in scores:
            if dimension in self.impact_weights:
                scores[dimension] *= self.impact_weights[dimension]

        return scores

    def _score_critical_path(self, failure: TestFailure) -> float:
        """Score impact on critical functionality."""
        score = 0.0

        # Check if it's a core feature
        core_features = [
            "build",
            "generate",
            "create-tenant",
            "authentication",
            "database",
        ]
        for feature in core_features:
            if feature in failure.feature.lower():
                score += 0.5

        # Check error type
        if failure.error_type in ["crash", "fatal", "timeout"]:
            score += 0.5

        # Check if it blocks other operations
        if (
            "blocked" in failure.error_message.lower()
            or "cannot proceed" in failure.error_message.lower()
        ):
            score += 0.3

        return min(score, 1.0)

    def _score_security(self, failure: TestFailure) -> float:
        """Score security impact."""
        score = 0.0

        security_terms = [
            "security",
            "authentication",
            "authorization",
            "credential",
            "token",
            "password",
            "secret",
            "vulnerability",
            "injection",
            "exposure",
            "privilege",
        ]

        failure_text = (
            f"{failure.feature} {failure.error_message} {failure.error_type}".lower()
        )

        for term in security_terms:
            if term in failure_text:
                score += 0.3

        # Check for specific security patterns
        if "unauthorized" in failure_text or "forbidden" in failure_text:
            score += 0.4

        if "exposed" in failure_text or "leaked" in failure_text:
            score += 0.5

        return min(score, 1.0)

    def _score_data_loss(self, failure: TestFailure) -> float:
        """Score data loss impact."""
        score = 0.0

        data_terms = [
            "data loss",
            "corruption",
            "deleted",
            "missing data",
            "lost",
            "unrecoverable",
            "destroyed",
            "truncated",
        ]

        failure_text = f"{failure.feature} {failure.error_message}".lower()

        for term in data_terms:
            if term in failure_text:
                score += 0.5

        # Check for database-related issues
        if "database" in failure_text or "neo4j" in failure_text:
            if "error" in failure_text or "fail" in failure_text:
                score += 0.3

        return min(score, 1.0)

    def _score_frequency(self, failure: TestFailure) -> float:
        """Score how frequently this issue might occur."""
        score = 0.5  # Default to medium frequency

        # Common operations have higher frequency
        common_operations = ["list", "get", "read", "view", "display"]
        for op in common_operations:
            if op in failure.feature.lower():
                score += 0.2

        # Rare operations have lower frequency
        rare_operations = ["migrate", "upgrade", "reset", "purge"]
        for op in rare_operations:
            if op in failure.feature.lower():
                score -= 0.2

        # Edge cases have lower frequency
        if (
            "edge case" in failure.scenario.lower()
            or "rare" in failure.scenario.lower()
        ):
            score -= 0.3

        return max(0.0, min(score, 1.0))

    def _score_ux(self, failure: TestFailure) -> float:
        """Score user experience impact."""
        score = 0.0

        # UI-related failures have high UX impact
        if "ui" in failure.feature.lower() or "gui" in failure.feature.lower():
            score += 0.4

        # Check for user-facing error messages
        ux_terms = [
            "confusing",
            "unclear",
            "misleading",
            "user",
            "interface",
            "display",
        ]
        failure_text = f"{failure.feature} {failure.error_message}".lower()

        for term in ux_terms:
            if term in failure_text:
                score += 0.2

        # Crashes have high UX impact
        if failure.error_type == "crash":
            score += 0.5

        return min(score, 1.0)

    def _generate_recommendations(
        self, failure: TestFailure, analysis: Dict[str, Any]
    ) -> List[str]:
        """
        Generate recommendations based on failure analysis.

        Args:
            failure: Test failure
            analysis: Analysis results

        Returns:
            List of recommendations
        """
        recommendations = []

        priority = analysis["priority"]
        scores = analysis["impact_scores"]

        # Priority-based recommendations
        if priority == Priority.CRITICAL:
            recommendations.append("Immediate attention required - consider hotfix")
            recommendations.append("Notify team leads and stakeholders")

        elif priority == Priority.HIGH:
            recommendations.append("Schedule for next sprint/release")
            recommendations.append("Consider workaround documentation")

        # Score-based recommendations
        if scores.get("security", 0) > 0.7:
            recommendations.append("Conduct security review")
            recommendations.append("Check for similar vulnerabilities")

        if scores.get("data_loss", 0) > 0.7:
            recommendations.append("Implement data recovery mechanism")
            recommendations.append("Add data integrity checks")

        if scores.get("critical_path", 0) > 0.7:
            recommendations.append("Add regression tests for this scenario")
            recommendations.append("Consider feature flag for rollback")

        if scores.get("ux", 0) > 0.7:
            recommendations.append("Improve error messages and user feedback")
            recommendations.append("Add user documentation")

        # Add general recommendations
        if failure.stack_trace:
            recommendations.append("Review stack trace for root cause")

        if failure.reproduction_steps:
            recommendations.append("Verify reproduction steps are minimal")

        return recommendations

    def prioritize_batch(
        self, failures: List[TestFailure]
    ) -> List[Tuple[TestFailure, Dict[str, Any]]]:
        """
        Prioritize a batch of test failures.

        Args:
            failures: List of test failures

        Returns:
            List of (failure, analysis) tuples sorted by priority
        """
        analyzed = []

        for failure in failures:
            analysis = self.analyze_failure(failure)
            analyzed.append((failure, analysis))

        # Sort by priority (Critical > High > Medium > Low) and total score
        def sort_key(item):
            _, analysis = item
            priority_order = {
                Priority.CRITICAL: 0,
                Priority.HIGH: 1,
                Priority.MEDIUM: 2,
                Priority.LOW: 3,
            }
            priority_rank = priority_order[analysis["priority"]]
            total_score = sum(analysis["impact_scores"].values())
            return (priority_rank, -total_score)  # Negative for descending score

        analyzed.sort(key=sort_key)

        logger.info(f"Prioritized {len(analyzed)} failures")

        return analyzed

    def get_priority_summary(self, failures: List[TestFailure]) -> Dict[str, Any]:
        """
        Get a summary of failure priorities.

        Args:
            failures: List of test failures

        Returns:
            Summary statistics
        """
        prioritized = self.prioritize_batch(failures)

        summary = {
            "total_failures": len(failures),
            "by_priority": {
                Priority.CRITICAL: 0,
                Priority.HIGH: 0,
                Priority.MEDIUM: 0,
                Priority.LOW: 0,
            },
            "top_issues": [],
            "recommendations": set(),
        }

        for failure, analysis in prioritized:
            priority = analysis["priority"]
            summary["by_priority"][priority] += 1

            # Add top issues
            if len(summary["top_issues"]) < 5:
                summary["top_issues"].append(
                    {
                        "feature": failure.feature,
                        "scenario": failure.scenario,
                        "priority": priority.value,
                        "impact_score": sum(analysis["impact_scores"].values()),
                    }
                )

            # Collect unique recommendations
            for rec in analysis["recommendations"][:2]:  # Top 2 recommendations
                summary["recommendations"].add(rec)

        summary["recommendations"] = list(summary["recommendations"])

        return summary
