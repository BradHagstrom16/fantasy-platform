# CFB-Era Lounge Design (C1)

**Status:** RULED — design complete 2026-07-20; ready for C2 implementation (transition plan §5/§8 Phases 2–4).
**Produced by:** the C1 design session (impeccable shape), per `docs/superpowers/plans/2026-07-20-cfb-era-transition-plan.md` §5.
**Governing docs:** `games/cfb/DESIGN.md` §3/§4/§8 (the lounge contract this spec executes), top-level `DESIGN.md` §1.6 + §5 (card recipes), the transition plan §5 (the seam + refactor contract).
**Visual companion:** `2026-07-20-cfb-era-lounge-design-mockup.html` (same directory) — all comps built from live `tokens.css` values; annotations in dashed mono chrome are commentary, not design.

**Brad's C1 rulings (2026-07-20, do not re-ask):**

1. **Live-state H1 = "Still Standing"** (court line carries week + field count).
2. **HELD summons stays Ceremonial**, calmer: gold border honest while the deadline still binds; calm comes from dropping the gold CTA and countdown dominance.
3. **Commissioner's Note renders full-width below the two-column pair** (S2.1.2 line-length lesson wins over §8.17's rail listing, which is treated as example, not principle).
4. **WC farewell strip is pre-state only** — the state machine retires it at season start; WC collapses to the archived tile permanently. (Finalizes transition-plan ruling 5.)

Carried-in settled constraints (earlier rulings; also do not re-ask): lounge substrate stays CCC purple/gold and CFB enters via content/copy/state only; no gold in CFB *room* surfaces (unchanged by this spec — the lounge is a platform surface and keeps its gold); no personal rank sparklines or any dossier analog (deliberate deletion); lead emphasis is outcome-colored, never crimson; controlled redundancy sanctioned (lounge summarizes, room completes); C2 merges early on main, rendering-identical, gated on the registry flip.

---

## 1. Scope and non-goals

This spec decides every design question for the CFB-era platform home (`/`): the state model, per-state composition, module specs, copy deck, color/contrast law, and the differentiation contract against the CFB room. C2 implements it behind the transition plan §5 seam without reopening design.

Non-goals: the CFB room (shipped), the WC room (frozen), the registry flip mechanics (§6 E), Golf. No new schema — everything below renders from `CfbWeek`, `CfbPick`, `CfbGame`, `CfbEnrollment`, `CfbWeekOutcome`, plus frozen WC data for the archive line.

---

## 2. State model

### 2.1 Lounge states (the dispatcher's vocabulary)

The four-state shell (`out` / `pre` / `live` / `post`) survives; only resolution changes. `cfb_lounge_state()` becomes the featured game's resolver behind the registry seam:

| State | Condition | Renders |
|---|---|---|
| `out` | not authenticated | Marketing surface (copy pass only, §4.1) |
| `pre` | authenticated; season not started (no `CfbWeek` has ever been active, or week 1 exists but picks not open) | The handoff: preseason decree + WC farewell + tiles (§4.2) |
| `live` | any week active or completed, season not concluded | The four-beat lounge (§4.3) |
| `post` | sole survivor exists (active enrollments == 1 with ≥ 1 eliminated), OR the final playoff week `is_complete` with > 1 active (tiebreak conclusion) | Terminal lounge (§4.4) |

`post` can begin mid-season (a sole survivor in week 9 ends the season then). The tiebreak variant must say so: never "sole survivor" language when cumulative spread decided it (`games/cfb/DESIGN.md` §1.10).

### 2.2 Live-state beats (per authenticated, enrolled, non-eliminated user)

Current week `W` = the `is_active` week; if none is active, the latest `is_complete` week (the aftermath window, which resolves to VERDICT).

