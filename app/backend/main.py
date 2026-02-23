"""LakebaseOps Monitoring App — FastAPI entry point."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lakebase_ops_app")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
try:
    from .routers import health, agents, metrics, performance, indexes, operations, lakebase

    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(metrics.router)
    app.include_router(performance.router)
    app.include_router(indexes.router)
    app.include_router(operations.router)
    app.include_router(lakebase.router)
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
            ],
        }
