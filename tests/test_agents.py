"""
Agent Layer: job registry, run-now, toggle, schedule parsing.
"""

from datetime import datetime, timedelta

from app.services.scheduler import _next_run, JOB_REGISTRY


class TestScheduleParsing:
    def test_daily_same_day_future(self):
        now = datetime(2026, 4, 22, 10, 0)
        nxt = _next_run("daily@15:00", now)
        assert nxt == datetime(2026, 4, 22, 15, 0)

    def test_daily_same_day_past_rolls_forward(self):
        now = datetime(2026, 4, 22, 20, 0)
        nxt = _next_run("daily@03:00", now)
        assert nxt == datetime(2026, 4, 23, 3, 0)

    def test_weekly_monday(self):
        # Wed 2026-04-22 → next Monday is 2026-04-27
        now = datetime(2026, 4, 22, 10, 0)
        nxt = _next_run("weekly@mon@04:00", now)
        assert nxt == datetime(2026, 4, 27, 4, 0)

    def test_hourly(self):
        now = datetime(2026, 4, 22, 10, 30)
        nxt = _next_run("hourly", now)
        assert nxt == datetime(2026, 4, 22, 11, 0)

    def test_interval(self):
        now = datetime(2026, 4, 22, 10, 0)
        nxt = _next_run("interval@30m", now)
        assert nxt == datetime(2026, 4, 22, 10, 30)


class TestJobRegistry:
    def test_three_builtin_jobs_registered(self):
        assert "nightly_rescore" in JOB_REGISTRY
        assert "weekly_behavior_refresh" in JOB_REGISTRY
        assert "daily_pipeline_snapshot" in JOB_REGISTRY

    def test_each_job_has_required_keys(self):
        for key, spec in JOB_REGISTRY.items():
            assert "name" in spec, f"{key} missing name"
            assert "description" in spec, f"{key} missing description"
            assert "schedule" in spec, f"{key} missing schedule"
            assert callable(spec["function"]), f"{key} function not callable"


def _seed_jobs_into_test_db(test_db):
    """Seed JOB_REGISTRY rows into the test DB (not the real one SessionLocal points at)."""
    from app.models import ScheduledJob
    from app.services.scheduler import _next_run, JOB_REGISTRY
    db = test_db()
    try:
        for key, spec in JOB_REGISTRY.items():
            if not db.query(ScheduledJob).filter(ScheduledJob.job_key == key).first():
                db.add(ScheduledJob(
                    job_key=key,
                    name=spec["name"],
                    description=spec["description"],
                    schedule=spec["schedule"],
                    enabled=True,
                    next_run=_next_run(spec["schedule"]),
                ))
        db.commit()
    finally:
        db.close()


class TestAgentEndpoints:
    def test_list_agents(self, client, test_db):
        _seed_jobs_into_test_db(test_db)
        r = client.get("/api/agents/")
        assert r.status_code == 200
        jobs = r.json()
        keys = [j["job_key"] for j in jobs]
        assert "nightly_rescore" in keys

    def test_toggle_agent(self, client, test_db):
        _seed_jobs_into_test_db(test_db)

        before = client.get("/api/agents/").json()
        rescore = next(j for j in before if j["job_key"] == "nightly_rescore")
        was_enabled = rescore["enabled"]

        r = client.post("/api/agents/nightly_rescore/toggle")
        assert r.status_code == 200
        assert r.json()["enabled"] != was_enabled
