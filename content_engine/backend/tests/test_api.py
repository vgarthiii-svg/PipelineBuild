"""End-to-end API tests covering the full workflow against an in-memory DB."""
from __future__ import annotations

import os
import tempfile

import pytest

# Point the app at a throwaway SQLite file BEFORE importing app modules.
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["AI_PROVIDER"] = "mock"
os.environ["SINGLE_USER_MODE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# Context-manager form triggers the lifespan handler (table creation + seed).
client = TestClient(app)
client.__enter__()


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_meta_lists_content_types():
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()
    assert len(data["content_types"]) == 13
    assert len(data["score_categories"]) == 14


def test_full_workflow():
    # 1. Brand
    brand = client.post("/api/brands", json={"name": "Northstar", "brand_voice": "plain-spoken"})
    assert brand.status_code == 201
    brand_id = brand.json()["id"]

    # 2. Project
    proj = client.post("/api/projects", json={
        "brand_id": brand_id, "title": "Feature launch", "platform": "LinkedIn",
        "content_type": "linkedin", "objective": "announce analytics", "cta": "Book a demo",
    })
    assert proj.status_code == 201
    pid = proj.json()["id"]

    # 3. Research
    rb = client.post(f"/api/projects/{pid}/research")
    assert rb.status_code == 200
    assert rb.json()["keywords"]

    # 4. Generate draft
    d = client.post(f"/api/projects/{pid}/generate")
    assert d.status_code == 200
    draft = d.json()
    did = draft["id"]
    assert draft["body"]

    # 5. Score
    s = client.post(f"/api/drafts/{did}/score")
    assert s.status_code == 200
    assert 0 <= s.json()["overall"] <= 100
    assert len(s.json()["categories"]) == 14

    # 6. Revise
    rev = client.post(f"/api/drafts/{did}/revise", json={"action": "shorten"})
    assert rev.status_code == 200

    # 7. Repurpose
    rp = client.post(f"/api/drafts/{did}/repurpose", json={"targets": ["Email newsletter"]})
    assert rp.status_code == 200
    assert rp.json()["outputs"]

    # 8. Export
    ex = client.get(f"/api/drafts/{did}/export/markdown")
    assert ex.status_code == 200
    assert "#" in ex.text

    # 9. Library
    lib = client.get("/api/library")
    assert lib.status_code == 200
    assert lib.json()["count"] >= 1

    # 10. Finalize
    fin = client.post(f"/api/drafts/{did}/finalize")
    assert fin.status_code == 200
    assert fin.json()["is_final"] is True


def test_ap_check_endpoint():
    r = client.post("/api/settings/ap-check", json={"text": "This is a revolutionary game-changer!"})
    assert r.status_code == 200
    assert r.json()["ap_score"] < 100


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
