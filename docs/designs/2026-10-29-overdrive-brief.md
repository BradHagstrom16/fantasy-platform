# Overdrive brief (2026-10-29)

The ready-to-paste prompt for the first `/impeccable overdrive` pass, and the `/design-review` that follows it. Written the day ADR-076 reset the motion and label doctrine, so the pass can use what the reset opened. Run it in a fresh session; this file is the whole handoff.

## Before you paste

- **Pick one target.** Overdrive does one moment, well. The options, best first:
  1. **The walk from the lounge into a room** (recommended; Brad's pick 2026-10-29). A cross-document View Transition: a headliner panel's head (`.hl-panel-link`, `core/main/templates/main/_hl_panel_head.html`) becomes the room's masthead (CFB `.page-hero.cfb-hero`, Docket `.page-hero.docket-hero`, golf `.golf-title`). It is a morph of the block, not of the words: the mark is the registry emoji, which no masthead carries, and the panel name is not the room's h1 ("Survivor" vs "The Survivors"), so the words crossfade inside the moving block. It is one moment, it uses a browser feature the Club has never used (only `/app` uses View Transitions, and only same-document ones), it degrades to an ordinary page load in Firefox, and it turns the dark lounge / light room split into the motion itself: you step through a door. It touches the lounge and all three rooms' mastheads, so it reads all four DESIGN.md files.
  2. **The CFB terminal moments**, newly open under ADR-076: the champion (`.championship-hero`, `games/cfb/templates/cfb/index.html`; the lounge's `.champ-banner`), the member's own elimination, the CFP reset. The champion may use particles or confetti in crimson and bone. Rare by nature: one champion a season, so verify with `CFB_FAKE_NOW` and the sandbox.
  3. **The Docket week turning graded**: the lounge board's tiles lighting as verdicts land (`.hl-board` / `.hl-tile`), or the ledger's movement (§8.12).
- **Decide nothing else in advance.** Overdrive proposes two or three directions and waits for your pick.

## The prompt

Replace the two `<...>` lines (and keep or drop the lounge-to-room block under them), then paste everything in the block.

```
/impeccable overdrive --target <path, e.g. core/main/templates/main/ or games/cfb/templates/cfb/>

TARGET: <the surface and the one moment, e.g. "the walk from a lounge headliner panel into its room:
a cross-document View Transition in which the panel head (.hl-panel-link) becomes the room's masthead block,
the words crossfading inside it (no masthead carries the panel's emoji mark or its exact name)">

<for the lounge-to-room target, keep these four lines too>
- Scope it: @view-transition { navigation: auto } opts in every same-origin navigation both pages share. Only
  lounge <-> room may transition (view transition types, or pageswap / pagereveal); every other link stays a plain load.
- Author the root: the default crossfade from the dark lounge to a light room passes through a muddy middle.
- The back button (room to lounge) plays it in reverse; the navbar holds still throughout.
- If a direction prerenders the room (Speculation Rules), say what that does to each blueprint's before_request
  hook, which would then run before the member has clicked.

REQUIRED READING before proposing. The loader drops the root doc under --target, so read all of these yourself:
- DESIGN.md (root): §4.5 Motion (ADR-076, the binding motion doctrine), §6 Do's and Don'ts, §1.6 Lounge and rooms,
  the headliner panel system, and the shipped motion precedents: The Live Wire, the Notification Preview morph,
  the Install Coach (ADR-074).
- PRODUCT.md: Anti-references, Motion and State Accessibility, Prioritize Emotional Utility.
- games/<slug>/DESIGN.md for every room the moment touches. CFB: §6.14 (terminal moments may be authored),
  §6.15, §6.16 (Ceremony-by-Composition, Crimson-Ceremony: no gold). Docket: §6.10, §6.11, §8.12.
  Golf: §6.10, §6.11, §7.28.
- ARCHITECTURE_DECISION_LOG.md ADR-076 (why the doctrine reads as it does) and ADR-049 (lounge vs room).

THE CONTRACT (root DESIGN.md §4.5; binding):
1. One authored moment, set off by something real (an action or a state change), never ambient. Nothing loops
   except a live indicator; nothing runs offscreen; nothing autoplays that a member did not start.
2. Material by meaning: transform and opacity, plus bounded blur, mask, clip-path, shadow or @property color when
   they carry the idea and stay smooth on a mid-range phone. No decorative glass. Never animate layout properties.
3. Ease out with var(--ease-out) or steeper. No curve overshoots (tests/test_motion_doctrine.py fails on any y
   outside 0 to 1).
4. The still state is the complete state. Under prefers-reduced-motion the movement stops and the confirmation
   stays: the shared opacity-only `fade-in` at var(--motion-feedback), or a color change. No JS = the still state.
   Put every reduced-motion override BELOW the rule it overrides (the cascade lock checks).
5. Every browser feature has a fallback that looks finished (@supports or a feature check). Cross-document View
   Transitions: Chrome/Edge/Safari; Firefox gets a normal navigation.
6. Vanilla CSS and JS in static/css/style.css and static/js/ (asset_version on every /static URL); no new library
   unless a direction genuinely needs one and says so. Tokens go in static/css/tokens.css.

STILL BANNED: gradient text; colored side-stripes; a third font; gold in the CFB or golf rooms; a second dark room in
the Docket or golf; pulsing or flashing countdowns; celebration on an ordinary action; sportsbook, broadcast,
mission-control or arcade effects; animated line movement (Docket); sparklines; room --game-* vars in the lounge
(accents are --lounge-* / --hl-* only, tests/test_lounge_accent_firewall.py); a label above a heading; emoji as icons.

PROPOSE 2-3 directions at different levels of ambition. For each: what the member sees and feels, the technique,
browser support and fallback, the performance cost, the reduced-motion version, and which doctrine lines it
touches (quote them). Recommend one. Build nothing until I pick.

AFTER I PICK:
- Build in a worktree branch.
- Lock it with a pytest file in the style of tests/test_cfb_pick_motion.py and tests/test_motion_doctrine.py:
  the moment's selectors, its reduced-motion path, its fallback, no forbidden property.
- Verify timing, easing and smoothness in a real browser with /browse (never the claude-in-chrome tools), at 390px
  and 1280px, with reduced motion on and off, on the worktree dev server (port 5099, ccc_local, the sandbox
  seeders and *_FAKE_NOW anchors). Batch fixes between looks; keep refining until it feels inevitable.
- Document the new primitive in the owning DESIGN.md the way The Live Wire entry is written: name, trigger,
  durations, curves, fallback, reduced-motion behavior. If it is a cross-surface primitive, also note it in root
  DESIGN.md §4.5 and add an ADR row.
- Stage by explicit path; open a draft PR.
```

## After the build: the design review

Run on the overdrive branch once the moment is built:

```
/design-review (diff-aware, on this branch)
Calibrate against DESIGN.md AND every games/<slug>/DESIGN.md the diff touches (the game doc owns its room; root
§4.5 owns motion). Judge the new moment against §4.5 and the overdrive brief's contract
(docs/designs/2026-10-29-overdrive-brief.md). Check it at 390px and 1280px with reduced motion on and off.
Do NOT commit: apply fixes and stop; I commit by explicit path.
```

`/design-review` makes an atomic commit per fix by default, and CLAUDE.md forbids a skill committing as a side effect, which is why the last line is there.
