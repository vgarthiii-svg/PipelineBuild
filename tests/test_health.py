"""
Health endpoints introduced by the stability pass.
"""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_errors_endpoint_returns_list(client):
    r = client.get("/api/health/errors")
    assert r.status_code == 200
    data = r.json()
    assert "errors" in data
    assert isinstance(data["errors"], list)


def test_backups_endpoint_returns_list(client):
    r = client.get("/api/health/backups")
    assert r.status_code == 200
    data = r.json()
    assert "backups" in data
    assert "retention_days" in data
