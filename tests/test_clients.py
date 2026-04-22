"""
Client CRUD + the cross-pipeline sync that bit us earlier.
"""


class TestClientCreation:
    def test_create_client(self, client):
        r = client.post("/api/clients/", json={"name": "New Co", "description": "desc"})
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "New Co"
        assert "id" in body

    def test_list_clients_includes_created(self, client):
        client.post("/api/clients/", json={"name": "X Corp"})
        r = client.get("/api/clients/")
        names = [c["name"] for c in r.json()]
        assert "X Corp" in names

    def test_new_client_appears_in_other_pipelines(self, client):
        # The big one: creating a client should auto-add it as a prospect in every
        # OTHER client's pipeline. Regression from earlier session.
        client.post("/api/clients/", json={"name": "Alpha"})
        client.post("/api/clients/", json={"name": "Beta"})

        # Beta's pipeline should contain Alpha now
        clients = client.get("/api/clients/").json()
        beta = next(c for c in clients if c["name"] == "Beta")
        pipeline = client.get(f"/api/pipeline/{beta['id']}").json()
        names_in_pipeline = [e["prospect_name"] for e in pipeline]
        assert "Alpha" in names_in_pipeline


class TestActiveToggle:
    def test_toggle_flips_flag(self, client):
        r = client.post("/api/clients/", json={"name": "Y Corp"})
        cid = r.json()["id"]
        # Start inactive by default (unless explicitly set)
        before = client.get(f"/api/clients/{cid}").json().get("active")

        client.put(f"/api/clients/{cid}/toggle-active")
        after = client.get(f"/api/clients/{cid}").json().get("active")

        assert bool(before) != bool(after)


class TestLensOptions:
    def test_lens_options_lists_prospects_and_clients(self, client):
        client.post("/api/clients/", json={"name": "Gamma"})
        r = client.get("/api/clients/lens-options")
        assert r.status_code == 200
        opts = r.json()
        names = [o["name"] for o in opts]
        assert "Gamma" in names
        # Any matching option should be flagged has_client_record
        gamma = next(o for o in opts if o["name"] == "Gamma")
        assert gamma["has_client_record"] is True


class TestClientDeletion:
    def test_delete_client_keeps_prospect(self, client):
        # Option B: deleting client keeps the company as a prospect
        r = client.post("/api/clients/", json={"name": "Delta"})
        cid = r.json()["id"]

        del_r = client.delete(f"/api/clients/{cid}")
        assert del_r.status_code == 200

        # Prospect should still exist
        prospects = client.get("/api/prospects/").json()
        names = [p["name"] for p in prospects]
        assert "Delta" in names

    def test_cascade_everywhere_removes_prospect_too(self, client):
        r = client.post("/api/clients/", json={"name": "Epsilon"})
        cid = r.json()["id"]

        del_r = client.delete(f"/api/clients/{cid}/cascade-everywhere")
        assert del_r.status_code == 200

        # Neither client nor prospect remains
        clients_r = client.get("/api/clients/").json()
        prospects_r = client.get("/api/prospects/").json()
        assert all(c["name"] != "Epsilon" for c in clients_r)
        assert all(p["name"] != "Epsilon" for p in prospects_r)