| Beat | Condition | Summons register |
|---|---|---|
| **OPEN** | `W` active, now < deadline, no `CfbPick` for `W` | Ceremonial, ◈, gold CTA |
| **HELD** | pick exists, now < deadline | Ceremonial (calmer), ◇, outline CTA |
| **LOCKED** | now ≥ deadline, user's `CfbWeekOutcome` for `W` absent | Informational, ◇, text route |
| **VERDICT** | `CfbWeekOutcome` for `W` exists; persists until the next week's picks open | Informational, ◇, outcome word |

LOCKED sub-variants (one card, different meta line):

- **Upcoming:** "Kickoff Saturday, 3:30 PM CT."
- **In progress:** "In progress · Alabama leads, 21–17." (renders whatever the scores sync has; no promise of live cadence)
- **Final, unprocessed:** "Final: Alabama 31, Auburn 20. The official verdict follows." — no provisional life language, ever (§10.8).
- **Autopick pending** (no pick at deadline, autopick job not yet run): "Deadline passed. The Commish is assigning your pick under the missed-pick rule."
- **Autopick assigned:** "Georgia was assigned under the missed-pick rule." with the AUTO distinction preserved.

### 2.3 Precedence and variants

Champion (→ `post`) → **standing Eliminated** → beat (VERDICT → LOCKED → HELD → OPEN) → Preseason — with one nuance: **the elimination week renders as its VERDICT** (the ELIMINATED verdict card, §5.1); the standing eliminated module (§5.2) takes over when the next week opens. A countdown never shows "0m": expiry *is* the LOCKED condition.

