"""
Unit tests for RemoteClient - HTTP + WebSocket client.

Tests cover:
- Client initialization
- HTTP request methods
- WebSocket progress streaming
- Error handling
- Timeout handling
- Context manager usage
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.remote.client.remote_client import RemoteClient


@pytest.fixture
def base_url():
    """Standard base URL for testing."""
    return "https://atg.example.com"


@pytest.fixture
def api_key():
    """Valid test API key."""
    return "atg_dev_" + "0" * 64


@pytest.fixture
def remote_client(base_url, api_key):
    """Create RemoteClient instance for testing."""
    return RemoteClient(base_url=base_url, api_key=api_key, timeout=30)


# Initialization Tests


def test_client_initializes_with_valid_params(base_url, api_key):
    """Test that RemoteClient initializes correctly with valid parameters."""
    client = RemoteClient(base_url=base_url, api_key=api_key, timeout=60)

    assert client.base_url == base_url
    assert client.api_key == api_key
    assert client.timeout == 60
    assert client._http_client is not None


def test_client_strips_trailing_slash_from_base_url(api_key):
    """Test that trailing slash is removed from base URL."""
    client = RemoteClient(base_url="https://atg.example.com/", api_key=api_key)

    assert client.base_url == "https://atg.example.com"


def test_client_uses_default_timeout(base_url, api_key):
    """Test that client uses default timeout of 3600 seconds."""
    client = RemoteClient(base_url=base_url, api_key=api_key)

    assert client.timeout == 3600


def test_client_creates_http_client_with_auth_header(base_url, api_key):
    """Test that HTTP client has authorization header configured."""
    client = RemoteClient(base_url=base_url, api_key=api_key)

    headers = client._http_client.headers
    assert "Authorization" in headers
    assert headers["Authorization"] == f"Bearer {api_key}"
    assert headers["User-Agent"] == "ATG-CLI/1.0"


# Context Manager Tests


@pytest.mark.asyncio
async def test_client_context_manager_entry(remote_client):
    """Test that client works as async context manager."""
    async with remote_client as client:
        assert client == remote_client


@pytest.mark.asyncio
async def test_client_context_manager_exit_closes_http_client(remote_client):
    """Test that context manager exit closes HTTP client."""
    mock_http_client = AsyncMock()
    remote_client._http_client = mock_http_client

    async with remote_client:
        pass

    mock_http_client.aclose.assert_called_once()


# Health Check Tests


@pytest.mark.asyncio
async def test_health_check_returns_true_when_service_healthy(remote_client):
    """Test that health_check returns True when service is healthy."""
    mock_response = Mock()
    mock_response.status_code = 200

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "get",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await remote_client.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_returns_false_when_service_unhealthy(remote_client):
    """Test that health_check returns False when service returns non-200."""
    mock_response = Mock()
    mock_response.status_code = 503

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "get",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await remote_client.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_health_check_returns_false_on_connection_error(remote_client):
    """Test that health_check returns False when connection fails."""
    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "get",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        result = await remote_client.health_check()

    assert result is False


# Scan Operation Tests


@pytest.mark.asyncio
async def test_scan_submits_job_with_tenant_id(remote_client):
    """Test that scan operation submits job with correct tenant ID."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-123", "status": "submitted"}

    mock_post = AsyncMock(return_value=mock_response)
    with patch.object(remote_client._http_client, "post", mock_post):  # type: ignore[attr-defined]  # patch() returns regular context manager
        result = await remote_client.scan(tenant_id=tenant_id)

    assert result["job_id"] == "job-123"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "/api/v1/scan"
    assert call_args[1]["json"]["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_scan_passes_additional_kwargs(remote_client):
    """Test that scan passes additional parameters to API."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-123"}

    mock_post = AsyncMock(return_value=mock_response)
    with patch.object(remote_client._http_client, "post", mock_post):  # type: ignore[attr-defined]  # patch() returns regular context manager
        await remote_client.scan(
            tenant_id=tenant_id, resource_limit=100, max_llm_threads=10
        )

    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["resource_limit"] == 100
    assert payload["max_llm_threads"] == 10


@pytest.mark.asyncio
async def test_scan_raises_for_http_error(remote_client):
    """Test that scan raises exception on HTTP error."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad request", request=Mock(), response=Mock()
    )

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await remote_client.scan(tenant_id="invalid")


