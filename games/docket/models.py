"""
The Docket — Database Models
============================
Import spine (DocketWeek + DocketGame) and grading spine (DocketPick,
DocketTiebreakerPrediction, DocketWeekResult). All tables use the
``docket_`` prefix.

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
from games.docket.utils import to_naive_utc


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
    # Audit timestamp: real wall clock (never the fake-now seam), stripped
    # to naive UTC explicitly rather than trusting driver offset handling.
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))

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

    # Grading spine: empty at import. Scores are written by the scores pass
    # (final INCLUDING overtime — D23, a grading rule the columns don't
    # encode); is_final gates grading; no_contest is an ADMIN ruling only
    # (postponed beyond the week ⇒ NC), never written by a sync run.
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    is_final = db.Column(db.Boolean, nullable=False, default=False)
    no_contest = db.Column(db.Boolean, nullable=False, default=False)
    nc_reason = db.Column(db.String(200), nullable=True)

    # Audit timestamp: real wall clock (never the fake-now seam), stripped
    # to naive UTC explicitly rather than trusting driver offset handling.
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))

    week = db.relationship('DocketWeek', foreign_keys=[week_id],
                           backref='games')

    def __repr__(self):
        return f'<DocketGame {self.away_team} @ {self.home_team}>'


class DocketPick(db.Model):
    """One locked side of one market in one of a user's 9 weekly slots.

    Slots 1–8 score; slot 9 is the dormant backup (D6 slot model — it
    substitutes into the earliest-kickoff No Contest slot, so it can never
    carry the best-pick designation itself). The one-side-per-market rule
    and the single best pick are SCHEMA constraints, not form validation.

    ``line_value`` + ``book`` snapshot the game's locked line at pick time
    (D7): grading reads the pick's own numbers, so a later admin line
    correction (D18) is an explicit re-snapshot, never silent drift. The
    write-path parity lock (snapshot == game's locked line at creation)
    lands with the pick service.
    """
    __tablename__ = 'docket_pick'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'week_id', 'game_id', 'market',
                            name='uq_docket_pick_one_side_per_market'),
        db.UniqueConstraint('user_id', 'week_id', 'slot',
                            name='uq_docket_pick_slot'),
        # Partial unique index: at most one is_best pick per (user, week).
        db.Index('uq_docket_pick_best_per_user_week', 'user_id', 'week_id',
                 unique=True,
                 sqlite_where=db.text('is_best'),
                 postgresql_where=db.text('is_best')),
        db.CheckConstraint('slot >= 1 AND slot <= 9',
                           name='ck_docket_pick_slot_range'),
        db.CheckConstraint('NOT (is_best AND slot = 9)',
                           name='ck_docket_pick_best_not_backup'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                        nullable=False, index=True)
    week_id = db.Column(db.Integer, db.ForeignKey('docket_week.id'),
                        nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('docket_game.id'),
                        nullable=False, index=True)
    # market: 'spread' | 'total'; side: 'home' | 'away' | 'over' | 'under'.
    # Value-space validation lives in the engine snapshots / pick service.
    market = db.Column(db.String(10), nullable=False)
    side = db.Column(db.String(10), nullable=False)
    slot = db.Column(db.Integer, nullable=False)
    is_best = db.Column(db.Boolean, nullable=False, default=False)
    is_autopick = db.Column(db.Boolean, nullable=False, default=False)
    line_value = db.Column(db.Float, nullable=False)
    book = db.Column(db.String(40), nullable=False)

    # Audit timestamps: real wall clock (never the fake-now seam), stripped
    # to naive UTC explicitly rather than trusting driver offset handling.
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))
    updated_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)),
        onupdate=lambda: to_naive_utc(datetime.now(UTC)))

    user = db.relationship('User', foreign_keys=[user_id])
    week = db.relationship('DocketWeek', foreign_keys=[week_id])
    game = db.relationship('DocketGame', foreign_keys=[game_id])

    def __repr__(self):
        return (f'<DocketPick u{self.user_id} w{self.week_id} '
                f'slot{self.slot} {self.market}/{self.side}>')


class DocketTiebreakerPrediction(db.Model):
    """A user's combined-score prediction for a week's designated game.

    Stored as INTEGER TENTHS (515 == 51.5) per D20: predictions, per-week
    error, and cumulative error are all-integer arithmetic end-to-end; the
    only ÷10 happens at render. No prediction row ⇒ the default rule (the
    designated game's locked O/U total) applies at grading time — defaults
    are computed, never materialized here.
    """
    __tablename__ = 'docket_tiebreaker_prediction'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'week_id',
                            name='uq_docket_prediction_user_week'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                        nullable=False, index=True)
    week_id = db.Column(db.Integer, db.ForeignKey('docket_week.id'),
                        nullable=False, index=True)
    prediction_tenths = db.Column(db.Integer, nullable=False)

    # Audit timestamps: real wall clock (never the fake-now seam), stripped
    # to naive UTC explicitly rather than trusting driver offset handling.
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))
    updated_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)),
        onupdate=lambda: to_naive_utc(datetime.now(UTC)))

    def __repr__(self):
        return (f'<DocketTiebreakerPrediction u{self.user_id} '
                f'w{self.week_id} {self.prediction_tenths}>')


class DocketWeekResult(db.Model):
    """Per-user week grade, written by the grading pass (D14).

    The CfbWeekOutcome pattern: one row per (user, week), upserted by the
    idempotent grading pass / ``flask docket recalc``; standings read this
    rollup and never re-derive from pick history. ``points`` is float in
    exact half steps (max 9); ``wins`` counts winning picks (a doubled
    best-pick win counts once); ``error_tenths`` is integer tenths (D20).
    ``is_dropped`` marks the season's drop-worst week — points only; wins
    and error still count from a dropped week.
    """
    __tablename__ = 'docket_week_result'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'week_id',
                            name='uq_docket_week_result_user_week'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                        nullable=False, index=True)
    week_id = db.Column(db.Integer, db.ForeignKey('docket_week.id'),
                        nullable=False, index=True)
    points = db.Column(db.Float, nullable=False)
    wins = db.Column(db.Integer, nullable=False)
    error_tenths = db.Column(db.Integer, nullable=False)
    is_dropped = db.Column(db.Boolean, nullable=False, default=False)
    # When the grading pass produced this row — set explicitly by the pass
    # (a grading fact, not an audit default).
    graded_at = db.Column(db.DateTime, nullable=False)

    # Audit timestamp: real wall clock (never the fake-now seam), stripped
    # to naive UTC explicitly rather than trusting driver offset handling.
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))

    def __repr__(self):
        return (f'<DocketWeekResult u{self.user_id} w{self.week_id} '
                f'{self.points}pts>')
