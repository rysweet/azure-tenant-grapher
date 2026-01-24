"""
Unit tests for RemoteProgressDisplay - Progress display for remote operations.

Tests cover:
- Initialization
- Progress updates
- Completion handling
- Error display
- Info messages
- Context manager usage
- Show/hide progress behavior
"""

from unittest.mock import Mock, patch

from src.remote.client.progress import RemoteProgressDisplay, create_progress_callback

# Initialization Tests


def test_progress_display_initializes_with_show_progress_true():
    """Test that RemoteProgressDisplay initializes with show_progress=True by default."""
    display = RemoteProgressDisplay()

    assert display.show_progress is True
    assert display.console is not None
    assert display._progress is None
    assert display._task_id is None


def test_progress_display_initializes_with_show_progress_false():
    """Test that RemoteProgressDisplay can be initialized with show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    assert display.show_progress is False


# Start Method Tests


def test_start_creates_progress_bar_when_show_progress_true():
    """Test that start() creates progress bar when show_progress=True."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start("Starting operation...")

    assert display._progress is not None
    assert display._task_id is not None


def test_start_does_nothing_when_show_progress_false():
    """Test that start() does nothing when show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    display.start("Starting operation...")

    assert display._progress is None
    assert display._task_id is None


def test_start_uses_default_description():
    """Test that start() uses default description if none provided."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

    # Progress should be started (we just verify it's not None)
    assert display._progress is not None


def test_start_uses_custom_description():
    """Test that start() uses custom description when provided."""
    display = RemoteProgressDisplay(show_progress=True)
    custom_desc = "Custom operation starting"

    with patch.object(display, "console"):
        with patch("src.remote.client.progress.Progress") as mock_progress_class:
            mock_progress_instance = Mock()
            mock_progress_class.return_value = mock_progress_instance
            mock_progress_instance.add_task.return_value = 1

            display.start(custom_desc)

            # Verify add_task was called with custom description
            mock_progress_instance.add_task.assert_called_once_with(
                custom_desc, total=100
            )


# Update Method Tests


def test_update_updates_progress_when_started():
    """Test that update() updates progress bar when started."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

        # Mock the progress bar
        mock_progress = Mock()
        display._progress = mock_progress
        display._task_id = 1

        display.update(50.0, "Processing resources")

        mock_progress.update.assert_called_once_with(
            1, completed=50.0, description="Processing resources"
        )


def test_update_does_nothing_when_show_progress_false():
    """Test that update() does nothing when show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    # Should not raise even though not started
    display.update(50.0, "Processing")

    assert display._progress is None


def test_update_does_nothing_when_not_started():
    """Test that update() does nothing if progress not started."""
    display = RemoteProgressDisplay(show_progress=True)

    # Don't call start()
    display.update(50.0, "Processing")

    # Should handle gracefully
    assert display._progress is None


def test_update_does_nothing_when_task_id_none():
    """Test that update() handles case where task_id is None."""
    display = RemoteProgressDisplay(show_progress=True)
    display._progress = Mock()
    display._task_id = None

    # Should not raise
    display.update(50.0, "Processing")

    display._progress.update.assert_not_called()


# Complete Method Tests


def test_complete_marks_operation_complete():
    """Test that complete() marks operation as 100% complete."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

        mock_progress = Mock()
        display._progress = mock_progress
        display._task_id = 1

        display.complete("Scan finished")

        # Should update to 100% and stop
        mock_progress.update.assert_called_once()
        call_args = mock_progress.update.call_args
        assert call_args[1]["completed"] == 100
        assert "✓" in call_args[1]["description"]
        assert "Scan finished" in call_args[1]["description"]

        mock_progress.stop.assert_called_once()


def test_complete_uses_default_message():
    """Test that complete() uses default message if none provided."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

        mock_progress = Mock()
        display._progress = mock_progress
        display._task_id = 1

        display.complete()

        call_args = mock_progress.update.call_args
        assert "Operation complete" in call_args[1]["description"]


def test_complete_does_nothing_when_show_progress_false():
    """Test that complete() does nothing when show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    display.complete("Done")

    assert display._progress is None


def test_complete_does_nothing_when_not_started():
    """Test that complete() does nothing if progress not started."""
    display = RemoteProgressDisplay(show_progress=True)

    # Don't call start()
    display.complete()

    assert display._progress is None


# Error Method Tests


def test_error_displays_error_message():
    """Test that error() displays error message to console."""
    display = RemoteProgressDisplay(show_progress=True)

    mock_console = Mock()
    display.console = mock_console

    display.error("Connection failed")

    mock_console.print.assert_called_once()
    call_args = mock_console.print.call_args[0][0]
    assert "✗" in call_args
    assert "Error" in call_args
    assert "Connection failed" in call_args


def test_error_stops_progress_if_running():
    """Test that error() stops progress bar if it's running."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

        mock_progress = Mock()
        display._progress = mock_progress

        mock_console = Mock()
        display.console = mock_console

        display.error("Something went wrong")

        mock_progress.stop.assert_called_once()
        mock_console.print.assert_called_once()


