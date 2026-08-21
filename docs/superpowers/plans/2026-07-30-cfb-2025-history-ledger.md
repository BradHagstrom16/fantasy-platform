# CFB 2025 History Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship "The First Season" — a public, read-only 2025 archive page at `/cfb/history` in the CFB midnight room, fed by a committed JSON snapshot exported once from the legacy `~/CF_Survivor/instance/picks.db`.

**Architecture:** A one-off stdlib exporter writes `games/cfb/data/season_2025.json` (standings, champion, attrition — no pick-level rows, no identities beyond display names). A `functools.lru_cache` loader feeds one new public route and template. No models, no migration, no admin surface, no prod import step. Spec: `docs/superpowers/specs/2026-07-30-cfb-2025-history-ledger-design.md` (approved by Brad 2026-07-30 — its §1 rulings table is binding; do not re-ask).

**Tech Stack:** Flask blueprint route (`games/cfb/routes.py`), Jinja template, CFB midnight-room CSS tokens (`static/css/style.css`), stdlib `sqlite3` + `json`, pytest.

## Global Constraints

- The legacy repo `~/CF_Survivor` is **read-only** — the exporter opens the DB with sqlite URI `?mode=ro` and nothing ever writes there.
- Snapshot excludes: emails, user ids, passwords, `has_paid`, `is_admin`, `username` keys, pick-level rows, team data. Display name = `display_name or username`, exported under the key `name`.
- **No gold anywhere** in CFB CSS or templates (Crimson-Ceremony Rule). Champion accent is `--cfb-survived` green (outcome carries outcome; crimson stays identity).
- `.cfb-eyebrow` never carries a glyph (`◈` U+25C8 / `◇` U+25C7 banned in the template).
- **No em dashes (U+2014) or double hyphens in UI copy** (template text). En dash (U+2013 / `&ndash;`) is permitted.
- The page is pure archive: **no `<form>`, no `<button>`, no POST target, no pick CTA** anywhere in `history.html`.
- Test files: ASCII-only source (reference glyphs via `chr(...)` escapes), CSS-scan idioms = anchored regex over `style.css` + template source, module docstring explaining the locks.
- Pluralization correct everywhere: 1 life / 2 lives.
- Do not reuse `.championship-hero` (single-purpose, render-gated primitive).
- Do not touch `deploy/nginx.conf`, systemd units, or any WC surface.
- Run commands with the project venv: `ENVIRONMENT=testing venv/bin/python -m pytest ...`, `venv/bin/ruff check .`.
- Verified 2025 facts (assert these exactly): 26 players; champion **Fourth & Pine** (2 lives, 0 losses, spread 163.5); 25 eliminated, each with exactly 2 graded losses; second-loss week == last pick week for all; alive-entering series `26, 26, 24, 20, 18, 14, 14, 12, 10, 9, 8, 8, 7, 4, 4, 4`; week 15 round name "Conference Championship Week", week 16 "CFP Round 1" (weeks 1–14 have blank round names — exporter normalizes `''` → `null`); season dates 2025-08-28 → 2025-12-19.
- Where those facts are enforced (clarified post-merge, PR #132): the two pick-level ones — "exactly 2 graded losses" and "second-loss week == last pick week" — are **source-only**, because the snapshot deliberately carries no pick rows. `scripts/export_2025_history.py` checks them against the legacy DB and any warning aborts the write, so a violation cannot reach the artifact; `tests/test_cfb_history.py` locks only what the snapshot can represent.

---

## File Structure

- Create: `scripts/export_2025_history.py` — one-off exporter (stdlib only; committed for provenance; deliberately untested in CI because it needs `~/CF_Survivor`)
- Create: `games/cfb/data/season_2025.json` — the committed snapshot; **the tested artifact**
- Create: `games/cfb/services/history.py` — cached loader, one public function `get_season_2025()`
- Modify: `games/cfb/routes.py` — add public `history()` route after `weekly_results` (~line 430)
- Create: `games/cfb/templates/cfb/history.html` — the archive page
- Modify: `static/css/style.css` — insert `.cfb-archive-*` block after the `.cfb-ledger-total` rule (~line 5357), **before** the `/* World Cup overrides */` comment
- Modify: `templates/base.html` — add the `2025` pill as the **last** pill in the CFB sub-nav (after the auth-guarded My Picks block, ~line 196)
- Test: `tests/test_cfb_history.py` — all three lock layers in one file

---

### Task 1: Branch, snapshot integrity tests, exporter, committed snapshot

**Files:**
- Create: `tests/test_cfb_history.py` (snapshot layer only; later tasks append)
- Create: `scripts/export_2025_history.py`
- Create: `games/cfb/data/season_2025.json` (generated, then committed)

**Interfaces:**
- Produces: `games/cfb/data/season_2025.json` with top-level keys `season`, `champion`, `standings`, `attrition`:
  - `season`: `{"year": 2025, "entrants": 26, "weeks": 16, "start_date": "2025-08-28", "end_date": "2025-12-19"}`
  - `champion`: `{"name": str, "final_lives": int, "cumulative_spread": float}`
  - `standings`: list of `{"name": str, "outcome": "champion"|"eliminated", "out_week": int|null, "final_lives": int, "cumulative_spread": float}` — pre-sorted: champion first, then `out_week` descending, then `cumulative_spread` ascending, then lowercased name (routes/templates never sort)
  - `attrition`: list of `{"week": 1..16, "round_name": str|null, "alive_entering": int, "cut": int}` in week order

- [x] **Step 1: Create the branch**

```bash
git checkout -b feat/cfb-2025-history-ledger
```

- [x] **Step 2: Write the failing snapshot tests**

Create `tests/test_cfb_history.py`:

```python
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
        for prev, nxt in zip(attrition, attrition[1:]):
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
```

- [x] **Step 3: Run the tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py -q`
Expected: ERROR in the `snapshot` fixture — `FileNotFoundError` for `games/cfb/data/season_2025.json` (all tests error out; that is the fail state).

- [x] **Step 4: Write the exporter**

Create `scripts/export_2025_history.py` (create the `scripts/` directory; add nothing else to it):

```python
"""One-off exporter: legacy CF_Survivor picks.db -> games/cfb/data/season_2025.json.

Reads the legacy SQLite DB read-only (sqlite URI mode=ro), derives the 2025
season ledger (standings, champion, attrition), and writes a deterministic
JSON snapshot. Stdlib only; no Flask, no imports from the legacy repo; the
legacy repo is never modified. Run once, locally:

    python scripts/export_2025_history.py
    python scripts/export_2025_history.py --db /path/to/picks.db

Deterministic output (sorted keys, stable row ordering): re-running against
the same DB produces an identical file, so an accidental re-run is a no-op
diff. Deliberately untested in CI (needs ~/CF_Survivor); the committed
snapshot is the tested artifact (tests/test_cfb_history.py).

Derivations (verified against the DB 2026-07-30, zero anomalies):
- out_week = week of a player's SECOND incorrect pick (two lives). Fallback
  (never triggered on the real data): last recorded pick week, with a loud
  warning for eyeballing before commit.
- alive_entering(week 1) = entrants; alive_entering(w+1) = alive_entering(w)
  minus cuts in w. Cross-checked against picks-per-week, which traces the
  live field exactly on the real data.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "games" / "cfb" / "data" / "season_2025.json"
DEFAULT_DB = Path.home() / "CF_Survivor" / "instance" / "picks.db"
SEASON_YEAR = 2025
TOTAL_LIVES = 2


def connect_readonly(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def derive(conn):
    warnings = []
    weeks = conn.execute(
        "SELECT id, week_number, round_name, date(start_date) AS start_date"
        " FROM week ORDER BY week_number"
    ).fetchall()
    users = conn.execute(
        "SELECT id, username, display_name, lives_remaining, is_eliminated,"
        " cumulative_spread FROM user"
    ).fetchall()

    cuts_by_week = {w["week_number"]: 0 for w in weeks}
    standings = []
    for u in users:
        name = u["display_name"] or u["username"]
        loss_weeks = [
            row["week_number"]
            for row in conn.execute(
                "SELECT w.week_number FROM pick p"
                " JOIN week w ON w.id = p.week_id"
                " WHERE p.user_id = ? AND p.is_correct = 0"
                " ORDER BY w.week_number",
                (u["id"],),
            )
        ]
        if u["is_eliminated"]:
            if len(loss_weeks) >= TOTAL_LIVES:
                out_week = loss_weeks[TOTAL_LIVES - 1]
            else:
                out_week = conn.execute(
                    "SELECT MAX(w.week_number) AS wk FROM pick p"
                    " JOIN week w ON w.id = p.week_id WHERE p.user_id = ?",
                    (u["id"],),
                ).fetchone()["wk"]
                warnings.append(
                    f"{name}: eliminated with {len(loss_weeks)} graded losses;"
                    f" out_week fell back to last pick week {out_week}"
                )
            cuts_by_week[out_week] += 1
            standings.append({
                "name": name,
                "outcome": "eliminated",
                "out_week": out_week,
                "final_lives": 0,
                "cumulative_spread": u["cumulative_spread"],
            })
        else:
            standings.append({
                "name": name,
                "outcome": "champion",
                "out_week": None,
                "final_lives": u["lives_remaining"],
                "cumulative_spread": u["cumulative_spread"],
            })

    standings.sort(
        key=lambda r: (
            0 if r["outcome"] == "champion" else 1,
            -(r["out_week"] or 0),
            r["cumulative_spread"],
            r["name"].lower(),
        )
    )

    attrition = []
    alive = len(users)
    for w in weeks:
        cut = cuts_by_week[w["week_number"]]
        attrition.append({
            "week": w["week_number"],
            "round_name": w["round_name"] or None,
            "alive_entering": alive,
            "cut": cut,
        })
        alive -= cut

    # Cross-check: picks per week should trace the live field exactly.
    for row in attrition:
        picks = conn.execute(
            "SELECT COUNT(*) AS n FROM pick p JOIN week w ON w.id = p.week_id"
            " WHERE w.week_number = ?",
            (row["week"],),
        ).fetchone()["n"]
        if picks != row["alive_entering"]:
            warnings.append(
                f"week {row['week']}: {picks} picks but"
                f" {row['alive_entering']} derived alive entering"
            )

    champions = [r for r in standings if r["outcome"] == "champion"]
    if len(champions) != 1:
        sys.exit(f"FATAL: expected exactly 1 champion, found {len(champions)}")
    if sum(cuts_by_week.values()) != len(users) - 1:
        sys.exit("FATAL: cuts do not sum to entrants - 1")

    champ = champions[0]
    data = {
        "season": {
            "year": SEASON_YEAR,
            "entrants": len(users),
            "weeks": len(weeks),
            "start_date": weeks[0]["start_date"],
            "end_date": weeks[-1]["start_date"],
        },
        "champion": {
            "name": champ["name"],
            "final_lives": champ["final_lives"],
            "cumulative_spread": champ["cumulative_spread"],
        },
        "standings": standings,
        "attrition": attrition,
    }
    return data, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    conn = connect_readonly(args.db)
    try:
        data, warnings = derive(conn)
    finally:
        conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT_PATH}")
    print(f"entrants: {data['season']['entrants']}")
    print(f"champion: {data['champion']['name']}"
          f" ({data['champion']['final_lives']} lives)")
    print("attrition (week: alive_entering, cut):")
    for row in data["attrition"]:
        label = f" [{row['round_name']}]" if row["round_name"] else ""
        print(f"  w{row['week']:>2}: {row['alive_entering']:>2} alive,"
              f" {row['cut']} cut{label}")
    if warnings:
        print("\nWARNINGS (eyeball before committing):")
        for w in warnings:
            print(f"  - {w}")
        sys.exit(1)
    print("\nno warnings; snapshot is commit-ready")


if __name__ == "__main__":
    main()
```

- [x] **Step 5: Run the exporter and eyeball the report**

Run: `venv/bin/python scripts/export_2025_history.py`
Expected: `no warnings; snapshot is commit-ready`, entrants 26, champion Fourth & Pine (2 lives), attrition series matching the Global Constraints list. If any WARNING prints, stop and investigate before committing.

- [x] **Step 6: Run the tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py -q`
Expected: all TestSnapshotIntegrity tests PASS.

- [x] **Step 7: Ruff**

Run: `venv/bin/ruff check scripts/ tests/test_cfb_history.py`
Expected: clean. Fix anything it flags (safe autofix: `venv/bin/ruff check --fix ...`).

- [x] **Step 8: Commit**

```bash
git add scripts/export_2025_history.py games/cfb/data/season_2025.json tests/test_cfb_history.py
git commit -m "$(cat <<'EOF'
feat(cfb): 2025 season snapshot + exporter + integrity locks

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Cached loader service

**Files:**
- Create: `games/cfb/services/history.py`
- Test: `tests/test_cfb_history.py` (append)

**Interfaces:**
- Consumes: `games/cfb/data/season_2025.json` (Task 1).
- Produces: `games.cfb.services.history.get_season_2025() -> dict` — returns the parsed snapshot (top-level keys `season`, `champion`, `standings`, `attrition`), cached per process, treat as read-only. Task 3's route imports exactly this name.

- [x] **Step 1: Append the failing loader tests**

Append to `tests/test_cfb_history.py`:

```python
class TestLoader:
    def test_returns_snapshot_keys(self):
        from games.cfb.services.history import get_season_2025
        data = get_season_2025()
        assert set(data) == {"season", "champion", "standings", "attrition"}

    def test_cached_per_process(self):
        from games.cfb.services.history import get_season_2025
        assert get_season_2025() is get_season_2025()
```

- [x] **Step 2: Run to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py::TestLoader -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'games.cfb.services.history'`.

- [x] **Step 3: Implement the loader**

Create `games/cfb/services/history.py`:

```python
"""2025 season archive loader.

The committed snapshot (games/cfb/data/season_2025.json, written once by
scripts/export_2025_history.py) is the archive page's only data source.
No fallback path on purpose: a missing or corrupt snapshot raises at first
request; the integrity locks in tests/test_cfb_history.py make that
unshippable rather than a runtime concern. Returned dicts are cached per
process -- treat them as read-only.
"""
import json
from functools import lru_cache
from pathlib import Path

_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "season_2025.json"


@lru_cache(maxsize=1)
def get_season_2025():
    """Return the 2025 season archive (season, champion, standings, attrition)."""
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
```

Do NOT add it to `games/cfb/services/__init__.py` re-exports — the existing `__init__` exports game-logic helpers; the route imports the module path directly.

- [x] **Step 4: Run to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py -q`
Expected: all PASS.

- [x] **Step 5: Ruff + commit**

```bash
venv/bin/ruff check games/cfb/services/history.py tests/test_cfb_history.py
git add games/cfb/services/history.py tests/test_cfb_history.py
git commit -m "$(cat <<'EOF'
feat(cfb): cached loader for the 2025 archive snapshot

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Route, template, and archive CSS

**Files:**
- Modify: `games/cfb/routes.py` (import + new route directly after the `weekly_results` function, before `make_pick` at ~line 433)
- Create: `games/cfb/templates/cfb/history.html`
- Modify: `static/css/style.css` (insert after the `.cfb-ledger-total` rule block ~line 5357, immediately before the `/* World Cup overrides */` comment)
- Test: `tests/test_cfb_history.py` (append route tests + the CSS/template design locks)

**Interfaces:**
- Consumes: `get_season_2025()` from Task 2.
- Produces: endpoint `cfb.history` at `GET /cfb/history` (public — Task 4's sub-nav pill points `url_for('cfb.history')` at it); template context keys `season`, `champion`, `standings`, `attrition`; CSS classes `.cfb-archive-champion`, `.cfb-archive-champion-name`, `.cfb-archive-champion-line`, `.cfb-archive-section`, `.cfb-archive-table`, `.cfb-archive-num`, `.cfb-archive-round`, `.cfb-archive-outcome`, `.cfb-archive-outcome-champion`, `.cfb-archive-row-champion`, `.cfb-archive-provenance`.

- [x] **Step 1: Append the failing route tests and design locks**

Append to `tests/test_cfb_history.py` (note the new module-level constants go with the existing ones at the top of the file):

```python
CSS_PATH = ROOT / "static" / "css" / "style.css"
TPL_PATH = ROOT / "games" / "cfb" / "templates" / "cfb" / "history.html"

EM_DASH = chr(0x2014)              # em dash (chr() keeps the source ASCII-clean)
CEREMONIAL_GLYPH = chr(0x25C8)     # black diamond containing small diamond
INFORMATIONAL_GLYPH = chr(0x25C7)  # white diamond
```

and (imports `re` — add `import re` to the top imports):

```python
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
```

- [x] **Step 2: Run to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py::TestRoute tests/test_cfb_history.py::TestDesignLocks -q`
Expected: TestRoute FAILs with 404; TestDesignLocks ERRORs on the missing `history.html` (FileNotFoundError) and FAILs the CSS scans.

- [x] **Step 3: Add the route**

In `games/cfb/routes.py`, add to the imports block (after the `games.cfb.services.score_fetcher` import at line 39):

```python
from games.cfb.services.history import get_season_2025
```

Insert directly after the end of the `weekly_results` function (before the `make_pick` route at ~line 433):

```python
@cfb_bp.route('/history')
def history():
    """The First Season: read-only 2025 archive (public, like standings).

    Spec: docs/superpowers/specs/2026-07-30-cfb-2025-history-ledger-design.md.
    Standings arrive pre-sorted in the snapshot; nothing here sorts or writes.
    """
    season = get_season_2025()
    return render_template(
        'cfb/history.html',
        season=season['season'],
        champion=season['champion'],
        standings=season['standings'],
        attrition=season['attrition'],
    )
```

- [x] **Step 4: Create the template**

Create `games/cfb/templates/cfb/history.html`:

```html
{% extends "base.html" %}
{% block title %}The First Season &middot; CFB Survivor{% endblock %}

{% block content %}
{# The room's quietest page: pure archive register, ceremony-by-reduction
   (spec: docs/superpowers/specs/2026-07-30-cfb-2025-history-ledger-design.md).
   No CTAs, no countdowns, no pick affordances anywhere on this surface. #}
<div class="page-hero cfb-hero">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="cfb-eyebrow">Club Archive &middot; {{ season.year }}</span>
    <h1>The First Season</h1>
    <div class="cfb-hero-field">
      <span class="cfb-count">{{ season.entrants }} entered</span>
      <span class="cfb-hero-field-sep">&middot;</span>
      <span class="cfb-count-cut">{{ season.entrants - 1 }} cut</span>
      <span class="cfb-hero-field-sep">&middot;</span>
      <span class="cfb-count">1 remained</span>
    </div>
  </div>
</div>

<div class="container mt-4 mb-5">

  {# Champion module. NOT .championship-hero (single-purpose, render-gated to a
     live sole survivor). Verdict-family grammar: raised surface, survived-green
     top rule (outcome carries outcome; crimson stays identity). #}
  <div class="cfb-archive-champion">
    <span class="cfb-eyebrow">One Remained</span>
    <div class="cfb-archive-champion-name">{{ champion.name }}</div>
    <p class="cfb-archive-champion-line">Survived all sixteen weeks. Both lives intact.</p>
  </div>

  {# Attrition: the season's narrative spine. Real counts, labeled, no chart. #}
  <div class="cfb-archive-section">
    <span class="cfb-eyebrow">The Cut, Week by Week</span>
    <div class="table-responsive">
      <table class="table cfb-archive-table">
        <thead>
          <tr>
            <th scope="col">Week</th>
            <th scope="col" class="cfb-col-center">Alive Entering</th>
            <th scope="col" class="cfb-col-center">Cut</th>
          </tr>
        </thead>
        <tbody>
          {% for row in attrition %}
          <tr>
            <td>Week {{ row.week }}{% if row.round_name %} <span class="cfb-archive-round">{{ row.round_name }}</span>{% endif %}</td>
            <td class="cfb-col-center cfb-archive-num">{{ row.alive_entering }}</td>
            <td class="cfb-col-center cfb-archive-num">{% if row.cut %}{{ row.cut }}{% else %}<span class="cfb-result-none">&ndash;</span>{% endif %}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  {# Final standings: champion first, then longest survivors (pre-sorted in the
     snapshot). No invented rank column: order + out-week tell the story without
     minting false precision (doctrine 10.3). The outcome column carries the
     state in text; the pips stay structural (fill vs hollow) with exact counts
     for assistive tech. #}
  <div class="cfb-archive-section">
    <span class="cfb-eyebrow">Final Standings</span>
    <div class="table-responsive">
      <table class="table cfb-archive-table">
        <thead>
          <tr>
            <th scope="col">Player</th>
            <th scope="col">Outcome</th>
            <th scope="col">Lives</th>
            <th scope="col" class="cfb-col-center">Cumulative Spread</th>
          </tr>
        </thead>
        <tbody>
          {% for row in standings %}
          <tr{% if row.outcome == 'champion' %} class="cfb-archive-row-champion"{% endif %}>
            <td><strong>{{ row.name }}</strong></td>
            <td>
              {% if row.outcome == 'champion' %}
              <span class="cfb-archive-outcome-champion">Champion</span>
              {% else %}
              <span class="cfb-archive-outcome">Out &middot; Week {{ row.out_week }}</span>
              {% endif %}
            </td>
            <td>
              <span class="lives-indicator">
                {% for i in range(row.final_lives) %}<span class="life"></span>{% endfor %}
                {% for i in range(2 - row.final_lives) %}<span class="life lost"></span>{% endfor %}
              </span>
              <span class="visually-hidden">{{ row.final_lives }} of 2 lives</span>
            </td>
            <td class="cfb-col-center cfb-archive-num">{{ '%.1f'|format(row.cumulative_spread) }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  {# Provenance: one quiet line, no link (club canon + quiet provenance ruling). #}
  <p class="cfb-archive-provenance">Season one was played at the old clubhouse. The record moved with the club.</p>

</div>
{% endblock %}
```

- [x] **Step 5: Add the CSS block**

In `static/css/style.css`, insert immediately after the closing brace of the `.cfb-ledger-total` rule (~line 5357) and before the `/* World Cup overrides */` comment:

```css

/* --- The First Season: 2025 archive (route cfb.history) -------------------
   The room's quietest page (spec 2026-07-30-cfb-2025-history-ledger-design):
   pure archive register, ceremony-by-reduction. Existing tokens only; the
   Crimson-Ceremony Rule holds. The champion rule is survived-green because
   outcome carries outcome (R1 ruling); crimson stays identity.
   (Comment wording stays clear of the banned-token literals on purpose:
   tests/test_cfb_history.py scans this whole block.) */
.cfb-archive-champion {
  margin-bottom: 2rem;
  padding: 1.75rem 1.5rem;
  background: var(--cfb-raised);
  border: 1px solid var(--cfb-hairline-strong);
  border-top: 2px solid var(--cfb-survived);
  border-radius: var(--radius-lg);
}
.cfb-archive-champion .cfb-eyebrow { display: block; margin-bottom: .5rem; }
.cfb-archive-champion-name {
  font-family: 'Teko', sans-serif;
  font-weight: 700;
  font-size: clamp(2.2rem, 6vw, 3.2rem);
  line-height: 1.05;
  letter-spacing: .02em;
  text-transform: uppercase;
  color: var(--cfb-white);
}
.cfb-archive-champion-line {
  margin: .35rem 0 0;
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.05rem;
  color: var(--cfb-bone-muted);
}
.cfb-archive-section { margin-bottom: 2rem; }
.cfb-archive-section > .cfb-eyebrow { display: block; margin-bottom: .6rem; }
.cfb-archive-table { margin-bottom: 0; }
.cfb-archive-num {
  font-family: 'Teko', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 1.05rem;
  letter-spacing: .03em;
  color: var(--cfb-bone);
}
.cfb-archive-round {
  display: inline-block;
  margin-left: .4rem;
  font-size: .8rem;
  color: var(--cfb-bone-subtle);
}
.cfb-archive-outcome { color: var(--cfb-bone-muted); }
.cfb-archive-outcome-champion { color: var(--cfb-survived); font-weight: 600; }
/* Quiet survived-green tint for the champion row (the tint-only convention;
   rgba of --cfb-survived #64DBA0, same pattern as the crimson you-row tint). */
.cfb-archive-row-champion > td { background: rgba(100, 219, 160, 0.06); }
.cfb-archive-provenance {
  margin: 2.5rem 0 0;
  font-family: 'Newsreader', Georgia, serif;
  font-style: italic;
  font-size: .95rem;
  color: var(--cfb-bone-subtle);
  text-align: center;
}
```

- [x] **Step 6: Run the new tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py -q`
Expected: all PASS (snapshot + loader + route + design locks).

- [x] **Step 7: Ruff + commit**

```bash
venv/bin/ruff check .
git add games/cfb/routes.py games/cfb/templates/cfb/history.html static/css/style.css tests/test_cfb_history.py
git commit -m "$(cat <<'EOF'
feat(cfb): The First Season, the 2025 archive page

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Sub-nav pill

**Files:**
- Modify: `templates/base.html` (CFB sub-nav pills block, lines 188–197)
- Test: `tests/test_cfb_history.py` (append)

**Interfaces:**
- Consumes: endpoint `cfb.history` (Task 3).
- Produces: the `2025` pill, last in the CFB sub-nav, public (outside the `current_user.is_authenticated` guard).

- [x] **Step 1: Append the failing pill lock**

Append to `tests/test_cfb_history.py` inside `TestDesignLocks`:

```python
    def test_subnav_pill_public_last_and_wired(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        m = re.search(r"subnav-cfb.*?</nav>", base, re.DOTALL)
        assert m, "CFB sub-nav block missing"
        block = m.group(0)
        assert "url_for('cfb.history')" in block
        assert ">2025</a>" in block
        pill_positions = [p.start() for p in re.finditer(r'class="subnav-pill', block)]
        history_pos = block.index("cfb.history")
        assert pill_positions[-1] < history_pos, "2025 pill must be the LAST pill"
        # Strip the pills' own `{% if request.endpoint ... %}active{% endif %}`
        # conditionals so the only {% endif %} left between the My Picks href
        # and the 2025 href is the auth guard's close -- proving the pill sits
        # OUTSIDE the guard (public).
        stripped = re.sub(
            r"\{% if request\.endpoint[^%]*%\}active\{% endif %\}", "", block
        )
        between = stripped[
            stripped.index("url_for('cfb.my_picks')"):stripped.index("url_for('cfb.history')")
        ]
        assert "{% endif %}" in between, "2025 pill must sit outside the auth guard (public)"
```

- [x] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py::TestDesignLocks::test_subnav_pill_public_last_and_wired -q`
Expected: FAIL (`url_for('cfb.history')` not in block).

- [x] **Step 3: Add the pill**

In `templates/base.html`, inside the CFB sub-nav `.subnav-pills` div, after the `{% endif %}` that closes the auth-guarded My Picks pill (line 196), add:

```html
                    <a class="subnav-pill {% if request.endpoint == 'cfb.history' %}active{% endif %}"
                       href="{{ url_for('cfb.history') }}">2025</a>
```

- [x] **Step 4: Run the full file to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_cfb_history.py -q`
Expected: all PASS.

- [x] **Step 5: Commit**

```bash
git add templates/base.html tests/test_cfb_history.py
git commit -m "$(cat <<'EOF'
feat(cfb): 2025 archive pill, last in the CFB sub-nav

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Full verification, browser smoke, detector, PR

**Files:**
- No new files. Possible micro-fixes to `history.html` / `style.css` from smoke findings (fold into this task's commit).

**Interfaces:**
- Consumes: everything above.
- Produces: a merged PR.

- [x] **Step 1: Full suite + lint**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q` and `venv/bin/ruff check .`
Expected: full suite green (1764+ tests), ruff clean. Any failure gets fixed before proceeding.

- [x] **Step 2: Browser smoke, desktop + mobile**

Start the dev server: `FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`, open `http://127.0.0.1:5099/cfb/history` (page is state-independent — no `CFB_FAKE_NOW` needed; the local `ccc_local` Postgres works as-is). Inspect logged-out (the public view). Checklist:

- Desktop: hero band reads midnight-and-crimson; champion module leads with the green rule; both tables scan; provenance line sits quiet at the foot.
- Mobile at true width (Chrome tooling `emulate "375x812x2,mobile,touch"` — NOT `resize_page`, which clamps ~500px): no horizontal body scroll (tables scroll inside `.table-responsive` only), "Who you callin a convict" wraps without breaking the row, hero field fits.
- Cross-route continuity: click Standings → Results → 2025; still one room, one game — the archive reads as the same midnight room, not a dashboard.

- [x] **Step 3: Run the impeccable mechanical detector once**

Run: `node ~/.agents/skills/impeccable/scripts/detect.mjs --json games/cfb/templates/cfb/history.html static/css/style.css`
(If `node` is missing from PATH: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"` first.)
Fix real findings in one batch; findings with no locatable source target are phantoms — ship (standing feedback rule).

- [x] **Step 4: Commit any smoke/detector fixes**

```bash
git add -A && git commit -m "$(cat <<'EOF'
fix(cfb): archive page smoke + detector fixes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```
(Skip if nothing changed.)

- [x] **Step 5: Push and open the PR**

```bash
git push -u origin feat/cfb-2025-history-ledger
gh pr create --title "feat(cfb): The First Season, the 2025 history ledger" --body "$(cat <<'EOF'
## Summary
- Public read-only 2025 archive at /cfb/history: The First Season (spec docs/superpowers/specs/2026-07-30-cfb-2025-history-ledger-design.md)
- One-off exporter (scripts/export_2025_history.py) -> committed snapshot games/cfb/data/season_2025.json (display names only; no ids, emails, or pick rows)
- Cached loader, archive template + .cfb-archive-* CSS (survived-green champion rule, no gold), 2025 pill last in the CFB sub-nav
- Three-layer locks in tests/test_cfb_history.py (snapshot integrity, route, design)

## Test plan
- [x] tests/test_cfb_history.py (snapshot integrity, route, design locks)
- [x] Full suite + ruff
- [x] Browser smoke desktop + 375px mobile; impeccable detector run

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Merge gate per repo practice: pytest + ruff + GitGuardian on the HEAD SHA. CodeRabbit is on the free tier until ~Sep — verify/address its comments if they post, but never wait on its check.

- [x] **Step 6: Merge, deploy is NOT required**

The page ships with the next routine deploy; nothing here needs prod steps, timers, nginx, or env vars. After merge: `gh pr merge --merge --delete-branch` (repo practice), then flip the plan's checkboxes and update the transition docs only if Brad asks.

---

## Execution Blueprint (per-task skill choice — ruled by Brad 2026-07-30)

Not blanket execution: each task was evaluated for **superpowers:subagent-driven-development** vs **superpowers:executing-plans** (inline). Follow this mapping; the reasons are part of the contract.

| Task | Mode | Why |
|---|---|---|
| 1 — exporter + snapshot + locks | **Inline** (executing-plans) | Reads `~/CF_Survivor` (outside the repo — subagent Bash on additional-directory paths can auto-deny or classifier-block, a known project gotcha), and Step 5 is a human-judgment gate: eyeball the sanity report before committing the snapshot. Keep it in the main loop where Brad can see the report. |
| 2 — cached loader | **Inline** (executing-plans) | ~10 lines, fully specified, zero design latitude. Subagent spin-up costs more than the task; batch it inline right after Task 1. |
| 3 — route + template + CSS | **Subagent-driven** | The largest diff and the only design-bearing surface (template + `.cfb-archive-*` block). A fresh subagent executes the verbatim code without this session's accumulated context, and subagent-driven's two-stage review is worth paying exactly here — a reviewer can meaningfully catch deviation from the doctrine locks (green-not-crimson rule, no-gold, glyph/em-dash bans) before it lands. No impeccable invocation is needed (design decisions are already made and encoded in the plan; the code is verbatim). |
| 4 — sub-nav pill | **Inline** (executing-plans) | One anchor tag + one test. Trivially mechanical. |
| 5 — verification, smoke, detector, PR | **Inline** (executing-plans) | Needs the main session's hands: dev-server management, Chrome MCP browser smoke (mobile emulation), judgment calls on detector findings (phantom rule), and the PR-to-merge flow that repo practice keeps in the driver's seat (never wait on CodeRabbit's check; verify its comments if they post). |

Sequencing: 1 → 2 → 3 → 4 → 5, strictly in order (each consumes the previous task's interface). Inline tasks run as one executing-plans pass with a checkpoint after Task 1's eyeball gate; Task 3 dispatches per subagent-driven-development, then execution returns inline for 4–5.
