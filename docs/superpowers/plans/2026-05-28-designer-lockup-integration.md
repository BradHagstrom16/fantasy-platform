# Designer Lockup Integration + Stale Logo Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the designer's finalized wordmark into the navbar, lead the auth brand panel with the full bust, and delete six superseded hand-authored logo files.

**Architecture:** Minimal import — copy only the net-new designed wordmark (3 color SVGs) into `static/img/logo/`. The navbar swaps its Teko CSS-text wordmark for an `<img>` of the bone wordmark (head-only below `md`); the auth desktop panel's shared `.brand-logo` fragment is extracted to a Jinja partial and changed from the small head to the full bust (existing `mascot-bust.svg`, byte-identical to the new delivery). Footer/email and the favicon raster pipeline are untouched.

**Tech Stack:** Flask + Jinja2 templates, Bootstrap 5.3 utility classes (`d-none`/`d-md-inline`), plain CSS in `static/css/style.css`, pytest (no pyright — this project verifies with pytest only).

**Spec:** `docs/superpowers/specs/2026-05-28-designer-lockup-integration-design.md`

---

## File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `static/img/logo/wordmark-bone.svg` | Create (cp v10) | Designed wordmark, bone — navbar on dark |
| `static/img/logo/wordmark-gold.svg` | Create (cp v08) | Designed wordmark, gold — kit |
| `static/img/logo/wordmark-purple.svg` | Create (cp v09) | Designed wordmark, purple — kit |
| `static/img/logo/lockup-horizontal-dark.svg` | Delete | Superseded hand-authored |
| `static/img/logo/lockup-horizontal-light.svg` | Delete | Superseded hand-authored |
| `static/img/logo/lockup-stacked-dark.svg` | Delete | Superseded hand-authored |
| `static/img/logo/lockup-stacked-light.svg` | Delete | Superseded hand-authored |
| `static/img/logo/wordmark-dark.svg` | Delete | Superseded hand-authored |
| `static/img/logo/wordmark-light.svg` | Delete | Superseded hand-authored |
| `core/auth/templates/auth/_brand_logo.html` | Create | Shared bust fragment, `{% include %}`d by 4 auth templates |
| `templates/base.html` | Modify (navbar brand, ~L43-47) | Wordmark `<img>` + `aria-label` |
| `core/auth/templates/auth/login.html` | Modify (~L11-14) | Use `_brand_logo.html` include |
| `core/auth/templates/auth/register.html` | Modify | Use `_brand_logo.html` include |
| `core/auth/templates/auth/forgot_password.html` | Modify | Use `_brand_logo.html` include |
| `core/auth/templates/auth/reset_password.html` | Modify | Use `_brand_logo.html` include |
| `static/css/style.css` | Modify (~L64, ~L7181) | `.brand-wordmark`, `.brand-bust` rules |
| `tests/test_logo_assets.py` | Modify | New wordmark files present; deleted files absent |
| `tests/test_asset_versioning.py` | Modify | Navbar wordmark versioned; swap auth-panel path lock to bust |
| `CLAUDE.md` | Modify | One-line brand-asset note |

---

### Task 1: Import the designed wordmark kit

**Files:**
- Create: `static/img/logo/wordmark-bone.svg`, `wordmark-gold.svg`, `wordmark-purple.svg`
- Test: `tests/test_logo_assets.py`

- [ ] **Step 1: Add the failing test** — append a new parametrized test to `tests/test_logo_assets.py` (after `test_logo_svg_exists_and_is_vector`, ~L21):

```python
WORDMARK_SVGS = ["wordmark-bone.svg", "wordmark-gold.svg", "wordmark-purple.svg"]


@pytest.mark.parametrize("name", WORDMARK_SVGS)
def test_designed_wordmark_exists_and_is_clean_vector(name):
    """The designer's standalone wordmark (2026-05-28 delivery) is imported as
    clean vector — no embedded raster, real <svg> markup."""
    p = LOGO / name
    assert p.exists(), f"{name} missing from static/img/logo/"
    text = p.read_text(errors="ignore")
    assert "<svg" in text[:600], f"{name} is not an SVG"
    assert "data:image" not in text, f"{name} contains an embedded raster"
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_designed_wordmark_exists_and_is_clean_vector -v`
Expected: 3 FAILs — "wordmark-bone.svg missing from static/img/logo/" etc.

