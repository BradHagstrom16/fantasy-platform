"""Regression locks for the designer logo asset set (2026-05-27)."""
import pathlib
from unittest import mock

import pytest
from PIL import Image

from app import create_app
from extensions import db
from models.user import User

LOGO = pathlib.Path("static/img/logo")

EXPECTED_SVGS = [
    "icon.svg", "favicon.svg", "mascot-bust.svg", "mascot-badger.svg",
    "seal-color.svg", "seal-bone.svg", "seal-purple.svg", "app-tile.svg",
]


@pytest.mark.parametrize("name", EXPECTED_SVGS)
def test_logo_svg_exists_and_is_vector(name):
    """Each shipped logo SVG exists and is real vector markup."""
    p = LOGO / name
    assert p.exists(), f"{name} missing from static/img/logo/"
    head = p.read_text(errors="ignore")[:600]
    assert "<svg" in head, f"{name} is not an SVG"


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


IMG = pathlib.Path("static/img")


def test_favicon_ico_is_multisize():
    """favicon.ico carries the 16/32/48 sizes browsers expect."""
    p = IMG / "favicon.ico"
    assert p.exists(), "favicon.ico missing"
    im = Image.open(p)
    assert im.format == "ICO"
    assert {(16, 16), (32, 32), (48, 48)} <= set(im.ico.sizes())


def test_apple_touch_icon_is_180_and_opaque():
    """apple-touch tile is 180px with an opaque background (iOS needs no transparency)."""
    im = Image.open(IMG / "apple-touch-icon-180.png").convert("RGBA")
    assert im.size == (180, 180)
    # corner must be opaque (iOS composites transparency onto a black/white box)
    assert im.getpixel((2, 2))[3] == 255


def test_seal_email_png_exists_and_transparent():
    """Email seal PNG is ~160px and keeps a transparent background for the purple band."""
    im = Image.open(LOGO / "seal-email.png").convert("RGBA")
    assert 120 <= max(im.size) <= 200
    # corner transparent (sits on the purple email band)
    assert im.getpixel((0, 0))[3] == 0


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


@pytest.fixture()
def client():
    """Testing app with a fresh in-memory schema, yielding a bound test client."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_footer_renders_seal(client):
    """The footer renders the full-color roundel seal."""
    # /login is anonymous and extends base.html (footer always renders)
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"img/logo/seal-color.svg" in resp.data


def test_login_page_renders_bust(client):
    """The rendered login desktop panel carries the bust image."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"img/logo/mascot-bust.svg" in resp.data


def test_forgot_password_email_includes_seal(client):
    """The reset-password email embeds the seal via an absolute static URL."""
    # create a registered user via the app bound to this client
    app = client.application
    with app.app_context():
        u = User(username="seal_user", email="seal_user@test.com")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

    with mock.patch("core.auth.routes.send_platform_email") as send:
        resp = client.post("/forgot-password",
                           data={"email": "seal_user@test.com", "csrf_token": "x"})

    # anti-enumeration flow always redirects to login
    assert resp.status_code == 302
    assert send.called, "send_platform_email was not called"
    # signature: send_platform_email(to, subject, plain, html)
    html = send.call_args.args[3]
    assert "/static/img/logo/seal-email.png" in html
    assert 'alt="Corrupt Commish Club"' in html
