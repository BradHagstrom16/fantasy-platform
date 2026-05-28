# Designer Lockup Integration + Stale Logo Cleanup — Design

**Date:** 2026-05-28
**Status:** Approved (brainstorm), pending spec review
**Predecessor:** PR #48 (`2026-05-27-designer-logo-integration`) integrated the designer's first 7-variant King Viking Badger set. This spec consumes the designer's **second, finalized 16-variant delivery** (gitignored `CCC-final/`) — specifically the standalone wordmark, which the first delivery lacked.

---

## Background

The designer (KingsBranding) delivered a finalized 16-variant set into the gitignored `CCC-final/` folder (SVG + transparent PNG per variant; `.ai`/`.eps`/`.pdf` 16-page masters; EPS for variants 01–07 only). This delivery closes both gaps flagged after PR #48: a **standalone wordmark** and a **dark-background mascot**.

### Full variant map (this delivery)

| # | Variant | Notes |
|---|---------|-------|
| 01 | Bare badger head, full color (no helmet) | = committed `mascot-badger.svg` |
| 02 | Full bust + helm + knotwork shoulders, full color | = committed `mascot-bust.svg` (**path data identical**) |
| 03 | Helmeted head, one-color **gold** | one-color head family |
| 04 | Roundel seal, bone+gold | = committed `seal-color.svg` (**identical**) |
| 05 | Roundel seal, one-color bone | = committed `seal-bone.svg` |
| 06 | Roundel seal, one-color purple | = committed `seal-purple.svg` |
| 07 | Head on purple rounded square (app tile) | = committed `app-tile.svg` |
| **08** | **Wordmark "CORRUPT COMMISH CLUB", gold** | 🆕 import |
| **09** | **Wordmark, purple** | 🆕 import |
| **10** | **Wordmark, bone/white** | 🆕 import (navbar) |
| 11 | Stacked lockup (head + gold wordmark) | brand kit (unused in app) |
| 12 | Horizontal plaque lockup | brand kit (unused in app) |
| 13 | Horizontal clean lockup | brand kit (unused in app) |
| 14 | Helmeted head, one-color **purple** | one-color head family |
| 15 | Helmeted head, one-color **bone** | the dark-bg mascot |
| 16 | Helmeted head, **full color** | committed `icon.svg` is the same drawing, sub-pixel re-export delta (42 paths / same viewBox) |

**Correction vs PR #48 memory:** the new delivery's numbering differs. The full-color primary head is **v16** (not v03); **v03 is a distinct one-color gold head**, not a duplicate. The set now carries a complete one-color head family — gold (03) / purple (14) / bone (15) — alongside the full-color head (16).

### Decision: minimal import

The committed bust (v02) and seal (v04) are byte-equivalent to the new files; the committed head (`icon.svg`) differs only by a sub-pixel re-export (invisible at navbar size, and it is raster-locked + tested in production). **We import only the net-new asset — the designed wordmark — and leave the existing head/bust/seal and the favicon/apple-touch raster pipeline untouched.** A full-set refresh was considered and deferred as unnecessary churn against the tested raster locks.

---

## Scope

### In scope

1. **Import the designed wordmark (full color kit)** into `static/img/logo/`:
   - `wordmark-bone.svg` ← `CCC-final/CCC-final-10.svg`
   - `wordmark-gold.svg` ← `CCC-final/CCC-final-08.svg`
   - `wordmark-purple.svg` ← `CCC-final/CCC-final-09.svg`
   - Naming follows the existing color-suffix convention (`seal-bone`/`seal-purple`/`seal-color`).

