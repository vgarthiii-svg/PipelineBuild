"""
Scoring presets: applying, clearing, and rescoring.
"""


class TestPresets:
    def test_list_presets(self, client):
        r = client.get("/api/clients/presets/list")
        assert r.status_code == 200
        presets = r.json()
        keys = [p["key"] for p in presets]
        assert "carrier_to_tech_vendor" in keys
        assert "carrier_to_carrier" in keys

    def test_apply_preset_activates_expected_count(self, client):
        # Create a lens
        r = client.post("/api/clients/", json={"name": "Preset Test Lens"})
        cid = r.json()["id"]

        # Apply preset
        ap = client.post(f"/api/clients/{cid}/presets/apply/carrier_to_tech_vendor")
        assert ap.status_code == 200
        assert ap.json()["activated"] == 6

        # Active criteria should match preset count
        crits = client.get(f"/api/clients/{cid}/criteria").json()
        active = [c for c in crits if c.get("active", True)]
        assert len(active) == 6

    def test_custom_preset_clears_all(self, client):
        r = client.post("/api/clients/", json={"name": "Clear Test"})
        cid = r.json()["id"]

        # First apply a preset
        client.post(f"/api/clients/{cid}/presets/apply/carrier_to_tech_vendor")
        # Then clear
        cl = client.post(f"/api/clients/{cid}/presets/apply/custom")
        assert cl.status_code == 200

        # No active criteria
        crits = client.get(f"/api/clients/{cid}/criteria").json()
        active = [c for c in crits if c.get("active", True)]
        assert len(active) == 0

    def test_unknown_preset_returns_404(self, client):
        r = client.post("/api/clients/", json={"name": "Bad Preset Test"})
        cid = r.json()["id"]
        bad = client.post(f"/api/clients/{cid}/presets/apply/nonexistent_preset")
        assert bad.status_code == 404
