# Phase 5 Changeover Kit (prepared 2026-07-30)

Paste-ready material for the **atomic WC→CFB changeover PR** (transition plan §6E, §8 Phase 5;
target ~Aug 17–24). Everything here was drafted in advance so the changeover session is the
two-line flip plus pastes from this file. The transition plan remains the SSoT for *why*;
this kit is the *what to type*.

---

## 1. Preconditions (Brad, before the PR is cut)

- [x] AP preseason poll released (~Aug 17). **Landed 2026-08-17.** Pool ruled: Top 25 +
      every "others receiving votes" team = **49** (same recipe/size as 2025). Louisiana is
      NOT in the ORV list — the AP-page numbers checksum exactly (69 voters × 325 = 22,425);
      the ESPN/Yahoo syndicated lists showing "Louisiana 4" are wrong.
- [x] Populate the CFB team list. **Executed 2026-08-17:** PR #148 merged (`4e31054`),
      deployed, `flask cfb populate-teams` added 49. **Path re-ruled 2026-08-17:** run
      `flask cfb populate-teams` on the droplet (the 2026 list now lives in
      `DEV_SEED_TEAMS`, reviewed in its own PR; the command's empty-table guard makes it a
      deliberate one-shot). The Manage Teams surface remains the tool for *later
      corrections*, not the initial seed — hand-checking ~49 of 138 boxes is
      transcription-error-prone and unreviewable. As of 2026-07-30 prod `cfb_team` has
      **0 rows** (expected; see §7) — this step is what makes "teams present" true.
- [x] Confirm on prod: `cfb_team` count = 49, still zero transactional rows; Manage Teams
      page shows exactly the 49 checked (visual cross-check). **Confirmed 2026-08-17:**
      49/49 exact set match against `DEV_SEED_TEAMS` (none missing, none unexpected, all
      conferences valid); 0 weeks / 0 games / 0 picks; the 1 enrollment is Brad's own
      (joined 2026-08-13 post-flip — legitimate, not test data).

## 2. The changeover PR (cut from MAIN, one commit-series, full CR cycle)

### 2a. `games/registry.py` — the atomic double flip

World Cup entry (currently lines ~65–66):

```python
        status='open',            # → status='completed',
        is_featured=True,         # → is_featured=False,
```

CFB entry (currently lines ~84–85):

```python
        status='coming_soon',     # → status='open',
        is_featured=False,        # → is_featured=True,
```

Also delete the CFB entry's four-line comment ("Lounge callables wired ahead of the Phase 5
changeover … transition plan section 6 E.") — it describes a pre-flip state that stops being
true in this same diff.

The changeover seam test (`tests/test_registry_seam.py`) already exercises the real CFB
lounge callables; no edit needed there.

### 2b. `tests/test_home_context.py::test_context_out_basic`

The only test the flip breaks (transition plan §1 finding, re-confirmed 2026-07-30 — the
assertion at lines ~112–113). Replace:

```python
        # WC is the only open game in the registry currently
        assert any(g.slug == 'worldcup' for g in ctx['available_games'])
```

with:

```python
        # CFB is the only open game in the registry post-changeover
        assert any(g.slug == 'cfb' for g in ctx['available_games'])
        assert not any(g.slug == 'worldcup' for g in ctx['available_games'])
```

### 2c. `core/auth/templates/auth/login.html` — brand-panel callout (lines ~76–86)

Replace the two-branch WC callout with a three-branch CFB-era version (new `/worldcup`
branch keeps a correct line for members following archive deep links):

```jinja
                {% if request.args.get('next', '').startswith('/cfb') %}
                <div class="login-callout mt-3">
                    <span>🏈</span>
                    <span>You're one step away from the <strong>CFB Survivor Pool</strong></span>
                </div>
                {% elif request.args.get('next', '').startswith('/worldcup') %}
                <div class="login-callout mt-3">
                    <span>⚽</span>
                    <span>The <strong>2026 World Cup</strong> archive awaits inside.</span>
                </div>
                {% else %}
                <div class="login-callout mt-3">
                    <span>🏈</span>
                    <span>The <strong>2026 CFB Survivor Pool</strong> is open. Join today.</span>
                </div>
                {% endif %}
```