- [ ] **Step 3: Copy the files from the gitignored delivery**

```bash
cp CCC-final/CCC-final-10.svg static/img/logo/wordmark-bone.svg
cp CCC-final/CCC-final-08.svg static/img/logo/wordmark-gold.svg
cp CCC-final/CCC-final-09.svg static/img/logo/wordmark-purple.svg
```

- [ ] **Step 4: Run it — expect PASS**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_designed_wordmark_exists_and_is_clean_vector -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add static/img/logo/wordmark-bone.svg static/img/logo/wordmark-gold.svg static/img/logo/wordmark-purple.svg tests/test_logo_assets.py
git commit -m "platform(brand): import designed wordmark kit (bone/gold/purple)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Delete the superseded hand-authored lockup/wordmark files

**Files:**
- Delete: 6 files (see table)
- Test: `tests/test_logo_assets.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_logo_assets.py`:

```python
RETIRED_SVGS = [
    "lockup-horizontal-dark.svg", "lockup-horizontal-light.svg",
    "lockup-stacked-dark.svg", "lockup-stacked-light.svg",
    "wordmark-dark.svg", "wordmark-light.svg",
]


@pytest.mark.parametrize("name", RETIRED_SVGS)
def test_retired_handauthored_logos_are_gone(name):
    """The hand-authored lockup-*/wordmark-* SVGs (PR #47) were never wired in
    and are superseded by the designer delivery. They must not linger."""
    assert not (LOGO / name).exists(), (
        f"{name} should have been deleted (superseded, unreferenced)"
    )
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_retired_handauthored_logos_are_gone -v`
Expected: 6 FAILs — "lockup-horizontal-dark.svg should have been deleted ...".

- [ ] **Step 3: Verify they are truly unreferenced, then delete**

```bash
grep -rn "lockup-horizontal\|lockup-stacked\|wordmark-dark\|wordmark-light" templates/ static/css/ core/ games/ ; echo "exit: $?"
# Expected: no matches (grep exit 1). If anything prints, STOP and report.
git rm static/img/logo/lockup-horizontal-dark.svg static/img/logo/lockup-horizontal-light.svg \
       static/img/logo/lockup-stacked-dark.svg static/img/logo/lockup-stacked-light.svg \
       static/img/logo/wordmark-dark.svg static/img/logo/wordmark-light.svg
```

- [ ] **Step 4: Run it — expect PASS**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_retired_handauthored_logos_are_gone -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_logo_assets.py
git commit -m "platform(brand): delete superseded hand-authored lockup/wordmark SVGs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Navbar — designed wordmark replaces the Teko CSS text

**Files:**
- Modify: `templates/base.html` (navbar brand, lines 43-47)
- Modify: `static/css/style.css` (after `.brand-mark`, line 64-65)
- Test: `tests/test_asset_versioning.py`

- [ ] **Step 1: Add the failing versioning lock** — in `tests/test_asset_versioning.py`, add the navbar wordmark to `BRAND_IMAGE_PATHS` (the list at ~L187). Insert this entry:

```python
    'img/logo/wordmark-bone.svg',   # navbar designed wordmark (md+)
```

Then add a dedicated a11y/markup test at the end of the file:

```python
def test_navbar_brand_has_wordmark_and_accessible_name(app):
    """Navbar brand swaps the Teko CSS text for the designed bone wordmark image,
    and the brand link keeps a stable accessible name at every viewport via
    aria-label (both images are decorative alt='')."""
    with app.test_client() as c:
        body = c.get('/login').data.decode('utf-8')
    assert 'img/logo/wordmark-bone.svg' in body, "navbar wordmark image missing"
    assert 'aria-label="Corrupt Commish Club"' in body, (
        "navbar brand link lost its accessible name — the wordmark is hidden "
        "below md, so the <a> needs aria-label or mobile users get no brand name"
    )
```

