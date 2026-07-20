# Per-game DESIGN.md convention (impeccable)

> **Renamed from `impeccable-loader-customization.md` (2026-07-20).** The old name described a local patch to the impeccable context loader that auto-discovered per-game `DESIGN.md` files. That patch was retired on 2026-05-29 (impeccable v3.5.0) because every skill update overwrote it, and baking one repo's logic into a globally-shared, externally-updated tool was fragile. The layering it supported is enforced by a project-level rule (below) instead. Re-verified against impeccable v3.9.1 on 2026-07-20: the stock loader still emits top-level files only.

## The layering

This repo hosts multiple games (Golf, CFB, World Cup) under one Flask blueprint structure. Design doctrine is split in two:

- **Top-level `DESIGN.md`** (repo root) — platform-foundation doctrine: CCC palette framework, typography, elevation, motion, design laws, cross-game components. Authoritative for **cross-game / platform** concerns.
- **`games/<slug>/DESIGN.md`** (per-game) — specialization: palette extensions, accent rank, register vocabulary, named primitives unique to that game. Authoritative for surfaces **under that game's directory**. Current files: `games/cfb/DESIGN.md` (the flagship's design contract) and `games/worldcup/DESIGN.md` (archived game; frozen). Golf's is planned for the ~Jan 2027 UI phase.

## How the per-game file gets loaded (the rule)

The **stock** impeccable loader (`scripts/context.mjs`) emits only the top-level `PRODUCT.md` / `DESIGN.md`. It does **not** discover per-game files. So the convention is enforced as a hard rule in `CLAUDE.md`:

> When working any UI surface under `games/<slug>/`, read `games/<slug>/DESIGN.md` alongside the top-level `DESIGN.md` **before** producing design output.

Pick the active game from the surface in focus (the file path, route, or template being worked on). Keep platform-foundation decisions anchored to the top-level file; defer game-specific palette/accent/register/primitive decisions to the per-game file.

This keeps project-specific knowledge in the project (where it belongs and survives every impeccable upgrade), instead of in a global tool patch.

## Running the loader in this repo

The impeccable setup step's project-relative invocation (`node .agents/skills/impeccable/scripts/context.mjs`) does **not** work here — this repo has no `.agents/` directory, so it fails with `MODULE_NOT_FOUND`. Use the skill's base directory instead:

```bash
node ~/.claude/skills/impeccable/scripts/context.mjs
```

(`~/.claude/skills/impeccable` is a symlink to the canonical global install at `~/.agents/skills/impeccable`.)

## Keeping impeccable current

Impeccable is an **npm-package skill**, installed globally at `~/.agents/skills/impeccable/` and symlinked into `~/.claude/skills/impeccable/` (same pattern as `find-skills`). It is **not** a Claude marketplace plugin, so `claude plugin update` does not cover it.

- **Update only via `/update-plugins`.** It runs `~/.claude/scripts/impeccable-skills-update.sh`, which updates the global install from `$HOME` (the one location that resolves to the global providers) and re-normalizes the `.agents`-canonical / `.claude`-symlink topology that the updater would otherwise break.
- **Never run `npx impeccable skills update` from a repo root.** Its `findProjectRoot()` targets the nearest `.git`, so it installs a stray project-local copy under `<repo>/.claude/skills/impeccable/` instead of updating the global one. A `PreToolUse` guardrail hook in `~/.claude/settings.json` blocks this; `.claude/skills/impeccable/` is also gitignored so a stray copy can never be committed (`add-game` is the only intended tracked project skill).

## If you ever want auto-injection back

A future option is to contribute per-game discovery upstream to impeccable so it ships in the stock loader (no local patch, survives updates). Until then, the project-level rule above is the maintenance contract.
