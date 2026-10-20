"""The one audience catalogue, read by the announce desk and the Tribune.

An audience key is a registry slug, or ``golf:<league slug>`` for one of the
Pay Sheet's leagues (ADR-075); plain ``golf`` is every league.
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


def audience_names():
    return dict(audience_choices())
