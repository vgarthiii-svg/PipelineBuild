import os
from dotenv import load_dotenv

# Load .env from project root (parent of app/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, SessionLocal, Base
from app.models import *  # noqa: F401, F403 - ensure all models are registered
from app.seed import seed_database

from app.routers import clients, prospects, pipeline, relationships, intros, activity

app = FastAPI(title="BD Pipeline Agent", version="1.0.0")

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

# Serve static files (dashboard)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


@app.on_event("startup")
def startup():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    # Seed if empty
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


@app.get("/")
def root():
    """Redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
