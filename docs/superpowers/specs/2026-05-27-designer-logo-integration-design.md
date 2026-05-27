# Designer Logo Integration — Design

**Date:** 2026-05-27
**Status:** Approved (design); implementation plan pending
**Author:** Brad + Claude (brainstorming session)

## Context

The designer (KingsBranding, Fiverr) delivered the finished **King Viking Badger** logo set into the gitignored `CCC-final/` folder. It replaces the hand-authored SVG system shipped in PR #47 (`static/img/logo/`). The delivery is 7 vector variants, each as SVG + transparent PNG (1500px) + EPS, plus master `.ai` / `.eps` / `.pdf` and a `.jpg` showcase. Colors are an exact match to the CCC tokens (`#3A1D72` = `--purple-700`, `#C9A227` = `--gold`, `#F3EFE6` = `--bone`).

The order is **not yet approved** — two delivery gaps were noted (no standalone wordmark/lockup; no dark-background mascot variant). This pass integrates what we have; Brad decides separately whether to request those from the designer.

### The 7 delivered variants

| # | What it is |
|---|---|
| 01 | Bare badger head (no helmet), full color |
| 02 | Viking-helmet badger, full bust w/ Norse knotwork shoulders |
| 03 | Viking-helmet badger head (cropped at neck), full color |
| 04 | "Corrupt Commish Club" roundel seal — bone + gold (full color) |
| 05 | Same roundel — all bone (one-color, for dark substrates) |
| 06 | Same roundel — all purple (one-color, for light substrates) |
| 07 | Helmet badger on a purple rounded square (designed as app icon; PNG is only 48px) |

### Integration surface (today)

- `templates/base.html:25-27` — favicon chain (`favicon.svg`, `favicon.ico`, `apple-touch-icon-180.png`)
- `templates/base.html:40` — navbar brand uses `favicon.svg` at 28px (`.brand-mark`)
- 4 auth pages (`core/auth/templates/auth/*.html`) — use `icon.svg` at 56px (`.brand-mark--lg`)
- `templates/base.html:199-210` — footer: text-only, dark substrate (voice band `--purple-800` + gold top border; utility band `--purple-900`). No logo today.
- `templates/email/reset_password_html.j2` — purple header band (`#2A1150`) with gold Teko wordmark text; **uses zero images**. Render context currently receives only `reset_url`.
- **No web manifest exists** (no PWA icons today).
- `lockup-*.svg` / `wordmark-*.svg` exist in `static/img/logo/` but are **referenced nowhere** — the live navbar uses a CSS-text wordmark, not an SVG file.

## Decisions

1. **Primary mark = variant 03** (helmeted head). Replaces hand-authored `icon.svg` + `favicon.svg`. Reduces cleanly while keeping the full Viking-badger identity.
2. **Transparent head everywhere** for browser-facing icons (navbar, auth, `favicon.svg`, browser-tab `.ico`) — chosen for consistency over a filled tile.
3. **One exception — the home-screen tile.** `apple-touch-icon` needs an opaque background (iOS composites transparent icons onto a black/white box). It uses the head on a solid purple field.
4. **Roundel seal = full-color (variant 04)**, used in **footer** (~92px, centered above the voice tagline) and **email header** (~64px, above the wordmark). Full-color chosen over bone because the gold arcs give real contrast/pop on purple. Bone (05) and purple (06) kept on file for future light/dark contexts.
5. **Raster scope matches today's set** — `.ico` + `apple-touch-180`. No PWA manifest (out of scope).
6. **Stale `lockup-*`/`wordmark-*` SVGs left untouched** — unused and now visually inconsistent with the new mascot, but out of scope for this pass. Flagged as a follow-up.
7. **Designer masters (`.ai`/`.eps`/`.pdf`) stay in gitignored `CCC-final/`** as the archive. Production-ready SVGs are copied into `static/img/logo/` (committed).

