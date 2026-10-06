# Per-game DESIGN.md convention (impeccable)

> **Renamed from `impeccable-loader-customization.md` (2026-07-20).** The old name described a local patch to the impeccable context loader that auto-discovered per-game `DESIGN.md` files. That patch was retired on 2026-05-29 (impeccable v3.5.0) because every skill update overwrote it, and baking one repo's logic into a globally-shared, externally-updated tool was fragile. The layering it supported is enforced by a project-level rule (below) instead. Re-verified against impeccable v3.9.1 on 2026-07-20: the stock loader still emits top-level files only.

## The layering

This repo hosts multiple games (CFB Survivor, The Docket, The Pay Sheet, the archived World Cup) under one Flask blueprint structure. Design doctrine is split in two:

- **Top-level `DESIGN.md`** (repo root) — platform-foundation doctrine: CCC palette framework, typography, elevation, motion, design laws, cross-game components. Authoritative for **cross-game / platform** concerns.
- **`games/<slug>/DESIGN.md`** (per-game) — specialization: palette extensions, accent rank, register vocabulary, named primitives unique to that game. Authoritative for surfaces **under that game's directory**. Current files: `games/cfb/DESIGN.md` (the dark midnight room), `games/docket/DESIGN.md` (the light court-paper room), `games/golf/DESIGN.md` (The Pay Sheet, the light paper room; U0, 2026-10-06) and `games/worldcup/DESIGN.md` (archived game; frozen).

## How the per-game file gets loaded (the rule)

Since impeccable v4 the loader resolves **exactly one** `DESIGN.md`: with `--target <path>` it walks up from the target to the nearest directory holding `PRODUCT.md` *or* `DESIGN.md` and resolves each doc there, falling back to the repo root only for what that directory lacks. So `impeccable context --target games/<slug>/…` loads `games/<slug>/DESIGN.md` plus the root `PRODUCT.md` and **drops the root `DESIGN.md`**; a run with no `--target` loads only the root pair (re-verified 2026-10-05, impeccable v4.3). Two consequences:

1. Every per-game file carries `extends: ../../DESIGN.md` in its frontmatter and **restates the root rules it depends on** (the Eyebrow Rule, the Two-Color Rule, the side-stripe ban, the em-dash ban, the tint-only current-user row): CFB §6.10, Docket §6.8, golf §6.11.
2. The layering is still enforced as a hard rule in `CLAUDE.md`, because a session that never runs the loader needs it too:

> When working any UI surface under `games/<slug>/`, read `games/<slug>/DESIGN.md` alongside the top-level `DESIGN.md` **before** producing design output.

Pick the active game from the surface in focus (the file path, route, or template being worked on). Keep platform-foundation decisions anchored to the top-level file; defer game-specific palette/accent/register/primitive decisions to the per-game file. The root frontmatter keeps one or two headline tokens per game (`cfb-crimson`, `docket-oxblood`, `golf-pen`, …) so the platform's `.impeccable/design.json` sidecar sees every room; each room's full family lives only in its own file, and a test per room keeps the doc's frontmatter equal to the CSS under `body.game-<slug>` (`tests/test_cfb_dark_foundation.py`, `tests/test_golf_design_doc.py`).

**What else is committed:** `.impeccable/config.json` (detector exceptions, each with its `--reason`), the `design.json` sidecar, and the per-surface briefs under `games/<slug>/.impeccable/surfaces/` (each surface's scope, mode and direction contract, written by impeccable's new-work flow before that surface is built). `config.local.json` and session output stay ignored.

This keeps project-specific knowledge in the project (where it belongs and survives every impeccable upgrade), instead of in a global tool patch.

## Running the loader in this repo

The impeccable setup step's project-relative invocation (`.agents/skills/impeccable/scripts/impeccable context`) does **not** work here — impeccable is a *global* install and this repo has no `.agents/` directory. Use the skill's base directory instead, from the repo root, with the surface as the target:

```bash
~/.claude/skills/impeccable/scripts/impeccable context --target games/golf/templates/golf/index.html
```

(`~/.claude/skills/impeccable` is a symlink to the canonical global install at `~/.agents/skills/impeccable`. The v4 launcher is a self-contained binary; the old `node …/context.mjs` form is gone.)

## Keeping impeccable current

Impeccable is an **npm-package skill**, installed globally at `~/.agents/skills/impeccable/` and symlinked into `~/.claude/skills/impeccable/` (same pattern as `find-skills`). It is **not** a Claude marketplace plugin, so `claude plugin update` does not cover it.

- **Update only via `/update-plugins`.** It runs `~/.claude/scripts/impeccable-skills-update.sh`, which updates the global install from `$HOME` (the one location that resolves to the global providers) and re-normalizes the `.agents`-canonical / `.claude`-symlink topology that the updater would otherwise break.
- **Never run `npx impeccable skills update` from a repo root.** Its `findProjectRoot()` targets the nearest `.git`, so it installs a stray project-local copy under `<repo>/.claude/skills/impeccable/` instead of updating the global one. A `PreToolUse` guardrail hook in `~/.claude/settings.json` blocks this; `.claude/skills/impeccable/` is also gitignored so a stray copy can never be committed (`add-game` is the only intended tracked project skill).

## If you ever want auto-injection back

A future option is to contribute per-game discovery upstream to impeccable so it ships in the stock loader (no local patch, survives updates). Until then, the project-level rule above is the maintenance contract.
