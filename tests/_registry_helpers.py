"""Shared helpers for tests that need to patch the game registry."""
from dataclasses import replace

# An in-season instant inside both games' self-serve join window (Wed Sep 2
# 2026, naive ISO = UTC on both seams). Both fall-'26 games close joining at
# the shared Week 1 deadline, Sat Sep 5 2026 11:00 CT (ADR-050), judged on
# each game's own clock seam — so every /join lock that ran on the real clock
# went red the moment that deadline passed.
IN_JOIN_WINDOW = '2026-09-02T12:00:00'


def open_join_window(monkeypatch):
    """Pin both games' clocks inside the self-serve join window."""
    monkeypatch.setenv('CFB_FAKE_NOW', IN_JOIN_WINDOW)
    monkeypatch.setenv('DOCKET_FAKE_NOW', IN_JOIN_WINDOW)


def set_status(monkeypatch, slug, status):
    """Rewrite a single registry entry's status for the duration of one test.

    Robust to future field additions on GameRegistryEntry — uses dataclasses.replace
    so unchanged fields are copied automatically.
    """
    from games import registry
    patched = [
        replace(entry, status=status) if entry.slug == slug else entry
        for entry in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)


def set_is_featured(monkeypatch, slug, is_featured):
    """Rewrite a single registry entry's is_featured flag for the duration of one test."""
    from games import registry
    patched = [
        replace(entry, is_featured=is_featured) if entry.slug == slug else entry
        for entry in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)


def pin_wc_era(monkeypatch):
    """Pin the full WC-era registry: WC the sole lounge owner, CFB pre-changeover.

    The frozen-WC test nets (test_home_routes, test_home_context, the pre-polish
    render, the pre-flip tiles lock) all assert the single-game WC lounge. Under
    the multi-featured seam the docket flag matters too: leaving docket featured
    would put a second headliner behind these pins and change every rendered
    byte. Pinning docket unfeatured here is what keeps those nets meaningful,
    and it composes from the two helpers above so future registry fields ride
    along automatically.
    """
    set_status(monkeypatch, 'worldcup', 'open')
    set_is_featured(monkeypatch, 'worldcup', True)
    set_status(monkeypatch, 'cfb', 'coming_soon')
    set_is_featured(monkeypatch, 'cfb', False)
    set_is_featured(monkeypatch, 'docket', False)
