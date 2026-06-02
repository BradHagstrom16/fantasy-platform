# WC Production Follow-ups — Design Spec

**Date:** 2026-06-01
**Branch:** `worldcup/production-testing`
**Ships as:** one PR

Five independent workstreams batched into one PR, finalizing World Cup
production-testing. Order of work: backend/TDD first (auto-join, derived
elimination, golf deprecation), then the impeccable CSS refactor, then the
docs/memory/repo cleanse last so docs describe the final state.

Full suite baseline: `ENVIRONMENT=testing venv/bin/python -m pytest tests/`
must be green (~957 passing) **before and after** the PR.

---

## 1. Signup auto-join to World Cup (behavior change — TDD)

### Intent
While the World Cup pick window is open, anyone who creates a platform account
wants to be in the World Cup pool. Once the tournament starts (pick deadline
passes), new signups no longer auto-join.

### Decision
WC-specific hook in the register route (not a generalized registry capability).
It is a time-bounded behavior that ends when the WC starts and is trivially
removable afterward. YAGNI over a registry flag with a single current consumer.

### Implementation
- **Site:** `core/auth/routes.py` `register()`, immediately after the existing
  `db.session.commit()` + `login_user(user, remember=True)`.
- **Gate:** auto-join only when `worldcup_state() == 'pre'` — equivalently
  `now_utc() < TOURNAMENT_DEADLINE_UTC` (picks still open). Import the state
  reader from `games.worldcup.services.state` so it honors `WC_FAKE_NOW` in
  dev/testing.
- **Enroll:** call `games.worldcup.services.enrollment.admin_enroll(user.id)`
  (idempotent — returns the existing row if present).
- **Notify:** add a second success flash after the account-created flash. Exact
  wording is UX copy and is set during the `/impeccable` invocation (it knows the
  CCC voice register); the auto-join implementation lands with a clearly-marked
  placeholder string that impeccable finalizes. Intent: confirm the WC enrollment
  and nudge the user toward making picks.
- **Comment:** a short code comment stating this is a sanctioned signup-time
  auto-join, distinct from the banned pick/admin auto-enroll path.

