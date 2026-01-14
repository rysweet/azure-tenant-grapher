"""
FastAPI Application for ATG Remote Service.

Philosophy:
- Ruthless simplicity - straightforward FastAPI setup
- Zero-BS - working endpoints only
- Long HTTP support (60 min timeout) + WebSocket progress

This is the main entry point for the ATG remote service.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..auth.api_keys import APIKeyStore
from ..auth.middleware import set_api_key_store
from ..common.exceptions import AuthenticationError, RemoteError
from ..db.connection_manager import ConnectionManager
from .config import ATGServerConfig, Neo4jConfig
from .dependencies import set_config, set_connection_manager
from .routers import generate, health, operations, scan
from .routers import websocket as ws_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Handles:
    - Configuration loading
    - Neo4j connection initialization
    - API key store setup
    - Graceful shutdown
    """
    # Startup
    logger.info("Starting ATG Remote Service...")

    connection_manager = None
    config = None

    try:
        # Load configuration
        config = ATGServerConfig.from_env()
        neo4j_config = Neo4jConfig.from_env(config.environment)

        logger.info(str(f"Configuration: {config}"))

        # Initialize Neo4j connection manager
        connection_manager = ConnectionManager(
            uri=neo4j_config.uri,
            user=neo4j_config.user,
            password=neo4j_config.password,
            max_pool_size=neo4j_config.max_pool_size,
        )
        await connection_manager.initialize()
        logger.info("Neo4j connection initialized")

        # Set global dependencies
        set_connection_manager(connection_manager)
        set_config(config)

        # Initialize services (Phase 4)
        from pathlib import Path

        from .dependencies import initialize_services

        output_dir = Path("outputs")
        initialize_services(connection_manager, output_dir)
        logger.info("Operation services initialized")

        # Initialize API key store
        api_key_store = APIKeyStore.from_key_list(config.api_keys, config.environment)
        set_api_key_store(api_key_store)
        logger.info(str(f"API key store initialized with {len(config.api_keys)} keys"))

        logger.info("Service startup complete")

        yield

    finally:
        # Shutdown
        logger.info("Shutting down ATG Remote Service...")

        if connection_manager:
            await connection_manager.close()
            logger.info("Neo4j connections closed")

        logger.info("Service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="ATG Remote Service",
    version="1.0.0",
    description="Azure Tenant Grapher remote execution service",
    lifespan=lifespan,
)

# Configure CORS
# Get allowed origins from environment variable with sensible defaults for development
allowed_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001",  # Dev defaults
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Explicit origins only (no wildcard)
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Explicit methods only
    allow_headers=["Authorization", "Content-Type"],  # Explicit headers only
)


# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors with 401 Unauthorized."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "AUTHENTICATION_FAILED",
                "message": str(exc),
            }
        },
    )


@app.exception_handler(RemoteError)
async def remote_error_handler(request: Request, exc: RemoteError):
    """Handle general remote errors with 500 Internal Server Error."""
    logger.exception(f"Remote error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with 400 Bad Request."""
    errors = exc.errors()
    first_error = errors[0] if errors else {}

    field = ".".join(str(loc) for loc in first_error.get("loc", []))
    message = first_error.get("msg", "Validation error")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"Invalid {field}: {message}",
            }
        },
    )


# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(scan.router, prefix="/api/v1", tags=["Scan"])
app.include_router(generate.router, prefix="/api/v1", tags=["Generate"])
app.include_router(operations.router, prefix="/api/v1", tags=["Operations"])
app.include_router(ws_router.router, tags=["WebSocket"])


__all__ = ["app"]
