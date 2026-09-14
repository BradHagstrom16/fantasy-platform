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
PWA = Path("static/img/pwa")
PURPLE = (58, 29, 114, 255)  # --purple-700 #3A1D72 (Council Purple)


def _head_on_purple(size, head_fraction):
    """The badger head centered on a solid Council Purple square of `size`px,
    the head scaled to `head_fraction` of the square's longest edge."""
    head = Image.open(SRC / "icon-1500.png").convert("RGBA")
    r = (size * head_fraction) / max(head.size)
    h = head.resize((round(head.width * r), round(head.height * r)), Image.LANCZOS)
    tile = Image.new("RGBA", (size, size), PURPLE)
    tile.alpha_composite(h, ((size - h.width) // 2, (size - h.height) // 2))
    return tile


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


def build_pwa_icons():
    """Write the installable-app (Web Push manifest) icon set into static/img/pwa/.

    - icon-192.png / icon-512.png: head on solid purple, `purpose: any` — the
      home-screen tile as-is (matches the apple-touch composition, ~0.83).
    - icon-512-maskable.png: `purpose: maskable` — head at 80% so it stays in
      the maskable safe zone (Android's circle mask), on a purple field that
      already bleeds to every edge (solid fill).
    - badge-96.png: a white monochrome silhouette of the head on transparent,
      for Android's status-bar `badge` glyph (the OS recolors it).
    """
    PWA.mkdir(parents=True, exist_ok=True)
    _head_on_purple(192, 0.83).convert("RGB").save(PWA / "icon-192.png")
    _head_on_purple(512, 0.83).convert("RGB").save(PWA / "icon-512.png")
    _head_on_purple(512, 0.80).convert("RGB").save(PWA / "icon-512-maskable.png")

    head = Image.open(SRC / "icon-1500.png").convert("RGBA")
    alpha = head.split()[3]
    white = Image.new("RGBA", head.size, (255, 255, 255, 0))
    white.putalpha(alpha)  # white silhouette masked by the head's shape
    r = 96 / max(white.size)
    white.resize((round(white.width * r), round(white.height * r)),
                 Image.LANCZOS).save(PWA / "badge-96.png")
    print("wrote pwa/icon-192.png, icon-512.png, icon-512-maskable.png, badge-96.png")


if __name__ == "__main__":
    build_favicon_ico()
    build_apple_touch()
    build_seal_email()
    build_pwa_icons()
