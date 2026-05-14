# Strategy — Unify the World Cup tab system (Stats → all 6 tabs)

> Companion scorecard: `docs/superpowers/specs/2026-05-13-worldcup-tab-unification-scorecard.md`.
> Window opened: 2026-05-13. Modeled on the P0–P6 impeccable design improvement project.

## How to resume in a fresh session

Open with: *"Read this file and the companion scorecard. Execute the next pending phase per the scorecard's status table."*

Each phase ships as its own PR. The assistant should:
1. Read this strategy + scorecard
2. Confirm the next pending phase from the scorecard's status table
3. Read the relevant template + CSS + pattern-lock tests for that phase
4. Make the migration edits
5. Run tests + detector + visual smoke
6. Open the PR (one per phase)
7. Update the scorecard with PR link + per-phase notes

---

## Context

The 6 World Cup tabs (HUB / ROSTER / BOARD / SCHEDULE / STATS / RULES) don't feel like the same designed game. HUB carries dark navy cards with white text; ROSTER mixes white cards (edit form) with dark cards (post-deadline read-only); BOARD also mixes; STATS is the closest to right (white cards / dark text / lead-rule accent); RULES is the furthest. The accent vocabulary is fragmented too — gold and red split across surfaces with no doctrine.

Brad's stated direction:
- **Standardize on white cards + dark text** across the WC body
- **USA red + white + blue** as the accent palette (gold demoted to quaternary)
- Each tab should feel like one designed game
- The dark navy hero stays — it's WC's signature identity moment

This is a **doctrinal pivot** in DESIGN.md (which frames `.card.wc-card` as the deliberate "Tribune-Dark" primitive), not a tactical fix. PRODUCT.md's "casual is the default" principle supports the shift.

---

## What the exploration found

### The 6 tabs today

| Tab | Body cards | Substrate | Closeness to target (1–5) |
|---|---|---|---|
| HUB | `.card.wc-card` (deadline, leaderboard preview) | dark navy `rgba(0,17,46,.8)` | **2** |
| ROSTER | `.tier-card` (pick form) + `.card.wc-card` (post-deadline read-only desktop) | mixed: white + dark | 2.5 |
| BOARD | `.card.wc-card` (leaderboard table) + `.your-standing-tribune` (white) | mixed: dark + white | 2.5 |
| SCHEDULE | inline match rows, light styling | bone page, no heavy card wrap | 3.5 |
| **STATS** | `.wc-stat-card` (white, dark text, lead-rule on `.is-lead`) | white throughout | **5 — reference** |
| RULES | white card sections, red eyebrows | white throughout | **5 — already aligned** |

### What's already the constant (don't change)
- **The dark navy hero** `.page-hero.wc-hero-grad` (`#0A1A50 → #00102E` gradient) renders identically on every tab. This is WC's signature identity moment.
- **The sub-nav** `.subnav-worldcup` (navy header with red active pill) already audited AA-clean.
- **Stats pattern**: `.wc-stat-card` + `.wc-card-head` + `.wc-stat-card.is-lead`. This is the target.

### Constraints from existing pattern-lock tests
- `tests/test_design_p6_s6_1_1.py::test_pi1_dark_card_eyebrow_lift_rule_exists` locks `.card.wc-card .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)` to `rgba(243,239,230,.85)` (bone @ .85 on navy).
- `tests/test_design_p2_s2_4_1.py::test_is_lead_css_uses_red_rule_top_no_border` locks `.wc-stat-card.is-lead` to `2px solid var(--wc-red)` (flipped in Phase 0; was `var(--gold)`).
- `tests/test_design_p6_s6_1_3.py` locks `.your-standing-tribune + .card.wc-card` gold-divider (Phase 2 territory).
- `tests/test_design_p6_s6_1_4.py` locks `.commish-note-body` gold-top (Phase 1 territory).
- CLAUDE.md documents `.card.wc-card` as a dark navy surface with foreground-color carve-outs.
- **Implication**: don't repaint `.card.wc-card` from dark to light — that breaks the locks and orphans the carve-outs. Instead, **migrate template usages off `.card.wc-card` and onto the Stats pattern**. `.card.wc-card` shrinks to zero use over phases, then is removed in Phase 5.

---

## The strategy

Treat this as a phased migration project, mirroring the original impeccable P0–P6 rollout. Six PRs total in a deliberate order, each independently shippable. Stats is the reference card; every phase brings one more tab onto it.

### The pattern (extracted from Stats, locked once at the start)

