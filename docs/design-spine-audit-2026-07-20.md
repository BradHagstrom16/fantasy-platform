# Design Spine Audit — 2026-07-20

**Scope:** currency + quality pass over the five design-spine documents, ahead of C1 (CFB-era lounge design).
**Deliverable:** the documents themselves. No UI changes, no token changes, no code changes.
**Status:** findings complete, awaiting Brad's rulings. **No edits applied yet.**

Documents audited:

1. `PRODUCT.md`
2. `DESIGN.md` (top level)
3. `games/cfb/DESIGN.md` (deepest pass — C1 builds on this)
4. `games/worldcup/DESIGN.md` (light touch)
5. `docs/impeccable-loader-customization.md`

---

## Executive summary

**The enforced contracts are healthy. The prose has drifted.**

573 design/asset/navbar test locks pass. Every rule the test suite actually enforces is intact. All the drift found in this audit lives in prose that no test covers — which is exactly why a manual pass was needed.

Severity distribution across 38 findings:

| Doc | Findings | Character of the work |
|---|---|---|
| `PRODUCT.md` | 3 | Line edits. One stale section with a dangling cross-reference. |
| `DESIGN.md` | 10 | Line edits. One dangerous falsehood (D1), several stale/wrong values. |
| `games/cfb/DESIGN.md` | 16 | **Structural rework.** Written pre-build, describes shipped work as forthcoming. |
| `games/worldcup/DESIGN.md` | 4 | Header note + two factual corrections. Doctrine untouched. |
| `docs/impeccable-loader-customization.md` | 5 | Line edits + one possible rename. Core thesis verified sound. |

**The two findings that matter most:**

- **D1** — top-level `DESIGN.md` §1.5 tells the reader the impeccable loader auto-discovers `games/*/DESIGN.md`. It does not, and the doc it cites as evidence exists specifically to record that the auto-discovery was retired. This actively causes agents to skip the per-game doctrine.
- **C3** — `games/cfb/DESIGN.md` documents `.cfb-stat-card` / `.is-lead` as "the foundational body component of the dark room." Neither exists. Three differently-named primitives do the job, using a **different color contract** than the doc specifies.

**The good news:** CFB's two hardest doctrinal rules (no `.cfb-hero-grad`, no gold in CFB) held everywhere in the shipped code, including in places the doc never anticipated — the admin masthead, form focus rings, the hero accent line. The CFB doc's *doctrine* survived implementation well. Its *tense* and *inventory* did not.

---

## Verification method

Every finding below is backed by evidence, not inference. What was checked:

- All five docs read in full, plus `CLAUDE.md` (treated as current per the 2026-07-20 future-focus rewrite).
- Doc claims grepped against `static/css/tokens.css`, `static/css/style.css`, `templates/`, `games/*/templates/`, `games/registry.py`.
- Cross-references followed to confirm targets exist (several do not).
- Contrast ratios computed independently with the WCAG 2.x relative-luminance formula, not taken from CSS comments. The CFB numbers were computed twice, by separate passes, and agree exactly.
- Git history checked to establish what shipped when (`22e0c0c`, `70e5c23`, `5b4a336`, and the A2–A6 series).
- `ENVIRONMENT=testing pytest -k "design or cfb_dark or logo or asset_versioning or navbar"` → **573 passed**.

Where a claim could not be resolved without a design judgment, it is listed under "Decisions needed" rather than silently resolved.

---

## Decisions needed from you

These block the edits. Everything else I can apply once you say go.

### Substantive (design rulings — I should not make these for you)

| # | Decision | Context | My lean |
|---|---|---|---|
| **R1** | **C3 — CFB lead emphasis.** The doc specifies `.is-lead` with a `2px solid var(--game-primary)` **crimson** top rule. The shipped code (`.cfb-verdict`) uses a 2px top rule colored by **survivor state** (`.is-survived` / `.is-lost` / `.is-pending`), never crimson. Which is doctrine? | The shipped choice is arguably *better* — it keeps crimson as identity-only per the Crimson-Is-Identity Rule, and lets outcome carry outcome. But it was never recorded as a decision. | Ratify the shipped behavior as doctrine and name it. But this is your call. |
| **R2** | **C16 — What does the CFB *room* own?** C1 must design a lounge signature surface that does not duplicate the CFB room's hub. The WC doc states this contract explicitly ("the lounge owns the rank dossier; the hub does not mirror it"). CFB's doc has no equivalent, so there is nothing to differentiate against. | This is the single biggest C1 blocker. | **You draft the substance; I restructure.** Per your usual spine-doc practice. |
| **R3** | **D4 — Golf side-stripe.** `.table-golf .row-current-user > td` carries `border-left: 3px solid var(--game-accent)`, with a code comment calling it deliberately retained. CFB and WC both use tint-only. §6's ban names "cards, list items, callouts, or alerts" — not table rows. Sanction it, or record it as debt? | Golf's UI phase (~Jan 2027) hasn't happened yet. | **Record as debt.** Three games converging on tint-only is worth more than one retained stripe. |