- [ ] **Step 2: Run them — expect FAIL**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest "tests/test_asset_versioning.py::test_navbar_brand_has_wordmark_and_accessible_name" "tests/test_asset_versioning.py::test_rendered_base_brand_images_are_versioned[img/logo/wordmark-bone.svg]" -v`
Expected: both FAIL (wordmark not yet in template / not found in body).

- [ ] **Step 3: Edit the navbar brand in `templates/base.html`** — replace lines 43-47:

```html
            <a class="navbar-brand" href="{{ url_for('main.index') }}" aria-label="Corrupt Commish Club">
                <img src="{{ url_for('static', filename='img/logo/favicon.svg') }}?v={{ asset_version }}" class="brand-mark" alt="">
                <img src="{{ url_for('static', filename='img/logo/wordmark-bone.svg') }}?v={{ asset_version }}" class="brand-wordmark d-none d-md-inline" alt="">
            </a>
```

- [ ] **Step 4: Add the `.brand-wordmark` rule in `static/css/style.css`** — directly after line 65 (`.brand-mark--lg { ... }`):

```css
.navbar.navbar-dark .brand-wordmark { height: 17px; width: auto; display: inline-block; vertical-align: middle; }
```

- [ ] **Step 5: Run them — expect PASS**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest "tests/test_asset_versioning.py::test_navbar_brand_has_wordmark_and_accessible_name" "tests/test_asset_versioning.py::test_rendered_base_brand_images_are_versioned[img/logo/wordmark-bone.svg]" -v`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/base.html static/css/style.css tests/test_asset_versioning.py
git commit -m "platform(brand): navbar uses designed bone wordmark (head-only below md)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Auth brand panel — lead with the full bust (extracted partial)

**Files:**
- Create: `core/auth/templates/auth/_brand_logo.html`
- Modify: `login.html`, `register.html`, `forgot_password.html`, `reset_password.html` (each, the `.brand-logo` block)
- Modify: `static/css/style.css` (after `.auth-panel-brand .brand-logo`, ~L7189)
- Modify: `tests/test_asset_versioning.py` (swap the auth-panel path lock from `icon.svg` to `mascot-bust.svg`)

> **Why the test swap:** `icon.svg` is referenced *only* by the auth panel's `.brand-logo`. Replacing it with the bust means `/login` no longer contains `icon.svg`, which would break `test_rendered_base_brand_images_are_versioned[img/logo/icon.svg]` (it asserts the path appears ≥1). The auth-panel mark is now `mascot-bust.svg`, so the lock must follow it.

- [ ] **Step 1: Add the failing tests** — in `tests/test_asset_versioning.py`, edit `BRAND_IMAGE_PATHS`: replace the `'img/logo/icon.svg'` line with:

```python
    'img/logo/mascot-bust.svg',     # auth brand panel hero (login/register/forgot/reset)
```

Then add a markup test to `tests/test_logo_assets.py`:

```python
import re as _re

AUTH_PANEL_TEMPLATES = ["login.html", "register.html", "forgot_password.html", "reset_password.html"]
AUTH_TPL_DIR = pathlib.Path("core/auth/templates/auth")


def test_auth_brand_panel_uses_shared_bust_partial():
    """All four auth panels include the shared brand-logo partial, the partial
    leads with the full bust, and no panel still hard-codes the old head."""
    partial = (AUTH_TPL_DIR / "_brand_logo.html").read_text()
    assert "mascot-bust.svg" in partial, "brand-logo partial must use the bust"
    for name in AUTH_PANEL_TEMPLATES:
        src = (AUTH_TPL_DIR / name).read_text()
        assert "_brand_logo.html" in src, f"{name} does not include the shared partial"
        assert "brand-mark--lg" not in src, f"{name} still hard-codes the old head mark"


def test_login_page_renders_bust(client):
    """The rendered login desktop panel carries the bust image."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"img/logo/mascot-bust.svg" in resp.data
```

- [ ] **Step 2: Run them — expect FAIL**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_auth_brand_panel_uses_shared_bust_partial tests/test_logo_assets.py::test_login_page_renders_bust "tests/test_asset_versioning.py::test_rendered_base_brand_images_are_versioned[img/logo/mascot-bust.svg]" -v`
Expected: all FAIL (partial missing / bust not rendered).

- [ ] **Step 3: Create the partial** `core/auth/templates/auth/_brand_logo.html`:

```html
<div class="brand-logo">
    <img src="{{ url_for('static', filename='img/logo/mascot-bust.svg') }}?v={{ asset_version }}" class="brand-bust" alt="">