```
Dark navy hero  ← stays (signature identity, already consistent)
  Text: white (body) + red (eyebrows / decorative spans)
  No gold in the hero copy by default. The gold phase-chip from the
  hub-polish PR flips to a red+white variant in Phase 1; the gold radial
  in the hero gradient is faint and stays for warmth.
  ↓
Light body on bone page
  ↓
.wc-stat-card  (white, dark text)
  - .wc-card-head        — Teko eyebrow @ --text-secondary OR --wc-red (decorative)
  - .wc-stat-card.is-lead — border-top: 2px solid var(--wc-red)  ← flipped in Phase 0
  - Body copy            — --text-primary (near-black) + --wc-navy for headings + --wc-red for emphasis
  ↓
Accent vocabulary (order matters — first three lead, last one whispers)
  1. White → card substrate (bone page substrate stays the platform default)
  2. Red   → primary CTAs (global `.btn-game` on WC), `.is-lead` rule, hero eyebrows,
             current-user row tint, ceremonial emphasis on light cards
  3. Navy  → dark hero substrate + table thead bar + heading text on light cards
             + the inactive `.btn-outline-secondary`-style restful state
  4. Gold  → quaternary only. Reserved for: focus rings (a11y lock, --gold-light),
             champion banners, podium glow on victory moments. Never on the hero phase
             chip, never on `.is-lead`, never on routine emphasis. If a designer reaches
             for gold and it's not in one of the reserved slots, push back to red.
```

### Migration order (lowest-risk first, builds momentum)

**Phase 0 — Quick wins + pattern codification (in flight at doc creation)**
- Fix the **group-letter pill** contrast bug: `.wc-team-card .team-group-pill` at style.css ~2854 had `color: var(--bone-mute)` on bone-tinted fill — ~1.05:1 on the `--bg-card` white substrate. Flip to navy-tinted fill + `--text-secondary` text for ~7:1; hover lifts to red.
- **Flip `.wc-stat-card.is-lead` from gold to red**: `border-top: 2px solid var(--wc-red)` (was `var(--gold)`). Stats page becomes the visible "before/after." All downstream phases inherit the red-rule reference. Test lock updated in lockstep.
- **Move this strategy + a scorecard into the repo** so future sessions can resume.
- **Deferred from Phase 0**: the broader gold audit (~92 `var(--gold` occurrences, 3 separate pattern-lock tests on different primitives) and the DESIGN.md doctrine rewrite. Brad's load-bearing-doc preference is to draft those himself; the strategy doc carries the doctrine until DESIGN.md catches up.

