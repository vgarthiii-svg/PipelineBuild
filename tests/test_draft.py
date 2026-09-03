"""
Live Draft tracker: snake math, start/pick/undo, best-available, me/Jake picks.
"""
from app.services.draft_engine import pick_coords, team_upcoming_picks
from app.services.espn_draft import normalize_name


class TestSnakeMath:
    def test_pick_coords_12_team_snake(self):
        # Round 1 straight, round 2 reversed.
        assert pick_coords(1, 12, True)[2] == 1
        assert pick_coords(2, 12, True)[2] == 2
        assert pick_coords(12, 12, True)[2] == 12
        assert pick_coords(13, 12, True)[2] == 12   # round 2 reverses
        assert pick_coords(24, 12, True)[2] == 1

    def test_owner_pick_slots(self):
        # You at slot 2 → overall 2, 23, 26; Jake at slot 5 → 5, 20, 29.
        assert team_upcoming_picks(2, 1, 12, 16, True, limit=3) == [2, 23, 26]
        assert team_upcoming_picks(5, 1, 12, 16, True, limit=3) == [5, 20, 29]

    def test_linear_draft(self):
        # Same order every round.
        assert pick_coords(13, 12, False)[2] == 1
        assert team_upcoming_picks(2, 1, 12, 16, False, limit=2) == [2, 14]


class TestDraftFlow:
    def _start(self, client, **kw):
        client.post("/api/rankings/import")  # seed the source
        body = {"num_teams": 12, "my_slot": 2, "jake_slot": 5, "snake": True}
        body.update(kw)
        r = client.post("/api/draft/start", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def test_start_sets_clock_and_owners(self, client):
        st = self._start(client)
        assert st["current_pick"] == 1
        assert st["on_the_clock"]["team_slot"] == 1
        assert st["me"]["slot"] == 2 and st["me"]["next_overall"] == 2 and st["me"]["picks_until"] == 1
        assert st["jake"]["slot"] == 5 and st["jake"]["next_overall"] == 5 and st["jake"]["picks_until"] == 4

    def test_pick_advances_and_removes_from_board(self, client):
        self._start(client)
        # Draft the #1 overall player by name.
        avail = client.get("/api/draft/best-available?limit=1").json()["players"]
        top = avail[0]
        st = client.post("/api/draft/pick", json={"player_id": top["player_id"]}).json()
        assert st["current_pick"] == 2
        assert st["drafted_count"] == 1
        assert st["picks"][0]["player_name"] == top["name"]
        # Gone from best-available now.
        names = [p["name"] for p in client.get("/api/draft/best-available?limit=5").json()["players"]]
        assert top["name"] not in names

    def test_pick_by_name(self, client):
        self._start(client)
        st = client.post("/api/draft/pick", json={"player_name": "Ja'Marr Chase"}).json()
        assert st["picks"][0]["player_name"] == "Ja'Marr Chase"
        assert st["picks"][0]["team_slot"] == 1

    def test_duplicate_pick_rejected(self, client):
        self._start(client)
        client.post("/api/draft/pick", json={"player_name": "Bijan Robinson"})
        dup = client.post("/api/draft/pick", json={"player_name": "bijan robinson"})
        assert dup.status_code == 409

    def test_undo_restores_clock_and_board(self, client):
        self._start(client)
        top = client.get("/api/draft/best-available?limit=1").json()["players"][0]
        client.post("/api/draft/pick", json={"player_id": top["player_id"]})
        st = client.post("/api/draft/undo").json()
        assert st["current_pick"] == 1
        assert st["drafted_count"] == 0
        names = [p["name"] for p in client.get("/api/draft/best-available?limit=1").json()["players"]]
        assert names[0] == top["name"]

    def test_position_filter_on_board(self, client):
        self._start(client)
        qbs = client.get("/api/draft/best-available?position=QB&limit=5").json()["players"]
        assert all(p["position"] == "QB" for p in qbs)

    def test_current_reflects_no_active(self, client):
        r = client.get("/api/draft/current").json()
        assert r["active"] is False

    def test_rosters_track_picks(self, client):
        self._start(client)
        # Pick 1 -> slot 1, pick 2 -> slot 2 (you).
        client.post("/api/draft/pick", json={"player_name": "Ja'Marr Chase"})
        st = client.post("/api/draft/pick", json={"player_name": "Bijan Robinson"}).json()
        # Slot 2 (you) should now own Bijan.
        assert any(pl["player_name"] == "Bijan Robinson" for pl in st["rosters"]["2"])


def test_normalize_name_matches_variants():
    assert normalize_name("Ja'Marr Chase") == normalize_name("jamarr chase")
    assert normalize_name("Kenneth Walker III") == normalize_name("Kenneth Walker")