- **Enrolled, eliminated:** standing eliminated module in the Summons slot; Who's Left and standings remain; no pick affordances anywhere.
- **Authenticated, not enrolled:** view-CTA variant in the Summons slot — "The pool is underway. 14 of 24 remain." + join CTA while the registry says joining is open (mirror the room's join policy; the lounge invents none) + "Follow the field ›". After joining closes: the field line + follow route only.
- **Revival week** (whole-pool wipe, §1.10): renders as a VERDICT variant — word `REVIVED` (live-green), sentence "Every remaining player lost in Week 9. The pool revives all who picked and lost. You continue with one life."
- **No Contest:** VERDICT variant — word `NO CONTEST` (bone-dim), sentence "Alabama's game was canceled. No life lost; the week counts as survived. Alabama stays used; the spread is excluded from your tiebreaker."

---

## 3. Module specs

### 3.1 The Summons (signature surface, anchor)

One identity across all four beats: eyebrow **`THE SUMMONS · WEEK N`** + a small state chip (OPEN/HELD/LOCKED/VERDICT — Teko, bordered, top-right; the OPEN chip borders gold, the rest bone-25%). Internal order per §8.9: state label → one decisive sentence (Teko ~2rem, warm white) → lives pips + deadline meta row → one action. It never carries the slate, spreads for browsing, or team choices — those are the room's.

Per-beat contract (copy deck in §6):

- **OPEN** — Ceremonial recipe. Eyebrow glyph ◈ (one of exactly two ◈ in the CFB era). Sentence: "You have not made a pick." Meta: pips + "Locks in 2d 14h · Saturday, 11:00 AM CT" (calm one-line countdown, tabular figures; relative + absolute; never the decree's big-numeral treatment — that is preseason-only). Action: **the metal-gold CTA** "Choose Team →" with sub-line "One team, win outright. Used teams stay used." Optional commissioner echo (italic, bone-mute): "Miss it and the Commish picks for you." — reinforcement only; the system states deadline and consequence itself.
- **HELD** — Ceremonial, calmer (ruling 2). ◇ eyebrow. Sentence: "Alabama is held." Support: "You may change your pick until Saturday, 11:00 AM CT." Action: outline "Review Pick". Never celebration, never "locked in".
- **LOCKED** — Informational recipe. Sentence: "Alabama at Auburn. Your pick is final." Meta per §2.2 sub-variant. No buttons; text route "Saturday's board ›" is optional and quiet.
- **VERDICT** — Informational recipe. The **verdict word** replaces the sentence slot: Teko 700, ~2.7rem, uppercase — `SURVIVED` (live-green) / `LOST A LIFE` (live-red; large-text-only law §7) / `ELIMINATED` (bone-white, cold — ash is never text). Then the factual sentence, updated pips, and the **field-impact line** (top-hairline-separated): "Three players lost a life in Week 8. Two were cut. 12 remain." + route "View week results ›". The field-impact line IS the recent-change module for launch (§8.13 stays deferred as a standalone).

**Gold CTA economy:** the metal-gold CTA appears in exactly two places in the CFB-era lounge — the OPEN summons and the pre-state decree. HELD gets outline; LOCKED/VERDICT get text routes. **◈ economy:** OPEN summons + champion banner, nothing else; every other eyebrow is ◇ or glyphless.

### 3.2 Who's Left (social anchor)

Informational recipe, rail position, `sec-head` "Who's Left" with a "The field ›" route. Phases resolve from data, never week numbers (thresholds are C2 constants, tunable):

- **A — no eliminations yet:** one line, no decoration: "The full field remains alive. **24** players, two lives each."
- **B — eliminations exist, active > max(10, half the field):** field line "**14** of 24 remain." + the **attrition band** — a single horizontal segmented bar: two-lives = solid `--live-green`, one-life = live-green at 40% alpha, out = ash at 55% alpha — with the count key directly beneath ("9 two lives · 5 one life · 10 out"; counts always adjacent, color never the sole carrier, `role="img"` + aria-label) + the cuts line: "Cut in Week 7: Tyler, Marissa."
- **C — active ≤ max(10, half the field):** the band yields to **names**: list rows of avatar + name + life pips, current-user row gold-tinted with the YOU chip, cuts line beneath.
- **D — active ≤ 4:** names carry the module: "**3** remain. One survives." + rows + the pick-reveal note post-deadline context line.

Banned here per §8.10/§8.14 and honored: no donuts, no percentages without counts, no trend arrows, no synthetic field-health scores.

### 3.3 Compact standings

Primary column, below the Summons (never above it — §8.11). Reuses the rolls silhouette: top-3 **active** players by official order + dot separator + the you-row when outside the top 3 (never force the full table to find yourself). Row anatomy: competition rank (rank 1 gold) · avatar + name (+ YOU chip) · tagline "Two lives · spread 61.0" · **life pips as the right-hand value** (points are a WC concept; lives are the CFB currency). You-row tint is the platform gold tint — never crimson (room-only). Official order and cumulative-spread formatting come from the room's central helpers; the lounge computes nothing itself (§10.5). Route: "Full standings ›".

### 3.4 Game tiles + the WC archived tile

The compact tiles strip generalizes (registry-driven; the WC-hardcoded block in `_game_tiles_compact.html` dissolves):

- **CFB (active):** existing `.cg--active` chrome; label from lounge state — `PRESEASON · SEP 3` / `WEEK 8 · 2 LIVES` (enrolled) / `WEEK 8 · LIVE` (not enrolled) / `ELIMINATED` / `CHAMPION · {name}` in post.
- **WC (archived, new `.cg--archived` treatment):** Informational-recipe chrome (bone-8% border on the 850→950 gradient), glyph desaturated ~55%, label bone-mute: `2026 · ESP WON · YOU 1ST` (enrollment-aware; anonymous/unenrolled: `2026 · ESP WON`). Links to the frozen WC post-state room. This is the permanent WC presence from season start onward (ruling 4).
- **Golf (coming soon):** unchanged dashed treatment, `2027`.

### 3.5 The farewell ledger strip (pre-state only — ruling 4)

One full-width Informational strip in the handoff composition: eyebrow `◇ THE 2026 LEDGER`, line "Spain took the Cup. The Commish took the pool." + finish fragment "You finished 1st of 9 · 487.0 pts" (enrollment-aware; omitted when unenrolled) + route "Visit the archive ›". Retired automatically when the state machine leaves `pre`. Data: frozen WC final match + final standings; read-only, no new WC queries beyond what `_context_post` already demonstrates.

### 3.6 The decree (generalized preseason primitive)

The decree is **platform lounge vocabulary** and generalizes rather than being rebuilt: seal band "By Decree of the Commish **No 002** · CFB Survivor '26" (the number increments per era — club continuity), H2 "First Pick Locks In", the big-days numeral (the only big-numeral countdown in the CFB era; weekly OPEN uses the calm one-liner), foot copy "Everyone starts with two lives. One team a week, win outright. Week 1 locks Saturday, Sep 5, 11:00 AM CT.", and the state-aware gold CTA: unenrolled → "Take Your Two Lives →" (join; sub "Join the pool. Lose twice and you're out."), enrolled → "Enter the Room →" (room landing). Countdown target: week 1's DB deadline when the row exists, else the `WEEK_1_START` constant with "first kickoff" copy.

### 3.7 Commissioner presence

Full-width Newsreader band below the two-column pair (ruling 3), reusing the existing admin-editable `commish_note_paragraphs` mechanism keyed by lounge state. Empty note = component absent (no empty card). Notes affecting deadlines, eligibility, or rules may additionally promote a one-line alert above the standings — never above the Summons.

---

## 4. Composition per state

### 4.1 `out` — copy pass only

Structure unchanged (hero, props, registry-driven join card, coming-soon rail). Copy: seal `◇ Open Court · CFB Survivor '26`; join-deadline line "Two lives. One pick a week. Season kicks off Thursday, Sep 3."; value props rewritten in survivor voice: "Survive the season" / "One pick a week, win outright. Lose twice and you're out." · "Outlast the field" / "Watch the pool thin every Saturday. Last one standing takes it." · "Read the Commish's Note" / (existing copy stays). Coming-soon rail now lists Golf only; WC appears nowhere on `out` (the archive is a members' surface).

### 4.2 `pre` — the handoff (single column)

Greet ("The club reconvenes, {name}" / H1 "The Season **Opens**" / court "Tuesday · 11 enrolled · first kickoff in 16 days") → decree (§3.6) → farewell strip (§3.5) → tiles (CFB `PRESEASON · SEP 3`, WC archived, Golf). No fabricated standings, no empty charts (§8.8).

### 4.3 `live` — the four-beat lounge

**Desktop:** two-column. Primary: greet → **Summons** (beat-resolved) → compact standings. Rail: **Who's Left** → tiles. Full-width below: Commissioner's Note (ruling 3). No deadline echo module in the rail — the Summons' deadline is one viewport away; duplicating it inside one screen is noise, not controlled redundancy.

**Mobile (single column, the narrative order — §8.17):** Summons → standings → Who's Left → tiles → Commish note. The unresolved pick is visible without scrolling. No sticky Choose Team at launch: the Summons opens the page; §8.17 sanctions a sticky later if real usage shows the need.

**Hierarchy by beat:** OPEN — the Summons dominates (gold CTA, ◈); nothing competes above it. HELD — calmer; standings and field may breathe. LOCKED — the lounge quiets; Who's Left and game status gain relative weight. VERDICT — the outcome word leads; field impact directly beneath; never buried.

**Greet:** "The pool plays on, {name}" (works for active and eliminated viewers) / H1 "Still **Standing**" (ruling 1) / court `{Weekday} · Week 8 · 14 remain`.

### 4.4 `post` — the terminal lounge

Sparse; ordinary modules removed (§8.8, ceremony by reduction). Greet ("The ledger closes, {name}" / "The 2026 **Season**" / court "One remained of 24 · the Commish records the year") → the champion banner: Ceremonial recipe, eyebrow `◈ SOLE SURVIVOR ◈`, name in Teko 700 gold-light (platform ceremony — gold is the lounge's, not the room's; the room's no-gold law stops at `body.game-cfb`), gold rule, evidence sentence (weeks survived, lives intact, field outlasted), detail line ("Final pick: Michigan, Week 14"). **Tiebreak variant:** eyebrow `◈ CHAMPION ◈`, evidence line leads with the mechanism: "Wins on cumulative spread: 41.5 against Jordan's 48.0." Never "sole survivor" for a tiebreak title. Below the banner: final Who's Left phase-D snapshot + route to full standings + tiles. Room analog (`.championship-hero`) remains distinct: midnight/crimson, no gold — two different rooms celebrating one fact.

---

## 5. Eliminated and view variants (live state)

### 5.1 Elimination verdict (the week it happens)

VERDICT card per §3.1: word `ELIMINATED` (bone-white), sentence "Alabama lost to Auburn. No lives remain. Your season ends in Week 8; the pool plays on.", drained pips (two hollow), routes "Follow who's left ›" · "Review my season ›". Cold, final, respectful — no alarm styling, no shame (the Cold-Elimination register crosses substrates as tone, not as component).

### 5.2 Standing eliminated module (every week after)

Informational card, quiet: eyebrow `◇ YOUR SEASON`, line "Out in Week 8. The pool plays on." (bone-dim, not white — reduced, not hidden), one supporting sentence naming the season path ("You survived seven weeks on Georgia, Texas, …"), the two routes. Who's Left and standings render normally — observation mode, never exile.

---

## 6. Copy deck

All UI copy: no em dashes or double hyphens; correct pluralization (1 life / 2 lives; 1 player remains / 2 players remain); survivor lexicon, no betting/tactical/hype language; the interface never manufactures drama.

| Slot | Copy |
|---|---|
| Greet pre / live / post | "The club reconvenes, {name}" / "The pool plays on, {name}" / "The ledger closes, {name}" |
| H1 pre / live / post | "The Season **Opens**" / "Still **Standing**" / "The 2026 **Season**" |
| Court pre / live / post | "Tuesday · 11 enrolled · first kickoff in 16 days" / "{Weekday} · Week 8 · 14 remain" / "One remained of 24 · the Commish records the year" |
| OPEN | "You have not made a pick." + "Locks in 2d 14h · Saturday, 11:00 AM CT" + [Choose Team →] |
| HELD | "Alabama is held." + "You may change your pick until Saturday, 11:00 AM CT." + [Review Pick] |
| LOCKED | "Alabama at Auburn. Your pick is final." + sub-variant meta (§2.2) |
| VERDICT win | SURVIVED + "Alabama defeated Auburn, 31–20. You advance with two lives." |
| VERDICT loss | LOST A LIFE + "Alabama lost to Auburn, 17–24. You have one life remaining. Your next loss eliminates you." |
| VERDICT elim | ELIMINATED + "Alabama lost to Auburn. No lives remain. Your season ends in Week 8; the pool plays on." |
| Field impact | "Three players lost a life in Week 8. Two were cut. 12 remain." |
| Who's Left A / D | "The full field remains alive. 24 players, two lives each." / "3 remain. One survives." |
| Cuts line | "Cut in Week 7: Tyler, Marissa." |
| Farewell | "Spain took the Cup. The Commish took the pool." · "You finished 1st of 9 · 487.0 pts" · "Visit the archive ›" |
| Errors (§8.18 verbatim) | "We could not confirm your current pick. Open the room to verify before the deadline." · "Standings are temporarily unavailable. Your pick and life status are unaffected." |

Route labels are §8.15's verbs exactly: Choose Team, Review Pick, View Week Results, Full Standings, Follow Who's Left, Review My Season, Visit the Archive. Numeric scores keep the en dash separator already shipped on WC surfaces ("31–20"); the Copy Discipline ban covers the em dash as prose punctuation, not numeric score separators.

---

## 7. Color and contrast law (lounge additions)

Computed against the purple ramp (`tokens.css` values), binding for C2:

| Foreground | purple-800 | purple-850 | purple-900 | purple-950 | Constraint on the lounge |
|---|---|---|---|---|---|
| `--live-green` #64DBA0 | 9.4 | 9.9 | 10.6 | 11.1 | unrestricted |
| `--live-red` #E63946 | 3.9 | 4.1 | 4.4 | 4.6 | **large/bold text only** (the verdict word qualifies; small text and captions never) |
| ash #6E625F | — | — | 3.1 | — | **never as text**; structure/segments only |
| `--gold` / `--gold-light` | 6.7 / 11.1 | 7.1 / 11.7 | 7.5 / 12.4 | 7.9 / 13.1 | unrestricted |
| `--bone-mute` (55%) | 5.1 | 5.2 | 5.4 | 5.5 | fine for captions ≥ 12px |

Rules: outcome color enters the lounge **only** through the platform live tokens (`--live-green`/`--live-red`) — never `--cfb-*` tokens, never crimson (crimson does not exist on the lounge, full stop). Hollow/filled pip structure carries life state before color. The attrition band always pairs with adjacent counts. The Ceremonial gold-30% border is decorative (1.7:1) and never the sole state carrier — the chip + eyebrow + CTA carry state.

## 8. Differentiation contract (what C2 must NOT build)

The lounge must never import: the midnight ramp or any `--cfb-*` surface token; crimson in any role; the room's `.cfb-pick-cta` composition (status row + slate adjacency); the room's verdict signature (2px outcome top rule on a raised surface — the lounge verdict is **typographic**, the word carries it); `.lives-indicator` (the lounge gets its own pip vocabulary, e.g. `.lounge-lives`, same structure grammar); the slate, spreads-for-browsing, or the used-team ledger; rank sparklines or any dossier analog (deleted, not pending); gold anywhere in the *room* (unchanged law — the boundary is `body.game-cfb`).

Shared with the room by design (controlled redundancy, §8.2): pick status, held team, deadline, lives, verdict, field counts, compact standings context — always the shortest useful version, always routed to the room for depth, both reading the same canonical state (§10.5; lounge computes nothing independently).

## 9. Data contract for C2 (context builder shape)

Per state, the CFB lounge builders need: **pre** — enrollment count, week-1 deadline (DB row else `WEEK_1_START`), user enrollment, WC archive line (champion + pool winner + viewer finish, from frozen WC data). **live** — enrollment (lives, eliminated, spread), current week + deadline + beat, pick + team + game (score/status/settled), `CfbWeekOutcome` for the verdict window, field aggregates (two-life/one-life/out counts, active total, last processed week's cuts by name), compact standings rows (top-3 active + viewer, official order from the room's central helpers), Who's Left phase inputs, commish paragraphs. **post** — champion (or tiebreak winner + both spread values), final field snapshot, viewer's season line. All time math through `games/cfb/utils.get_current_time()` (the `CFB_FAKE_NOW` seam); deadlines via `make_aware` (pool-tz columns). Beat + phase resolution implemented centrally (one resolver, §10.4), never per-template.

## 10. Accessibility, loading, empty states

DOM order matches visual priority (screen reader meets: state → action → deadline → field → standings → note). The attrition band is `role="img"` with a full-count aria-label; pips pair with text labels ("2 lives") everywhere. State chips are text, not color. Live regions announce verdict/lock transitions only — never countdown ticks. Countdown is the calm §6.14 form; at expiry the component *is* the LOCKED card. Unknown state renders as loading, never guessed ("no pick" is asserted only when known true — §8.18 error copy verbatim in §6). Empty branches: no eliminations → Who's Left phase A; no commish note → no component; no cuts → omit the cuts line.

## 11. Deferred (explicitly not in C2 launch scope)

Standalone Recent Change module (§8.13 — folded into the field-impact + cuts lines for now); sticky mobile Choose Team (§8.17 — sanctioned, not built); field-attrition history visualization (§8.14 — the band shows now, not history); any WC revival surfaces.
