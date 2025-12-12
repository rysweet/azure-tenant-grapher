"""
Remote Client - HTTP + WebSocket client for ATG remote service.

Philosophy:
- Simple async HTTP client with long timeouts (30-60 min)
- WebSocket for progress updates
- Zero-BS implementation - everything works

Public API:
    RemoteClient: HTTP + WebSocket client
"""

import asyncio
import json
from typing import Any, AsyncIterator, Callable, Dict, Optional

import httpx
from websockets import connect


class RemoteClient:
    """
    HTTP + WebSocket client for ATG remote service.

    Handles authentication, long-running requests, and progress streaming.

    Philosophy:
    - Simple async HTTP with httpx
    - WebSocket for progress updates
    - Long HTTP timeout (30-60 min, no queue needed)
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 3600):
        """
        Initialize remote client.

        Args:
            base_url: Base URL of ATG service (e.g., https://atg.example.com)
            api_key: Authentication API key
            timeout: Request timeout in seconds (default: 3600 = 60 min)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Create HTTP client with authentication and long timeout
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "ATG-CLI/1.0"},
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit - cleanup HTTP client."""
        await self._http_client.aclose()

    async def scan(
        self,
        tenant_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute scan operation on remote service.

        Args:
            tenant_id: Azure tenant ID to scan
            progress_callback: Optional callback for progress updates (progress, message)
            **kwargs: Additional scan parameters (resource_limit, max_llm_threads, etc.)

        Returns:
            Dictionary with scan results

        Raises:
            RemoteExecutionError: If scan fails
            ConnectionError: If cannot connect to service
        """
        # Submit scan job
        payload = {"tenant_id": tenant_id, **kwargs}

        response = await self._http_client.post("/api/v1/scan", json=payload)
        response.raise_for_status()

        result = response.json()
        job_id = result.get("job_id")

        # Stream progress via WebSocket if callback provided
        if progress_callback and job_id:
            async for event in self._stream_progress(job_id):
                if event.get("type") == "progress":
                    progress_callback(
                        event.get("progress", 0.0), event.get("message", "")
                    )
                elif event.get("type") == "complete":
                    break
                elif event.get("type") == "error":
                    raise Exception(event.get("message", "Scan failed"))

        return result

    async def _stream_progress(self, job_id: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream progress updates via WebSocket.

        Args:
            job_id: Job identifier

        Yields:
            Progress event dictionaries
        """
        # Convert http:// to ws:// and https:// to wss://
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/progress/{job_id}"

        try:
            async with connect(
                ws_url, extra_headers={"Authorization": f"Bearer {self.api_key}"}
            ) as websocket:
                while True:
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(), timeout=self.timeout
                        )
                        event = json.loads(message)
                        yield event

                        # Break on complete or error
                        if event.get("type") in ("complete", "error"):
                            break
                    except asyncio.TimeoutError:
                        # Timeout waiting for message
                        yield {"type": "error", "message": "Progress stream timed out"}
                        break
        except Exception as e:
            # Connection failed
            yield {"type": "error", "message": f"WebSocket connection failed: {e}"}

    async def generate_iac(
        self,
        tenant_id: str,
        output_format: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate IaC via remote service.

        Args:
            tenant_id: Azure tenant ID
            output_format: terraform, bicep, or arm
            progress_callback: Optional callback for progress updates
            **kwargs: Additional generation parameters

        Returns:
            Dictionary with generation results and artifact URLs

        Raises:
            RemoteExecutionError: If generation fails
        """
        payload = {"tenant_id": tenant_id, "output_format": output_format, **kwargs}

        response = await self._http_client.post("/api/v1/generate-iac", json=payload)
        response.raise_for_status()

        result = response.json()
        job_id = result.get("job_id")

        # Stream progress if callback provided
        if progress_callback and job_id:
            async for event in self._stream_progress(job_id):
                if event.get("type") == "progress":
                    progress_callback(
                        event.get("progress", 0.0), event.get("message", "")
                    )
                elif event.get("type") == "complete":
                    break
                elif event.get("type") == "error":
                    raise Exception(event.get("message", "IaC generation failed"))

        return result

    async def health_check(self) -> bool:
        """
        Check if service is healthy and reachable.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self._http_client.get("/health")
            return response.status_code == 200
        except Exception:
            return False


__all__ = ["RemoteClient"]