**Phase 1 — HUB (smallest blast radius, just touched in PR #21)**
- Migrate the hub's three dark-card surfaces (deadline, roster preview, leaderboard preview) onto `.wc-stat-card`.
- The hub-polish PR (#21) reconciliation:
  - `.card.wc-card .btn-game` red-override → **delete** the scoped rule. Replace with global `body.game-worldcup .btn-game` repaint to `--wc-red`. CTAs are red on every WC substrate after Phase 1.
  - `.page-hero.wc-hero-grad .phase-indicator` gold variant → **flip to red+white**. Hero stays dark; chip becomes faint red-tinted pill + white text + red dot.
  - `.wc-card-deadline` gold-top on dark → re-derive as `.wc-stat-card.is-lead` on a light card.
  - `.page-hero.wc-hero-grad .wc-eyebrow:not(...)` contrast lift on hero → stays (still bone @ .85 on dark navy).
  - `.row-current-user` red tint at 14% + gold-light anchor → keep tint; flip the anchor to `var(--game-primary)` (navy) on light substrate.
- Touch `.commish-note-body` gold-top if it's in the hub flow (S6.1.4 PI-1 test lock at `test_design_p6_s6_1_4.py:128`).

**Phase 2 — BOARD (leaderboard.html + player_detail.html)**
- Migrate the leaderboard table out of `.card.wc-card`. Bootstrap `.card` default (white) on the bone page substrate is the lift; `<thead>` and `.row-current-user` styles need light-substrate re-derivation.
- `.your-standing-tribune` already white — keep.
- `.table-worldcup` thead stays navy `var(--game-primary-dark) (#001040)` per locked decision Q3 — strongest USA pattern.
- The `.your-standing-tribune + .card.wc-card` gold-divider lock (S6.1.3 PI-1 at `test_design_p6_s6_1_3.py:113`) flips to red in lockstep with the surface migration.

**Phase 3 — ROSTER read-only (post-deadline desktop table)**
- The ROSTER edit form is already `.tier-card` white. Only the post-deadline read-only view wraps in `.card.wc-card`. Migrate that wrapper out.
- Pattern is the same as Phase 2's leaderboard migration; benefits from the conventions locked there.

**Phase 4 — SCHEDULE (light polish only)**
- SCHEDULE is already light-ish (3.5/5). Audit its match-row patterns against the locked Stats reference and align typography + spacing. No substrate change needed.

**Phase 5 — Cleanup + DESIGN.md/CLAUDE.md update**
- Once nothing uses `.card.wc-card` for content, retire the rule and its pattern-lock tests.
- Update CLAUDE.md's "dark `.card.wc-card` surface" notes — replace with the new Casual-Light pattern documentation.
- Update DESIGN.md to retire the Tribune-Dark primitive and codify the Casual-Light pattern with the accent rank doctrine. Brad drafts this section per his load-bearing-doc preference; the assistant restructures for the consuming tool.
- Run `$impeccable critique` on each of the 6 tabs to verify the score improvement.

---

## Decisions confirmed with Brad

1. **Pivot direction**: yes — move WC's body from "Tribune-Dark" to "Casual-Light." Dark navy hero stays as the WC signature.
2. **`.btn-game` red**: **global on WC**. `body.game-worldcup .btn-game` repaints red so every WC button reads red regardless of substrate.
3. **Leaderboard `<thead>`**: **stays navy, white body**. Strongest USA pattern.
4. **Migration order**: P0 → HUB → BOARD → ROSTER → SCHEDULE → cleanup. Each phase ships as its own PR.
5. **Accent rank-order**: red → white → blue → gold. Gold is **quaternary** — reserved for focus rings (a11y lock), champion banners, podium glow only.

---

## Files in scope

- `static/css/style.css` — every phase touches it; `.card.wc-card` shrinks, `.wc-stat-card` extends.
- `static/css/tokens.css` — likely unchanged.
- `DESIGN.md` — Phase 5 retires Tribune-Dark, codifies Casual-Light + accent rank.
- `CLAUDE.md` — Phase 5 updates the dark-card pattern lock note.
- WC templates:
  - `games/worldcup/templates/worldcup/home_shell.html` + `_home_pre.html` / `_home_live.html` / `_home_post.html` / `_home_out.html` (Phase 1)
  - `games/worldcup/templates/worldcup/leaderboard.html` + `player_detail.html` (Phase 2)
  - `games/worldcup/templates/worldcup/picks.html` (Phase 3 — read-only only)
  - `games/worldcup/templates/worldcup/schedule.html` (Phase 4)
- Pattern-lock tests:
  - `tests/test_design_p2_s2_4_1.py::test_is_lead_css_uses_red_rule_top_no_border` — updated in Phase 0 (gold→red flip)
  - `tests/test_design_p6_s6_1_1.py` — updates in Phase 1 (`.card.wc-card .wc-eyebrow` lock) / retires in Phase 5
  - `tests/test_design_p6_s6_1_3.py` — updates in Phase 2 (`.your-standing-tribune + .card.wc-card` gold-divider)
  - `tests/test_design_p6_s6_1_4.py` — updates in Phase 1 (`.commish-note-body` gold-top if in hub flow)
  - `tests/test_design_p2_s2_5_1.py` — referenced by CLAUDE.md; verify before Phase 1
- Reference card to clone: `.wc-stat-card` definitions in `style.css` around :4380+ and Stats template at `games/worldcup/templates/worldcup/stats.html`

## Verification (per phase)

Each phase ends with:
1. **Visual smoke**: dev server + `WC_FAKE_NOW` covering pre/live/post for the tab in question.
2. **Cross-tab smoke**: click HUB → ROSTER → BOARD → SCHEDULE → STATS → RULES in one session; the eye-test is "this is one game."
3. **Tests**: `pytest tests/test_design_*.py tests/test_worldcup_*.py`. Baseline 626 passing.
4. **Detector**: `npx impeccable --json games/worldcup/templates/worldcup/` should remain clean.
5. **Per-tab `$impeccable critique`**: re-score the tab; record the lift on the scorecard.

## What this strategy is NOT

- **A big-bang reskin in one PR.** Five tabs of color changes, dozens of pattern-lock test updates, and a re-derived recently-shipped polish at once = high regression risk.
- **Repainting `.card.wc-card` from dark to light.** Fights the existing pattern-lock tests, orphans the foreground carve-outs, and forces tests to flip in lockstep with templates. Migrating *off* the class is cleaner.
- **Lightening the hero.** The dark navy hero is the constant that already unifies all 6 tabs. The casual-light migration is below-hero only.
