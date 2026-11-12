"""
app/main.py
FastAPI application factory for the Wayfind agent backend.

NOTE (v2 architecture): This is an INTERNAL service.
  - No CORS (the browser never calls this service directly)
  - No public auth (handled by ShelterAppUiBackend)
  - Requests are authenticated via X-Internal-Key header (shared secret)
  - Only ShelterAppUiBackend should be able to reach this service

Responsibilities:
  - Create the FastAPI app instance
  - Register internal auth middleware (X-Internal-Key validation)
  - Register global exception handlers (never expose stack traces)
  - Mount the /internal router
  - Expose /health endpoint (exempt from auth, for container health checks)
  - Manage application lifespan:
      startup  → initialise session store, warm up MCP client
      shutdown → close session store, close MCP client

Usage:
  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from agent.dependencies import set_llm, set_mcp_client
from agent.runner import run_agent
from app.config import get_settings
from app.routes.agent import router as agent_router
from app.session import create_session_store
from mcp_client.client import WayfindMCPClient
from mcp_client.llm import WayfindLLM

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

    # ── LLM Client (Phase 6) ──────────────────────────────────────────────────
    logger.info("Initialising WayfindLLM (provider=%s)", settings.llm_provider)
    _api_key_map = {
        "groq": settings.groq_api_key,
        "gemini": settings.gemini_api_key,
        "openai": settings.openai_api_key,
    }
    llm_client = WayfindLLM(
        provider=settings.llm_provider,
        api_key=_api_key_map.get(settings.llm_provider, ""),
    )
    set_llm(llm_client)
    app.state.llm = llm_client

    # ── MCP Client (Phase 6) ──────────────────────────────────────────────────
    logger.info("Initialising WayfindMCPClient (transport=%s)", settings.mcp_transport)
    mcp_client = WayfindMCPClient(
        transport=settings.mcp_transport,
        server_url=settings.mcp_server_url,
    )
    await mcp_client.startup()
    set_mcp_client(mcp_client)
    app.state.mcp_client = mcp_client

    # ── Graph runner (wired in Phase 11) ───────────────────────────────────────
    logger.info("Wiring LangGraph runner into application state...")
    app.state.graph_runner = run_agent

    logger.info("Wayfind agent backend started (internal-only mode)")
    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down Wayfind agent backend...")
    await session_store.close()

    if app.state.mcp_client is not None:
        try:
            await app.state.mcp_client.shutdown()
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
        title="Wayfind Internal Agent API",
        description=(
            "Internal agent backend for Wayfind. "
            "Accepts events from ShelterAppUiBackend, runs LangGraph, "
            "and returns structured agent events. "
            "NOT publicly accessible — secured by X-Internal-Key header."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Internal auth middleware ───────────────────────────────────────────────
    _register_internal_auth_middleware(app, settings)

    # ── Exception handlers ─────────────────────────────────────────────────────
    _register_exception_handlers(app)

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(agent_router, prefix="/internal")
    _add_health_route(app)

    return app


def _register_internal_auth_middleware(app: FastAPI, settings) -> None:
    """Register middleware that validates the X-Internal-Key shared secret.

    Every request EXCEPT /health must carry:
        X-Internal-Key: <SHELTER_BACKEND_API_KEY>

    Requests with a missing or wrong key are rejected with HTTP 403.
    The key is compared using a constant-time check to resist timing attacks.
    """
    import hmac

    @app.middleware("http")
    async def internal_key_middleware(request: Request, call_next):
        # Health endpoint is always exempt — needed for Docker/k8s health checks
        if request.url.path == "/health":
            return await call_next(request)

        provided_key = request.headers.get("X-Internal-Key", "")
        expected_key = settings.shelter_backend_api_key

        # Constant-time comparison to resist timing attacks
        if not hmac.compare_digest(
            provided_key.encode("utf-8"),
            expected_key.encode("utf-8"),
        ):
            logger.warning(
                "Rejected request to %s — invalid or missing X-Internal-Key",
                request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"message": "Forbidden."},
            )

        return await call_next(request)


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    CRITICAL: Never return stack traces, internal error messages, or
    infrastructure details to the caller.  All unhandled exceptions
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


# ── Health endpoint (auth-exempt) ──────────────────────────────────────────────

def _add_health_route(app: FastAPI) -> None:
    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok", "service": "wayfind-agent"}


# ── Module-level app instance (used by uvicorn) ────────────────────────────────
app = create_app()
