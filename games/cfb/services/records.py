"""Survivor's board for the club's permanent record (ADR-068).

``season_finishes`` is the registry seam ``flask records close cfb YEAR``
calls. Two sources:

- 2025, the first season, played at the old clubhouse: the frozen archive
  ``games/cfb/data/season_2025.json`` (names only, never accounts) plus the
  hand-kept link map ``season_2025_links.json`` (archive name -> username)
  that names the members who have an account here. The archive file stays
  frozen (ADR-057, tests/test_cfb_history.py); links live in this second
  file so the archive never carries an identity.
- 2026 and later: the live tables, only once the lounge says the season
  is 'post' (a sole survivor, or the final playoff week complete).

Place is competition rank. Survivors take the official standings' ranks;
every eliminated player ranks after every survivor, by out week alone
(later out = better, the same week shares a place). Cumulative spread is
what the detail line prints, never a ranking key here: it only ever breaks
equal-lives ties among survivors, and the official standings already did.
"""
import json
from pathlib import Path

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from extensions import db
from games.cfb.models import CfbEnrollment, CfbWeek, CfbWeekOutcome
from games.cfb.services.game_logic import get_official_standings
from games.cfb.services.history import get_season_2025
from games.cfb.services.lounge import cfb_lounge_state
from models.records import FinishDraft, SeasonNotClosed
from models.user import User
from utils.identifier import normalize_identifier

ARCHIVE_YEAR = 2025
LINKS_2025_PATH = Path(__file__).resolve().parent.parent / 'data' / 'season_2025_links.json'


def _lives(n: int) -> str:
    return f'{n} life' if n == 1 else f'{n} lives'


def _out_detail(out_week: int, spread: float) -> str:
    return f'Out Week {out_week} · spread {spread:.1f}'


def _eliminated_places(out_weeks: list[int], survivors: int) -> list[int]:
    """Places for the eliminated, after every survivor: 1 + survivors + the
    count who lasted strictly longer."""
    return [1 + survivors + sum(1 for w in out_weeks if w > week) for week in out_weeks]


def season_finishes(season_year: int) -> list[FinishDraft]:
    if season_year == ARCHIVE_YEAR:
        return _archive_2025()
    if (season_year != current_app.config['CFB_SEASON_YEAR']
            or cfb_lounge_state() != 'post'):
        raise SeasonNotClosed(f'Survivor {season_year} has not concluded')
    return _live_season(season_year)


def _live_season(season_year: int) -> list[FinishDraft]:
    survivors, ranks = get_official_standings(season_year)
    drafts = [
        FinishDraft(
            user_id=e.user_id,
            name=e.get_display_name(),
            place=ranks[e.id],
            outcome='champion' if ranks[e.id] == 1 else 'survived',
            detail=f'{_lives(e.lives_remaining)} · spread {e.cumulative_spread or 0.0:.1f}',
        )
        for e in survivors
    ]
    eliminated = (
        CfbEnrollment.query
        .filter_by(season_year=season_year, is_eliminated=True)
        .options(joinedload(CfbEnrollment.user))
        .all()
    )
    # The week that eliminated each player: the LAST outcome carrying the
    # elimination with its lost life (a revived player can fall twice).
    out_week = dict(db.session.execute(
        select(CfbWeekOutcome.user_id, func.max(CfbWeek.week_number))
        .join(CfbWeek, CfbWeek.id == CfbWeekOutcome.week_id)
        .filter(CfbWeekOutcome.is_eliminated.is_(True),
                CfbWeekOutcome.lost_life.is_(True))
        .group_by(CfbWeekOutcome.user_id)
    ).all())
    eliminated.sort(key=lambda e: (-out_week[e.user_id], e.get_display_name().lower()))
    places = _eliminated_places([out_week[e.user_id] for e in eliminated], len(survivors))
    drafts.extend(
        FinishDraft(
            user_id=e.user_id,
            name=e.get_display_name(),
            place=place,
            outcome='eliminated',
            detail=_out_detail(out_week[e.user_id], e.cumulative_spread or 0.0),
        )
        for e, place in zip(eliminated, places, strict=True)
    )
    return drafts


def _archive_2025() -> list[FinishDraft]:
    standings = get_season_2025()['standings']
    links = json.loads(LINKS_2025_PATH.read_text(encoding='utf-8'))
    user_ids = {}
    for name, username in links.items():
        user = db.session.scalar(select(User).filter(
            func.lower(User.username) == normalize_identifier(username)))
        if user is None:
            raise LookupError(f'{name!r} links to {username!r}, which is not a member')
        user_ids[name] = user.id
    survivors = [row for row in standings if row['outcome'] == 'champion']
    fallen = [row for row in standings if row['outcome'] != 'champion']
    places = _eliminated_places([row['out_week'] for row in fallen], len(survivors))
    drafts = [
        FinishDraft(
            user_id=user_ids.get(row['name']),
            name=row['name'],
            place=1,
            outcome='champion',
            detail=f"{_lives(row['final_lives'])} · spread {row['cumulative_spread']:.1f}",
        )
        for row in survivors
    ]
    drafts.extend(
        FinishDraft(
            user_id=user_ids.get(row['name']),
            name=row['name'],
            place=place,
            outcome='eliminated',
            detail=_out_detail(row['out_week'], row['cumulative_spread']),
        )
        for row, place in zip(fallen, places, strict=True)
    )
    return drafts
