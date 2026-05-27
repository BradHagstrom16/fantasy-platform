# Designer Logo Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-authored King Viking Badger logo system (PR #47) with the finished designer delivery — variant 03 head as the primary mark, a full-color roundel seal in the footer + email, and a transparency-safe raster pipeline for the favicon/app-icon.

**Architecture:** Production SVGs are copied from the gitignored `CCC-final/` delivery into committed `static/img/logo/`. Raster outputs (`.ico`, apple-touch, email seal PNG) are derived by a committed Pillow build script from two committed source PNGs (`scripts/logo-src/`) — `qlmanage` is avoided because it bakes an opaque white background and destroys transparency. The footer and email-header reference the seal; the email uses an absolute URL built with Flask's existing `url_for(..., _external=True)` mechanism (same one `reset_url` already uses), so no separate `SITE_URL` plumbing is needed.

**Tech Stack:** Flask + Jinja2, Pillow (raster derivation), pytest.

**Spec:** `docs/superpowers/specs/2026-05-27-designer-logo-integration-design.md`

---

## File Structure

**Created:**
- `static/img/logo/mascot-bust.svg`, `mascot-badger.svg`, `seal-color.svg`, `seal-bone.svg`, `seal-purple.svg`, `app-tile.svg`, `seal-email.png` — new brand assets
- `scripts/logo-src/icon-1500.png`, `scripts/logo-src/seal-1500.png` — committed transparent source PNGs for the raster build
- `scripts/build_logo_rasters.py` — reproducible Pillow raster builder
- `tests/test_logo_assets.py` — asset presence/format regression locks

**Modified:**
- `static/img/logo/icon.svg`, `favicon.svg` — replaced with variant 03 content
- `static/img/favicon.ico`, `static/img/apple-touch-icon-180.png` — regenerated
- `templates/base.html:199-210` — footer seal `<img>`
- `static/css/style.css` (after `.ccc-footer-voice` block ~line 154) — `.ccc-footer-seal` rule
- `core/auth/routes.py:122-127` — pass `seal_url` to the email template
- `templates/email/reset_password_html.j2:14-18` — seal `<img>` in the header band

**Untouched (out of scope):** `lockup-*.svg`, `wordmark-*.svg`; designer masters in `CCC-final/`.

---

### Task 1: Copy production SVGs + source PNGs into the repo

**Files:**
- Create: `static/img/logo/{mascot-bust,mascot-badger,seal-color,seal-bone,seal-purple,app-tile}.svg`, `scripts/logo-src/{icon-1500,seal-1500}.png`
- Modify: `static/img/logo/{icon,favicon}.svg`
- Test: `tests/test_logo_assets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_logo_assets.py`:

```python
"""Regression locks for the designer logo asset set (2026-05-27)."""
import pathlib

import pytest

LOGO = pathlib.Path("static/img/logo")

EXPECTED_SVGS = [
    "icon.svg", "favicon.svg", "mascot-bust.svg", "mascot-badger.svg",
    "seal-color.svg", "seal-bone.svg", "seal-purple.svg", "app-tile.svg",
]


@pytest.mark.parametrize("name", EXPECTED_SVGS)
def test_logo_svg_exists_and_is_vector(name):
    p = LOGO / name
    assert p.exists(), f"{name} missing from static/img/logo/"
    head = p.read_text(errors="ignore")[:600]
    assert "<svg" in head, f"{name} is not an SVG"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py -v`
Expected: FAIL — `mascot-bust.svg missing` (and other new names absent).

- [ ] **Step 3: Copy the assets**

