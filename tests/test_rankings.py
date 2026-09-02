"""
PPR Draft Board: import, list/filter, meta, and player profile endpoints.
"""


class TestRankings:
    def _import(self, client):
        r = client.post("/api/rankings/import")
        assert r.status_code == 200
        return r.json()

    def test_import_loads_players(self, client):
        res = self._import(client)
        assert res["source"] == "REDRAFT PPR"
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
        assert sources[0]["source"] == "REDRAFT PPR"
        assert sources[0]["count"] > 300

    def test_multiple_sources_are_isolated(self, client):
        # Default source
        base = self._import(client)
        # A second source imported from the same bundled file under a new name
        custom = client.post("/api/rankings/import?source=Custom Board").json()
        assert custom["source"] == "Custom Board"

        sources = {s["source"]: s["count"] for s in client.get("/api/rankings/sources").json()}
        assert "REDRAFT PPR" in sources and "Custom Board" in sources

        # Listing/meta are scoped per source and don't bleed across sources
        only_custom = client.get("/api/rankings?source=Custom Board&limit=1000").json()
        assert all(p["source"] == "Custom Board" for p in only_custom)
        assert len(only_custom) == base["total"]

        meta_custom = client.get("/api/rankings/meta?source=Custom Board").json()
        assert meta_custom["source"] == "Custom Board"
        assert meta_custom["total"] == base["total"]
