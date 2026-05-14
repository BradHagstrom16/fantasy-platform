# Impeccable loader customization — per-game DESIGN.md discovery

The impeccable skill loader at `~/.claude/skills/impeccable/scripts/load-context.mjs` is customized locally to discover **per-game DESIGN.md files** in addition to the top-level `DESIGN.md`. This document records what was changed, why, and how to re-apply the customization if a future impeccable skill upgrade overwrites it.

## Why the customization exists

The fantasy-platform repo hosts multiple fantasy games (Golf, CFB, World Cup) under one Flask blueprint structure. Each game has its own design specialization — palette, register, primitives, accent rank — that doesn't belong in the platform-foundation `DESIGN.md`. The clean architecture is:

- **Top-level `DESIGN.md`** (repo root): platform-foundation doctrine. CCC palette framework, typography, elevation, motion, design laws, cross-game components.
- **`games/<slug>/DESIGN.md`** (per-game): specialization. Palette extensions, accent rank, register vocabulary, named primitives unique to that game.

For the impeccable skill (`$impeccable craft`, `$impeccable critique`, etc.) to honor this layering, the loader needs to discover the per-game files automatically. The stock upstream loader reads top-level only; the customization adds a `perGameDesigns` array to its JSON output.

## What changed

Two upstream files modified on Brad's local install (not committed anywhere upstream):

### 1. `~/.claude/skills/impeccable/scripts/load-context.mjs`

Added a `findPerGameDesigns(cwd)` helper that scans `<cwd>/games/<slug>/DESIGN.md` (case-insensitive) and returns an array of `{gameSlug, designPath, design}` sorted by slug. The helper is invoked from `loadContext()`; the result lands in the returned JSON under a new `perGameDesigns` field. Behavior is backward-compatible: consumers that don't read the field see no difference.

Documentation comments updated to describe the new field and the discovery contract.

### 2. `~/.claude/skills/impeccable/SKILL.md`

One paragraph added to the "Context gathering" gate explaining when `perGameDesigns` is non-empty and how the skill should consume it. Tells the skill to treat each per-game entry as authoritative for surfaces under that game's directory, while keeping the top-level DESIGN.md authoritative for cross-game concerns.

## How to re-apply the customization after an upstream upgrade

When `~/.claude/skills/impeccable/` is updated (e.g., via `update-plugins` or a fresh marketplace install), the upstream files will overwrite the customizations. Re-apply with:

```bash
# Verify the customization is intact (returns non-empty perGameDesigns array).
# Run from the repo root (the loader uses cwd to discover games/<slug>/DESIGN.md).
node ~/.claude/skills/impeccable/scripts/load-context.mjs | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('perGameDesigns count:', len(d.get('perGameDesigns', [])))"
```

If the count is 0 (and at least one `games/<slug>/DESIGN.md` exists in this repo), the customization needs re-applying. The diff is small and well-scoped:

**`load-context.mjs`**: in the JSON output docstring (top-of-file comment), add a `perGameDesigns: Array<{gameSlug, designPath, design}>` line; add a paragraph explaining per-game discovery is always relative to cwd. In `loadContext()`, after the `design` variable is read, add:

```javascript
const perGameDesigns = findPerGameDesigns(cwd);
```

And add `perGameDesigns` to the returned object.

Define the helper at module scope:

```javascript
function findPerGameDesigns(cwd) {
  const gamesDir = path.join(cwd, 'games');
  if (!fs.existsSync(gamesDir)) return [];
  let entries;
  try {
    entries = fs.readdirSync(gamesDir, { withFileTypes: true });
  } catch {
    return [];
  }
  const results = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const gameSlug = entry.name;
    const designPath = firstExisting(path.join(gamesDir, gameSlug), DESIGN_NAMES);
    if (!designPath) continue;
    const design = safeRead(designPath);
    if (design === null) continue;
    results.push({
      gameSlug,
      designPath: path.relative(cwd, designPath),
      design,
    });
  }
  results.sort((a, b) => a.gameSlug.localeCompare(b.gameSlug));
  return results;
}
```

**`SKILL.md`**: in the "Context gathering" section, after the bullet describing PRODUCT.md / DESIGN.md, add a paragraph explaining per-game DESIGN.md discovery and the `perGameDesigns` field. Then add a paragraph below the loader-invocation block describing how to consume `perGameDesigns` when non-empty (the per-game file is authoritative for its game's surfaces; the top-level remains authoritative for cross-game concerns).

The full reference text of both modifications is in the commit that introduced the customization (PR #28 / commit on `worldcup/tab-unification-phase-5`).

## Long-term direction

The customization is small enough to be a reasonable upstream contribution. If multiple impeccable users adopt monorepo / per-game patterns, this discovery contract belongs in the stock loader. Until then, this doc is the maintenance contract: anyone working on this repo who notices `perGameDesigns` is missing from the loader output should re-apply per the snippet above.
