"""
The Docket — Database Models (import-spine slice)
=================================================
DocketWeek + DocketGame only; pick/result tables land with the grading
engine. All tables use the ``docket_`` prefix.

DATETIME CONTRACT (D6 — single contract, a deliberate, pre-approved
deviation from CFB's split contract): every datetime column in every
``docket_*`` table stores naive UTC. No pool-timezone wall clock is ever
written to a docket column. America/Chicago exists in exactly two places —
week-boundary/deadline computation at week creation
(games/docket/services/weeks.py, DST-safe wall-clock arithmetic) and
rendering. Writers convert through games/docket/utils.to_naive_utc().
Test-locked by tests/test_docket_models.py.

Game identity is the Odds API event id end-to-end (D22): no curated team
table, no name matching — ``api_event_id`` is globally unique and teams are
stored as the API's participant names verbatim.
"""
from datetime import UTC, datetime

from extensions import db


class DocketWeek(db.Model):
    """One docket week: a half-open [start_at, end_at) slice of the season.

    Weeks partition time continuously at Tuesday 06:00 America/Chicago
    boundaries; a game belongs to the week containing its kickoff. The
    stored bounds/deadline are those CT wall-clock instants converted to
    naive UTC at creation.
    """
    __tablename__ = 'docket_week'

    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, unique=True, nullable=False)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    deadline_at = db.Column(db.DateTime, nullable=False)
    # Weekly designated tiebreaker game (Week 1 hand-set: Wisconsin @ Notre
    # Dame; admin designation UI lands with T9). use_alter breaks the
    # docket_week <-> docket_game FK cycle at CREATE TABLE time.
    tiebreaker_game_id = db.Column(
        db.Integer,
        db.ForeignKey('docket_game.id', name='fk_docket_week_tiebreaker_game',
                      use_alter=True),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    tiebreaker_game = db.relationship(
        'DocketGame', foreign_keys=[tiebreaker_game_id])

    def __repr__(self):
        return f'<DocketWeek {self.week_number}>'


class DocketGame(db.Model):
    """One importable game (either sport) on a week's docket.

    ``kickoff`` is the LIVE commence time, refreshed from the free /events
    endpoint on every sync run (D19). ``kickoff_at_deadline`` is frozen by
    the deadline pass (D7) as the slot-substitution ordering input — no
    writer exists in the import-spine slice.

    Lines follow the DQ-6 analog (D3): the first fetch that finds a posted
    market locks it — value, bookmaker key, and locked_at move as one unit
    per market (D17) — and later runs only fill still-empty markets. A
    locked line is never overwritten. ``home_spread`` is from the home
    team's perspective (negative = home favored); ``total_points`` is the
    O/U total.
    """
    __tablename__ = 'docket_game'

    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey('docket_week.id'),
                        nullable=False, index=True)
    # The Odds API sport key: americanfootball_ncaaf | americanfootball_nfl.
    sport = db.Column(db.String(40), nullable=False)
    api_event_id = db.Column(db.String(64), unique=True, nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    kickoff = db.Column(db.DateTime, nullable=False)
    kickoff_at_deadline = db.Column(db.DateTime, nullable=True)

    home_spread = db.Column(db.Float, nullable=True)
    spread_book = db.Column(db.String(40), nullable=True)
    spread_locked_at = db.Column(db.DateTime, nullable=True)
    total_points = db.Column(db.Float, nullable=True)
    total_book = db.Column(db.String(40), nullable=True)
    total_locked_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    week = db.relationship('DocketWeek', foreign_keys=[week_id],
                           backref='games')

    def __repr__(self):
        return f'<DocketGame {self.away_team} @ {self.home_team}>'
