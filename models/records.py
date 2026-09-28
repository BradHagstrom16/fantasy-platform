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
from dataclasses import dataclass
from datetime import UTC, datetime

from flask import g
from sqlalchemy import select

from extensions import db

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


class SeasonFinish(db.Model):
    __tablename__ = 'season_finishes'
    __table_args__ = (
        db.UniqueConstraint('game', 'season_year', 'name',
                            name='uq_season_finish_game_year_name'),
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
    # renames (the live pages follow the rename, the record does not).
    name = db.Column(db.String(80), nullable=False)
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
    return db.session.scalars(
        select(SeasonFinish).filter_by(game=game, season_year=season_year)
        .order_by(SeasonFinish.place, SeasonFinish.name)).all()


def champions() -> list[SeasonFinish]:
    """Every place-1 row, newest season first, then game, then name."""
    return db.session.scalars(
        select(SeasonFinish).filter_by(place=1)
        .order_by(SeasonFinish.season_year.desc(), SeasonFinish.game,
                  SeasonFinish.name)).all()


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


def record_season(game: str, season_year: int, drafts: list[FinishDraft], *,
                  force: bool = False) -> list[SeasonFinish]:
    """Write a finished season's board. Refuses an already-recorded season
    unless ``force``, which replaces its rows in the same transaction."""
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
