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