## Asset inventory — `static/img/logo/`

| File | Source variant | Role | Action |
|---|---|---|---|
| `icon.svg` | 03 | auth pages (56px), master head | replace |
| `favicon.svg` | 03 | navbar (28px) + browser tab | replace |
| `favicon.ico` | 03 → 16/32/48 | tab fallback (transparent head) | regenerate |
| `apple-touch-icon-180.png` | 03 head on solid purple square, 180px | iOS/Android tile | regenerate |
| `mascot-bust.svg` | 02 | large hero/showcase mark | new, on file |
| `mascot-badger.svg` | 01 | alt mark (no helmet) | new, on file |
| `seal-color.svg` | 04 | roundel — footer + email | new, **used** |
| `seal-bone.svg` | 05 | roundel for dark substrates | new, on file |
| `seal-purple.svg` | 06 | roundel for light substrates | new, on file |
| `app-tile.svg` | 07 | app-icon vector (archive of designer's tile) | new, on file |
| `seal-email.png` | 04 → ~160px | raster seal for Gmail-safe email | new, **used** |

SVGs copied from the delivery get a light cleanup (strip Illustrator comments / `enable-background` cruft); no `svgo` on this machine, so a small Python/regex pass or ship-as-is.

## Raster pipeline (transparency-safe)

**Constraint learned during brainstorming:** `qlmanage` bakes an opaque white background and cannot preserve transparency. Use **Pillow** (available) for all raster derivation, sourced from the designer's transparent 1500px PNGs. No new tooling.

- `favicon.ico` — Pillow downscale variant 03 → 16/32/48, save multi-res `.ico` (alpha preserved).
- `apple-touch-icon-180.png` — Pillow paste the variant 03 head, centered, onto a **solid full-bleed purple square** (no built-in rounding — iOS applies its own mask). This avoids variant 07's 48px PNG and its double-rounding.
- `seal-email.png` — Pillow downscale variant 04 (transparent) to ~160px.

## Email seal wiring

- Gmail strips SVG → email uses the **raster** `seal-email.png`.
- Referenced by **absolute URL** via `{{ seal_url }}`: `<img src="{{ seal_url }}" width="64" height="64" alt="Corrupt Commish Club">` in the purple header band of `reset_password_html.j2`, above the wordmark.
- **Pass `seal_url` into the email render context** alongside `reset_url` — generated with `url_for('static', filename='img/logo/seal-email.png', _external=True)`, the same `_external=True` mechanism `reset_url` already uses, so no separate `SITE_URL` plumbing is needed. Any future HTML email adopts the same header pattern.
- Images skip the `?v=` cache-bust param (per CLAUDE.md convention — rename to bust).

## Verification

- Run the dev server; eyeball navbar (28px), auth (56px), and footer seal on the real CCC purple substrate.
- **Favicon at 16px in a real browser tab** — the one spot the detailed head is at risk. Verify, don't assume. Fallback if muddy: a bolder simplified favicon cut.
- Render the reset-password email; confirm the seal loads from the absolute URL and reads on the purple band.
- Run the test suite, including `tests/test_asset_versioning.py` (asset cache-busting is locked there).

## Docs to update

- `project_logo_king_viking_badger.md` memory — official logo is now the professional designer set, not hand-authored; record the new asset map.
- Record the **Pillow-not-qlmanage** rasterization gotcha (qlmanage bakes white, breaks transparency).

## Non-goals / out of scope

- Requesting the missing wordmark/lockup or dark-mascot variant from the designer (Brad's separate call; order not yet approved).
- Regenerating or deleting the unused `lockup-*`/`wordmark-*` SVGs.
- PWA manifest / maskable icons.
- Committing the designer masters (`.ai`/`.eps`/`.pdf`) — they stay in gitignored `CCC-final/`.

## Open questions

- None blocking. The 16px favicon legibility is the one item flagged for verification rather than assumption.
