"""Pytest configuration for IAC tests."""

import pytest


@pytest.fixture(autouse=True)
def force_handler_registration():
    """Force handler registration before each test.

    This ensures that all handlers, including newly added ones,
    are properly registered in the HandlerRegistry before tests run.
    """
    import src.iac.emitters.terraform.handlers as handlers_module
    from src.iac.emitters.terraform.handlers import HandlerRegistry

    # Clear existing handlers to force fresh registration
    HandlerRegistry._handlers = []
    HandlerRegistry._type_cache = {}
    handlers_module._handlers_registered = False

    # Force re-registration
    handlers_module._register_all_handlers()
    handlers_module._handlers_registered = True

    # WORKAROUND: Explicitly import private_endpoint handler to force registration
    # This is needed due to pytest import caching issues
    try:
        from src.iac.emitters.terraform.handlers.network import private_endpoint

        _ = private_endpoint  # Prevent unused import warning
    except Exception:
        pass

    yield