### Factual (need a call, but low stakes)

| # | Decision | Context | My lean |
|---|---|---|---|
| **R4** | **D6 / W3 — which WC navy is canonical?** Both DESIGN.md frontmatters say `#002868`. `tokens.css` says `--wc-navy: #001A4D` and always has. But `style.css` uses literal `rgba(0,40,104,…)` (= `#002868`) in ~10 places, commented "literal WC navy." Two real values. | Canonicalize `#001A4D` and document `#002868` as the legacy literal, or reconcile the literals in code later? | Canonicalize `#001A4D`, document the legacy. Don't touch code — WC surfaces are frozen. |
| **R5** | **C10 — `instance/seed_cfb_sandbox.py`.** §6's primary CFB smoke procedure references this seeder. It is not in the checkout (correctly gitignored, but absent). | Rewrite §6 to describe seeding generically, or commit the seeder somewhere runnable? | Rewrite §6 generically. A gitignored artifact should not be load-bearing in doctrine. |
| **R6** | **C13 — `.cfb-eyebrow-crimson`.** Defined in CSS, instructed twice in the doc, used **zero** times in templates. The implementation concluded there is no valid site for it. | Keep as sanctioned-but-unused, or retire? | Keep, but narrow the doc guidance to match the stricter CSS comment. |
| **R7** | **L5 — rename the loader doc?** `docs/impeccable-loader-customization.md` is named for a customization that no longer exists and opens by apologizing for its own name. Content is really "the per-game DESIGN.md convention." | Rename to `docs/per-game-design-doc-convention.md` and update two referrers (`CLAUDE.md`, `DESIGN.md` §1.5)? | **Yes, rename** — we're already editing both referrers. Don't carry the apology into the CFB era. |
| **R8** | **P3 — add `## Platform: web` to PRODUCT.md?** Absent is already treated as `web`, so behavior is correct either way. | Purely defensive explicitness. | Optional. Add it; it's one line. |

### Process

| # | Decision | My recommendation |
|---|---|---|
| **R9** | How to handle `games/cfb/DESIGN.md`? It needs structural rework, not line fixes. | Split: I do the mechanical half alone (tense, hexes, metrics, inventory, admin section, a11y column). You draft the substance for **R1** and **R2**; I restructure it into the doc. |

---

## Findings

### 1. PRODUCT.md

| # | Severity | Finding |
|---|---|---|
| P1 | High | Stale section + dangling cross-reference |
| P2 | Low | "hosts today" list doesn't reflect the archived/flagship split |
| P3 | Low | No `## Platform` field (see R8) |

**P1 — "Known Surface Constraints" is stale, and its cross-reference goes nowhere.**

- **Current:** §Accessibility cites `.card.wc-card { background: rgba(0, 17, 46, .8); }` as "a documented recurring legibility risk," then says *"See CLAUDE.md, '`.card.wc-card` is a dark navy surface' for the locked pattern."*
- **Reality:** No bare `.card.wc-card` rule exists in `style.css` (retired in P5). That exact value now lives on `.wc-champion-banner` (`style.css:10422`). `grep wc-card CLAUDE.md` returns **zero** matches — the pointer is dead.
- **Proposed:** Rewrite around what is now true *and larger than before*. The principle survives; the example is obsolete. Name the three current dark substrates (`.wc-champion-banner`, the entire `body.game-cfb` midnight room, auth backdrops), state the scoped-lift rule, and add the two live invariants PRODUCT.md currently omits: the `:root { --bs-secondary-color }` redirect protecting `.text-muted` on bone, and the ban on raw `color: var(--text-muted)` on bone/white.
- **Why:** This is the section a designer consults before putting text on a dark surface, and CFB just made dark surfaces the default for the flagship. Pointing it at a retired class trains readers to distrust the doc.

