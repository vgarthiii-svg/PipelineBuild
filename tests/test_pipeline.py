"""
Pipeline operations: quick-add, remove, score-all.
"""


class TestPipeline:
    def test_quick_add_creates_prospect_and_entry(self, client):
        r = client.post("/api/clients/", json={"name": "Host"})
        cid = r.json()["id"]

        qa = client.post(f"/api/pipeline/quick-add?client_id={cid}&company_name=TargetCo")
        assert qa.status_code == 200

        entries = client.get(f"/api/pipeline/{cid}").json()
        names = [e["prospect_name"] for e in entries]
        assert "TargetCo" in names

    def test_score_all_produces_matchmaker_score(self, client):
        # Create lens with preset so criteria exist
        r = client.post("/api/clients/", json={"name": "ScoreHost"})
        cid = r.json()["id"]
        client.post(f"/api/clients/{cid}/presets/apply/carrier_to_tech_vendor")

        # Add a prospect
        client.post(f"/api/pipeline/quick-add?client_id={cid}&company_name=ScoreTarget")

        # Score
        sa = client.post(f"/api/pipeline/{cid}/score-all")
        assert sa.status_code == 200
        scored = sa.json()
        # Every entry should have a matchmaker score after scoring
        for e in scored:
            assert e.get("matchmaker_score") is not None
            assert e.get("tier") in ("hot", "warm", "monitor", "pass", "filtered")

    def test_remove_entry_only_affects_this_client(self, client):
        # Create two clients, add a prospect to both pipelines
        r1 = client.post("/api/clients/", json={"name": "Host1"})
        r2 = client.post("/api/clients/", json={"name": "Host2"})
        c1 = r1.json()["id"]
        c2 = r2.json()["id"]

        client.post(f"/api/pipeline/quick-add?client_id={c1}&company_name=Shared")

        # Shared should appear in both c1 and c2 pipelines (quick-add adds to all)
        p1 = client.get(f"/api/pipeline/{c1}").json()
        p2 = client.get(f"/api/pipeline/{c2}").json()
        entry_in_c1 = next(e for e in p1 if e["prospect_name"] == "Shared")
        assert any(e["prospect_name"] == "Shared" for e in p2)

        # Remove from c1's pipeline only
        client.delete(f"/api/pipeline/{entry_in_c1['id']}")

        # Gone from c1, still in c2
        p1_after = client.get(f"/api/pipeline/{c1}").json()
        p2_after = client.get(f"/api/pipeline/{c2}").json()
        assert all(e["prospect_name"] != "Shared" for e in p1_after)
        assert any(e["prospect_name"] == "Shared" for e in p2_after)


class TestBreakdown:
    def test_breakdown_endpoint_shape(self, client):
        r = client.post("/api/clients/", json={"name": "BreakdownHost"})
        cid = r.json()["id"]
        client.post(f"/api/clients/{cid}/presets/apply/carrier_to_tech_vendor")
        client.post(f"/api/pipeline/quick-add?client_id={cid}&company_name=BTarget")
        client.post(f"/api/pipeline/{cid}/score-all")

        entries = client.get(f"/api/pipeline/{cid}").json()
        target = next(e for e in entries if e["prospect_name"] == "BTarget")

        b = client.get(f"/api/pipeline/{target['id']}/breakdown")
        assert b.status_code == 200
        data = b.json()
        # Shape assertions — these are what the UI relies on
        assert "pmf" in data
        assert "criteria" in data["pmf"]
        assert "rs" in data
        assert "friction" in data
        assert "intent" in data
        assert "formula" in data
