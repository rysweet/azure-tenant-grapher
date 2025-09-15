#!/usr/bin/env python3
"""
Service Manager Module

Purpose: Start, stop, and manage application services
Contract: Manage service lifecycle with proper error handling
"""

import asyncio
import logging
import os
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
import psutil
import json

logger = logging.getLogger(__name__)


class ServiceProcess:
    """Represents a managed service process."""

    def __init__(self, name: str, command: List[str], cwd: Optional[str] = None, env: Optional[Dict] = None):
        self.name = name
        self.command = command
        self.cwd = cwd
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.start_time: Optional[float] = None
        self.logs: List[str] = []

    def is_running(self) -> bool:
        """Check if service is running."""
        if not self.process:
            return False
        return self.process.poll() is None


class ServiceManager:
    """
    Manages application services and their lifecycle.

    Public Interface:
        - start_service(name, command, cwd): Start a service
        - stop_service(name): Stop a service
        - restart_service(name): Restart a service
        - check_service(name): Check if service is running
        - start_all(): Start all configured services
        - stop_all(): Stop all services
        - get_status(): Get status of all services
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize service manager."""
        self.config = config or {}
        self.services: Dict[str, ServiceProcess] = {}
        self.startup_timeout = self.config.get("startup_timeout", 30)
        self.shutdown_timeout = self.config.get("shutdown_timeout", 10)
        self.health_check_interval = self.config.get("health_check_interval", 1)

    async def start_service(
        self,
        name: str,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict] = None,
        health_check_url: Optional[str] = None,
        startup_timeout: Optional[int] = None
    ) -> bool:
        """
        Start a service process.

        Args:
            name: Service name
            command: Command to execute
            cwd: Working directory
            env: Environment variables
            health_check_url: Optional URL to check for service health
            startup_timeout: Optional timeout override

        Returns:
            True if service started successfully
        """
        if name in self.services and self.services[name].is_running():
            logger.info(f"Service {name} is already running")
            return True

        logger.info(f"Starting service: {name}")
        service = ServiceProcess(name, command, cwd, env)

        try:
            # Prepare environment
            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            # Start process
            service.process = subprocess.Popen(
                command,
                cwd=cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            service.pid = service.process.pid
            service.start_time = time.time()
            self.services[name] = service

            logger.info(f"Service {name} started with PID {service.pid}")

            # Start log collection in background
            asyncio.create_task(self._collect_logs(service))

            # Wait for service to be ready
            timeout = startup_timeout or self.startup_timeout
            if health_check_url:
                ready = await self._wait_for_service(health_check_url, timeout)
                if not ready:
                    logger.error(f"Service {name} failed health check")
                    await self.stop_service(name)
                    return False

            logger.info(f"Service {name} is ready")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to start service {name}: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error starting service {name}: {e}")
            return False

    async def stop_service(self, name: str, force: bool = False) -> bool:
        """
        Stop a service process.

        Args:
            name: Service name
            force: Force kill if graceful shutdown fails

        Returns:
            True if service stopped successfully
        """
        if name not in self.services:
            logger.warning(f"Service {name} not found")
            return False

        service = self.services[name]
        if not service.is_running():
            logger.info(f"Service {name} is not running")
            return True

        logger.info(f"Stopping service: {name}")

        try:
            # Try graceful shutdown
            service.process.terminate()

            # Wait for process to terminate
            try:
                service.process.wait(timeout=self.shutdown_timeout)
                logger.info(f"Service {name} stopped gracefully")
                return True

            except subprocess.TimeoutExpired:
                if force:
                    logger.warning(f"Force killing service {name}")
                    service.process.kill()
                    service.process.wait(timeout=5)
                    logger.info(f"Service {name} force killed")
                    return True
                else:
                    logger.error(f"Service {name} did not stop within timeout")
                    return False

        except Exception as e:
            logger.error(f"Error stopping service {name}: {e}")
            return False

        finally:
            # Clean up
            if name in self.services:
                del self.services[name]

    async def restart_service(self, name: str) -> bool:
        """
        Restart a service.

        Args:
            name: Service name

        Returns:
            True if service restarted successfully
        """
        logger.info(f"Restarting service: {name}")

        if name not in self.services:
            logger.error(f"Service {name} not found")
            return False

        service = self.services[name]

        # Stop the service
        if not await self.stop_service(name):
            return False

        # Wait a moment
        await asyncio.sleep(1)

        # Start the service
        return await self.start_service(
            name,
            service.command,
            service.cwd,
            service.env
        )

    def check_service(self, name: str) -> bool:
        """
        Check if a service is running.

        Args:
            name: Service name

        Returns:
            True if service is running
        """
        if name not in self.services:
            return False

        return self.services[name].is_running()

    async def start_all(self, service_configs: List[Dict[str, Any]]) -> bool:
        """
        Start all configured services.

        Args:
            service_configs: List of service configurations

        Returns:
            True if all services started successfully
        """
        success = True

        for config in service_configs:
            name = config.get("name")
            command = config.get("command", [])
            cwd = config.get("cwd")
            env = config.get("env", {})
            health_check = config.get("health_check")

            if not name or not command:
                logger.error(f"Invalid service configuration: {config}")
                success = False
                continue

            if not await self.start_service(name, command, cwd, env, health_check):
                success = False
                if config.get("required", True):
                    logger.error(f"Required service {name} failed to start, aborting")
                    break

        return success

    async def stop_all(self) -> None:
        """Stop all running services."""
        logger.info("Stopping all services")

        # Stop in reverse order
        service_names = list(self.services.keys())
        for name in reversed(service_names):
            await self.stop_service(name, force=True)

    async def _wait_for_service(self, health_check_url: str, timeout: int) -> bool:
        """
        Wait for service to become healthy.

        Args:
            health_check_url: URL to check
            timeout: Maximum time to wait

        Returns:
            True if service became healthy
        """
        import aiohttp

        start_time = time.time()
        last_error = None

        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_check_url, timeout=5) as response:
                        if response.status < 500:
                            return True

            except Exception as e:
                last_error = e

            await asyncio.sleep(self.health_check_interval)

        if last_error:
            logger.error(f"Health check failed: {last_error}")

        return False

    async def _collect_logs(self, service: ServiceProcess) -> None:
        """Collect logs from service process."""
        if not service.process:
            return

        try:
            # Read stdout
            for line in iter(service.process.stdout.readline, ''):
                if line:
                    service.logs.append(f"[STDOUT] {line.strip()}")
                    logger.debug(f"{service.name}: {line.strip()}")

        except Exception as e:
            logger.error(f"Error collecting logs for {service.name}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all services.

        Returns:
            Dictionary with service status information
        """
        status = {
            "total": len(self.services),
            "running": 0,
            "stopped": 0,
            "services": {}
        }

        for name, service in self.services.items():
            is_running = service.is_running()
            if is_running:
                status["running"] += 1
            else:
                status["stopped"] += 1

            status["services"][name] = {
                "running": is_running,
                "pid": service.pid,
                "uptime": time.time() - service.start_time if service.start_time else 0,
                "command": " ".join(service.command),
                "log_count": len(service.logs)
            }

        return status

    def get_service_logs(self, name: str, limit: int = 100) -> List[str]:
        """
        Get logs for a specific service.

        Args:
            name: Service name
            limit: Maximum number of log lines to return

        Returns:
            List of log lines
        """
        if name not in self.services:
            return []

        service = self.services[name]
        return service.logs[-limit:] if limit else service.logs

    def export_logs(self, output_dir: str = "logs") -> Dict[str, str]:
        """
        Export all service logs to files.

        Args:
            output_dir: Directory to save logs

        Returns:
            Dictionary mapping service names to log file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        log_files = {}

        for name, service in self.services.items():
            if service.logs:
                log_file = output_path / f"{name}_{int(time.time())}.log"
                with open(log_file, 'w') as f:
                    f.write("\n".join(service.logs))
                log_files[name] = str(log_file)
                logger.info(f"Exported logs for {name} to {log_file}")

        return log_files

    def cleanup(self) -> None:
        """Clean up all resources."""
        asyncio.create_task(self.stop_all())