</div>
```

- [ ] **Step 4: Replace the `.brand-logo` block in each of the 4 templates** — in `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, find this identical block:

```html
            <div class="brand-logo">
                <img src="{{ url_for('static', filename='img/logo/icon.svg') }}?v={{ asset_version }}" class="brand-mark brand-mark--lg" alt="">
                <span>Corrupt Commish Club</span>
            </div>
```

and replace it with:

```html
            {% include "auth/_brand_logo.html" %}
```

Leave each template's `.brand-headline`, `.brand-sub`, and `.brand-games` exactly as they are (page-specific copy).

- [ ] **Step 5: Add the `.brand-bust` rule in `static/css/style.css`** — directly after the `.auth-panel-brand .brand-logo { ... }` block (closes at ~L7189):

```css
.auth-panel-brand .brand-bust { width: 150px; height: auto; display: block; }
```

- [ ] **Step 6: Run them — expect PASS**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_auth_brand_panel_uses_shared_bust_partial tests/test_logo_assets.py::test_login_page_renders_bust "tests/test_asset_versioning.py::test_rendered_base_brand_images_are_versioned[img/logo/mascot-bust.svg]" -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add core/auth/templates/auth/_brand_logo.html core/auth/templates/auth/login.html core/auth/templates/auth/register.html core/auth/templates/auth/forgot_password.html core/auth/templates/auth/reset_password.html static/css/style.css tests/test_logo_assets.py tests/test_asset_versioning.py
git commit -m "platform(brand): auth panel leads with the full bust (shared partial)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Full suite + manual smoke + doc note

**Files:**
- Modify: `CLAUDE.md` (Design system & CSS, or the cache-bust brand-image note)

- [ ] **Step 1: Run the full test suite — expect all green**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q`
Expected: all pass. If `test_rendered_base_brand_images_are_versioned[img/logo/icon.svg]` still appears or fails, the Task 4 `BRAND_IMAGE_PATHS` swap was missed — fix it.

- [ ] **Step 2: Manual visual smoke** (Jinja auto-reload needs `FLASK_DEBUG=1`)

```bash
FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```
Verify in a browser:
- `http://localhost:5099/` ≥ md: navbar shows head + bone wordmark; < md (narrow the window): head only, no "CCC" text, no overflow.
- `http://localhost:5099/login` ≥ md: left panel leads with the full bust above the headline; < md: form card only (panel hidden), unaffected.
- DevTools: the navbar `<a class="navbar-brand">` exposes "Corrupt Commish Club" as its accessible name (Accessibility pane) at both widths.

- [ ] **Step 3: Add a CLAUDE.md note** — in the "Design system & CSS" bullets, add:

```markdown
- **Navbar wordmark + auth bust:** the navbar brand pairs the head mark with the designer's `wordmark-bone.svg` (`<img>`, `d-none d-md-inline` — head-only below md; the `<a class="navbar-brand">` carries `aria-label="Corrupt Commish Club"` so the link keeps an accessible name when the wordmark is hidden). The auth desktop brand panel leads with `mascot-bust.svg` via the shared `core/auth/templates/auth/_brand_logo.html` partial (included by login/register/forgot/reset). Designed wordmark kit lives at `static/img/logo/wordmark-{bone,gold,purple}.svg`; the brand-kit lockups + one-color heads stay unwired in the gitignored `CCC-final/`.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "platform(brand): document navbar wordmark + auth bust conventions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notes for the implementer

- **This project verifies with pytest only — never run pyright** and never add a pyright step.
- The wordmark/bust source files live in the **gitignored** `CCC-final/`; `mascot-bust.svg` is already committed and byte-identical to `CCC-final/CCC-final-02.svg`, so Task 4 needs no copy.
- All new `<img>` URLs MUST carry `?v={{ asset_version }}` (nginx serves `/static/` immutable for 30d behind Cloudflare; the versioning tests enforce this).
- Don't touch `icon.svg`/`favicon.svg`/the favicon raster pipeline — out of scope by design (minimal import).
