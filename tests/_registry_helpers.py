"""Shared helpers for tests that need to patch the game registry."""
from dataclasses import replace


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
