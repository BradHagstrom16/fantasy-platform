"""The First Season: 2025 archive ledger locks.

Spec: docs/superpowers/specs/2026-07-30-cfb-2025-history-ledger-design.md
Three layers land across the feature tasks: (1) snapshot integrity -- the
committed games/cfb/data/season_2025.json is the tested artifact (the
exporter script is deliberately untested in CI: it needs ~/CF_Survivor);
(2) the public read-only route; (3) design locks in the established
CSS-scan idioms (anchored regex over style.css + template source).

Verified against picks.db 2026-07-30: 26 players, one champion (Fourth &
Pine, both lives intact), 25 eliminated each via exactly two graded losses,
alive-entering series 26,26,24,20,18,14,14,12,10,9,8,8,7,4,4,4.

ASCII-only per the CFB phase rule; non-ASCII glyphs referenced via escapes.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "games" / "cfb" / "data" / "season_2025.json"

EXPECTED_ALIVE_ENTERING = [26, 26, 24, 20, 18, 14, 14, 12, 10, 9, 8, 8, 7, 4, 4, 4]


@pytest.fixture(scope="module")
def snapshot():
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


class TestSnapshotIntegrity:
    def test_top_level_shape(self, snapshot):
        assert set(snapshot) == {"season", "champion", "standings", "attrition"}
        assert snapshot["season"] == {
            "year": 2025, "entrants": 26, "weeks": 16,
            "start_date": "2025-08-28", "end_date": "2025-12-19",
        }

    def test_exactly_26_players(self, snapshot):
        assert len(snapshot["standings"]) == 26

    def test_exactly_one_champion_with_both_lives(self, snapshot):
        champions = [r for r in snapshot["standings"] if r["outcome"] == "champion"]
        assert len(champions) == 1
        champ = champions[0]
        assert champ["final_lives"] == 2
        assert champ["out_week"] is None
        assert champ["name"] == snapshot["champion"]["name"] == "Fourth & Pine"
        assert snapshot["champion"]["final_lives"] == 2

    def test_25_eliminated_each_with_out_week(self, snapshot):
        eliminated = [r for r in snapshot["standings"] if r["outcome"] == "eliminated"]
        assert len(eliminated) == 25
        for row in eliminated:
            assert row["out_week"] in range(1, 17)
            assert row["final_lives"] == 0

    def test_attrition_series_matches_verified_field(self, snapshot):
        attrition = snapshot["attrition"]
        assert [row["week"] for row in attrition] == list(range(1, 17))
        assert [row["alive_entering"] for row in attrition] == EXPECTED_ALIVE_ENTERING
        assert sum(row["cut"] for row in attrition) == 25

    def test_attrition_internally_consistent(self, snapshot):
        attrition = snapshot["attrition"]
        # strict=False is deliberate: the offset slice is one shorter.
        for prev, nxt in zip(attrition, attrition[1:], strict=False):
            assert nxt["alive_entering"] == prev["alive_entering"] - prev["cut"]

    def test_round_names(self, snapshot):
        by_week = {row["week"]: row["round_name"] for row in snapshot["attrition"]}
        assert by_week[15] == "Conference Championship Week"
        assert by_week[16] == "CFP Round 1"
        assert all(by_week[wk] is None for wk in range(1, 15))

    def test_standings_presorted(self, snapshot):
        rows = snapshot["standings"]
        assert rows[0]["outcome"] == "champion"
        keys = [
            (-r["out_week"], r["cumulative_spread"], r["name"].lower())
            for r in rows[1:]
        ]
        assert keys == sorted(keys)

    def test_no_forbidden_keys(self, snapshot):
        raw = SNAPSHOT_PATH.read_text(encoding="utf-8").lower()
        for forbidden in (
            "email", "password", "user_id", '"id"', "has_paid",
            "is_admin", "username", "pick",
        ):
            assert forbidden not in raw, forbidden