def test_error_does_nothing_when_show_progress_false():
    """Test that error() does nothing when show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    display.error("Error message")

    # Should not raise


# Info Method Tests


def test_info_displays_info_message():
    """Test that info() displays info message to console."""
    display = RemoteProgressDisplay(show_progress=True)

    mock_console = Mock()
    display.console = mock_console

    display.info("Connecting to service")

    mock_console.print.assert_called_once()
    call_args = mock_console.print.call_args[0][0]
    assert "i" in call_args
    assert "Connecting to service" in call_args


def test_info_does_nothing_when_show_progress_false():
    """Test that info() does nothing when show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    display.info("Info message")

    # Should not raise


# Context Manager Tests


def test_context_manager_entry_returns_self():
    """Test that context manager entry returns self."""
    display = RemoteProgressDisplay()

    with display as d:
        assert d == display


def test_context_manager_exit_stops_progress():
    """Test that context manager exit stops progress if running."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

        mock_progress = Mock()
        display._progress = mock_progress

        display.__exit__(None, None, None)

        mock_progress.stop.assert_called_once()


def test_context_manager_exit_handles_no_progress():
    """Test that context manager exit handles case where progress not started."""
    display = RemoteProgressDisplay()

    # Should not raise
    display.__exit__(None, None, None)


def test_context_manager_exit_with_exception():
    """Test that context manager exit is called even with exception."""
    display = RemoteProgressDisplay(show_progress=True)

    # Create a mock progress before entering context manager
    mock_progress = Mock()
    display._progress = mock_progress

    try:
        with display:
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Progress should still be stopped
    mock_progress.stop.assert_called_once()


# Callback Factory Tests


def test_create_progress_callback_returns_callable():
    """Test that create_progress_callback returns a callable function."""
    display = RemoteProgressDisplay()
    callback = create_progress_callback(display)

    assert callable(callback)


def test_create_progress_callback_calls_display_update():
    """Test that callback function calls display.update()."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "update") as mock_update:
        callback = create_progress_callback(display)
        callback(75.0, "Almost done")

        mock_update.assert_called_once_with(75.0, "Almost done")


def test_create_progress_callback_works_with_remote_client():
    """Test that callback works as expected with remote client pattern."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        display.start()

        mock_progress = Mock()
        display._progress = mock_progress
        display._task_id = 1

        callback = create_progress_callback(display)

        # Simulate remote client calling callback
        callback(25.0, "Starting scan")
        callback(50.0, "Processing resources")
        callback(75.0, "Generating results")

        # Should have called update 3 times
        assert mock_progress.update.call_count == 3


# Integration Tests


def test_full_progress_workflow():
    """Test complete progress workflow from start to completion."""
    display = RemoteProgressDisplay(show_progress=True)

    with patch.object(display, "console"):
        # Start
        display.start("Starting remote scan")
        assert display._progress is not None

        mock_progress = Mock()
        display._progress = mock_progress
        display._task_id = 1

        # Update multiple times
        display.update(25.0, "Discovering resources")
        display.update(50.0, "Processing resources")
        display.update(75.0, "Building graph")

        # Complete
        display.complete("Scan completed successfully")

        # Verify workflow
        assert mock_progress.update.call_count == 4  # 3 updates + 1 complete
        mock_progress.stop.assert_called_once()


def test_full_error_workflow():
    """Test complete error workflow."""
    display = RemoteProgressDisplay(show_progress=True)

    # Mock progress and console before starting
    mock_progress = Mock()
    mock_console = Mock()

    display._progress = mock_progress
    display.console = mock_console

    # Update
    display.update(30.0, "Processing")

    # Error occurs
    display.error("Connection lost")

    # Verify error handling
    mock_progress.stop.assert_called_once()
    mock_console.print.assert_called_once()
    error_msg = mock_console.print.call_args[0][0]
    assert "Connection lost" in error_msg


def test_no_progress_mode_workflow():
    """Test that all methods work correctly when show_progress=False."""
    display = RemoteProgressDisplay(show_progress=False)

    # Should not raise any exceptions
    display.start("Starting")
    display.update(50.0, "Processing")
    display.info("Info message")
    display.complete("Done")
    display.error("Error message")

    # Nothing should have been created
    assert display._progress is None
    assert display._task_id is None


def test_context_manager_with_progress():
    """Test context manager usage with progress display."""
    with RemoteProgressDisplay(show_progress=True) as display:
        with patch.object(display, "console"):
            display.start("Operation starting")

            mock_progress = Mock()
            display._progress = mock_progress
            display._task_id = 1

            display.update(50.0, "Halfway")
            display.complete()

    # Progress should be stopped after context exits
    mock_progress.stop.assert_called()
