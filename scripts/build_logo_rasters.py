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
    """Write a multi-size favicon.ico (16/32/48) from the variant-03 head."""
    head = Image.open(SRC / "icon-1500.png").convert("RGBA")
    base = head.resize((256, 256), Image.LANCZOS)
    base.save(IMG / "favicon.ico", format="ICO",
              sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote favicon.ico (16/32/48)")


def build_apple_touch():
    """Write apple-touch-icon-180.png: the head composited on a solid purple square."""
    head = Image.open(SRC / "icon-1500.png").convert("RGBA")
    r = 150 / max(head.size)
    h = head.resize((round(head.width * r), round(head.height * r)), Image.LANCZOS)
    tile = Image.new("RGBA", (180, 180), PURPLE)
    tile.alpha_composite(h, ((180 - h.width) // 2, (180 - h.height) // 2))
    tile.convert("RGB").save(IMG / "apple-touch-icon-180.png")
    print("wrote apple-touch-icon-180.png (head on solid purple, 180x180)")


def build_seal_email():
    """Write seal-email.png: the roundel seal downscaled to ~160px (transparent)."""
    seal = Image.open(SRC / "seal-1500.png").convert("RGBA")
    r = 160 / max(seal.size)
    seal.resize((round(seal.width * r), round(seal.height * r)),
                Image.LANCZOS).save(LOGO / "seal-email.png")
    print("wrote seal-email.png (~160px, transparent)")


if __name__ == "__main__":
    build_favicon_ico()
    build_apple_touch()
    build_seal_email()
