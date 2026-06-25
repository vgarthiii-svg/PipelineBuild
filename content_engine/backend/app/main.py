"""Content Creator Engine — FastAPI application entrypoint.

Wires routers, initializes the DB, seeds system rules, and serves the SPA.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .routers import brands, calendar, drafts, library, meta, projects
from .routers import settings as settings_router
from .seed import seed_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create tables and seed system data on startup."""
    init_db()
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Content Creator Engine",
    version="1.0.0",
    description="A marketing command center: research, generate, score, revise, "
                "repurpose, and organize content across platforms.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ai_enabled": settings.ai_enabled,
        "research_enabled": settings.research_enabled,
        "ai_provider": settings.ai_provider,
    }


# API routers
app.include_router(meta.router)
app.include_router(brands.router)
app.include_router(projects.router)
app.include_router(drafts.router)
app.include_router(library.router)
app.include_router(calendar.router)
app.include_router(settings_router.router)


# --- Serve the SPA frontend ------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
