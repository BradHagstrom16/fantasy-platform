"""The one audience catalogue, read by the announce desk and the Tribune.

An audience key is a registry slug, or ``golf:<league slug>`` for one of the
Pay Sheet's leagues (ADR-075); plain ``golf`` is every league. A label is the
catalogue's today (a renamed league relabels its sent letters); a stored key
the catalogue no longer offers prints raw, on the desk and in the Tribune alike.
"""
from games.golf.services.leagues import leagues as golf_leagues
from games.registry import GAMES


def audience_choices():
    """Every audience as (key, label), in registry order, golf's leagues
    right after golf itself."""
    choices = []
    for entry in GAMES:
        choices.append((entry.slug, entry.display_name))
        if entry.slug == 'golf':
            choices.extend((f'golf:{league.slug}', league.name)
                           for league in golf_leagues())
    return choices


def audience_labels(keys, choices) -> list[str]:
    """The labels for stored ``keys``: catalogue order, then any key the
    catalogue no longer offers, raw. ``choices`` is ``audience_choices()``,
    passed in so a page builds it once."""
    chosen = set(keys)
    known = {key for key, _label in choices}
    return ([label for key, label in choices if key in chosen]
            + [key for key in keys if key not in known])
