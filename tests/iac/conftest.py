"""Pytest configuration for IAC tests."""

import pytest


@pytest.fixture(autouse=True)
def force_handler_registration():
    """Force handler registration before each test.

    This ensures that all handlers, including newly added ones,
    are properly registered in the HandlerRegistry before tests run.

    KNOWN ISSUE: This fixture has a limitation where handlers already imported
    before the registry is cleared won't be re-registered due to Python's module
    caching. As a workaround, we directly register handlers that may have been
    missed. This is tracked as a test infrastructure issue requiring module
    reload support.
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

    # WORKAROUND: Manually register handlers that may have been cached
    # This is needed because Python's module caching prevents @handler decorator
    # from re-executing on subsequent imports
    try:
        from src.iac.emitters.terraform.handlers.network.bastion import (
            BastionHostHandler,
        )
        from src.iac.emitters.terraform.handlers.network.private_endpoint import (
            PrivateEndpointHandler,
        )

        # Manually register if not already present
        for handler_class in [BastionHostHandler, PrivateEndpointHandler]:
            if handler_class not in HandlerRegistry._handlers:
                HandlerRegistry.register(handler_class)
    except Exception:
        pass

    yield
