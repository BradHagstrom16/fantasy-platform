"""Survivor's live boards for the Commish's announcements.

``[[survivor-board]]``, ``[[survivor-cuts]]`` and ``[[survivor-picks]]`` in
an announcement body (core/admin/announce.py, utils/letter_markup.py) render
through these builders: each takes the token's settings and returns a Club
Letter Block, read from the database at render time so the preview, the
test send and the real send all carry the current numbers.

The reveal guard: a board shows a COMPLETE week only (the default is the
latest complete week; ``week=N`` is refused until week N completes), so an
announcement can never put a pick in front of the pool before its week has
settled. A ``ValueError`` is the admin's error line, worded to follow the
board's name.
"""
from flask import current_app
from sqlalchemy.orm import joinedload

from games.cfb.models import CfbEnrollment, CfbGame, CfbPick, CfbWeek
from games.cfb.services.game_logic import get_official_standings, pick_distribution
from games.cfb.services.lounge import cuts_sentence, field_impact_sentence
from games.cfb.services.week_state import latest_complete_week
from games.cfb.utils import get_week_display_name
from utils.email_layout import (
    paragraph_block,
    result_block,
    stack_blocks,
    text_span,
)
from utils.letter_markup import board_number

DEFAULT_TOP = 10
RESULT_TAGS = {'W': 'Won', 'L': 'Lost', 'NC': 'No contest', None: 'Pending'}


def _finished_week(args, *, allowed):
    number = board_number(args, 'week', allowed=allowed)
    if number is None:
        week = latest_complete_week()
        if week is None:
            raise ValueError('has no finished week to show yet.')
        return week
    week = CfbWeek.query.filter_by(week_number=number).first()
    if week is None:
        raise ValueError(f'has no Week {number}.')
    if not week.is_complete:
        raise ValueError(f'shows finished weeks only; Week {number} is not '
                         f'complete yet.')
    return week


def _lives(count):
    return 'One life' if count == 1 else f'{count} lives'


def survivor_board(args):
    """Still standing, in the official order (lives, then cumulative
    spread), competition-ranked; ``top=N`` (default 10) caps the table and
    a line counts the rest."""
    top = board_number(args, 'top', allowed=('top',), default=DEFAULT_TOP)
    season = current_app.config.get('CFB_SEASON_YEAR', 2026)
    standings, ranks = get_official_standings(season)
    if not standings:
        raise ValueError('has nobody standing to show.')
    rows = [(f'{ranks[e.id]}. {e.get_display_name()}',
             f'{_lives(e.lives_remaining)} · spread '
             f'{(e.cumulative_spread or 0.0):+.1f}')
            for e in standings[:top]]
    blocks = [result_block(f'Still standing: {len(standings)}', rows)]
    rest = len(standings) - len(rows)
    if rest:
        blocks.append(paragraph_block([text_span(
            f'And {rest} more still standing; the full board is on the site.'
        )]))
    return stack_blocks(blocks)


def survivor_cuts(args):
    """The week's damage in words: who lost a life, who was cut, how many
    remain ("Three players lost a life in Week 3. Two were cut. 12
    remain."), then the names of the cut."""
    week = _finished_week(args, allowed=('week',))
    season = current_app.config.get('CFB_SEASON_YEAR', 2026)
    enrollments = (CfbEnrollment.query.filter_by(season_year=season)
                   .options(joinedload(CfbEnrollment.user)).all())
    lines = [field_impact_sentence(week, get_week_display_name(week))]
    cut = cuts_sentence(week, enrollments)
    if cut:
        lines.append(cut)
    return stack_blocks([paragraph_block([text_span(line)]) for line in lines])


def survivor_picks(args):
    """Who the field backed in the week: every picked team with its locked
    spread, how many rode it, and the result in words. The Results page's
    order (count, then name), never by spread."""
    week = _finished_week(args, allowed=('week',))
    picks = (CfbPick.query.filter_by(week_id=week.id)
             .options(joinedload(CfbPick.team)).all())
    if not picks:
        raise ValueError(f'has no picks in {get_week_display_name(week)}.')
    games = CfbGame.query.filter_by(week_id=week.id).all()
    rows = []
    for row in pick_distribution(picks, games):
        team = row['name']
        if row['spread'] is not None:
            team = f'{team} ({row["spread"]:+g})'
        picked = f'{row["count"]} pick{"s" if row["count"] != 1 else ""}'
        rows.append((team, picked, RESULT_TAGS[row['result']]))
    return result_block(f'{get_week_display_name(week)} pick split', rows)


BOARDS = {
    'survivor-board': survivor_board,
    'survivor-cuts': survivor_cuts,
    'survivor-picks': survivor_picks,
}
