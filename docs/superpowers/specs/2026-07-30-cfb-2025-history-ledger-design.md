# CFB 2025 History Ledger — Design

**Date:** 2026-07-30
**Status:** Approved (Brad, section-by-section, 2026-07-30)
**Workstream:** Legacy 2025 history migration (Brad's 2026-07-30 ruling: migrate at launch; leaning ratified here: light read-only ledger, no relational import, no user linking)
**Source of truth:** `~/CF_Survivor/instance/picks.db` (read-only; one season — 26 users, 16 weeks, 319 games, 208 picks, 49 teams; schema in that repo's `models.py`)

---

## 1. Rulings (settled during brainstorm — do not re-ask)

| Question | Ruling |
|---|---|
| Placement | CFB room page at `/cfb/history` — **the lowest-priority page of the entire CFB site** |
| Depth | Standings + season story (champion moment, final standings, week-by-week attrition). **No pick-level replay** |
| Access | Public — no login gate, no enrollment gate (same convention as standings/results) |
| Fiction | Club canon + quiet provenance: 2025 is the club's inaugural Survivor season in full Survivor voice, with one quiet archival line noting the old clubhouse (no link, no URL) |
| Data shape | **Approach A** — committed JSON snapshot + read-only route. No models, no migration, no admin surface, no prod import step |
| User linking | None. Display names render as plain text; b1gbrad.pythonanywhere.com identities never map to cccfantasy.com accounts |

## 2. The season being archived (verified against picks.db)

- 26 entrants; picks per week trace attrition exactly: 26, 26, 24, 20, 18, 14, 14, 12, 10, 9, 8, 8, 7, 4, 4, 4.
- Week 15 = "Conference Championship Week"; week 16 = "CFP Round 1" (`is_playoff_week`).
- Week 16: four players picked, three picked wrong and were eliminated. **Fourth & Pine won with both lives intact** — the only non-eliminated player. Season dates: 2025-08-28 → 2025-12-19.
- Legacy `admin` account displays as `B1G_Brad` (led cumulative spread at 193.0, eliminated anyway — spread is the tax, not the game).

## 3. Architecture

```
scripts/export_2025_history.py   (committed; stdlib sqlite3; run once, locally)
        │  reads ~/CF_Survivor/instance/picks.db via sqlite3 URI ?mode=ro
        ▼
games/cfb/data/season_2025.json  (committed snapshot — THE tested artifact)
        ▼
games/cfb/services/history.py    get_season_2025() — functools.lru_cache loader
        ▼
GET /cfb/history                 (public; games/cfb/routes.py)
        ▼
games/cfb/templates/cfb/history.html
```

### Export script (`scripts/export_2025_history.py`)

- Stdlib `sqlite3` only; **no Flask, no imports from the legacy repo**; opens the DB read-only (`file:...?mode=ro`). The legacy repo is never modified.
- Deterministic output (sorted keys, stable ordering) so a re-run produces an identical diff.
- Derives per player: display name (`display_name or username`), final lives, eliminated flag, cumulative spread, **out-week** = week of the second incorrect pick.
- Out-week fallback: if a player's elimination cannot be located as two graded losses (e.g. legacy missed-pick edge), fall back to their last recorded pick week and **print a warning** for eyeballing before commit.
- Prints a sanity report: counts, champion, attrition series, any warnings.
- Deliberately untested in CI (depends on `~/CF_Survivor`). Its job ends when the snapshot is committed.

### Snapshot schema (`games/cfb/data/season_2025.json`)

Four blocks, nothing else:

```json
{
  "season": {"year": 2025, "entrants": 26, "weeks": 16,
             "start_date": "2025-08-28", "end_date": "2025-12-19"},
  "champion": {"name": "Fourth & Pine", "final_lives": 2,
               "cumulative_spread": -163.5},
  "standings": [
    {"name": "...", "outcome": "champion" | "eliminated",
     "out_week": null | 1-16, "final_lives": 0-2,
     "cumulative_spread": 0.0}
  ],
  "attrition": [
    {"week": 1-16, "round_name": null | "Conference Championship Week" | "CFP Round 1",
     "alive_entering": N, "cut": N}
  ]
}
```

**Excluded by design:** emails, user ids, passwords, `has_paid`, `is_admin`, pick-level rows, team data.

### Serving

- `games/cfb/services/history.py::get_season_2025()` — loads the JSON once per process, returns plain dicts. **No fallback path**: a missing/corrupt snapshot fails loudly; the CI schema locks make that unshippable rather than a runtime concern.
- Route: `GET /cfb/history`, endpoint `cfb.history`, no decorators (public, like standings/results). Anonymous responses stay CDN-cacheable per platform convention. **Standings arrive pre-sorted in the snapshot** (the export script sorts; the route and template render as-is — Jinja sort ban never comes into play).

## 4. Page design

**Register:** the room's quietest page. Pure archive: zero urgency machinery — no CTAs, no countdowns, no pick affordances, no forms. Ceremony-by-reduction is the whole design; the page is calm because the season is over. Still unmistakably the midnight room (substrate, Teko/Newsreader, crimson-as-identity), never a stats dashboard.

Structure, top to bottom:

1. **Hero** — standard platform `.page-hero` (midnight→crimson band). Eyebrow (`.cfb-eyebrow`, no glyph per the game-body rule): `CLUB ARCHIVE · 2025`. H1 (Survivor voice): **"The First Season"**. Hero field reuses the shipped `.cfb-hero-field` pattern: `26 entered · 25 cut · 1 remained`.
2. **Champion module** — **not** `.championship-hero` (single-purpose primitive, render-gated to a live sole survivor; reuse forbidden by doctrine §7.2). New quiet primitive `.cfb-archive-champion` in the verdict family's grammar: raised midnight surface (`--cfb-raised`), **survived-green 2px top rule** (outcome carries outcome; crimson stays identity — the ratified R1 contract), eyebrow `ONE REMAINED` (past tense of the shipped champion eyebrow "One Remains"), the name **Fourth & Pine** in Teko `--cfb-white`, one Newsreader evidence line: "Survived all sixteen weeks. Both lives intact." The intact-lives fact leads because it is the story of the season.
3. **Attrition table** — "The Cut, week by week." Compact 16-row table (doctrine-sanctioned form: real counts, labeled, no chart): week, round name where one exists, alive entering, cut that week. Teko tabular figures for numbers.
4. **Final standings** — 26-row ledger: player, outcome ("Champion" / "Out · Week N"), final lives as shipped `.lives-indicator` pips (with text labels for color-independence), cumulative spread. Ordered champion first, then out-week **descending** (longest survivors high); within a shared out-week, the better tiebreak position first (row-order determinism mirroring the platform tiebreak convention, not a claimed official rank). **Amended 2026-09-01:** the archive was converted to the live sign convention (signed from the picked team's side, favorite negative, higher is better); every stored `cumulative_spread` was negated (163.5 became -163.5) and the within-out-week order is now higher spread first, which is the same row order as before. **No invented rank column** — the 2025 pool never published ordinal ranks for eliminated players; order + out-week tell the story without minting false precision (doctrine §10.3).
5. **Provenance line** — one bone-subtle Newsreader sentence at the foot, no link: "Season one was played at the old clubhouse. The record moved with the club."

**Navigation:** a `2025` pill in the **last** position of the CFB sub-nav in `base.html`, endpoint `cfb.history`. Present and discoverable, structurally the lowest item — matching the ruling. The sub-nav label already reads "CFB 2026", so the pill reads as the archive door.

**CSS:** small `.cfb-archive-*` block appended to the CFB section of `style.css`, consuming existing tokens only (midnight ramp, hairlines, `--cfb-survived`, bone scale). **No gold anywhere** (Crimson-Ceremony Rule). No new colors. Crimson only where identity already puts it (hero, active pill). All copy honors the em-dash ban and correct pluralization.

## 5. Testing (`tests/test_cfb_history.py`)

Three layers:

1. **Snapshot integrity locks** (the committed JSON is the tested artifact):
   - exactly 26 players; exactly one champion (2 lives, not eliminated, `out_week` null);
   - 25 eliminated players, each with `out_week` in 1–16;
   - attrition covers weeks 1–16; `alive_entering` starts at 26 and never increases; cuts sum to 25;
   - forbidden-key scan: no email, user id, password, `has_paid`, `is_admin` anywhere in the file.
2. **Route tests:** anonymous GET `/cfb/history` → 200 with champion name, archive eyebrow, attrition content; page contains **no** form, POST target, or pick CTA.
3. **Design locks** (established CFB idioms — anchored regex over `style.css` + template source):
   - `.cfb-archive-*` block inside the CFB section; no gold token within it;
   - champion top rule is survived-green, not crimson;
   - template carries no `◈`/`◇` glyph and no em dash in UI copy;
   - `2025` pill exists in `base.html`'s CFB sub-nav, points at `cfb.history`, last position.

**Edge cases:** names like `P$` and "Who you callin a convict" ride through Jinja autoescape (one appears in a test assertion); long-name wrap checked at 375 px during smoke.

## 6. Verification cadence

- Browser smoke desktop + true mobile (`emulate "375x812x2,mobile,touch"`); page is state-independent, so no `CFB_FAKE_NOW` walking.
- Impeccable mechanical detector once after the build: `node ~/.agents/skills/impeccable/scripts/detect.mjs --json <changed targets>`.
- Cross-route continuity: still "one room, one season, one game" — not a dashboard, not the WC room.
- Full pytest suite + ruff clean.

## 7. Out of scope (explicit)

- Pick-level replay / per-player season paths (can arrive later as progressive disclosure without schema changes to what ships here).
- Any linking of 2025 names to cccfantasy.com accounts.
- A generalized multi-season archive framework — the 2026 season will archive naturally in the live `cfb_*` tables; this page solves 2025 only. The route name `/cfb/history` is deliberately year-neutral so a future archive surface can grow there if ever wanted.
- Deleting `~/CF_Survivor` (stays until migration confirmed done; per standing memory, never propose deleting it without Brad's confirmation).
