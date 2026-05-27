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