```bash
cp CCC-final/CCC-final-03.svg static/img/logo/icon.svg
cp CCC-final/CCC-final-03.svg static/img/logo/favicon.svg
cp CCC-final/CCC-final-02.svg static/img/logo/mascot-bust.svg
cp CCC-final/CCC-final-01.svg static/img/logo/mascot-badger.svg
cp CCC-final/CCC-final-04.svg static/img/logo/seal-color.svg
cp CCC-final/CCC-final-05.svg static/img/logo/seal-bone.svg
cp CCC-final/CCC-final-06.svg static/img/logo/seal-purple.svg
cp CCC-final/CCC-final-07.svg static/img/logo/app-tile.svg
mkdir -p scripts/logo-src
cp CCC-final/CCC-final-03.png scripts/logo-src/icon-1500.png
cp CCC-final/CCC-final-04.png scripts/logo-src/seal-1500.png
```

Note: `favicon.svg` and `icon.svg` are intentionally identical (variant 03) — the "head everywhere" decision. The old hand-authored simplified favicon cut is retired.

- [ ] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py -v`
Expected: PASS (8 parametrized cases green).

- [ ] **Step 5: Commit**

```bash
git add static/img/logo/*.svg scripts/logo-src/ tests/test_logo_assets.py
git commit -m "platform(brand): swap in designer SVG logo set (variant 03 primary)"
```

---

### Task 2: Reproducible raster build (favicon.ico, apple-touch, email seal)

**Files:**
- Create: `scripts/build_logo_rasters.py`
- Modify: `static/img/favicon.ico`, `static/img/apple-touch-icon-180.png`; Create: `static/img/logo/seal-email.png`
- Test: `tests/test_logo_assets.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_logo_assets.py`)**

```python
from PIL import Image

IMG = pathlib.Path("static/img")


def test_favicon_ico_is_multisize():
    p = IMG / "favicon.ico"
    assert p.exists(), "favicon.ico missing"
    im = Image.open(p)
    assert im.format == "ICO"
    assert {(16, 16), (32, 32), (48, 48)} <= set(im.ico.sizes())


def test_apple_touch_icon_is_180_and_opaque():
    im = Image.open(IMG / "apple-touch-icon-180.png").convert("RGBA")
    assert im.size == (180, 180)
    # corner must be opaque (iOS composites transparency onto a black/white box)
    assert im.getpixel((2, 2))[3] == 255


def test_seal_email_png_exists_and_transparent():
    im = Image.open(LOGO / "seal-email.png").convert("RGBA")
    assert 120 <= max(im.size) <= 200
    # corner transparent (sits on the purple email band)
    assert im.getpixel((0, 0))[3] == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py -k "favicon_ico or apple_touch or seal_email" -v`
Expected: FAIL — `seal-email.png` missing; `favicon.ico`/apple-touch still the old hand-authored rasters (ico size-set assertion or apple-touch opacity may already pass, but `seal_email` fails). At least one test fails.

- [ ] **Step 3: Write the build script**

Create `scripts/build_logo_rasters.py`:

```python
"""Derive raster logo assets from committed transparent PNG masters.

Run from the repo root:  venv/bin/python scripts/build_logo_rasters.py

Pillow only — `qlmanage` bakes an opaque white background and destroys
transparency, so it must NOT be used for these assets.
"""
from pathlib import Path

from PIL import Image

SRC = Path("scripts/logo-src")
LOGO = Path("static/img/logo")
IMG = Path("static/img")
PURPLE = (58, 29, 114, 255)  # --purple-700 #3A1D72


def build_favicon_ico():
    head = Image.open(SRC / "icon-1500.png").convert("RGBA")
    base = head.resize((256, 256), Image.LANCZOS)
    base.save(IMG / "favicon.ico", format="ICO",
              sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote favicon.ico (16/32/48)")


def build_apple_touch():
    head = Image.open(SRC / "icon-1500.png").convert("RGBA")
    r = 150 / max(head.size)
    h = head.resize((round(head.width * r), round(head.height * r)), Image.LANCZOS)
    tile = Image.new("RGBA", (180, 180), PURPLE)
    tile.alpha_composite(h, ((180 - h.width) // 2, (180 - h.height) // 2))
    tile.convert("RGB").save(IMG / "apple-touch-icon-180.png")
    print("wrote apple-touch-icon-180.png (head on solid purple, 180x180)")


def build_seal_email():
    seal = Image.open(SRC / "seal-1500.png").convert("RGBA")
    r = 160 / max(seal.size)
    seal.resize((round(seal.width * r), round(seal.height * r)),
                Image.LANCZOS).save(LOGO / "seal-email.png")
    print("wrote seal-email.png (~160px, transparent)")


if __name__ == "__main__":
    build_favicon_ico()
    build_apple_touch()
    build_seal_email()
```

- [ ] **Step 4: Run the build script**

Run: `venv/bin/python scripts/build_logo_rasters.py`
Expected output:
```
wrote favicon.ico (16/32/48)
wrote apple-touch-icon-180.png (head on solid purple, 180x180)
wrote seal-email.png (~160px, transparent)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py -v`
Expected: PASS (all cases green).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_logo_rasters.py static/img/favicon.ico static/img/apple-touch-icon-180.png static/img/logo/seal-email.png tests/test_logo_assets.py
git commit -m "platform(brand): regenerate rasters via Pillow (ico, apple-touch, email seal)"
```

---

### Task 3: Footer seal

**Files:**
- Modify: `templates/base.html:200-204`, `static/css/style.css` (after `.ccc-footer-voice` block)
- Test: `tests/test_logo_assets.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_logo_assets.py`)**

```python
from app import create_app
from extensions import db


@pytest.fixture()
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_footer_renders_seal(client):
    # /login is anonymous and extends base.html (footer always renders)
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"img/logo/seal-color.svg" in resp.data
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_footer_renders_seal -v`
Expected: FAIL — `seal-color.svg` not in the footer markup yet.

- [ ] **Step 3: Add the seal to the footer**

In `templates/base.html`, change the footer voice band (currently lines 200-204):

```html
        <div class="ccc-footer-voice">
            <div class="container">
                <img src="{{ url_for('static', filename='img/logo/seal-color.svg') }}" class="ccc-footer-seal" alt="Corrupt Commish Club" width="72" height="72">
                An exclusive members&rsquo; club. The Commish keeps the ledger. The Club keeps the code. The losers keep the tab.
            </div>
        </div>
```

- [ ] **Step 4: Add the CSS**

In `static/css/style.css`, immediately after the closing `}` of the `.ccc-footer-voice` rule (~line 154):

```css
.ccc-footer-seal {
  display: block;
  width: 72px;
  height: 72px;
  margin: 0 auto .75rem;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_footer_renders_seal -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/base.html static/css/style.css tests/test_logo_assets.py
git commit -m "platform(brand): add full-color roundel seal to site footer"
```

---

### Task 4: Email header seal + absolute seal URL

**Files:**
- Modify: `core/auth/routes.py:122-127`, `templates/email/reset_password_html.j2:14-18`
- Test: `tests/test_logo_assets.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_logo_assets.py`)**

```python
from unittest import mock

from models.user import User


def test_forgot_password_email_includes_seal(client):
    # create a registered user via the app bound to this client
    app = client.application
    with app.app_context():
        u = User(username="seal_user", email="seal_user@test.com")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

    with mock.patch("core.auth.routes.send_platform_email") as send:
        client.post("/forgot-password",
                    data={"email": "seal_user@test.com", "csrf_token": "x"})

    assert send.called, "send_platform_email was not called"
    # signature: send_platform_email(to, subject, plain, html)
    html = send.call_args.args[3]
    assert "/static/img/logo/seal-email.png" in html
    assert 'alt="Corrupt Commish Club"' in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_forgot_password_email_includes_seal -v`
Expected: FAIL — the rendered email has no seal `<img>` yet.

- [ ] **Step 3: Pass `seal_url` from the route**

In `core/auth/routes.py`, update the reset-email block (currently lines 122-127):

```python
            token = generate_reset_token(user.email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            seal_url = url_for('static', filename='img/logo/seal-email.png', _external=True)
            plain = render_template('email/reset_password_plain.txt',
                                    reset_url=reset_url, user=user)
            html = render_template('email/reset_password_html.j2',
                                   reset_url=reset_url, seal_url=seal_url, user=user)
```

- [ ] **Step 4: Add the seal to the email header band**

In `templates/email/reset_password_html.j2`, replace the header band (currently lines 14-18):

```html
        <!-- Header band -->
        <tr>
          <td style="background:#2A1150; padding:24px 28px; text-align:center;">
            <img src="{{ seal_url }}" width="64" height="64" alt="Corrupt Commish Club" style="display:block; margin:0 auto 8px; border:0;">
            <span style="font-family:'Teko', sans-serif; font-size:24px; font-weight:600; letter-spacing:.04em; color:#C9A227; text-transform:uppercase;">Corrupt Commish Club</span>
          </td>
        </tr>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_logo_assets.py::test_forgot_password_email_includes_seal -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/auth/routes.py templates/email/reset_password_html.j2 tests/test_logo_assets.py
git commit -m "platform(brand): add roundel seal to password-reset email header"
```

---

### Task 5: Full-suite verification, browser smoke, docs

**Files:** none (verification + docs)

- [ ] **Step 1: Run the full test suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/`
Expected: PASS — including `tests/test_asset_versioning.py` (asset cache-busting lock) and the new `tests/test_logo_assets.py`. If any prior test referenced the old logo bytes, investigate before proceeding.

- [ ] **Step 2: Browser smoke — navbar, auth, footer**

Run: `FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`
Then load `http://localhost:5099/` and `http://localhost:5099/login`. Confirm: navbar mark (28px) is the new head; auth mark (56px) is the new head; footer shows the full-color seal on the purple band. Use the chrome-devtools/playwright MCP to screenshot if helpful.

- [ ] **Step 3: Favicon at 16px (the one flagged risk)**

In the browser, inspect the actual tab favicon and zoom a 16px render of `static/img/logo/favicon.svg`. Confirm the helmeted head reads at 16px and is not muddy. If it IS muddy, STOP and flag — the fallback is a bolder simplified favicon cut (separate decision), not shipping a muddy mark.

- [ ] **Step 4: Render and eyeball the reset email**

In a Python shell within the app context, render `email/reset_password_html.j2` with a sample `seal_url` and `reset_url`, write it to a temp `.html`, and open it. Confirm the seal sits on the purple band and reads. (Production sends use the absolute `url_for(_external=True)` URL.)

```python
venv/bin/python - <<'PY'
from app import create_app
from flask import render_template
app = create_app('development')
with app.test_request_context():
    html = render_template('email/reset_password_html.j2',
                           reset_url='https://cccfantasy.com/x',
                           seal_url='https://cccfantasy.com/static/img/logo/seal-email.png',
                           user=None)
    open('/tmp/ccc-email-preview.html','w').write(html)
print('wrote /tmp/ccc-email-preview.html')
PY
```

- [ ] **Step 5: Update the logo memory doc**

Update `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_logo_king_viking_badger.md`: the official logo is now the **professional designer delivery** (variant 03 head primary; full-color roundel seal in footer + email), not the hand-authored SVGs. Record the new asset map (`static/img/logo/` names from this plan), the `scripts/build_logo_rasters.py` Pillow pipeline, and the **gotcha**: `qlmanage` bakes an opaque white background — use Pillow for transparent rasters. Note the unused `lockup-*`/`wordmark-*` SVGs are now stale (follow-up).

- [ ] **Step 6: Final review commit (if any docs/cleanup changed)**

```bash
git status
# commit any remaining intended changes; do NOT commit CCC-final/ (gitignored) or unrelated files
```

---

## Notes / Follow-ups

- **Order not yet approved.** Two delivery gaps (no standalone wordmark/lockup; no dark-background mascot variant) are Brad's separate call with the designer.
- **Stale assets:** `lockup-*.svg` / `wordmark-*.svg` remain in `static/img/logo/` unused and now visually inconsistent. Removing or regenerating them is a deliberate follow-up, not part of this pass.
- **No PWA manifest** today; maskable icons are out of scope.
