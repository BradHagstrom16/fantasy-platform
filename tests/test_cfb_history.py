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
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "games" / "cfb" / "data" / "season_2025.json"
CSS_PATH = ROOT / "static" / "css" / "style.css"
TPL_PATH = ROOT / "games" / "cfb" / "templates" / "cfb" / "history.html"

EXPECTED_ALIVE_ENTERING = [26, 26, 24, 20, 18, 14, 14, 12, 10, 9, 8, 8, 7, 4, 4, 4]

EM_DASH = chr(0x2014)              # em dash (chr() keeps the source ASCII-clean)
CEREMONIAL_GLYPH = chr(0x25C8)     # black diamond containing small diamond
INFORMATIONAL_GLYPH = chr(0x25C7)  # white diamond


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


class TestLoader:
    def test_returns_snapshot_keys(self):
        from games.cfb.services.history import get_season_2025
        data = get_season_2025()
        assert set(data) == {"season", "champion", "standings", "attrition"}

    def test_cached_per_process(self):
        from games.cfb.services.history import get_season_2025
        assert get_season_2025() is get_season_2025()


@pytest.fixture(scope="module")
def client():
    from app import create_app
    app = create_app("testing")
    with app.app_context():
        from extensions import db
        db.create_all()
        with app.test_client() as c:
            yield c


class TestRoute:
    def test_public_200_with_season_content(self, client):
        resp = client.get("/cfb/history")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "The First Season" in html
        assert "Club Archive" in html
        assert "Fourth &amp; Pine" in html
        assert "CFP Round 1" in html
        assert "Season one was played at the old clubhouse." in html

    def test_autoescape_carries_special_names(self, client):
        html = client.get("/cfb/history").get_data(as_text=True)
        assert "P$" in html
        assert "Who you callin a convict" in html


class TestDesignLocks:
    @pytest.fixture(scope="class")
    def css(self):
        return CSS_PATH.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def tpl(self):
        return TPL_PATH.read_text(encoding="utf-8")

    def test_archive_block_lives_in_cfb_section(self, css):
        start = css.index("/* === CFB SURVIVOR POOL === */")
        end = css.index("/* === WORLD CUP FANTASY POOL === */")
        assert ".cfb-archive-champion {" in css[start:end]

    def test_archive_css_block_has_no_gold(self, css):
        m = re.search(
            r"/\* --- The First Season:.*?\.cfb-archive-provenance \{[^}]*\}",
            css,
            re.DOTALL,
        )
        assert m, "archive CSS block sentinel comment or terminal rule missing"
        assert "gold" not in m.group(0).lower()

    def test_champion_rule_is_survived_green_not_crimson(self, css):
        m = re.search(r"^\.cfb-archive-champion \{([^}]*)\}", css, re.MULTILINE)
        assert m
        body = m.group(1)
        assert "border-top: 2px solid var(--cfb-survived)" in body
        assert "crimson" not in body

    def test_template_carries_no_eyebrow_glyphs(self, tpl):
        assert CEREMONIAL_GLYPH not in tpl
        assert INFORMATIONAL_GLYPH not in tpl

    def test_template_copy_has_no_em_dash(self, tpl):
        assert EM_DASH not in tpl
        assert "&mdash;" not in tpl

    def test_template_is_pure_archive(self, tpl):
        low = tpl.lower()
        assert "<form" not in low
        assert "<button" not in low
        assert 'method="post"' not in low
        assert "cfb-pick-cta" not in low
        assert "championship-hero" not in low
