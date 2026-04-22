"""
Nightly SQLite backup with retention.

Uses sqlite3's `.backup()` API so the copy is a consistent snapshot even if
the DB is being written to. Retains the last 14 days, cleans up older files.
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "pipeline.db")
BACKUP_DIR = os.path.join(_PROJECT_ROOT, "data", "backups")
RETENTION_DAYS = 14

os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_now() -> str:
    """Run a single backup. Returns the path to the file created."""
    stamp = datetime.now().strftime("%Y%m%d")
    target = os.path.join(BACKUP_DIR, f"pipeline-{stamp}.db")

    # SQLite online backup API produces a consistent snapshot
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()

    log.info("Backup complete: %s (%.1f KB)", os.path.basename(target), os.path.getsize(target) / 1024)
    return target


def prune_old_backups(retention_days: int = RETENTION_DAYS) -> int:
    """Delete backups older than retention_days. Returns number deleted."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    for name in os.listdir(BACKUP_DIR):
        if not name.startswith("pipeline-") or not name.endswith(".db"):
            continue
        path = os.path.join(BACKUP_DIR, name)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if mtime < cutoff:
                os.remove(path)
                removed += 1
                log.info("Pruned old backup: %s", name)
        except OSError as e:
            log.warning("Could not prune %s: %s", name, e)
    return removed


def list_backups():
    """Return metadata for each existing backup, newest first."""
    out = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not name.startswith("pipeline-") or not name.endswith(".db"):
            continue
        path = os.path.join(BACKUP_DIR, name)
        try:
            stat = os.stat(path)
            out.append({
                "filename": name,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            continue
    return out


async def _backup_loop(interval_hours: int = 24):
    """Background task: sleeps, backs up, prunes, repeats."""
    # First backup 5 minutes after startup so we don't hammer cold boot
    await asyncio.sleep(300)
    while True:
        try:
            backup_now()
            prune_old_backups()
        except Exception as e:
            log.exception("Backup loop iteration failed: %s", e)
        await asyncio.sleep(interval_hours * 3600)


def start_scheduler(interval_hours: int = 24):
    """Kick off the background backup loop. Call from FastAPI startup."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_backup_loop(interval_hours))
        log.info("Backup scheduler started. Interval: %dh, retention: %dd.", interval_hours, RETENTION_DAYS)
    except Exception as e:
        log.exception("Failed to start backup scheduler: %s", e)