### Why this is NOT the banned pattern
CLAUDE.md and `tests/test_golf_auto_enroll_removed.py` ban enrollment-row
creation from **pick** and **admin** paths (silent cross-enrollment). Signup is
a separate, intentional path. The reservation in CLAUDE.md ("platform admins
enroll users via /admin/enrollments") was written before this product decision;
it remains true for pick/admin routes. The data-contract memory
`project_per_game_enrollment.md` 4-forbidden-patterns are about silent
cross-enrollment from interior routes — unaffected.

### Tests (TDD — write first)
- Pre-deadline POST `/register` (valid) → a `WorldCupEnrollment` row exists for
  the new user with `season_year == SEASON_YEAR`, and the "make your picks"
  flash is present.
- Post-deadline POST `/register` (with `WC_FAKE_NOW` past
  `TOURNAMENT_DEADLINE_UTC` + `ENVIRONMENT=testing` in the same `patch.dict`) →
  **no** `WorldCupEnrollment` row created; account still created + logged in.
- Idempotency: signup never creates a duplicate enrollment (admin_enroll guard).
- Existing-user login path is unchanged (no enrollment side effects on login).

Note: tests that set `WC_FAKE_NOW` must also set `'ENVIRONMENT': 'testing'` in
the same `patch.dict(os.environ, ...)` (CLAUDE.md time-seam gotcha).

---

## 2. Follow-up A — Shared CTA recipe (pure CSS refactor — /impeccable)

### Intent
`.home-shell .decree-cta` (pre-state countdown, `_countdown_card.html`) and
`.home-shell .dossier-cta` (live-state dossier, `_dossier_card.html`) are
intentionally parallel metal-gold "seal" CTAs authored as two near-identical
blocks. Extract the shared stack; reduce each to its genuine differences. No
behavior or visual change.

### Confirmed diff (audited)
The two blocks are byte-identical **except**:
- `.decree-cta`: `margin: 1.5rem auto 0.25rem;` `max-width: 22rem;`
- `.dossier-cta`: `margin-top: 1.25rem;` `max-width: 24rem;`

Everything else is identical: `display:flex` column layout, `align-items`,
`gap`, `padding`, `background: var(--metal-gold-flat)`, `border-radius`,
`text-decoration`, `box-shadow`, `transition`, `:hover` lift + shadow, `:hover i`
`translateX(3px)`, `:active` press (incl. inset gold ring), `:focus-visible`
outline, and the `prefers-reduced-motion` reset. The label/sub sub-elements
(`-label`, `-sub`, `-label i`) are likewise identical.

### Implementation
- New shared selector `.home-shell .cta-seal` owns the full layout/interaction
  stack, plus `.cta-seal-label`, `.cta-seal-sub`, `.cta-seal-label i`, and the
  hover/active/focus-visible/reduced-motion rules.
- `.home-shell .decree-cta` reduces to `{ margin: 1.5rem auto 0.25rem;
  max-width: 22rem; }`; `.home-shell .dossier-cta` to `{ margin-top: 1.25rem;
  max-width: 24rem; }`.
- Templates apply both classes: `class="cta-seal decree-cta"` /
  `class="cta-seal dossier-cta"`; sub-elements switch to
  `cta-seal-label` / `cta-seal-sub`.
  - `_countdown_card.html` currently uses `{{ _cta_label/_sub/_href }}` vars —
    preserve those; only the class names change.
  - `_dossier_card.html` keeps its literal "Enter the World Cup" / "Your roster
    and the live ledger." copy.

### Guardrails
- **Trophy Rule:** metal-gold stays reserved for the primary CTA — the shared
  recipe keeps `--metal-gold-flat`; no new metal-gold consumers introduced.
- Reduced-motion block and keyboard `:focus-visible` parity preserved on the
  shared selector.
- Invoke `/impeccable` for the CSS work, reading top-level `DESIGN.md` **and**
  `games/worldcup/DESIGN.md` (CLAUDE.md hard rule for any `games/<slug>/` UI).
- If a design test locks these CTAs, extend it to assert the shared recipe (and
  that `.decree-cta`/`.dossier-cta` carry only their deltas).

### Verification
Visually confirm pre + live home states at desktop and mobile widths using the
dev-server + `WC_FAKE_NOW` recipe in CLAUDE.md. Both states must render
identically to before.

---

## 3. Follow-up B — Derived knockout elimination (behavior fix — TDD)

### Problem
`WorldCupTeam.is_eliminated` is group-stage-only by data contract (set True only
for teams that fail to advance from their group — `scoring.py` ~line 259).
Knockout losers (R32/R16/QF/SF/runner-up) keep `is_eliminated=False`. Every UI
that reads `is_eliminated` as "team is out of the tournament" under-reports
eliminations during/after the knockout rounds.

### New helper
`games/worldcup/services/elimination.py`:

```python
def eliminated_team_ids(season_year=SEASON_YEAR) -> set[int]:
    """Team ids that are out of the tournament (group OR knockout).

    A team is out if is_eliminated (group-stage exit) OR it appears in a
    completed knockout match where it is not the winner. NULL winner_team_id
    on a completed KO match counts as elimination for BOTH teams (knockouts
    never legitimately draw) — matching team_detail._path_status semantics.
    """
```

- One query for all completed KO matches → build the loser set in Python →
  union with the `is_eliminated=True` set. N+1-free.
- `season_year` param accepted for API symmetry / forward-compat; teams and
  matches are a single tournament edition today (no per-season column on
  `WorldCupTeam`/`WorldCupMatch`), so the param is currently advisory — document
  that. The completed-match set IS the edition.
- Optional convenience `is_team_out(team_id, eliminated_ids)` membership wrapper
  if it reads cleaner at call sites; otherwise sites use `in eliminated_ids`.

### Read-sites routed through the helper
- **Leaderboard** (`games/worldcup/routes.py` leaderboard route +
  `templates/worldcup/leaderboard.html`): route computes
  `eliminated_ids = eliminated_team_ids()` once and passes it to the template;
  template replaces `team.is_eliminated` membership checks at desktop
  (:114 `is-out`, :116 "· out", :117 aria "eliminated") and mobile (:181) with
  `pick.team_id in eliminated_ids`. **No ORM mutation** — set membership only
  (CLAUDE.md transient-attr rule).
- **Live hub** (`games/worldcup/services/home_context.py`): `_context_live`
  uses the set for the Leverage Board row 'out' status (:447) and `alive_count`
  (:396).
- **Picks/standing** (`games/worldcup/routes.py:226`): `alive_count` uses the set.

### Evaluate (each gets a documented verdict in the PR)
`picks.html:109,114`, `_pick_row.html:10`, `groups.html:72`. Expectation:
`groups.html` group-standings `is_eliminated` is legitimately group-scoped
(a team eliminated *in the group stage*) and stays as-is. Evaluate
picks/_pick_row per their actual semantic ("out of tournament" vs "group exit")
and migrate only the tournament-out ones.

### Tests (TDD — write first)
- A knockout loser (e.g. lost a completed R32 match) reads as **out** on the
  leaderboard rail and on the Leverage Board.
- A group winner that lost in the R32 is **out** (distinct from group-stage
  exit).
- A still-advancing team is **not** out.
- Group-stage `is_eliminated=True` team still reads out (no regression).
- Parity test: `eliminated_team_ids()` agrees with
  `team_detail._path_status()` elimination (a team is in the set iff
  `_path_status` returns a non-None `eliminated_at_index`).
- Dense-rank parity and D11 ownership-privacy gates remain untouched.

### Docs
Update the `is_eliminated` "derive KO elimination from completed matches"
guidance in CLAUDE.md and `memory/project_wc_data_contracts.md` to name the
concrete `eliminated_team_ids()` helper.

---

## 4. Datetime deprecation cleanup (golf pytz → zoneinfo)

### Scope
golf is the only offender (`coming_soon`, not live in prod — low risk to touch
now). No `datetime.utcnow()`/`utcfromtimestamp()` anywhere in the repo. Targets:
- `games/golf/utils.py:14` — `GOLF_LEAGUE_TZ = pytz.timezone('America/Chicago')`
- `games/golf/constants.py:23` — `SEASON_CUTOFF_DATE = datetime(..., tzinfo=pytz.UTC)`
- `games/golf/models.py` — `.localize()` at :178/:202/:203/:221, `.astimezone()` :223
- `games/golf/services/sync.py` — `pytz.timezone` type hints (:186/:230),
  `pytz.timezone(tz_name)` :190, `pytz.UTC` :224/:369, `.localize()`
  :244/:249/:277/:278/:299, `.astimezone()` :469
- `games/golf/services/reminders.py:228,450,823` — `.localize()`
- `games/golf/cli.py:61` — `datetime.now()` → `datetime.now(timezone.utc)`

### Translation rules
- `pytz.timezone('America/Chicago')` → `ZoneInfo('America/Chicago')`
- `tz.localize(naive_dt)` → `naive_dt.replace(tzinfo=tz)` — **DST-correct** in
  zoneinfo (the broken-`.replace` caveat that forced pytz's `.localize()` does
  not apply to `ZoneInfo`); this is exactly the CLAUDE.md idiom.
- `pytz.UTC` → `timezone.utc` (matches CLAUDE.md UTC convention)
- type hints `pytz.timezone` → `ZoneInfo`
- `datetime.fromtimestamp(ts, tz=pytz.UTC)` → `datetime.fromtimestamp(ts, tz=timezone.utc)`
- `.astimezone(GOLF_LEAGUE_TZ)` — unchanged behavior with `ZoneInfo`
- remove every `import pytz`; add `from zoneinfo import ZoneInfo` /
  `from datetime import timezone` as needed.

### Verification
Run golf-related tests and the full suite before and after; zero behavior change
expected. Result: zero `pytz` and zero naive `datetime.now()` in the repo,
matching the CLAUDE.md timezone convention.

---

## 5. CLAUDE.md / memory / repo cleanse

### CLAUDE.md
Run `/claude-md-management:claude-md-improver` focused on **conciseness** —
remove outdated, duplicated, or low-value content. Known stale item: the
"games/golf/ — Golf Pick 'Em (live)" / "all three live" claim (golf + cfb are
`coming_soon`; only worldcup is `open`). Update the `is_eliminated` guidance to
reference the new helper (see §3).

### Memory cleanse
Audit `memory/` for notes that are low-value, outdated, duplicated by CLAUDE.md,
or only mattered to a past conversation. Delete or merge; update `MEMORY.md`
index accordingly. Add/update the data-contract note for `eliminated_team_ids`.

### Repo file cleanup
Propose a concrete delete-list of files that are safe to remove before shipping
to production (stale scratch docs, superseded artifacts) for **explicit user
approval before deleting anything**. Do NOT propose deleting the gitignored
`_migration_source/` (kept for golf/cfb go-live per
`project_migration_source_kept.md`).

---

## Out of scope
- Generalizing auto-join into a registry capability (deferred until a second
  consumer exists, e.g. CFB launch).
- Mass-migrating legacy `.query` → SQLAlchemy 2.0 `select()` (CLAUDE.md policy:
  new/changed code only).
- Any WC scoring-engine change.
