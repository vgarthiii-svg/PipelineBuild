import logging
import os
import sqlite3
import traceback
from dotenv import load_dotenv

# Load .env from project root (parent of app/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)

# Configure logging BEFORE importing anything that might log on import
from app.logging_config import configure_logging, error_ring
configure_logging()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import engine, SessionLocal, Base, DB_PATH
from app.models import *  # noqa: F401, F403 - ensure all models are registered
from app.seed import seed_database
from app.services import backup as backup_service

from app.routers import clients, prospects, pipeline, relationships, intros, activity
from app.routers import behavior, intent, filters, notifications, profiles, schedules

log = logging.getLogger("bd_pipeline")

app = FastAPI(title="BD Pipeline Agent", version="2.0.0")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch any unhandled exception, log it with full traceback, return 500."""
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check /api/health/errors for details."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(clients.router)
app.include_router(prospects.router)
app.include_router(pipeline.router)
app.include_router(relationships.router)
app.include_router(intros.router)
app.include_router(activity.router)
app.include_router(behavior.router)
app.include_router(intent.router)
app.include_router(filters.router)
app.include_router(notifications.router)
app.include_router(profiles.router)
app.include_router(schedules.router)

# Serve static files (dashboard)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


def _run_migrations():
    """Add new columns to existing tables (safe to run repeatedly)."""
    conn = sqlite3.connect(DB_PATH)
    alter_statements = [
        # Prospect identity layer columns
        "ALTER TABLE prospects ADD COLUMN industry_vertical TEXT",
        "ALTER TABLE prospects ADD COLUMN sub_vertical TEXT",
        "ALTER TABLE prospects ADD COLUMN business_model TEXT",
        "ALTER TABLE prospects ADD COLUMN stage TEXT",
        "ALTER TABLE prospects ADD COLUMN capability_provides TEXT",
        "ALTER TABLE prospects ADD COLUMN capability_needs TEXT",
        "ALTER TABLE prospects ADD COLUMN channels TEXT",
        "ALTER TABLE prospects ADD COLUMN tech_stack TEXT",
        "ALTER TABLE prospects ADD COLUMN regulatory_footprint TEXT",
        # Pipeline 4-layer scoring columns
        "ALTER TABLE pipeline_entries ADD COLUMN filtered BOOLEAN DEFAULT 0",
        "ALTER TABLE pipeline_entries ADD COLUMN filter_reason TEXT",
        "ALTER TABLE pipeline_entries ADD COLUMN friction_coefficient REAL DEFAULT 1.0",
        "ALTER TABLE pipeline_entries ADD COLUMN intent_multiplier REAL DEFAULT 1.0",
        # Criteria library columns
        "ALTER TABLE scoring_criteria ADD COLUMN active BOOLEAN DEFAULT 1",
        "ALTER TABLE scoring_criteria ADD COLUMN group_name TEXT",
        "ALTER TABLE scoring_criteria ADD COLUMN library_id INTEGER",
        # Client active flag
        "ALTER TABLE clients ADD COLUMN active BOOLEAN DEFAULT 0",
    ]
    for stmt in alter_statements:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Column already exists
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    # Create all tables (including new ones)
    Base.metadata.create_all(bind=engine)
    # Add new columns to existing tables
    _run_migrations()
    # Seed if empty
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    # Start nightly backup loop
    backup_service.start_scheduler(interval_hours=24)
    # Start agent scheduler
    from app.services import scheduler as agent_scheduler
    agent_scheduler.seed_jobs()
    agent_scheduler.start_scheduler()
    log.info("BD Pipeline Agent started. DB=%s, backups=%s", DB_PATH, backup_service.BACKUP_DIR)


@app.get("/")
def root():
    """Redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.get("/favicon.ico")
def favicon():
    """Serve favicon from the canonical root path (browsers check /favicon.ico by default)."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/favicon.svg", status_code=301)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.get("/api/health/errors")
def recent_errors(limit: int = 50):
    """Return the most recent ERROR/CRITICAL log records (in-memory ring buffer)."""
    snap = error_ring.snapshot()
    # Most recent first
    snap = list(reversed(snap))[:limit]
    return {"count": len(snap), "errors": snap}


@app.get("/api/health/backups")
def list_backup_files():
    """List all backup files with size + timestamp. Used by the dashboard."""
    return {"backups": backup_service.list_backups(), "retention_days": backup_service.RETENTION_DAYS}


@app.post("/api/health/backups/run")
def run_backup_now():
    """Trigger an immediate manual backup. Useful before risky schema changes."""
    try:
        path = backup_service.backup_now()
        return {"status": "ok", "filename": os.path.basename(path)}
    except Exception as e:
        log.exception("Manual backup failed")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@app.get("/api/sources/status")
def source_status():
    """Check configuration status of each data source."""
    from app.services import hubspot_scan, apollo_enrich
    return {
        "gmail": {
            "configured": bool(os.environ.get("GMAIL_OAUTH_TOKEN")),
            "requires": "Google OAuth setup (not yet implemented)",
        },
        "hubspot": {
            "configured": hubspot_scan.is_configured(),
            "requires": "HUBSPOT_API_KEY in .env",
        },
        "calendar": {
            "configured": bool(os.environ.get("GOOGLE_CALENDAR_OAUTH_TOKEN")),
            "requires": "Google OAuth setup (not yet implemented)",
        },
        "apollo": {
            "configured": apollo_enrich.is_configured(),
            "requires": "APOLLO_API_KEY in .env",
        },
        "conference": {
            "configured": True,
            "requires": "Conference attendees table (always active)",
        },
        "relmap": {
            "configured": True,
            "requires": "Relationships table (always active)",
        },
    }