**P2 — "Examples of what CCC hosts today."** Flat list, no status. WC concluded 2026-07-19 and is archived; CFB is the active flagship; Golf launches ~Jan 2027. Keep the list (format range is the point), add one clause on current era. Do **not** add a status table — `games/registry.py` is the SSoT.

**P3 — No `## Platform` field.** See R8.

---

### 2. DESIGN.md (top level)

| # | Severity | Finding |
|---|---|---|
| **D1** | **Highest** | §1.5 claims the loader auto-discovers per-game files. False, and self-contradicting. |
| D2 | High | §1.5 lists CFB doctrine as "(planned)" — it shipped |
| D3 | High | §6 describes an already-paid debt as outstanding |
| D4 | Ruling | A *real* remaining side-stripe the ban doesn't address (see R3) |
| D5 | Medium | §5 states the wrong WC current-user accent |
| D6 | Ruling | Frontmatter `wc-navy` contradicts the token (see R4) |
| D7 | Medium | Frontmatter `cfb-midnight` doesn't match the shipped room |
| D8 | Medium | §4 documents 4 of 9 shadow tokens |
| D9 | Low | §3's caption-floor exception list is a scope leak |
| **D10** | **High** | The lounge/room architecture is absent from the design spine — **C1 blocker** |

**D1 — The loader does not auto-discover per-game DESIGN.md files.**

- **Current:** *"the impeccable skill loader discovers `games/*/DESIGN.md` automatically (see `docs/impeccable-loader-customization.md` for the loader's discovery contract)."*
- **Reality:** Flatly false, and self-contradicting — the cited doc exists specifically to record that auto-discovery was **retired on 2026-05-29**. Verified against `scripts/context.mjs` (no `games/*` discovery) and against this session's own loader run, which emitted top-level `PRODUCT.md` + `DESIGN.md` only.
- **Proposed:** Replace with the actual contract: loader emits top-level only; per-game layering is enforced by the `CLAUDE.md` hard rule; read `games/<slug>/DESIGN.md` manually.
- **Why this is the worst finding in the doc:** it is not ordinary staleness. It tells an agent the game file will arrive on its own, so the agent does not go read it, and produces CFB design output with **zero CFB doctrine loaded**. It directly defeats the layering the section is trying to establish.