@pytest.mark.asyncio
async def test_scan_streams_progress_when_callback_provided(remote_client):
    """Test that scan streams progress updates via WebSocket when callback provided."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-123"}

    progress_updates = []

    def progress_callback(progress: float, message: str):
        progress_updates.append({"progress": progress, "message": message})

    # Mock _stream_progress to yield events
    async def mock_stream_progress(job_id):
        yield {"type": "progress", "progress": 50.0, "message": "Scanning resources"}
        yield {"type": "complete", "progress": 100.0, "message": "Scan complete"}

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress", new=mock_stream_progress):  # type: ignore[attr-defined]  # patch() returns regular context manager
            await remote_client.scan(
                tenant_id=tenant_id, progress_callback=progress_callback
            )

    assert len(progress_updates) == 1
    assert progress_updates[0]["progress"] == 50.0
    assert progress_updates[0]["message"] == "Scanning resources"


@pytest.mark.asyncio
async def test_scan_handles_error_events_from_websocket(remote_client):
    """Test that scan raises exception when WebSocket sends error event."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-123"}

    async def mock_stream_progress(job_id):
        yield {"type": "error", "message": "Scan failed"}

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress", new=mock_stream_progress):  # type: ignore[attr-defined]  # patch() returns regular context manager
            with pytest.raises(Exception, match="Scan failed"):
                await remote_client.scan(
                    tenant_id=tenant_id, progress_callback=lambda p, m: None
                )


@pytest.mark.asyncio
async def test_scan_skips_progress_streaming_when_no_callback(remote_client):
    """Test that scan skips WebSocket streaming when no callback provided."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-123"}

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress") as mock_stream:  # type: ignore[attr-defined]  # patch() returns regular context manager
            result = await remote_client.scan(tenant_id=tenant_id)

    # _stream_progress should not be called
    mock_stream.assert_not_called()
    assert result["job_id"] == "job-123"


# Generate IaC Tests


@pytest.mark.asyncio
async def test_generate_iac_submits_job_with_format(remote_client):
    """Test that generate_iac submits job with tenant ID and format."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-456", "status": "submitted"}

    mock_post = AsyncMock(return_value=mock_response)
    with patch.object(remote_client._http_client, "post", mock_post):  # type: ignore[attr-defined]  # patch() returns regular context manager
        result = await remote_client.generate_iac(
            tenant_id=tenant_id, output_format="terraform"
        )

    assert result["job_id"] == "job-456"
    call_args = mock_post.call_args
    assert call_args[0][0] == "/api/v1/generate-iac"
    payload = call_args[1]["json"]
    assert payload["tenant_id"] == tenant_id
    assert payload["output_format"] == "terraform"


@pytest.mark.asyncio
async def test_generate_iac_passes_additional_kwargs(remote_client):
    """Test that generate_iac passes additional parameters."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-456"}

    mock_post = AsyncMock(return_value=mock_response)
    with patch.object(remote_client._http_client, "post", mock_post):  # type: ignore[attr-defined]  # patch() returns regular context manager
        await remote_client.generate_iac(
            tenant_id=tenant_id, output_format="bicep", cross_tenant=True
        )

    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["cross_tenant"] is True


@pytest.mark.asyncio
async def test_generate_iac_streams_progress_when_callback_provided(remote_client):
    """Test that generate_iac streams progress updates when callback provided."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-456"}

    progress_updates = []

    def progress_callback(progress: float, message: str):
        progress_updates.append({"progress": progress, "message": message})

    async def mock_stream_progress(job_id):
        yield {"type": "progress", "progress": 75.0, "message": "Generating IaC"}
        yield {"type": "complete", "progress": 100.0}

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress", new=mock_stream_progress):  # type: ignore[attr-defined]  # patch() returns regular context manager
            await remote_client.generate_iac(
                tenant_id=tenant_id,
                output_format="terraform",
                progress_callback=progress_callback,
            )

    assert len(progress_updates) == 1
    assert progress_updates[0]["progress"] == 75.0


