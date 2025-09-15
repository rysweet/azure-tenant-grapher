#!/usr/bin/env python3
"""
Health Checker Module

Purpose: Verify service availability and dependencies before running demos
Contract: Check services, dependencies, and provide health status
"""

import asyncio
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp
import sys

logger = logging.getLogger(__name__)


class HealthCheck:
    """Represents a single health check result."""

    def __init__(self, name: str, healthy: bool, message: str, details: Optional[Dict] = None):
        self.name = name
        self.healthy = healthy
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "details": self.details
        }


class HealthChecker:
    """
    Performs health checks on services and dependencies.

    Public Interface:
        - check_all(): Run all health checks
        - check_service(url): Check if service is accessible
        - check_dependencies(): Verify required dependencies
        - check_azure_auth(): Verify Azure authentication
        - get_summary(): Get health check summary
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize health checker."""
        self.config = config or {}
        self.checks: List[HealthCheck] = []
        self.timeout = self.config.get("timeout", 5)

    async def check_all(self) -> bool:
        """
        Run all health checks.

        Returns:
            True if all checks pass, False otherwise
        """
        self.checks = []

        # Check Python version
        self._check_python_version()

        # Check required dependencies
        await self._check_dependencies()

        # Check application service
        app_url = self.config.get("app", {}).get("url", "http://localhost:3000")
        await self.check_service(app_url)

        # Check Azure authentication if configured
        auth_method = self.config.get("authentication", {}).get("method", "azure_cli")
        if auth_method == "azure_cli":
            await self.check_azure_auth()

        # Check browser dependencies
        await self._check_playwright()

        # Check disk space
        self._check_disk_space()

        # Return overall health
        return all(check.healthy for check in self.checks)

    def _check_python_version(self) -> None:
        """Check Python version compatibility."""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            self.checks.append(HealthCheck(
                "Python Version",
                True,
                f"Python {version.major}.{version.minor}.{version.micro}"
            ))
        else:
            self.checks.append(HealthCheck(
                "Python Version",
                False,
                f"Python {version.major}.{version.minor} detected, requires 3.8+",
                {"current": f"{version.major}.{version.minor}", "required": "3.8+"}
            ))

    async def check_service(self, url: str, name: Optional[str] = None) -> bool:
        """
        Check if a service is accessible.

        Args:
            url: Service URL to check
            name: Optional name for the service

        Returns:
            True if service is healthy
        """
        service_name = name or f"Service at {url}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status < 500:
                        self.checks.append(HealthCheck(
                            service_name,
                            True,
                            f"Service responding (status: {response.status})",
                            {"url": url, "status": response.status}
                        ))
                        return True
                    else:
                        self.checks.append(HealthCheck(
                            service_name,
                            False,
                            f"Service error (status: {response.status})",
                            {"url": url, "status": response.status}
                        ))
                        return False

        except asyncio.TimeoutError:
            self.checks.append(HealthCheck(
                service_name,
                False,
                f"Service timeout after {self.timeout}s",
                {"url": url, "timeout": self.timeout}
            ))
            return False

        except aiohttp.ClientError as e:
            self.checks.append(HealthCheck(
                service_name,
                False,
                f"Cannot connect to service: {str(e)}",
                {"url": url, "error": str(e)}
            ))
            return False

        except Exception as e:
            self.checks.append(HealthCheck(
                service_name,
                False,
                f"Unexpected error: {str(e)}",
                {"url": url, "error": str(e)}
            ))
            return False

    async def _check_dependencies(self) -> None:
        """Check required Python dependencies."""
        required_packages = [
            "playwright",
            "pyyaml",
            "aiohttp",
            "pillow"
        ]

        try:
            import importlib.metadata

            missing = []
            for package in required_packages:
                try:
                    importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    # Try alternative package names
                    if package == "pyyaml":
                        try:
                            importlib.metadata.version("PyYAML")
                        except:
                            missing.append(package)
                    elif package == "pillow":
                        try:
                            importlib.metadata.version("Pillow")
                        except:
                            missing.append(package)
                    else:
                        missing.append(package)

            if missing:
                self.checks.append(HealthCheck(
                    "Python Dependencies",
                    False,
                    f"Missing packages: {', '.join(missing)}",
                    {"missing": missing}
                ))
            else:
                self.checks.append(HealthCheck(
                    "Python Dependencies",
                    True,
                    "All required packages installed"
                ))

        except Exception as e:
            self.checks.append(HealthCheck(
                "Python Dependencies",
                False,
                f"Cannot check dependencies: {str(e)}"
            ))

    async def check_azure_auth(self) -> bool:
        """
        Check Azure CLI authentication status.

        Returns:
            True if authenticated
        """
        try:
            result = subprocess.run(
                ["az", "account", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import json
                account = json.loads(result.stdout)
                self.checks.append(HealthCheck(
                    "Azure Authentication",
                    True,
                    f"Authenticated to {account.get('name', 'Unknown')}",
                    {"tenant": account.get('tenantId'), "subscription": account.get('id')}
                ))
                return True
            else:
                self.checks.append(HealthCheck(
                    "Azure Authentication",
                    False,
                    "Not authenticated - run 'az login'",
                    {"error": result.stderr}
                ))
                return False

        except subprocess.TimeoutExpired:
            self.checks.append(HealthCheck(
                "Azure Authentication",
                False,
                "Azure CLI check timed out"
            ))
            return False

        except FileNotFoundError:
            self.checks.append(HealthCheck(
                "Azure Authentication",
                False,
                "Azure CLI not installed",
                {"suggestion": "Install Azure CLI: https://aka.ms/azure-cli"}
            ))
            return False

        except Exception as e:
            self.checks.append(HealthCheck(
                "Azure Authentication",
                False,
                f"Cannot check authentication: {str(e)}"
            ))
            return False

    async def _check_playwright(self) -> None:
        """Check Playwright browser installation."""
        browsers = ["chromium", "firefox", "webkit"]
        browser = self.config.get("test", {}).get("browser", "chromium")

        try:
            from playwright.async_api import async_playwright

            # Check if specific browser is installed
            playwright_path = shutil.which("playwright")
            if playwright_path:
                result = subprocess.run(
                    ["playwright", "install", "--dry-run"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if browser in result.stdout.lower() and "missing" not in result.stdout.lower():
                    self.checks.append(HealthCheck(
                        f"Playwright {browser.title()}",
                        True,
                        f"{browser.title()} browser installed"
                    ))
                else:
                    self.checks.append(HealthCheck(
                        f"Playwright {browser.title()}",
                        False,
                        f"{browser.title()} not installed - run 'playwright install {browser}'",
                        {"browser": browser}
                    ))
            else:
                self.checks.append(HealthCheck(
                    "Playwright",
                    False,
                    "Playwright CLI not found",
                    {"suggestion": "Run: pip install playwright && playwright install"}
                ))

        except ImportError:
            self.checks.append(HealthCheck(
                "Playwright",
                False,
                "Playwright not installed",
                {"suggestion": "Run: pip install playwright"}
            ))

        except Exception as e:
            self.checks.append(HealthCheck(
                "Playwright",
                False,
                f"Cannot check Playwright: {str(e)}"
            ))

    def _check_disk_space(self) -> None:
        """Check available disk space."""
        try:
            import shutil
            path = Path.cwd()
            stat = shutil.disk_usage(path)

            # Convert to GB
            free_gb = stat.free / (1024 ** 3)
            total_gb = stat.total / (1024 ** 3)
            used_percent = (stat.used / stat.total) * 100

            if free_gb < 1:
                self.checks.append(HealthCheck(
                    "Disk Space",
                    False,
                    f"Low disk space: {free_gb:.1f}GB free",
                    {"free_gb": free_gb, "total_gb": total_gb, "used_percent": used_percent}
                ))
            else:
                self.checks.append(HealthCheck(
                    "Disk Space",
                    True,
                    f"{free_gb:.1f}GB free ({used_percent:.1f}% used)",
                    {"free_gb": free_gb, "total_gb": total_gb, "used_percent": used_percent}
                ))

        except Exception as e:
            logger.warning(f"Cannot check disk space: {e}")

    def get_summary(self) -> str:
        """
        Get health check summary.

        Returns:
            Formatted summary string
        """
        if not self.checks:
            return "No health checks performed"

        healthy = sum(1 for c in self.checks if c.healthy)
        total = len(self.checks)

        lines = [
            "\n" + "=" * 60,
            "🏥 HEALTH CHECK SUMMARY",
            "=" * 60,
            f"Status: {'✅ HEALTHY' if healthy == total else '⚠️ ISSUES DETECTED'}",
            f"Checks Passed: {healthy}/{total}",
            ""
        ]

        for check in self.checks:
            icon = "✅" if check.healthy else "❌"
            lines.append(f"{icon} {check.name}: {check.message}")

        lines.append("=" * 60 + "\n")
        return "\n".join(lines)

    def get_failed_checks(self) -> List[HealthCheck]:
        """Get list of failed health checks."""
        return [c for c in self.checks if not c.healthy]

    def is_healthy(self) -> bool:
        """Check if all health checks passed."""
        return all(c.healthy for c in self.checks) if self.checks else False
