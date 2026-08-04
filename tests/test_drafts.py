"""
Draft Tracker: /api/intros/drafts aggregates intro packages across pipelines.
"""


def _make_entry_with_draft(client, client_name="DraftHost", company="DraftTarget"):
    cid = client.post("/api/clients/", json={"name": client_name}).json()["id"]
    client.post(f"/api/pipeline/quick-add?client_id={cid}&company_name={company}")
    entry = client.get(f"/api/pipeline/{cid}").json()[0]
    # No ANTHROPIC_API_KEY in tests -> fallback template, package created immediately.
    gen = client.post(f"/api/intros/generate/{entry['id']}")
    assert gen.status_code == 200
    return cid, entry


class TestDraftTracker:
    def test_empty_when_no_intros(self, client):
        r = client.get("/api/intros/drafts")
        assert r.status_code == 200
        body = r.json()
        assert body["summary"] == {"total": 0, "draft": 0, "approved": 0, "sent": 0}
        assert body["items"] == []

    def test_generated_intro_appears_as_draft(self, client):
        cid, entry = _make_entry_with_draft(client)
        body = client.get("/api/intros/drafts").json()
        assert body["summary"]["total"] == 1
        assert body["summary"]["draft"] == 1
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["status"] == "draft"
        assert item["prospect_name"] == "DraftTarget"
        assert item["client_name"] == "DraftHost"
        assert item["pipeline_entry_id"] == entry["id"]

    def test_status_filter(self, client):
        _make_entry_with_draft(client)
        # No 'sent' packages yet
        sent = client.get("/api/intros/drafts?status=sent").json()
        assert sent["items"] == []
        # Summary still reflects the draft regardless of the status filter
        assert sent["summary"]["draft"] == 1
        drafts = client.get("/api/intros/drafts?status=draft").json()
        assert len(drafts["items"]) == 1

    def test_client_filter_scopes_results(self, client):
        cid_a, _ = _make_entry_with_draft(client, client_name="ClientA", company="TargetA")
        cid_b, _ = _make_entry_with_draft(client, client_name="ClientB", company="TargetB")
        only_a = client.get(f"/api/intros/drafts?client_id={cid_a}").json()
        assert only_a["summary"]["total"] == 1
        assert only_a["items"][0]["client_name"] == "ClientA"

    def test_latest_package_per_entry_only(self, client):
        cid, entry = _make_entry_with_draft(client)
        # Regenerate: a second package for the same entry
        client.post(f"/api/intros/generate/{entry['id']}")
        body = client.get("/api/intros/drafts").json()
        # Still one tracker row for the entry (latest kept)
        rows_for_entry = [i for i in body["items"] if i["pipeline_entry_id"] == entry["id"]]
        assert len(rows_for_entry) == 1

    def test_marking_sent_moves_status(self, client):
        cid, entry = _make_entry_with_draft(client)
        pkg = client.get(f"/api/intros/{entry['id']}").json()
        client.put(f"/api/intros/{pkg['id']}", json={"status": "sent"})
        body = client.get("/api/intros/drafts").json()
        assert body["summary"]["sent"] == 1
        assert body["summary"]["draft"] == 0
        assert body["items"][0]["status"] == "sent"