@pytest.mark.asyncio
async def test_generate_iac_raises_on_error_event(remote_client):
    """Test that generate_iac raises exception on error event."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job-456"}

    async def mock_stream_progress(job_id):
        yield {"type": "error", "message": "IaC generation failed"}

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress", new=mock_stream_progress):  # type: ignore[attr-defined]  # patch() returns regular context manager
            with pytest.raises(Exception, match="IaC generation failed"):
                await remote_client.generate_iac(
                    tenant_id=tenant_id,
                    output_format="terraform",
                    progress_callback=lambda p, m: None,
                )


# WebSocket Progress Streaming Tests


@pytest.mark.asyncio
async def test_stream_progress_converts_http_to_ws_url(remote_client):
    """Test that _stream_progress constructs correct WebSocket URL."""
    job_id = "job-123"

    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)
    mock_ws.recv = AsyncMock(side_effect=[json.dumps({"type": "complete"})])

    with patch("src.remote.client.remote_client.connect", return_value=mock_ws) as mock_connect:  # type: ignore[attr-defined]  # patch() returns regular context manager
        async for _ in remote_client._stream_progress(job_id):
            pass

        # Verify connect was called with correct WebSocket URL
        called_url = mock_connect.call_args[0][0]
        assert called_url == f"wss://atg.example.com/ws/progress/{job_id}"


@pytest.mark.asyncio
async def test_stream_progress_yields_parsed_json_events(remote_client):
    """Test that _stream_progress yields parsed JSON events."""
    mock_websocket = AsyncMock()
    mock_websocket.recv = AsyncMock(
        side_effect=[
            json.dumps({"type": "progress", "progress": 10.0}),
            json.dumps({"type": "complete"}),
        ]
    )
    mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
    mock_websocket.__aexit__ = AsyncMock(return_value=None)

    events = []
    with patch("src.remote.client.remote_client.connect", return_value=mock_websocket):  # type: ignore[attr-defined]  # patch() returns regular context manager
        async for event in remote_client._stream_progress("job-123"):
            events.append(event)

    assert len(events) == 2
    assert events[0]["type"] == "progress"
    assert events[0]["progress"] == 10.0
    assert events[1]["type"] == "complete"


@pytest.mark.asyncio
async def test_stream_progress_stops_on_complete_event(remote_client):
    """Test that _stream_progress stops yielding after complete event."""
    mock_websocket = AsyncMock()
    mock_websocket.recv = AsyncMock(
        side_effect=[
            json.dumps({"type": "progress", "progress": 50.0}),
            json.dumps({"type": "complete"}),
            json.dumps(
                {"type": "progress", "progress": 100.0}
            ),  # Should not be yielded
        ]
    )
    mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
    mock_websocket.__aexit__ = AsyncMock(return_value=None)

    events = []
    with patch("src.remote.client.remote_client.connect", return_value=mock_websocket):  # type: ignore[attr-defined]  # patch() returns regular context manager
        async for event in remote_client._stream_progress("job-123"):
            events.append(event)

    assert len(events) == 2
    assert events[1]["type"] == "complete"


@pytest.mark.asyncio
async def test_stream_progress_stops_on_error_event(remote_client):
    """Test that _stream_progress stops yielding after error event."""
    mock_websocket = AsyncMock()
    mock_websocket.recv = AsyncMock(
        side_effect=[
            json.dumps({"type": "progress", "progress": 25.0}),
            json.dumps({"type": "error", "message": "Failed"}),
        ]
    )
    mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
    mock_websocket.__aexit__ = AsyncMock(return_value=None)

    events = []
    with patch("src.remote.client.remote_client.connect", return_value=mock_websocket):  # type: ignore[attr-defined]  # patch() returns regular context manager
        async for event in remote_client._stream_progress("job-123"):
            events.append(event)

    assert len(events) == 2
    assert events[1]["type"] == "error"


@pytest.mark.asyncio
async def test_stream_progress_yields_error_on_timeout(remote_client):
    """Test that _stream_progress yields error event on timeout."""
    mock_websocket = AsyncMock()
    mock_websocket.recv = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
    mock_websocket.__aexit__ = AsyncMock(return_value=None)

    events = []
    with patch("src.remote.client.remote_client.connect", return_value=mock_websocket):  # type: ignore[attr-defined]  # patch() returns regular context manager
        async for event in remote_client._stream_progress("job-123"):
            events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "timed out" in events[0]["message"].lower()


@pytest.mark.asyncio
async def test_stream_progress_yields_error_on_connection_failure(remote_client):
    """Test that _stream_progress yields error event on WebSocket connection failure."""
    events = []

    with patch(  # type: ignore[attr-defined]  # patch() returns regular context manager
        "src.remote.client.remote_client.connect",
        side_effect=Exception("Connection refused"),
    ):
        async for event in remote_client._stream_progress("job-123"):
            events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "connection failed" in events[0]["message"].lower()


# Edge Cases and Error Handling


@pytest.mark.asyncio
async def test_scan_with_no_job_id_skips_progress_streaming(remote_client):
    """Test that scan skips progress streaming if response has no job_id."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"status": "completed"}  # No job_id

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress") as mock_stream:  # type: ignore[attr-defined]  # patch() returns regular context manager
            result = await remote_client.scan(
                tenant_id=tenant_id, progress_callback=lambda p, m: None
            )

    # Should not call _stream_progress even with callback
    mock_stream.assert_not_called()
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_iac_with_no_job_id_skips_progress_streaming(remote_client):
    """Test that generate_iac skips progress streaming if response has no job_id."""
    tenant_id = "12345678-1234-1234-1234-123456789012"
    mock_response = Mock()
    mock_response.json.return_value = {"status": "completed"}  # No job_id

    with patch.object(  # type: ignore[attr-defined]  # patch() returns regular context manager
        remote_client._http_client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch.object(remote_client, "_stream_progress") as mock_stream:  # type: ignore[attr-defined]  # patch() returns regular context manager
            result = await remote_client.generate_iac(
                tenant_id=tenant_id,
                output_format="terraform",
                progress_callback=lambda p, m: None,
            )

    mock_stream.assert_not_called()
    assert result["status"] == "completed"
