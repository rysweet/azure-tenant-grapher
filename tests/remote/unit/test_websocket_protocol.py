"""
Unit tests for WebSocket protocol and message handling.

Tests WebSocket message format, event serialization, progress streaming,
and protocol validation following simplified architecture.

Philosophy:
- Test WebSocket logic in isolation
- Mock WebSocket connections
- Fast execution (< 100ms per test)
- Follow simplified architecture (long HTTP + WebSocket progress)
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

# =============================================================================
# WebSocket Message Format Tests (Architecture Section 4.1)
# =============================================================================


def test_progress_message_serializes_correctly():
    """Test that progress messages serialize to correct JSON format.

    Expected format:
    {
        "type": "progress",
        "job_id": "scan-abc123",
        "progress": 45.5,
        "message": "Processing resources...",
        "timestamp": "2025-12-09T10:30:45Z"
    }
    """
    from src.remote.websocket.protocol import ProgressMessage

    # This class doesn't exist yet - will fail!
    msg = ProgressMessage(
        job_id="scan-abc123",
        progress=45.5,
        message="Processing resources...",
        timestamp=datetime.fromisoformat("2025-12-09T10:30:45"),
    )

    json_str = msg.to_json()
    data = json.loads(json_str)

    assert data["type"] == "progress"
    assert data["job_id"] == "scan-abc123"
    assert data["progress"] == 45.5
    assert data["message"] == "Processing resources..."
    assert data["timestamp"] == "2025-12-09T10:30:45"


def test_error_message_serializes_correctly():
    """Test that error messages serialize with error details."""
    from src.remote.websocket.protocol import ErrorMessage

    msg = ErrorMessage(
        job_id="scan-abc123",
        error_code="AZURE_AUTH_FAILED",
        error_message="Failed to authenticate with Azure",
        details={"tenant_id": "12345678-..."},
    )

    json_str = msg.to_json()
    data = json.loads(json_str)

    assert data["type"] == "error"
    assert data["job_id"] == "scan-abc123"
    assert data["error_code"] == "AZURE_AUTH_FAILED"
    assert data["error_message"] == "Failed to authenticate with Azure"
    assert data["details"]["tenant_id"] == "12345678-..."


def test_completion_message_serializes_correctly():
    """Test that completion messages serialize with result summary."""
    from src.remote.websocket.protocol import CompletionMessage

    msg = CompletionMessage(
        job_id="scan-abc123",
        status="completed",
        result={"resources_discovered": 1523, "duration_seconds": 320},
    )

    json_str = msg.to_json()
    data = json.loads(json_str)

    assert data["type"] == "completion"
    assert data["job_id"] == "scan-abc123"
    assert data["status"] == "completed"
    assert data["result"]["resources_discovered"] == 1523


def test_message_deserializes_from_json():
    """Test that messages can be deserialized from JSON."""
    from src.remote.websocket.protocol import from_json

    json_str = json.dumps(
        {
            "type": "progress",
            "job_id": "scan-abc123",
            "progress": 45.5,
            "message": "Processing resources...",
            "timestamp": "2025-12-09T10:30:45",
        }
    )

    msg = from_json(json_str)

    assert msg.type == "progress"
    assert msg.job_id == "scan-abc123"
    assert msg.progress == 45.5


def test_invalid_message_raises_error():
    """Test that invalid JSON raises appropriate error."""
    from src.remote.websocket.protocol import ProtocolError, from_json

    invalid_json = "not valid json"

    with pytest.raises(ProtocolError):
        from_json(invalid_json)


def test_message_validates_required_fields():
    """Test that message validation ensures required fields are present."""
    from src.remote.websocket.protocol import ProgressMessage, ProtocolError

    with pytest.raises(ProtocolError) as exc_info:
        ProgressMessage(
            job_id=None,  # Required field missing
            progress=45.5,
            message="Test",
        )

    assert "job_id" in str(exc_info.value).lower()


# =============================================================================
# WebSocket Manager Tests (Architecture Section 3.2)
# =============================================================================


@pytest.mark.asyncio
async def test_websocket_manager_registers_connection():
    """Test that WebSocketManager registers new connections."""
    from src.remote.websocket.manager import WebSocketManager

    # This class doesn't exist yet - will fail!
    manager = WebSocketManager()

    mock_websocket = AsyncMock()
    job_id = "scan-abc123"

    await manager.register(job_id, mock_websocket)

    assert job_id in manager.connections
    assert manager.connections[job_id] == mock_websocket


@pytest.mark.asyncio
async def test_websocket_manager_unregisters_connection():
    """Test that WebSocketManager unregisters connections."""
    from src.remote.websocket.manager import WebSocketManager

    manager = WebSocketManager()

    mock_websocket = AsyncMock()
    job_id = "scan-abc123"

    await manager.register(job_id, mock_websocket)
    await manager.unregister(job_id)

    assert job_id not in manager.connections


@pytest.mark.asyncio
async def test_websocket_manager_sends_message_to_connection():
    """Test that WebSocketManager sends messages to specific connection."""
    from src.remote.websocket.manager import WebSocketManager
    from src.remote.websocket.protocol import ProgressMessage

    manager = WebSocketManager()

    mock_websocket = AsyncMock()
    mock_websocket.send = AsyncMock()
    job_id = "scan-abc123"

    await manager.register(job_id, mock_websocket)

    msg = ProgressMessage(job_id=job_id, progress=50.0, message="Halfway done")

    await manager.send_message(job_id, msg)

    mock_websocket.send.assert_called_once()
    sent_data = mock_websocket.send.call_args[0][0]
    data = json.loads(sent_data)

    assert data["type"] == "progress"
    assert data["progress"] == 50.0


@pytest.mark.asyncio
async def test_websocket_manager_broadcasts_to_all_connections():
    """Test that WebSocketManager can broadcast to all connections."""
    from src.remote.websocket.manager import WebSocketManager
    from src.remote.websocket.protocol import ProgressMessage

    manager = WebSocketManager()

    # Register multiple connections
    mock_ws1 = AsyncMock()
    mock_ws1.send = AsyncMock()
    mock_ws2 = AsyncMock()
    mock_ws2.send = AsyncMock()

    await manager.register("job1", mock_ws1)
    await manager.register("job2", mock_ws2)

    msg = ProgressMessage(
        job_id="broadcast", progress=100.0, message="All jobs complete"
    )

    await manager.broadcast(msg)

    mock_ws1.send.assert_called_once()
    mock_ws2.send.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_manager_handles_closed_connections():
    """Test that WebSocketManager handles closed connections gracefully."""
    from src.remote.websocket.manager import WebSocketManager
    from src.remote.websocket.protocol import ProgressMessage

    manager = WebSocketManager()

    mock_websocket = AsyncMock()
    # Simulate closed connection
    mock_websocket.send = AsyncMock(side_effect=Exception("Connection closed"))
    job_id = "scan-abc123"

    await manager.register(job_id, mock_websocket)

    msg = ProgressMessage(job_id=job_id, progress=50.0, message="Test")

    # Should not raise, just log and unregister
    await manager.send_message(job_id, msg)

    # Connection should be unregistered
    assert job_id not in manager.connections


@pytest.mark.asyncio
async def test_websocket_manager_tracks_connection_count():
    """Test that WebSocketManager tracks active connection count."""
    from src.remote.websocket.manager import WebSocketManager

    manager = WebSocketManager()

    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()

    await manager.register("job1", mock_ws1)
    assert manager.connection_count() == 1

    await manager.register("job2", mock_ws2)
    assert manager.connection_count() == 2

    await manager.unregister("job1")
    assert manager.connection_count() == 1


# =============================================================================
# Progress Streaming Tests (Architecture Section 3.2)
# =============================================================================


@pytest.mark.asyncio
async def test_progress_stream_sends_updates():
    """Test that ProgressStream sends progress updates via WebSocket."""
    from src.remote.websocket.progress import ProgressStream

    mock_manager = Mock()
    mock_manager.send_message = AsyncMock()

    job_id = "scan-abc123"

    # This class doesn't exist yet - will fail!
    stream = ProgressStream(job_id, mock_manager)

    await stream.send_progress(50.0, "Halfway done")

    mock_manager.send_message.assert_called_once()
    call_args = mock_manager.send_message.call_args[0]

    assert call_args[0] == job_id  # job_id
    msg = call_args[1]
    assert msg.progress == 50.0
    assert msg.message == "Halfway done"


@pytest.mark.asyncio
async def test_progress_stream_sends_error():
    """Test that ProgressStream sends error messages."""
    from src.remote.websocket.progress import ProgressStream

    mock_manager = Mock()
    mock_manager.send_message = AsyncMock()

    job_id = "scan-abc123"

    stream = ProgressStream(job_id, mock_manager)

    await stream.send_error("AZURE_AUTH_FAILED", "Authentication failed")

    mock_manager.send_message.assert_called_once()
    call_args = mock_manager.send_message.call_args[0]

    msg = call_args[1]
    assert msg.type == "error"
    assert msg.error_code == "AZURE_AUTH_FAILED"


@pytest.mark.asyncio
async def test_progress_stream_sends_completion():
    """Test that ProgressStream sends completion message."""
    from src.remote.websocket.progress import ProgressStream

    mock_manager = Mock()
    mock_manager.send_message = AsyncMock()

    job_id = "scan-abc123"

    stream = ProgressStream(job_id, mock_manager)

    await stream.send_completion({"resources": 1523})

    mock_manager.send_message.assert_called_once()
    call_args = mock_manager.send_message.call_args[0]

    msg = call_args[1]
    assert msg.type == "completion"
    assert msg.result["resources"] == 1523


@pytest.mark.asyncio
async def test_progress_stream_context_manager():
    """Test that ProgressStream works as async context manager."""
    from src.remote.websocket.progress import ProgressStream

    mock_manager = Mock()
    mock_manager.send_message = AsyncMock()
    mock_manager.register = AsyncMock()
    mock_manager.unregister = AsyncMock()

    job_id = "scan-abc123"
    mock_websocket = AsyncMock()

    async with ProgressStream(job_id, mock_manager, mock_websocket) as stream:
        await stream.send_progress(50.0, "Test")

    # Should register on enter and unregister on exit
    mock_manager.register.assert_called_once_with(job_id, mock_websocket)
    mock_manager.unregister.assert_called_once_with(job_id)


# =============================================================================
# Message Validation Tests
# =============================================================================


def test_progress_validates_percentage_range():
    """Test that progress percentage is validated (0-100)."""
    from src.remote.websocket.protocol import ProgressMessage, ProtocolError

    with pytest.raises(ProtocolError) as exc_info:
        ProgressMessage(
            job_id="test",
            progress=150.0,  # Invalid - > 100
            message="Test",
        )

    assert "progress" in str(exc_info.value).lower()


def test_job_id_format_validation():
    """Test that job_id format is validated."""
    from src.remote.websocket.protocol import ProgressMessage, ProtocolError

    invalid_job_ids = [
        "",  # Empty
        "x",  # Too short
        "invalid job id with spaces",  # Spaces
        "invalid/job/id",  # Slashes
    ]

    for job_id in invalid_job_ids:
        with pytest.raises(ProtocolError):
            ProgressMessage(job_id=job_id, progress=50.0, message="Test")


def test_message_size_limit():
    """Test that messages are rejected if too large."""
    from src.remote.websocket.protocol import ProgressMessage, ProtocolError

    # Create message with very large content
    large_message = "x" * (1024 * 1024 * 2)  # 2MB

    with pytest.raises(ProtocolError) as exc_info:
        msg = ProgressMessage(job_id="test", progress=50.0, message=large_message)
        msg.validate()

    assert "size" in str(exc_info.value).lower()


# =============================================================================
# WebSocket Connection Tests
# =============================================================================


@pytest.mark.asyncio
async def test_websocket_connection_accepts_valid_handshake():
    """Test that WebSocket connection accepts valid handshake."""
    from src.remote.websocket.connection import WebSocketConnection

    mock_websocket = AsyncMock()
    mock_websocket.accept = AsyncMock()

    # This class doesn't exist yet - will fail!
    conn = WebSocketConnection(mock_websocket)

    await conn.accept()

    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_connection_validates_api_key():
    """Test that WebSocket connection validates API key from query params."""
    from src.remote.auth import InvalidAPIKeyError
    from src.remote.websocket.connection import WebSocketConnection

    mock_websocket = AsyncMock()
    # Simulate invalid API key in query params
    mock_websocket.query_params = {"api_key": "invalid_key"}

    conn = WebSocketConnection(mock_websocket)

    with pytest.raises(InvalidAPIKeyError):
        await conn.accept()


@pytest.mark.asyncio
async def test_websocket_connection_closes_gracefully():
    """Test that WebSocket connection closes gracefully."""
    from src.remote.websocket.connection import WebSocketConnection

    mock_websocket = AsyncMock()
    mock_websocket.close = AsyncMock()

    conn = WebSocketConnection(mock_websocket)

    await conn.close(code=1000, reason="Normal closure")

    mock_websocket.close.assert_called_once_with(code=1000, reason="Normal closure")


@pytest.mark.asyncio
async def test_websocket_connection_handles_ping_pong():
    """Test that WebSocket connection handles ping/pong for keepalive."""
    from src.remote.websocket.connection import WebSocketConnection

    mock_websocket = AsyncMock()
    mock_websocket.send = AsyncMock()

    conn = WebSocketConnection(mock_websocket)

    # Simulate receiving ping
    await conn.on_ping(b"ping_data")

    # Should send pong
    mock_websocket.send.assert_called_once()


# =============================================================================
# Performance Tests
# =============================================================================


def test_message_serialization_performance():
    """Test that message serialization is fast (< 1ms per message)."""
    import time

    from src.remote.websocket.protocol import ProgressMessage

    msg = ProgressMessage(job_id="test", progress=50.0, message="Test message")

    start = time.perf_counter()
    for _ in range(1000):
        msg.to_json()
    elapsed = time.perf_counter() - start

    # Should serialize 1000 messages in < 100ms (0.1ms per message)
    assert elapsed < 0.1


def test_message_deserialization_performance():
    """Test that message deserialization is fast."""
    import time

    from src.remote.websocket.protocol import Message

    json_str = json.dumps(
        {
            "type": "progress",
            "job_id": "test",
            "progress": 50.0,
            "message": "Test message",
            "timestamp": "2025-12-09T10:30:45",
        }
    )

    from src.remote.websocket.protocol import from_json

    start = time.perf_counter()
    for _ in range(1000):
        from_json(json_str)
    elapsed = time.perf_counter() - start

    # Should deserialize 1000 messages in < 100ms
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_websocket_manager_handles_high_throughput():
    """Test that WebSocketManager handles many messages per second."""
    import time

    from src.remote.websocket.manager import WebSocketManager
    from src.remote.websocket.protocol import ProgressMessage

    manager = WebSocketManager()

    # Register 10 connections
    for i in range(10):
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        await manager.register(f"job{i}", mock_ws)

    msg = ProgressMessage(job_id="test", progress=50.0, message="Test")

    start = time.perf_counter()
    # Send 1000 messages
    for i in range(1000):
        await manager.send_message(f"job{i % 10}", msg)
    elapsed = time.perf_counter() - start

    # Should send 1000 messages in < 1 second (1000 msgs/sec)
    assert elapsed < 1.0
