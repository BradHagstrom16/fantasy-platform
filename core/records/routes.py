"""The Record: every finished season, who won it, and where everyone finished.

Public, one page, read straight from the ledger (models.records); nothing is
computed here. A champion's name is the door into that season's board, and
each board points at the room's own archive of the season where one exists.
"""
from flask import render_template, url_for

from core.records import records_bp
from games.registry import get_entry
from models.records import champions, finishes_for, seasons_on_record

# The room's own archive of a season, by endpoint name so this module never
# imports a game: a bare endpoint, or ``(endpoint, kwargs)`` for a page that
# takes the season as a query (the Pay Sheet's Record Room, ``?season=``). A
# season with no entry simply shows no link. Only a PUBLIC page pinned to
# that season belongs here: this page is public, and a live room page (the
# Docket's ledger is members-only and always the current season) would send
# a visitor to a join page or to the wrong year. The Docket's entry waits for
# a public page pinned to one season.
SEASON_ARCHIVES = {
    ('cfb', 2025): 'cfb.history',
    ('worldcup', 2026): 'worldcup.leaderboard',
    ('golf', 2026): ('golf.record_room', {'season': 2026}),
}


def archive_url(value) -> str:
    """The URL of a SEASON_ARCHIVES value: an endpoint, or one with its query."""
    if isinstance(value, tuple):
        endpoint, kwargs = value
        return url_for(endpoint, **kwargs)
    return url_for(value)


def _game_name(slug: str) -> str:
    return get_entry(slug).short_name


def _row(finish) -> dict:
    """One finish for the templates: the recorded name always, the avatar
    when the row is linked, and the member's current name only when it has
    moved on from the one the season recorded."""
    user = finish.user
    current = user.get_display_name() if user is not None else None
    return {
        'place': finish.place,
        'name': finish.name,
        'detail': finish.detail,
        'avatar': user.get_avatar() if user is not None else None,
        'now': current if current is not None and current != finish.name else None,
    }


@records_bp.route('', strict_slashes=False)
def index():
    roll = [
        {**_row(row), 'game': row.game, 'season_year': row.season_year,
         'game_name': _game_name(row.game)}
        for row in champions()
    ]
    boards = []
    for game, season_year in seasons_on_record():
        archive = SEASON_ARCHIVES.get((game, season_year))
        boards.append({
            'game': game,
            'season_year': season_year,
            'game_name': _game_name(game),
            'rows': [_row(row) for row in finishes_for(game, season_year)],
            'archive_url': archive_url(archive) if archive else None,
        })
    return render_template('records/index.html', roll=roll, boards=boards)
