"""
app/main.py
FastAPI application factory for the Wayfind agent backend.

Responsibilities:
  - Create the FastAPI app instance
  - Register CORS middleware (reads CORS_ORIGINS from settings)
  - Register global exception handlers (never expose stack traces)
  - Mount the /api router
  - Manage application lifespan:
      startup  → initialise session store, warm up MCP client
      shutdown → close session store, close MCP client

Usage:
  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes.agent import router as agent_router
from app.session import create_session_store

logger = logging.getLogger(__name__)

# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Startup:
      1. Initialise session store (Redis or memory)
      2. Attach graph_runner to app.state (wired in Phase 11)
      3. Log readiness

    Shutdown:
      1. Close session store connections
      2. Close MCP client (Phase 6)
    """
    settings = get_settings()

    # ── Session store ──────────────────────────────────────────────────────────
    logger.info("Initialising session store (backend=%s)", settings.session_backend)
    session_store = create_session_store(
        backend=settings.session_backend,
        redis_url=settings.redis_url,
    )
    app.state.session_store = session_store

    # ── Graph runner (wired in Phase 11) ───────────────────────────────────────
    # Phase 3 placeholder — replaced once agent/runner.py exists.
    app.state.graph_runner = None

    # ── MCP Client (wired in Phase 6) ─────────────────────────────────────────
    app.state.mcp_client = None

    logger.info("Wayfind agent backend started and ready")
    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down Wayfind agent backend...")
    await session_store.close()

    if app.state.mcp_client is not None:
        try:
            await app.state.mcp_client.close()
        except Exception:
            logger.warning("Error closing MCP client during shutdown", exc_info=True)

    logger.info("Shutdown complete")


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Called once at import time (module-level ``app`` below).
    """
    settings = get_settings()

    app = FastAPI(
        title="Wayfind Agent API",
        description=(
            "Prompt-first backend for missing children, found children, "
            "and shelter access. Powered by LangGraph + FastMCP."
        ),
        version="0.1.0",
        # Disable auto-generated docs in production if desired
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type", "X-Session-ID"],
        expose_headers=["X-Session-ID"],
    )

    # ── Exception handlers ─────────────────────────────────────────────────────
    _register_exception_handlers(app)

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(agent_router, prefix="/api")

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    CRITICAL: Never return stack traces, internal error messages, or
    infrastructure details to the client.  All unhandled exceptions
    return the same generic JSON body.
    """

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Something went wrong. Please try again."},
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "The requested resource was not found."},
        )

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={"message": "Method not allowed."},
        )


# ── Module-level app instance (used by uvicorn) ────────────────────────────────
app = create_app()