2. **Navbar** (`templates/base.html`): replace the Teko CSS-text wordmark with an `<img>` of `wordmark-bone.svg`. Keep the existing head (`favicon.svg`). Head-only below `md` (replaces today's "CCC" text span). Wordmark `<img>` carries `?v={{ asset_version }}`.

3. **Auth brand panel**: lead the desktop brand panel with the full bust (existing `mascot-bust.svg`) instead of the small head; keep the headline + games list. The `.auth-panel-brand` markup is duplicated across exactly four templates — `login.html`, `register.html`, `forgot_password.html`, `reset_password.html` — all four must be updated identically. (`change_password.html` and `profile.html` have no brand panel.)

4. **Cleanup**: delete the 6 unreferenced, superseded hand-authored files:
   - `static/img/logo/lockup-horizontal-dark.svg`, `lockup-horizontal-light.svg`
   - `static/img/logo/lockup-stacked-dark.svg`, `lockup-stacked-light.svg`
   - `static/img/logo/wordmark-dark.svg`, `wordmark-light.svg`
   (Confirmed: zero references in `templates/`, `static/`, `core/`, `games/`.)

5. **Tests**: extend `tests/test_logo_assets.py` (assert the 3 new wordmark files exist + are clean vector; assert the 6 deleted files are gone) and `tests/test_asset_versioning.py` (assert the navbar wordmark `<img>` is rendered with `?v=`).

### Out of scope (deliberately)

- **Footer** — unchanged; the seal stays in its ceremonial voice band (the name already lives in the copyright bar).
- **Email** — unchanged; the seal header stays.
- Re-importing head/bust/seal; rebuilding `favicon.ico` / `apple-touch-icon-180.png`.
- The brand-kit lockups (v11/v12/v13) and one-color heads (v03/v14/v15) — kept on file in `CCC-final/`, not wired into the app (YAGNI; available for merch/social/marketing).
- The **designer order decision** (whether to request per-variant EPS for the lockups/wordmark before approving): a business decision for Brad, tracked outside this spec.

---

## Accessibility

The navbar brand link currently derives its accessible name from the visible text span. Replacing that text with an image — and hiding the wordmark image below `md` — would strip the link's accessible name on mobile. **Mitigation:** add `aria-label="Corrupt Commish Club"` to the `<a class="navbar-brand">` and mark both the head and wordmark images decorative (`alt=""`). This guarantees a stable accessible name at every viewport, independent of which images are visible. The existing 44×44 touch-target floor (`min-height: 44px`) is preserved.

---

## Component-by-component

### Navbar (`templates/base.html`)

Before:
```html
<a class="navbar-brand" href="{{ url_for('main.index') }}">
  <img src="{{ url_for('static', filename='img/logo/favicon.svg') }}?v={{ asset_version }}" class="brand-mark" alt="">
  <span class="d-none d-md-inline">Corrupt Commish Club</span>
  <span class="d-md-none">CCC</span>
</a>
```
After:
```html
<a class="navbar-brand" href="{{ url_for('main.index') }}" aria-label="Corrupt Commish Club">
  <img src="{{ url_for('static', filename='img/logo/favicon.svg') }}?v={{ asset_version }}" class="brand-mark" alt="">
  <img src="{{ url_for('static', filename='img/logo/wordmark-bone.svg') }}?v={{ asset_version }}" class="brand-wordmark d-none d-md-inline" alt="">
</a>
```
CSS: add `.navbar.navbar-dark .brand-wordmark { height: ~17px; width: auto; }` and verify vertical centering inside the existing inline-flex 44px hit-box. The Teko `.navbar-brand` font rules become inert for the brand label (no text node) but remain for any other consumer — no rule deletion required.

### Auth brand panel (`core/auth/templates/auth/*`)

Replace the `.brand-logo` head + adjacent text with the full bust; keep `.brand-headline` + `.brand-sub` + `.brand-games`. Add a `.brand-bust` style (centered, ~150px). The panel is `display:none` below `md`, so this is a desktop-only enhancement — mobile auth cards are unaffected.

**DRY improvement (in scope):** the `.auth-panel-brand` block is currently duplicated verbatim across all four templates. Since the bust change must be applied identically to each, extract the panel into a shared partial (`core/auth/templates/auth/_brand_panel.html`) and `{% include %}` it from the four templates. This collapses four edits to one and removes a standing drift risk. If the four copies turn out to have already diverged, reconcile to the login.html version (the canonical one) as part of the extraction.

### Footer / Email

No change.

---

## Testing strategy

- `tests/test_logo_assets.py`: new wordmark files present + contain `<svg` and no `data:image`; the 6 deleted files absent.
- `tests/test_asset_versioning.py`: rendered `base.html` navbar wordmark `<img>` URL contains `?v=`.
- Manual smoke (pytest-only project; no pyright): render navbar at < md and ≥ md (head-only vs head+wordmark); render an auth page desktop panel (bust) and mobile (card only). Verify navbar brand link exposes "Corrupt Commish Club" as its accessible name at both breakpoints.

---

## Risks

- **Wordmark legibility at navbar height (~17px):** the designed wordmark is condensed; verify "CORRUPT COMMISH CLUB" stays legible at the bone-on-purple-700 contrast. Fallback: nudge height up 1–2px. (Low — validated in the brainstorm mockup on the real fill.)
- **Auth bust weight:** the bust is the heaviest mark; confirm it doesn't overpower the 380px panel or push the games list below the fold at common heights. (Low — panel is vertically centered and scrolls within its column.)