New neutral class in `style.css` (the incumbent `.wc-login-callout` carries WC-navy tints,
`rgba(0,40,104,…)`, wrong era for auth chrome; platform purple is `--purple-700` #3A1D72).
Add alongside the existing rule — WC surfaces stay frozen, the old class simply goes unused:

```css
.login-callout {
  display: flex;
  align-items: center;
  gap: .5rem;
  justify-content: center;
  font-size: .82rem;
  color: var(--text-secondary);
  background: rgba(58, 29, 114, .05);
  border: 1px solid rgba(58, 29, 114, .12);
  border-radius: 8px;
  padding: .5rem .75rem;
}
```

(Mirror any remaining declarations from `.wc-login-callout` at style.css:9941 — only the two
navy rgba values change.)

### 2d. `CLAUDE.md` edits (same PR)

1. **Project Overview, games list:** CFB line → active/`open`/featured ("registry `open` as
   of <flip date>; season starts Thu Sep 3"); WC line → registry `'completed'` (drop the
   "stays `'open'` until the CFB changeover" clause — the changeover happened).
2. **Architecture: lounge vs rooms:** update "CFB's set is next (C2 slice 3+)" → shipped and
   featured; the lounge now dispatches to CFB through the seam; WC's lounge set remains
   archived behind the seam.
3. **World Cup section:** registry status line → `'completed'`.
4. Leave the Production-ops scheduled-jobs state alone — timers flip at Phase 6, and that
   section gets its update then.

### 2e. Plan/docs bookkeeping (same PR)

- Flip the transition plan §8 **Phase 5** checkbox `[x]` (checkbox discipline).
- Suite + Ruff green locally; full CodeRabbit cycle; merge only on a clean latest review.

## 3. Deploy + verify (Brad at the droplet)

`git push origin main` locally, then on the droplet `./deploy.sh`, then the standard
post-deploy verification (CLAUDE.md Production Deployment — all four checks, including
`ps -o args= -C gunicorn`).

## 4. Post-deploy content pastes (Brad, via `/admin/commish-note`)

The three CFB-era Commish notes, drafted to the C1 copy laws (survivor lexicon, no em
dashes, no manufactured drama; the WC-era notes below are replaced wholesale). The post
note's `{champion}` placeholder interpolates at render time — keep it verbatim.

**Executed at the Aug 11 flip** — verified on prod 2026-08-17: all three `commish_notes`
rows present, updated 2026-08-11 19:24 UTC, bodies matching the texts below.

**pre:**

> The Club reconvenes for football season. The terms are simple and unforgiving: one pick a
> week, the pick must win outright, and a team once used is spent for the year. Two lives
> cover the whole season, so spend them like they are the only two you get. They are. The
> Commish wishes every one of you a long autumn. History says most of you will not get one.

**live:**

> The season runs and the pool thins on Saturdays. Picks lock at the deadline, results post
> when the games settle, and the Commish does not reopen a locked card. No appeals, no
> sympathy for bad beats, no credit for close. Watch your used teams, mind the tiebreaker,
> and keep the trash talk inside the room.

**post:**

> The 2026 season is settled and the ledger closes. {champion} outlasted the field and the
> Club records it as such. Every burned favorite, every Saturday sweat, and every cut is
> part of the record now. Whatever your finish, the rivalry held and the receipts are in
> the Club's history. Rest up. The Commish will be in touch when the next ledger opens.

## 5. Post-flip smoke (prod, non-admin account)

- [ ] `/` renders the CFB lounge `pre` state (decree countdown, farewell strip, archived WC
      tile labeled `COMPLETED`); logged-out `/` shows the CFB out-shell join card.
- [ ] Join → pick → standings as a non-admin (the §6F flow, front half).
- [ ] Login page shows the CFB callout; a `?next=/worldcup/...` login shows the archive line.
- [ ] WC archive still reachable for enrolled members; WC join correctly closed.
- [ ] All three commish notes render (fake-clock states were browser-smoked in Phase 4; prod
      only needs the current state plus spot checks).

## 6. What this kit does NOT cover

**Phase 6 — ops enablement** stays a launch-week act (transition plan §6F): enabling the
five `cfb-*` timers **by explicit name** (no globs), the week-1 dry run, and the week-1
Thu/Fri deadline-semantics product check.

## 7. Early readiness-check results (2026-07-30, read-only; §6F re-verifies launch week)

| Check | Result |
|---|---|
| `cfb-*` systemd units | All 10 installed (5 services `static`, 5 timers `disabled`). `PRESET: enabled` column was the known `preset-all` hazard — **closed 2026-08-13 by ADR-044**, which ships `deploy/10-fantasy-platform.preset` with `ignore cfb-*.timer`, so `preset-all` now leaves these exactly as it finds them. |
| Prod `.env` | All seven vars SET: `ODDS_API_KEY` (Odds API key), `EMAIL_ADDRESS` + `EMAIL_PASSWORD` (Brevo **SMTP auth login/key** — the login is not an inbox), `MAIL_FROM_ADDRESS` (visible From, the DKIM sender), `SMTP_SERVER` + `SMTP_PORT` (Brevo relay), and `ADMIN_EMAIL` (game-admin **alert recipient** — verified distinct from the SMTP login `EMAIL_ADDRESS`, i.e. a real mailbox). |
| CFB tables | 0 weeks / 0 games / 0 picks / 0 enrollments (no sandbox data ever reached prod). `cfb_team` = 0 — expected pre-AP-poll; §1 populates it. |
| Odds API | Key valid (HTTP 200); quota 500 remaining / 0 used. |
