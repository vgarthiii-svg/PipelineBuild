import os

from dotenv import load_dotenv

# Load .env from the project root (parent of app/) before anything else
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine, IMAGE_DIR
from app.models import *  # noqa: F401,F403 - register models
from app.routers import cards, dashboard

app = FastAPI(title="Sports Card Tracker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure tables exist as soon as the app is imported (robust for any ASGI runner)
Base.metadata.create_all(bind=engine)

app.include_router(cards.router)
app.include_router(dashboard.router)

# Serve uploaded card images
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# Serve the web UI
_STATIC_DIR = os.path.join(_PROJECT_ROOT, "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "vision_model": os.environ.get("CARD_VISION_MODEL", "claude-opus-4-8"),
    }
