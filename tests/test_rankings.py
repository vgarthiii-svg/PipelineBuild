"""
PPR Draft Board: import, list/filter, meta, and player profile endpoints.
"""
from app.services.rankings_import import DEFAULT_SOURCE, EXPERT_SOURCE


class TestRankings:
    def _import(self, client):
        r = client.post("/api/rankings/import")
        assert r.status_code == 200
        return r.json()

    def test_import_loads_players(self, client):
        res = self._import(client)
        assert res["source"] == DEFAULT_SOURCE
        assert res["total"] > 300
        assert res["imported"] == res["total"]

    def test_import_is_idempotent_upsert(self, client):
        first = self._import(client)
        second = self._import(client)
        # Second run updates, does not duplicate.
        assert second["total"] == first["total"]
        assert second["imported"] == 0
        assert second["updated"] == first["total"]

    def test_list_ranked_and_position_rank(self, client):
        self._import(client)
        rows = client.get("/api/rankings?limit=5").json()
        assert rows[0]["rank"] == 1
        # Overall list is sorted ascending by rank
        assert [r["rank"] for r in rows] == sorted(r["rank"] for r in rows)
        # Every row carries a within-position rank
        assert all(r["position_rank"] is not None for r in rows)

    def test_position_filter(self, client):
        self._import(client)
        rbs = client.get("/api/rankings?position=RB").json()
        assert len(rbs) > 0
        assert all(r["position"] == "RB" for r in rbs)
        # position_rank is 1..N within RB, starting at 1
        assert rbs[0]["position_rank"] == 1

    def test_tier_and_search_filters(self, client):
        self._import(client)
        tier_s = client.get("/api/rankings?tier=S").json()
        assert all(r["tier"] == "S" for r in tier_s)
        found = client.get("/api/rankings?q=chase").json()
        assert any("Chase" in r["name"] for r in found)

    def test_meta_shape(self, client):
        self._import(client)
        meta = client.get("/api/rankings/meta").json()
        assert meta["total"] > 300
        assert "RB" in meta["positions"] and "WR" in meta["positions"]
        assert meta["position_counts"]["RB"] > 0
        assert "S" in meta["tiers"]

    def test_player_profile_and_value_delta(self, client):
        self._import(client)
        # Ja'Marr Chase, player_id 7564: rank 3, expert 3.0 -> value_delta 0.0
        p = client.get("/api/rankings/7564").json()
        assert p["name"] == "Ja'Marr Chase"
        assert p["position"] == "WR"
        assert p["rank"] == 3
        assert p["value_delta"] == 0.0

    def test_missing_player_404(self, client):
        self._import(client)
        assert client.get("/api/rankings/99999999").status_code == 404

    def test_sources_listed_with_counts(self, client):
        self._import(client)
        sources = client.get("/api/rankings/sources").json()
        assert len(sources) == 1
        assert sources[0]["source"] == DEFAULT_SOURCE
        assert sources[0]["count"] > 300

    def test_upload_csv_creates_named_source(self, client):
        csv = (
            "player_id,Rank,Name,Team,Position,Tier,Mason Dodd Rank,Expert Rank\n"
            "1,1,Test QB,KC,QB,S,1,1.5\n"
            "2,2,Test RB,SF,RB,A,-,3.0\n"
        )
        r = client.post(
            "/api/rankings/upload",
            files={"file": ("my_board.csv", csv, "text/csv")},
            data={"source": "My Board"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "My Board"
        assert body["total"] == 2
        rows = client.get("/api/rankings?source=My Board").json()
        assert {p["name"] for p in rows} == {"Test QB", "Test RB"}
        # '-' Mason Dodd rank parses to null, not a crash
        rb = next(p for p in rows if p["name"] == "Test RB")
        assert rb["mason_dodd_rank"] is None

    def test_upload_defaults_source_to_filename(self, client):
        csv = "player_id,Rank,Name,Position\n5,1,Solo Guy,WR\n"
        r = client.post(
            "/api/rankings/upload",
            files={"file": ("week1_ranks.csv", csv, "text/csv")},
        )
        assert r.status_code == 200
        assert r.json()["source"] == "week1_ranks"

    def test_upload_rejects_csv_without_name_column(self, client):
        csv = "player_id,Rank,Position\n1,1,QB\n"
        r = client.post(
            "/api/rankings/upload",
            files={"file": ("bad.csv", csv, "text/csv")},
            data={"source": "Bad"},
        )
        assert r.status_code == 400

    def test_delete_source_removes_only_that_source(self, client):
        self._import(client)  # default source
        client.post("/api/rankings/import?source=Doomed").json()
        # Delete the extra source
        d = client.delete("/api/rankings/sources/Doomed")
        assert d.status_code == 200
        assert d.json()["source"] == "Doomed"
        assert d.json()["deleted"] > 0
        # It's gone; the default source is untouched
        sources = {s["source"] for s in client.get("/api/rankings/sources").json()}
        assert "Doomed" not in sources
        assert DEFAULT_SOURCE in sources
        assert client.get("/api/rankings?source=Doomed").json() == []

    def test_delete_missing_source_404(self, client):
        self._import(client)
        assert client.delete("/api/rankings/sources/Nope").status_code == 404

    def test_rename_source(self, client):
        base = self._import(client)
        r = client.put(
            f"/api/rankings/sources/{DEFAULT_SOURCE}",
            params={"new_name": "My Custom Board"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["old_source"] == DEFAULT_SOURCE
        assert body["new_source"] == "My Custom Board"
        assert body["count"] == base["total"]
        # Old name gone, new name carries all the players
        sources = {s["source"]: s["count"] for s in client.get("/api/rankings/sources").json()}
        assert DEFAULT_SOURCE not in sources
        assert sources["My Custom Board"] == base["total"]

    def test_rename_missing_source_404(self, client):
        self._import(client)
        r = client.put("/api/rankings/sources/Nope", params={"new_name": "X"})
        assert r.status_code == 404

    def test_rename_empty_name_400(self, client):
        self._import(client)
        r = client.put(f"/api/rankings/sources/{DEFAULT_SOURCE}", params={"new_name": "  "})
        assert r.status_code == 400

    def test_pull_by_short_handle(self, client):
        # Bundled source is "Mason Dodd PPR Redraft 2026"; pull it by "Mason Dodd PPR".
        base = self._import(client)
        rows = client.get("/api/rankings", params={"source": "Mason Dodd PPR"}).json()
        assert len(rows) == base["total"]
        assert all(p["source"] == base["source"] for p in rows)

    def test_short_handle_is_case_insensitive(self, client):
        base = self._import(client)
        rows = client.get("/api/rankings", params={"source": "mason dodd ppr"}).json()
        assert len(rows) == base["total"]
        meta = client.get("/api/rankings/meta", params={"source": "mason dodd"}).json()
        assert meta["source"] == base["source"]
        assert meta["total"] == base["total"]

    def test_player_profile_via_short_handle(self, client):
        self._import(client)
        p = client.get("/api/rankings/7564", params={"source": "Mason Dodd PPR"}).json()
        assert p["name"] == "Ja'Marr Chase"

    def test_ambiguous_handle_returns_empty(self, client):
        # Two sources sharing the "Mason Dodd PPR" prefix -> handle is ambiguous.
        self._import(client)  # Mason Dodd PPR Redraft 2026
        client.post("/api/rankings/import", params={"source": "Mason Dodd PPR Dynasty"})
        rows = client.get("/api/rankings", params={"source": "Mason Dodd PPR"}).json()
        assert rows == []  # ambiguous -> no silent pick

    def test_derive_expert_source(self, client):
        base = self._import(client)
        r = client.post("/api/rankings/derive-expert")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == EXPERT_SOURCE
        assert body["total"] == base["total"]

        # It's a distinct, selectable source alongside the base.
        sources = {s["source"] for s in client.get("/api/rankings/sources").json()}
        assert EXPERT_SOURCE in sources and DEFAULT_SOURCE in sources

        rows = client.get("/api/rankings", params={"source": EXPERT_SOURCE, "limit": 1000}).json()
        # Ranked by expert_rank ascending, with a fresh 1..N overall rank.
        assert [p["rank"] for p in rows] == list(range(1, len(rows) + 1))
        experts = [p["expert_rank"] for p in rows]
        assert experts == sorted(experts)
        # #1 by expert consensus is the lowest expert_rank (Jahmyr Gibbs, 1.13).
        assert rows[0]["name"] == "Jahmyr Gibbs"

    def test_pull_expert_by_short_handle(self, client):
        self._import(client)
        client.post("/api/rankings/derive-expert")
        rows = client.get("/api/rankings", params={"source": "Expert"}).json()
        assert len(rows) > 300
        assert all(p["source"] == EXPERT_SOURCE for p in rows)

    def test_derive_expert_is_idempotent(self, client):
        self._import(client)
        first = client.post("/api/rankings/derive-expert").json()
        second = client.post("/api/rankings/derive-expert").json()
        assert first["total"] == second["total"]
        # Rebuilt in place — not duplicated.
        rows = client.get("/api/rankings", params={"source": EXPERT_SOURCE, "limit": 1000}).json()
        assert len(rows) == second["total"]

    def test_legacy_source_name_migrates(self, test_db):
        # Simulate an existing DB seeded under the old "REDRAFT PPR" label.
        from app.models import PlayerRanking
        from app.services.rankings_import import migrate_legacy_source_names
        db = test_db()
        try:
            db.add(PlayerRanking(source="REDRAFT PPR", player_id=1, rank=1, name="Old Guy", position="RB"))
            db.commit()
            migrate_legacy_source_names(db)
            assert db.query(PlayerRanking).filter(PlayerRanking.source == "REDRAFT PPR").count() == 0
            assert db.query(PlayerRanking).filter(PlayerRanking.source == DEFAULT_SOURCE).count() == 1
        finally:
            db.close()

    def test_rename_collision_409(self, client):
        self._import(client)
        client.post("/api/rankings/import?source=Other").json()
        r = client.put(f"/api/rankings/sources/{DEFAULT_SOURCE}", params={"new_name": "Other"})
        assert r.status_code == 409

    def test_multiple_sources_are_isolated(self, client):
        # Default source
        base = self._import(client)
        # A second source imported from the same bundled file under a new name
        custom = client.post("/api/rankings/import?source=Custom Board").json()
        assert custom["source"] == "Custom Board"

        sources = {s["source"]: s["count"] for s in client.get("/api/rankings/sources").json()}
        assert DEFAULT_SOURCE in sources and "Custom Board" in sources

        # Listing/meta are scoped per source and don't bleed across sources
        only_custom = client.get("/api/rankings?source=Custom Board&limit=1000").json()
        assert all(p["source"] == "Custom Board" for p in only_custom)
        assert len(only_custom) == base["total"]

        meta_custom = client.get("/api/rankings/meta?source=Custom Board").json()
        assert meta_custom["source"] == "Custom Board"
        assert meta_custom["total"] == base["total"]