**D2 — §1.5 lists CFB as "(planned)."** Shipped in `22e0c0c` (PR #85); 40 KB of doctrine. Golf's "(planned)" is still correct. Promote CFB to a real entry mirroring WC's shape: the dark-first room, midnight ramp, crimson accent rank, survivor-state layer, Survivor voice, `.championship-hero`.

**D3 — §6 describes paid debt as outstanding.** The Don't says the `.card.border-success` / `-danger` / `-warning` / `-primary` rules "violate the impeccable absolute ban on side-stripe borders; they should migrate to full borders…". They already did: `style.css:8881-8884` are `border: 1px solid …` + background tints, exactly the prescribed fix. Restate as settled convention. *A doc that flags fixed problems teaches readers to skim its warnings.*

**D4 — A real remaining side-stripe.** `style.css:3448` — `.table-golf .row-current-user > td { border-left: 3px solid var(--game-accent) }`, with an in-code comment calling it deliberately retained. The platform fallback (`3457`), CFB (`3748`), and WC (`5775`) are all tint-only. §6's ban names "cards, list items, callouts, or alerts" — table rows unaddressed. **See R3.**

**D5 — §5 Tables states the wrong WC accent.** Doc: *"CFB uses crimson tint, WC uses gold tint."* Reality: WC uses **red** — `rgba(191,10,48,.14)` (`style.css:5775`), with `style.css:11404` commenting "red = competitive emphasis per the WC accent rank." Gold would contradict the Gold-Quaternary Rule this same doc endorses. CFB crimson is correct.

**D6 — Frontmatter `wc-navy: "#002868"`.** `tokens.css:27` says `--wc-navy: #001A4D`, and has since the tokens were introduced (`4fd53ed`); `#002868` has **never** been in `tokens.css`. `CLAUDE.md` also documents `#001A4D`. But `style.css` uses literal `rgba(0,40,104,…)` (= `#002868`) in ~10 places, with `style.css:5832` calling it "literal WC navy." **See R4.**

**D7 — Frontmatter `cfb-midnight: "#0F0F1A"`.** Shipped room is a warm crimson-black ramp: `--cfb-canvas: #0E0A0C`, `--cfb-surface: #150F12` (`style.css:3586-3589`). `#0F0F1A` is *cool*-tinted — the opposite of the doc's own "warm, never WC's cool navy" reasoning. (`CLAUDE.md` repeats `#0f0f1a`; worth fixing there in a later pass.)

**D8 — §4 Shadow Vocabulary documents 4 of 9 tokens.** Undocumented: `--shadow-lift-strong`, `--shadow-navbar`, `--shadow-dropdown`, `--shadow-sticky-up`, `--shadow-btn-primary-hover`. The last is even commented "(DESIGN.md §Buttons)" — but §5 Buttons hardcodes the literal `0 4px 14px rgba(58, 29, 114, 0.3)` rather than naming the token that exists for it. *An undocumented token gets re-invented as a literal; that is how a shadow scale rots.*

**D9 — §3's caption-floor exception list is a scope leak.** The platform-foundation section enumerates WC-specific class names (`.tier-mobile-card-picks`, `.tier-teams-list`, `.wc-microcaption`, `.player-pick-card …`). Keep the *principle* at platform level; move the WC class list into `games/worldcup/DESIGN.md`. Otherwise every game's exceptions accrete into the foundation doc.

**D10 — The lounge/room architecture is absent from the design spine.**

- §5 documents `.home-shell` card recipes (Ceremonial vs Informational, `.ballot-card`, `.dossier`) as platform foundation. But the *architecture* those recipes serve — lounge vs room, substrate distinction as by-design separation, "dominated by whichever single game is currently live" — appears nowhere in `DESIGN.md`. §1 mentions "lounge" once, poetically.
- That doctrine currently lives only in `CLAUDE.md` (an engineering doc) and the transition plan. Meanwhile every `.home-shell` recipe consumer is a WC-era lounge partial, and transition plan §5 will split them per game.
- **Proposed:** Add a short §1.6 "Lounge and rooms" stating the architecture, and annotate §5's recipes with which are reusable platform vocabulary vs WC-lounge specifics that C2 will move.
- **Why:** C1 *is* lounge design. A designer reading the design spine end-to-end would not learn that the lounge and the rooms are deliberately different substrates — the single most load-bearing fact about the surface they are about to design.

---

### 3. games/cfb/DESIGN.md — deepest pass

**Headline:** the doc's doctrine survived implementation remarkably well. Its two hardest rules (no `.cfb-hero-grad`, no gold in CFB) held everywhere, including places the doc never anticipated. What did not survive is its **tense** and its **inventory** — it is a pre-build plan describing work as forthcoming, and it catalogues **3 of the 101** `.cfb-*` classes that shipped.

| # | Severity | Finding |
|---|---|---|
| C1 | High | Header dependency block describes a resolved tension as unresolved |
| C2 | High | Six more "A2 will…" deferrals for work that shipped (A2–A6) |
| **C3** | **Highest** | `.cfb-stat-card` / `.is-lead` documented as foundational — **never built** (see R1) |
| **C4** | **Highest** | 15 class families, ~97 classes, entirely undocumented |
| C5 | High | The entire admin cluster is invisible to the doc |
| C6 | High | `cfb-bone-subtle` hex is wrong **and fails the doc's own AA target** |
| C7 | Medium | `.cfb-eyebrow` letter-spacing nearly 2× off |
| C8 | High | Three undocumented tokens + the whole rebase block |
| C9 | Medium | `.elimination-alert` "known debt" is paid |
| C10 | Ruling | `instance/seed_cfb_sandbox.py` does not exist (see R5) |
| C11 | Medium | Two survivor-state colors have text-use limits the doc doesn't state |
| C12 | Low | `.badge-pending` shipped as a named class with undocumented doctrine |
| C13 | Ruling | `.cfb-eyebrow-crimson` defined, instructed, used zero times (see R6) |
| C14 | Note | Five classes used in templates with no CSS rule (code debt, not a doc fix) |
| C15 | Low | Em-dash rule wording looser than platform, reads as self-violating |
| **C16** | **High** | Doc says nothing about CFB's presence in the lounge — **C1 blocker** (see R2) |

#### Stale planning voice

**C1 — The header's most prominent warning describes a resolved tension as unresolved.** The block reads *"Platform-foundation dependency (resolve on `main`, not in this PR): … Until that companion edit lands on `main`, this file and the top-level Don't are in tension; the carve-out is a required follow-up, not optional."* It landed in `70e5c23`; `DESIGN.md:394` now carries the carve-out and names CFB by example. Delete the block; replace with one line stating the top-level §6 carve-out sanctions this room.

**C2 — Six more deferrals to a phase that completed.** L9 "A2 tunes exact values"; L170 "A2 sets final copy"; L194 "A2 fixes it"; L200 "the CSS is built / reconciled in A2"; L253 "A2 migrates it"; L309 the sandbox seeder. A2.0 through A6 plus A3-admin all shipped (`5b4a336`, `e24807e`, `c6c7dc1`, `7e0ff09`, `55fdd9a`, `b7bb814`, `3d84861`), locked by six design test files. The L170 H1 table is no longer "illustrative" — it is shipped copy, verbatim: "The Survivors", "Saturday's Verdict" / "The Cut", "Your Card", "Take Your Two Lives". The L194 em-dash violation it cites was fixed. Convert every deferral to present-tense description.

#### The big one

**C3 — `.cfb-stat-card` and CFB's `.is-lead` do not exist.**

- **Doc:** a full §4 subsection calling `.cfb-stat-card` *"the foundational body component of the dark room and the doctrinal model for how CFB renders information density."* Specifies substrate, hairline, internal order, and `.is-lead` lifting to `--cfb-raised` with a `2px solid var(--game-primary)` **crimson** top rule. §2 references `.cfb-stat-card.is-lead` twice as a crimson consumer.
- **Reality:** zero matches in `style.css`, zero in templates. The only `.is-lead` in the codebase is WC's. `--cfb-raised`'s own CSS comment still points at a selector never authored for CFB.
- **What shipped instead:** `.cfb-verdict` implements the mechanic under a different name and a **different color contract** — raised surface + 2px top rule, but the rule is survivor-state colored (`.is-survived` / `.is-lost` / `.is-pending`), never crimson. `.cfb-week-summary` and `.cfb-season-lead` are the other family members.
- **Why it matters most:** the implementation made a real doctrinal decision — *lead emphasis in CFB is carried by outcome color, not identity crimson* — which is arguably better than the doc's, and is nowhere recorded. C1 will read the doc, reach for `.cfb-stat-card.is-lead`, and find nothing. **See R1.**

#### Inventory gap

**C4 — 15 class families, ~97 classes, undocumented.** §4 documents 3 real `.cfb-*` classes plus one that doesn't exist. Shipped and absent from the doc:

| Family | Representative classes |
|---|---|
| Hero content | `.cfb-hero`, `.cfb-hero-field`, `.cfb-count`, `.cfb-count-cut` |
| Status row | `.cfb-status-row/-item/-num/-label`, `.cfb-deadline` |
| Current-user identity | `.cfb-you-tag` |
| Pick / slate | `.cfb-holding`, `.cfb-slate-head`, `.cfb-matchup`, `.cfb-confirm-pick`, `.cfb-empty-slate` |
| Verdict | `.cfb-verdict` (+ `.is-survived`/`.is-lost`/`.is-pending`) and 8 sub-elements |
| Week summary | `.cfb-week-summary`, `.cfb-summary-stat/-num/-label/-sep` |
| The Cut | `.cfb-cut-title/-list/-player` |
| Field ledger | `.cfb-field-table/-head/-week`, `.cfb-avatar`, `.cfb-auto-tag` |
| Pick distribution | `.cfb-distribution`, `.cfb-dist-*` |
| Season / My Picks | `.cfb-season-lead/-main/-aside`, `.cfb-ledger-total` |
| Team pool | `.cfb-team-pool`, `.cfb-team-chip`, `.cfb-used-grid` |
| Coverage | `.cfb-coverage`, `.cfb-coverage-*` |
| Notes | `.cfb-spread-note`, `.cfb-board-note` |
| Join | `.cfb-join-rules/-form/-stake/-lives/-entry` |
| Admin | `.cfb-admin-masthead/-title/-sub/-chip` |

`.cfb-hero-field` / `.cfb-count` carry the "who is left standing?" answer that §1 names as one of the product's three primary questions — undocumented.

**C5 — The entire admin cluster is invisible to the doc.** Eight admin templates, ~200 lines of dedicated CSS ("the Commissioner's Desk"), a test lock (`tests/test_cfb_admin_a3.py`). §6's smoke path lists five user screens and stops. The admin block encodes real CFB doctrine found nowhere in the doc:

- admin keeps a **functional** H1 (a deliberate exception to the Survivor voice rule);
- the platform's gold masthead rule + gold eyebrow + purple H1 go **crimson rule / bone-muted eyebrow / bone-white H1** here (Crimson-Ceremony Rule applied to admin);
- a **crimson focus ring** replaces the platform gold ring;
- destructive actions use a restrained lost-red **outline, never a filled red shout** (Cold-Elimination register);
- inputs sit a step *deeper* than their card (canvas, not surface) so the field reads as an inset well.

That doctrine is good and should not live only in CSS comments.

#### Wrong values

**C6 — `cfb-bone-subtle: "#8A817C"` is wrong, and fails the doc's own AA target.** Shipped value is `#938980` (`style.css:3597`). Computed independently, twice: the doc's `#8A817C` lands **4.28:1 on `--cfb-lifted`** — below the 4.5:1 floor the doc states on that very line. The shipped value clears at 4.76:1. *The doc publishes a hex that would break the room's stated a11y floor if implemented from.*

**C7 — `.cfb-eyebrow` metrics.** Doc says "~`0.7rem`, letter-spacing ~`0.08em`". Shipped: `.8rem` / `.15em` — tracking is nearly 2× off. Weight (500) and case match.

**C8 — Undocumented tokens and the rebase block.**
- `--cfb-hairline-strong` (`rgba(243,239,230,.14)`) is load-bearing across card hover, alerts, `.cfb-verdict`, admin buttons, form controls. The doc documents a one-step hairline; a two-step scale shipped.
- `--game-primary-dark: #1A0B0D` is an undocumented fifth ramp step (the hero gradient origin).
- §2's "Token strategy" names six rebased tokens illustratively. Shipped: eight platform tokens, **seven Bootstrap base tokens**, and a **neutralized three-step shadow scale**. The Bootstrap rebase and shadow neutralization are the two hardest-won pieces of the dark foundation and appear nowhere in the doc.

**C9 — `.elimination-alert` "known debt" is paid.** Migrated off the side-stripe to a full-container treatment (`style.css:3855-3868`). Same class of error as D3.

**C10 — `instance/seed_cfb_sandbox.py` does not exist.** §6's primary smoke procedure for the flagship game references an artifact not in the checkout. The gitignore claim is correct; the file is simply absent. **See R5.**

#### Missing a11y constraints the code discovered

**C11 — Two survivor-state colors have text-use limits the doc doesn't state.**

Contrast ratios, computed independently (WCAG 2.x):

| Foreground | canvas `#0E0A0C` | surface `#150F12` | raised `#1E1518` | lifted `#281D20` |
|---|---|---|---|---|
| `--cfb-bone` `#F3EFE6` | 17.14 | 16.50 | 15.57 | 14.22 |
| `--cfb-bone-muted` `#B4AAA4` | 8.64 | 8.32 | 7.85 | 7.17 |
| **doc** `bone-subtle` `#8A817C` | 5.16 | 4.97 | 4.69 | **4.28 ✗** |
| **shipped** `bone-subtle` `#938980` | 5.74 | 5.53 | 5.21 | 4.76 ✓ |
| `--cfb-lost-life` `#E63946` | 4.72 | 4.54 | **4.29 ✗** | **3.92 ✗** |
| `--cfb-eliminated` `#6E625F` | **3.35 ✗** | **3.22 ✗** | **3.04 ✗** | **2.78 ✗** |
| `--cfb-crimson-bright` `#E8282F` | **4.47 ✗** | **4.31 ✗** | **4.06 ✗** | **3.71 ✗** |

- `--cfb-lost-life` clears AA **only on canvas and surface**. The CSS knows: `.spread-badge` and destructive admin buttons are deliberately placed on surface with comments explaining why. §2's table presents the color unconditionally.
- `--cfb-eliminated` **never clears AA as text on any ramp step**. The CSS only ever uses it as a background (with white on top) or as a border — both correct. The doc presents it as a plain palette color with no prohibition.
- **Proposed:** add a use-constraint column to §2's survivor-state table. This is exactly what lounge design will get wrong.

#### Minor

**C12 — `.badge-pending` shipped as a named class** (doc names bare `PENDING` text). Its CSS records a decision the doc never captured: hollow outline so it reads distinct from the filled chips **by structure, not hue** — the Crimson-Is-Identity Rule applied. Worth promoting into the doc. Ships a second label variant `TBD`, also undocumented.

**C13 — `.cfb-eyebrow-crimson` defined, instructed twice, used zero times.** See R6.

**C14 — Five classes used in templates with no CSS rule:** `cfb-cell-player`, `cfb-cut-avatar`, `cfb-cut-name`, `cfb-pay-status`, `cfb-verdict-main`. Unclear whether intentional hooks or leftovers. **Not a doc fix** — flagging as code debt.

**C15 — Em-dash rule wording.** L294 says "in CFB copy," where the platform docs say "in UI copy, error messages, button labels, and any prose generated for CCC surfaces." CFB's own doc prose contains 100 em dashes — fine under the platform scoping, but self-violating under CFB's looser wording. Tighten to match.

#### The C1 readiness gap

**C16 — The doc says nothing about CFB's presence in the lounge.**

- CFB's only lounge mention is a negative: *"never touch the lounge."*
- By contrast, `games/worldcup/DESIGN.md` carries an explicit differentiation contract: the lounge owns the rank-trend dossier; the hub must **not** mirror it; the hub leans into multipliers instead. That contract is *why* the two surfaces read as distinct rooms.
- CFB has no equivalent. C1 must design a lounge signature surface that does not duplicate the CFB room's hub — but the doc never says what the room's hub owns, so there is nothing to differentiate from.
- **Proposed:** add a "CFB and the lounge" subsection stating what the CFB *room* owns (the weekly decision, the field ledger, the verdict), giving C1 a boundary to design against. Pairs with D10. **See R2.**

---

### 4. games/worldcup/DESIGN.md — light touch

Frozen game. Doctrine untouched; corrections only.

| # | Severity | Finding |
|---|---|---|
| W1 | Medium | No archived-status header note |
| W2 | Medium | Frontmatter `wc-champion-banner-bg` contradicts the doc's own body |
| W3 | Ruling | Same `wc-navy` issue as D6 (see R4) |
| W4 | Trivial | Bare-filename citation |

**W1 — Archived-status header.** Add 2–3 lines to the existing header blockquote only: tournament concluded 2026-07-19; surfaces frozen per `CLAUDE.md`; this doc is archive doctrine plus the regression net under the lounge extraction; edit only for a revival or the planned lounge move. **No body changes.**

**W2 — Frontmatter contradicts its own body.** Frontmatter says `wc-champion-banner-bg: "#001A4DCC"` (= `rgba(0,26,77,.8)`). §4 body text says `rgba(0, 17, 46, .8)`. `style.css:10423` confirms the **body** is right. Correct the frontmatter to `#00112ECC`. Pure factual fix, not a doctrine edit.

**W3 — `wc-navy: "#002868"`.** Resolve consistently with R4.

**W4 — Bare-filename citation.** §2's tier table cites `WORLD_CUP_GAME_DESIGN.md`; it lives at `games/worldcup/WORLD_CUP_GAME_DESIGN.md`. Make it path-qualified.

---

### 5. docs/impeccable-loader-customization.md

| # | Severity | Finding |
|---|---|---|
| L1 | — | Core claims **verified sound** |
| L2 | Medium | "Currently only `games/worldcup/DESIGN.md` exists" |
| L3 | Low | Presents v3.5.0 as the current loader |
| L4 | Medium | **New:** the documented invocation path does not work in this repo |
| L5 | Ruling | The filename now misleads (see R7) |

**L1 — Verified sound.** Stock loader emits top-level only (no `games/*` discovery in `context.mjs`); `.agents`-canonical / `.claude`-symlink topology intact; `.gitignore:44` blocks stray project-local copies. The doc's central thesis holds.

**L2 — Stale inventory.** CFB shipped. Update to name both, and note Golf is expected ~2027.

**L3 — Version.** Installed is v3.9.1. The v3.5.0 reference is legitimate *history* (when the patch was retired); reword so it reads as history, and note the discovery contract was re-verified against 3.9.1 on 2026-07-20.

**L4 — New: capture the invocation gotcha.** The impeccable setup step instructs `node .agents/skills/impeccable/scripts/context.mjs`. That project-relative path **does not exist in this repo** and fails with `MODULE_NOT_FOUND` — it cost a failed tool call at the start of this very session. The working invocation is the skill base dir: `node ~/.claude/skills/impeccable/scripts/context.mjs`. Add a short "Running the loader in this repo" section; this doc is its natural home, and it is a recurring per-session tax.

**L5 — Filename.** See R7.

---

## Recommended next steps

### Your move (blocking)

- [ ] **R1** — rule on CFB lead emphasis (crimson vs survivor-state). *Substantive.*
- [ ] **R2** — draft what the CFB **room** owns, so C1 has a lounge boundary. *You draft; I restructure.*
- [ ] **R3** — Golf side-stripe: sanction or debt.
- [ ] **R4** — canonical WC navy.
- [ ] **R5** — CFB sandbox seeder: rewrite §6 or commit the seeder.
- [ ] **R6** — `.cfb-eyebrow-crimson`: keep or retire.
- [ ] **R7** — rename the loader doc?
- [ ] **R8** — add `## Platform: web` to PRODUCT.md?
- [ ] **R9** — confirm the split approach for `games/cfb/DESIGN.md`.

### My move (once you've ruled)

Sequenced so the cheap, unambiguous work lands first and the CFB rework has your rulings in hand.

- [ ] **Step 1 — the four line-edit docs.** `PRODUCT.md` (P1–P3), `DESIGN.md` (D1–D9), `games/worldcup/DESIGN.md` (W1–W4), loader doc (L2–L5). All mechanical once R3/R4/R7/R8 are settled.
- [ ] **Step 2 — `DESIGN.md` §1.6 "Lounge and rooms."** Depends on nothing; unblocks C1 independently of the CFB doc.
- [ ] **Step 3 — `games/cfb/DESIGN.md`, mechanical half.** Tense throughout, hexes (C6), metrics (C7), delete resolved dependencies (C1, C2, C9), token documentation (C8), class-family inventory (C4), admin subsection (C5), a11y constraint column (C11), C12/C15.
- [ ] **Step 4 — `games/cfb/DESIGN.md`, substantive half.** Restructure your R1 and R2 drafts into §2/§4 and a new lounge-boundary subsection.
- [ ] **Step 5 — self-review + verification.** Re-run the 573 design locks (docs shouldn't move them, but confirm), re-grep every hex and class name asserted in the edited docs against the code, and confirm no cross-reference points at a nonexistent target — that was the root cause of P1, D1, and C10.
- [ ] **Step 6 — commit on `main`** (spine-doc discipline), then fast-forward the `fantasy-cfb-prep` worktree.
- [ ] **Step 7 — mutual sign-off** that the spine is ready, so C1 starts with no doc caveats.

### Deliberately out of scope

Noted here so they don't get silently absorbed:

- **C14** — five template classes with no CSS rule. Code debt; needs a separate look.
- **D7 follow-on** — `CLAUDE.md` also carries the stale `#0f0f1a` CFB midnight and would benefit from the same correction. Separate pass; `CLAUDE.md` was just rewritten and I'd rather not churn it in the same session.
- **The `#002868` literals in `style.css`** — if R4 canonicalizes `#001A4D`, reconciling ~10 literal `rgba(0,40,104,…)` usages is a code change on **frozen WC surfaces**. Recommend documenting the legacy value and leaving the code alone.
- **Golf** — `games/golf/DESIGN.md` still doesn't exist and correctly remains "(planned)" for the ~Jan 2027 UI phase.

---

## Appendix: what was verified clean

Worth recording so the next audit doesn't re-check it.

- **573 design / asset-versioning / navbar / CFB-dark test locks pass.**
- **Zero** `background-clip: text` rules in `style.css` (4 grep hits are all comments affirming the ban). Gradient text remains fully retired.
- **Zero** raw `color: var(--text-muted)` in `style.css`. The bone-substrate invariant holds.
- CFB's two hardest rules held in shipped code: **no `.cfb-hero-grad`** (the only grep hit is a comment affirming the ban) and **no gold in CFB** — including in the admin masthead, form focus rings, and hero accent line, none of which the doc anticipated.
- The hero halftone-dot overlay **was** scoped to crimson as the doc directed, and went further (accent line, ambient glow, `.lead` contrast lift all retuned).
- `.subnav-cfb` values match the doc exactly (`#0a080f`, `#C5050C`, `197,5,12`).
- `.championship-hero` composition matches, including the `clamp()` staying within the platform ≤6rem display ceiling.
- Top-level `DESIGN.md` §5 Navigation and Auth Surface Composition claims all verified against `templates/base.html`, `core/auth/templates/auth/`, and `style.css`.
- Radius tokens (`--radius` `.5rem`, `--radius-lg` `.875rem`) match §5.
- CFB H1 Survivor-voice copy shipped verbatim as the doc's table specified.
