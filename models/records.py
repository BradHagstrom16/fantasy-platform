"""
The club's permanent record (open-items §E, ADR-068)
=====================================================
One row per member per finished season of a game: where they finished and
what the season recorded about them. Written once at season end by
``flask records close`` through each game's ``season_finishes`` registry
callable; read by ``/records`` and by ``User.get_avatar`` (the reigning
champion is derived from the place-1 rows, never declared).

The rows are a ledger, not a cache: a game's live tables may be scoped,
reseeded or archived later without the club losing who won what. ``name``
is frozen as the season recorded it (the 2025 CFB season has names and no
accounts), ``user_id`` links it to a member when one is known.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from flask import g
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from extensions import db
from models.user import User

_G_KEY = '_reigning_champion_ids'


@dataclass(frozen=True)
class FinishDraft:
    """What a game's ``season_finishes(season_year)`` returns per member.

    ``place`` is competition rank (ties share and gap); ``outcome`` is the
    game's own word for the finish when it has one (CFB: champion /
    survived / eliminated), ``detail`` the one line the board prints.
    """
    user_id: int | None
    name: str
    place: int
    outcome: str | None
    detail: str | None


class SeasonNotClosed(Exception):
    """The game says this season is not final yet."""


class SeasonAlreadyOnRecord(Exception):
    """Rows exist for this game and season; pass force to rewrite them."""


class InvalidBoard(Exception):
    """A board the record will not hold: empty, places that are not a
    competition rank, a name or a member twice, or (Survivor 2025) a link map
    that names a stranger or a name the archive never had."""


class SeasonFinish(db.Model):
    __tablename__ = 'season_finishes'
    __table_args__ = (
        db.UniqueConstraint('game', 'season_year', 'name',
                            name='uq_season_finish_game_year_name'),
        # One finish per member per season. NULLs are distinct on both
        # engines, so any number of unlinked names still fit.
        db.UniqueConstraint('game', 'season_year', 'user_id',
                            name='uq_season_finish_game_year_user'),
        db.Index('ix_season_finish_game_year', 'game', 'season_year'),
    )

    id = db.Column(db.Integer, primary_key=True)
    # The registry slug (games/registry.py), never a display name.
    game = db.Column(db.String(20), nullable=False)
    season_year = db.Column(db.Integer, nullable=False)
    # NULL means the season never linked this name to an account (the 2025
    # CFB names until the link map names them).
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True,
                        index=True)
    # The name as the season recorded it; frozen even when the member later
    # renames (the live pages follow the rename, the record does not). As
    # wide as the platform display name it copies.
    name = db.Column(db.String(User.display_name.type.length), nullable=False)
    # Competition rank: 1 + the count who finished strictly better.
    place = db.Column(db.Integer, nullable=False)
    outcome = db.Column(db.String(30), nullable=True)
    detail = db.Column(db.String(200), nullable=True)
    # How many finished that season: the denominator every place carries.
    field_size = db.Column(db.Integer, nullable=False)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(UTC))

    user = db.relationship('User')

    def __repr__(self):
        return f'<SeasonFinish {self.game} {self.season_year} #{self.place} {self.name}>'


def seasons_on_record() -> list[tuple[str, int]]:
    """Every (game, season_year) with rows, newest season first, then game."""
    rows = db.session.execute(
        select(SeasonFinish.game, SeasonFinish.season_year).distinct()
        .order_by(SeasonFinish.season_year.desc(), SeasonFinish.game)).all()
    return [(game, year) for game, year in rows]


def finishes_for(game: str, season_year: int) -> list[SeasonFinish]:
    """One season's board, place then name; the linked members ride along
    (the page prints their avatar and current name, never per row)."""
    return db.session.scalars(
        select(SeasonFinish).filter_by(game=game, season_year=season_year)
        .options(joinedload(SeasonFinish.user))
        .order_by(SeasonFinish.place, func.lower(SeasonFinish.name),
                  SeasonFinish.name)).all()


def champions() -> list[SeasonFinish]:
    """Every place-1 row, newest season first, then game, then name."""
    return db.session.scalars(
        select(SeasonFinish).filter_by(place=1)
        .options(joinedload(SeasonFinish.user))
        .order_by(SeasonFinish.season_year.desc(), SeasonFinish.game,
                  func.lower(SeasonFinish.name), SeasonFinish.name)).all()


def reigning_champion_user_ids() -> frozenset[int]:
    """The linked winners of each game's most recently closed season.

    Cached on ``g`` for the app context: a standings page calls
    ``User.get_avatar()`` once per row, and this is one query per request.
    ``record_season`` clears the cache, so a close inside a request (the
    tests, a CLI run) reads its own write.
    """
    if _G_KEY not in g:
        winners = champions()
        latest = {}
        for row in winners:
            latest[row.game] = max(latest.get(row.game, row.season_year),
                                   row.season_year)
        setattr(g, _G_KEY, frozenset(
            row.user_id for row in winners
            if row.user_id is not None and row.season_year == latest[row.game]))
    return getattr(g, _G_KEY)


def clear_reigning_champion_cache() -> None:
    """Registered as a before_request hook (app.py): g outlives a request
    whenever an app context was pushed before it (the test fixture, a CLI
    run), so each request starts from the record, not a cached set."""
    g.pop(_G_KEY, None)


def _check_board(game: str, season_year: int, drafts: list[FinishDraft]) -> None:
    """The one boundary where three games' builders feed a permanent ledger:
    refuse what the trophy and the page cannot read. Competition rank means
    every place is 1 + the count placed strictly better, so a board without
    a place 1 fails here too."""
    label = f'{game} {season_year}'
    if not drafts:
        raise InvalidBoard(f'{label}: the board is empty')
    places = [d.place for d in drafts]
    if any(p != 1 + sum(1 for o in places if o < p) for p in places):
        raise InvalidBoard(
            f'{label}: places {sorted(places)} are not a competition rank')
    names = Counter(d.name for d in drafts)
    twice = sorted(name for name, n in names.items() if n > 1)
    if twice:
        raise InvalidBoard(f'{label}: recorded twice: {", ".join(twice)}')
    members = Counter(d.user_id for d in drafts if d.user_id is not None)
    twice = sorted(uid for uid, n in members.items() if n > 1)
    if twice:
        raise InvalidBoard(
            f'{label}: one member under two names (user ids {twice})')


def record_season(game: str, season_year: int, drafts: list[FinishDraft], *,
                  force: bool = False) -> list[SeasonFinish]:
    """Write a finished season's board. Refuses a board ``_check_board``
    rejects, and an already-recorded season unless ``force``, which replaces
    its rows in the same transaction."""
    _check_board(game, season_year, drafts)
    existing = finishes_for(game, season_year)
    if existing and not force:
        raise SeasonAlreadyOnRecord(f'{game} {season_year} is already on record')
    for row in existing:
        db.session.delete(row)
    # Flush the deletes first: the unit of work would otherwise INSERT the
    # new rows before the DELETEs and trip the (game, season, name) key on
    # the very rows being replaced. Same transaction; commit is below.
    db.session.flush()
    rows = [
        SeasonFinish(game=game, season_year=season_year, user_id=d.user_id,
                     name=d.name, place=d.place, outcome=d.outcome,
                     detail=d.detail, field_size=len(drafts))
        for d in drafts
    ]
    db.session.add_all(rows)
    db.session.commit()
    g.pop(_G_KEY, None)
    return rows
