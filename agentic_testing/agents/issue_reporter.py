"""Issue reporter agent for creating GitHub issues from test failures."""

import asyncio
import json
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import GitHubConfig
from ..models import TestFailure
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IssueReporter:
    """Agent responsible for reporting issues to GitHub."""

    def __init__(self, config: GitHubConfig):
        """
        Initialize issue reporter.

        Args:
            config: GitHub configuration
        """
        self.config = config
        self.repository = config.repository
        self.create_issues = config.create_issues
        self.issue_labels = config.issue_labels
        self.assign_to = config.assign_to
        self.use_gh_cli = config.use_gh_cli

        # Cache for recent issues to avoid duplicates
        self._issue_cache = {}
        self._cache_ttl = timedelta(hours=24)

    async def report_failure(self, failure: TestFailure) -> Optional[str]:
        """
        Report a test failure as a GitHub issue.

        Args:
            failure: Test failure to report

        Returns:
            Issue number if created, None otherwise
        """
        if not self.create_issues:
            logger.info("Issue creation disabled, skipping report")
            return None

        # Check for duplicate
        if await self._is_duplicate(failure):
            logger.info(f"Duplicate issue detected for {failure.scenario}, skipping")
            return None

        # Create issue
        issue_data = failure.to_github_issue()

        if self.use_gh_cli:
            issue_number = await self._create_issue_with_gh_cli(issue_data)
        else:
            issue_number = await self._create_issue_with_api(issue_data)

        if issue_number:
            # Cache the issue
            fingerprint = failure.generate_fingerprint()
            self._issue_cache[fingerprint] = {
                "issue_number": issue_number,
                "created_at": datetime.now(),
            }

            logger.info(f"Created issue #{issue_number} for {failure.scenario}")

        return issue_number

    async def _create_issue_with_gh_cli(
        self, issue_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Create issue using GitHub CLI.

        Args:
            issue_data: Issue data dictionary

        Returns:
            Issue number if created
        """
        try:
            # Build gh command
            cmd = [
                "gh",
                "issue",
                "create",
                "--repo",
                self.repository,
                "--title",
                issue_data["title"],
                "--body",
                issue_data["body"],
            ]

            # Add labels
            for label in issue_data.get("labels", []) + self.issue_labels:
                cmd.extend(["--label", label])

            # Add assignee
            if self.assign_to:
                cmd.extend(["--assignee", self.assign_to])

            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Extract issue number from output
                output = stdout.decode().strip()
                if "/issues/" in output:
                    issue_number = output.split("/issues/")[-1]
                    return issue_number
                return output
            else:
                logger.error(f"Failed to create issue: {stderr.decode()}")
                return None

        except Exception as e:
            logger.error(f"Error creating issue with gh CLI: {e}")
            return None

    async def _create_issue_with_api(self, issue_data: Dict[str, Any]) -> Optional[str]:
        """
        Create issue using GitHub API.

        Args:
            issue_data: Issue data dictionary

        Returns:
            Issue number if created
        """
        try:
            import os

            from github import Github

            # Get token from environment or gh auth
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                # Try to get token from gh CLI
                result = subprocess.run(
                    ["gh", "auth", "token"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    token = result.stdout.strip()

            if not token:
                logger.error("No GitHub token available")
                return None

            # Create GitHub client
            g = Github(token)
            repo = g.get_repo(self.repository)

            # Create issue
            issue = repo.create_issue(
                title=issue_data["title"],
                body=issue_data["body"],
                labels=issue_data.get("labels", []) + self.issue_labels,
                assignee=self.assign_to,
            )

            return str(issue.number)

        except Exception as e:
            logger.error(f"Error creating issue with API: {e}")
            return None

    async def _is_duplicate(self, failure: TestFailure) -> bool:
        """
        Check if this failure is a duplicate of an existing issue.

        Args:
            failure: Test failure to check

        Returns:
            True if duplicate exists
        """
        fingerprint = failure.generate_fingerprint()

        # Check cache first
        if fingerprint in self._issue_cache:
            cache_entry = self._issue_cache[fingerprint]
            if datetime.now() - cache_entry["created_at"] < self._cache_ttl:
                return True

        # Search for existing issues
        if self.use_gh_cli:
            return await self._search_duplicate_with_gh_cli(failure)
        else:
            return await self._search_duplicate_with_api(failure)

    async def _search_duplicate_with_gh_cli(self, failure: TestFailure) -> bool:
        """
        Search for duplicate issues using gh CLI.

        Args:
            failure: Test failure to search for

        Returns:
            True if duplicate found
        """
        try:
            # Search for similar issues
            search_query = f"{failure.feature} {failure.error_type}"

            cmd = [
                "gh",
                "issue",
                "list",
                "--repo",
                self.repository,
                "--search",
                search_query,
                "--state",
                "open",
                "--json",
                "number,title,body",
                "--limit",
                "10",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                issues = json.loads(stdout.decode())

                # Check for similar issues
                for issue in issues:
                    if self._is_similar_issue(failure, issue):
                        logger.info(f"Found similar issue #{issue['number']}")
                        return True

            return False

        except Exception as e:
            logger.error(f"Error searching for duplicates: {e}")
            return False

    async def _search_duplicate_with_api(self, failure: TestFailure) -> bool:
        """
        Search for duplicate issues using GitHub API.

        Args:
            failure: Test failure to search for

        Returns:
            True if duplicate found
        """
        # Implementation would use PyGithub similar to create
        # For now, return False to allow issue creation
        return False

    def _is_similar_issue(self, failure: TestFailure, issue: Dict[str, Any]) -> bool:
        """
        Check if an issue is similar to the failure.

        Args:
            failure: Test failure
            issue: GitHub issue data

        Returns:
            True if issues are similar
        """
        # Check title similarity
        if failure.feature in issue.get(
            "title", ""
        ) and failure.error_type in issue.get("title", ""):
            return True

        # Check body for scenario ID
        if failure.scenario_id in issue.get("body", ""):
            return True

        # Could add more sophisticated similarity checks here
        return False

    async def batch_report(self, failures: List[TestFailure]) -> List[str]:
        """
        Report multiple failures, avoiding duplicates.

        Args:
            failures: List of test failures

        Returns:
            List of created issue numbers
        """
        issue_numbers = []

        for failure in failures:
            issue_number = await self.report_failure(failure)
            if issue_number:
                issue_numbers.append(issue_number)

            # Add small delay to avoid rate limiting
            await asyncio.sleep(2)

        return issue_numbers

    async def update_issue_with_screenshot(
        self, issue_number: str, screenshot_path: str
    ) -> bool:
        """
        Update an issue with a screenshot.

        Args:
            issue_number: GitHub issue number
            screenshot_path: Path to screenshot file

        Returns:
            True if successful
        """
        if not self.use_gh_cli:
            logger.warning("Screenshot upload only supported with gh CLI")
            return False

        try:
            # Upload image and get URL
            # Note: This is a simplified version - actual implementation would need
            # to upload to a service and get a public URL

            comment = f"![Screenshot]({screenshot_path})\n\n_Screenshot captured during test execution_"

            cmd = [
                "gh",
                "issue",
                "comment",
                issue_number,
                "--repo",
                self.repository,
                "--body",
                comment,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return process.returncode == 0

        except Exception as e:
            logger.error(f"Error updating issue with screenshot: {e}")
            return False
