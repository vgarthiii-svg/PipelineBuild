import os

from dotenv import load_dotenv

# Load .env from the project root (parent of app/) before anything else
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine, ensure_schema, IMAGE_DIR
from app.models import *  # noqa: F401,F403 - register models
from app.routers import cards, dashboard, checklists, suggest, settings as settings_router
from app.auth import COOKIE, COOKIE_MAX_AGE, hash_password, get_password_hash

app = FastAPI(title="Sports Card Tracker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_public(path: str) -> bool:
    """Paths reachable without logging in (the login flow + its icon/manifest)."""
    if path == "/login" or path.startswith("/api/login") or path.startswith("/api/logout"):
        return True
    if path.startswith("/static/icon-") or path == "/static/manifest.json":
        return True
    return False


@app.middleware("http")
async def require_login(request: Request, call_next):
    expected = get_password_hash()
    if not expected:  # no password set -> auth disabled
        return await call_next(request)
    path = request.url.path
    if _is_public(path) or request.cookies.get(COOKIE) == expected:
        return await call_next(request)
    if path.startswith("/api/") or path.startswith("/images/"):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return RedirectResponse(url="/login")

# Create tables and apply any forward-only column additions on import
ensure_schema()

app.include_router(cards.router)
app.include_router(dashboard.router)
app.include_router(checklists.router)
app.include_router(suggest.router)
app.include_router(settings_router.router)

# Serve uploaded card images
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# Serve the web UI
_STATIC_DIR = os.path.join(_PROJECT_ROOT, "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


@app.on_event("startup")
def startup():
    ensure_schema()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_HTML


@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    pw = (body.get("password") or "").strip()
    expected = get_password_hash()
    if expected and hash_password(pw) == expected:
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, expected, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")
        return resp
    return JSONResponse({"ok": False, "detail": "Wrong password"}, status_code=401)


@app.post("/api/logout")
def api_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


LOGIN_HTML = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>Card Tracker — Sign in</title>
<link rel="apple-touch-icon" href="/static/icon-180.png"/>
<link rel="icon" href="/static/icon-180.png"/>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:#0b0f17;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  .box{width:90%;max-width:340px;text-align:center;padding:24px}
  .logo{width:72px;height:72px;border-radius:16px;object-fit:contain}
  h1{font-size:20px;margin:14px 0 22px}
  input{width:100%;padding:14px;border-radius:12px;border:1px solid #233044;background:#111826;
    color:#e6edf3;font-size:16px;margin-bottom:12px}
  button{width:100%;padding:14px;border:none;border-radius:12px;background:#1f6feb;color:#fff;
    font-size:16px;font-weight:600;cursor:pointer}
  .err{color:#f87171;font-size:14px;min-height:18px;margin-top:12px}
</style></head><body>
<div class="box">
  <img class="logo" src="/static/icon-180.png" alt=""/>
  <h1>Card Tracker</h1>
  <form id="f">
    <input id="pw" type="password" placeholder="Password" autocomplete="current-password" autofocus/>
    <button type="submit">Sign in</button>
    <p class="err" id="err"></p>
  </form>
</div>
<script>
document.getElementById('f').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({password:document.getElementById('pw').value})});
  if(r.ok){ location.href='/'; }
  else { document.getElementById('err').textContent='Wrong password. Try again.'; }
});
</script></body></html>"""


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "vision_model": os.environ.get("CARD_VISION_MODEL", "claude-opus-4-8"),
    }
