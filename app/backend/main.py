"""LakebaseOps Monitoring App — FastAPI entry point."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lakebase_ops_app")

# Paths that bypass auth (health checks, static assets)
_AUTH_EXEMPT_PREFIXES = ("/api/health", "/assets", "/favicon")
_IS_LOCAL = os.getenv("LAKEBASE_LOCAL_DEV", "").lower() in ("1", "true", "yes")


class DatabricksProxyAuthMiddleware(BaseHTTPMiddleware):
    """Validate Databricks Apps proxy headers on non-exempt routes.

    When deployed behind the Databricks Apps reverse proxy, every
    authenticated request carries ``X-Forwarded-User`` and
    ``X-Forwarded-Email`` headers.  This middleware rejects requests
    that lack these headers unless the app is running in local-dev
    mode (``LAKEBASE_LOCAL_DEV=1``).
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for health checks, static assets, and root
        if path == "/" or any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return await call_next(request)

        # In local dev mode, skip proxy header validation
        if _IS_LOCAL:
            return await call_next(request)

        forwarded_user = request.headers.get("X-Forwarded-User", "")
        forwarded_email = request.headers.get("X-Forwarded-Email", "")

        if not forwarded_user and not forwarded_email:
            logger.warning(f"Auth rejected: missing proxy headers on {path}")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized — missing Databricks proxy headers"},
            )

        # Attach user info to request state for downstream use
        request.state.user = forwarded_user
        request.state.email = forwarded_email
        return await call_next(request)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger.info(f"main.py loaded, STATIC_DIR={STATIC_DIR}, exists={STATIC_DIR.exists()}")
logger.info(f"CWD={os.getcwd()}, __file__={__file__}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LakebaseOps app starting up")
    yield
    logger.info("LakebaseOps app shutting down")


app = FastAPI(
    title="LakebaseOps Monitor",
    description="3 Agents, 47 Tools, 7 Delta Tables — Real-time monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_raw = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else []
_cors_credentials = bool(_cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware — validates Databricks Apps proxy headers
app.add_middleware(DatabricksProxyAuthMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a safe error response."""
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# Register API routers
try:
    from .routers import health, agents, metrics, performance, indexes, operations, lakebase, jobs, assessment

    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(metrics.router)
    app.include_router(performance.router)
    app.include_router(indexes.router)
    app.include_router(operations.router)
    app.include_router(lakebase.router)
    app.include_router(jobs.router)
    app.include_router(assessment.router)
    logger.info("All routers registered successfully")
except Exception as e:
    logger.error(f"Failed to import/register routers: {e}", exc_info=True)

# Serve built frontend (SPA fallback)
ASSETS_DIR = STATIC_DIR / "assets"
INDEX_HTML = STATIC_DIR / "index.html"

if STATIC_DIR.exists() and ASSETS_DIR.exists() and INDEX_HTML.exists():
    logger.info("Mounting static frontend assets")
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        if full_path.startswith("api/"):
            return HTMLResponse(content='{"error":"not found"}', status_code=404)
        file = STATIC_DIR / full_path
        if file.is_file() and STATIC_DIR in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(str(INDEX_HTML))
else:
    logger.warning(
        f"Static files not found: STATIC_DIR={STATIC_DIR.exists()}, "
        f"assets={ASSETS_DIR.exists() if STATIC_DIR.exists() else 'N/A'}, "
        f"index={INDEX_HTML.exists() if STATIC_DIR.exists() else 'N/A'}"
    )

    @app.get("/")
    async def root():
        """Root endpoint when no frontend is deployed."""
        return {
            "status": "ok",
            "app": "LakebaseOps Monitor",
            "agents": 3,
            "tools": 47,
            "tables": 7,
            "endpoints": [
                "/api/health",
                "/api/agents/summary",
                "/api/metrics/overview",
                "/api/metrics/trends",
                "/api/performance/queries",
                "/api/performance/regressions",
                "/api/indexes/recommendations",
                "/api/operations/vacuum",
                "/api/operations/sync",
                "/api/operations/branches",
                "/api/operations/archival",
                "/api/lakebase/realtime",
                "/api/assessment/discover",
                "/api/assessment/profile",
                "/api/assessment/readiness",
                "/api/assessment/blueprint",
            ],
        }
