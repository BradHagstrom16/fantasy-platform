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
