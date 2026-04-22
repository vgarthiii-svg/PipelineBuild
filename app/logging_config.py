"""
Structured logging for the BD Pipeline Agent.

- Info and above → rotating file at data/logs/app.log (10 MB × 5 files)
- Errors additionally captured to data/logs/errors.log for the health dashboard
- Console handler (stdout) kept for uvicorn / LaunchAgent compatibility
- In-memory ring buffer of recent errors (last 100) queryable via /api/health/errors
"""

import json
import logging
import os
import sys
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

APP_LOG = os.path.join(LOG_DIR, "app.log")
ERROR_LOG = os.path.join(LOG_DIR, "errors.log")


class RingBufferHandler(logging.Handler):
    """Keep the most recent error records in memory for the health dashboard."""

    def __init__(self, capacity: int = 100):
        super().__init__(level=logging.ERROR)
        self.buffer: deque = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append({
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
            "exception": self.format_exception(record),
        })

    @staticmethod
    def format_exception(record: logging.LogRecord):
        if not record.exc_info:
            return None
        import traceback
        return "".join(traceback.format_exception(*record.exc_info))

    def snapshot(self):
        return list(self.buffer)


# Single module-level instance so routers can read from it
error_ring = RingBufferHandler(capacity=100)


class JsonFormatter(logging.Formatter):
    """Compact single-line JSON, greppable in Terminal."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            import traceback
            payload["exc"] = "".join(traceback.format_exception(*record.exc_info)).strip()
        return json.dumps(payload, default=str)


def configure_logging():
    """Install handlers on the root logger. Safe to call multiple times."""
    root = logging.getLogger()
    if getattr(root, "_bd_pipeline_configured", False):
        return

    root.setLevel(logging.INFO)

    # Console handler — human-readable
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-7s %(name)s :: %(message)s"))

    # Main rotating file — JSON
    app_file = RotatingFileHandler(APP_LOG, maxBytes=10 * 1024 * 1024, backupCount=5)
    app_file.setLevel(logging.INFO)
    app_file.setFormatter(JsonFormatter())

    # Error-only rotating file — JSON
    error_file = RotatingFileHandler(ERROR_LOG, maxBytes=5 * 1024 * 1024, backupCount=5)
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(JsonFormatter())

    root.addHandler(console)
    root.addHandler(app_file)
    root.addHandler(error_file)
    root.addHandler(error_ring)

    # SQLAlchemy is loud at DEBUG; keep it at WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # uvicorn access logs stay at INFO (its own handler wires in)

    root._bd_pipeline_configured = True

    logging.getLogger(__name__).info("Logging configured. app.log + errors.log active.")
