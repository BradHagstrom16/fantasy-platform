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

Division of labour: the snapshot omits pick rows, so "each eliminated player
lost exactly twice" and "the second loss is their last pick week" are
checkable ONLY here, against the legacy DB. This script owns those
source-only invariants; tests/test_cfb_history.py locks only what the
snapshot can actually represent. Any warning aborts the write, so a
violation of either invariant cannot reach the committed artifact.

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


def _live_convention(legacy_spread):
    """Legacy stored favorites positive ("lower is better"); the platform
    stores the signed spread from the picked team's side (favorite
    negative, higher is better). Same season, opposite sign (2026-09-01)."""
    return -legacy_spread if legacy_spread else 0.0


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
            # The snapshot carries no pick rows, so these two invariants are
            # only checkable here, against the legacy DB. Warnings (not a hard
            # exit) keep the spec's warn-and-eyeball contract; because main()
            # now refuses to write when any warning fires, a violation still
            # cannot reach the committed snapshot.
            last_pick_week = conn.execute(
                "SELECT MAX(w.week_number) AS wk FROM pick p"
                " JOIN week w ON w.id = p.week_id WHERE p.user_id = ?",
                (u["id"],),
            ).fetchone()["wk"]
            if len(loss_weeks) >= TOTAL_LIVES:
                out_week = loss_weeks[TOTAL_LIVES - 1]
                if len(loss_weeks) > TOTAL_LIVES:
                    warnings.append(
                        f"{name}: {len(loss_weeks)} graded losses in a"
                        f" {TOTAL_LIVES}-life pool; out_week taken from loss"
                        f" {TOTAL_LIVES} (week {out_week})"
                    )
                if out_week != last_pick_week:
                    warnings.append(
                        f"{name}: out_week {out_week} but the last recorded"
                        f" pick is week {last_pick_week}"
                    )
            else:
                out_week = last_pick_week
                plural = "loss" if len(loss_weeks) == 1 else "losses"
                warnings.append(
                    f"{name}: eliminated with {len(loss_weeks)} graded"
                    f" {plural}; out_week fell back to last pick week {out_week}"
                )
            cuts_by_week[out_week] += 1
            standings.append({
                "name": name,
                "outcome": "eliminated",
                "out_week": out_week,
                "final_lives": 0,
                "cumulative_spread": _live_convention(u["cumulative_spread"]),
            })
        else:
            standings.append({
                "name": name,
                "outcome": "champion",
                "out_week": None,
                "final_lives": u["lives_remaining"],
                "cumulative_spread": _live_convention(u["cumulative_spread"]),
            })

    standings.sort(
        key=lambda r: (
            0 if r["outcome"] == "champion" else 1,
            -(r["out_week"] or 0),
            -r["cumulative_spread"],  # higher spread first (the live rule)
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
            "cumulative_spread": champ["cumulative_spread"],  # already converted
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

    print(f"entrants: {data['season']['entrants']}")
    print(f"champion: {data['champion']['name']}"
          f" ({data['champion']['final_lives']} lives)")
    print("attrition (week: alive_entering, cut):")
    for row in data["attrition"]:
        label = f" [{row['round_name']}]" if row["round_name"] else ""
        print(f"  w{row['week']:>2}: {row['alive_entering']:>2} alive,"
              f" {row['cut']} cut{label}")
    # Validate BEFORE touching OUT_PATH: a rejected derivation must never
    # overwrite the trusted committed snapshot, or recovering the good file
    # would mean reaching for git after a failed run.
    if warnings:
        print("\nWARNINGS (snapshot NOT written; eyeball before re-running):")
        for w in warnings:
            print(f"  - {w}")
        sys.exit(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {OUT_PATH}")
    print("no warnings; snapshot is commit-ready")


if __name__ == "__main__":
    main()
