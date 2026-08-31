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


class DocketEnrollment(db.Model):
    """A user's season membership in The Docket (CfbEnrollment shape).

    One row per (user, season). ``is_admin`` is the enrollment-scoped game
    admin tier (platform admins bypass it in ``docket_admin_required``).
    ``created_at`` follows the D6 naive-UTC contract, unlike CFB's aware
    audit lambda — every docket column stores naive UTC.
    """
    __tablename__ = 'docket_enrollment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    season_year = db.Column(db.Integer, nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    has_paid = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))

    user = db.relationship('User', backref='docket_enrollments')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'season_year',
                            name='uq_docket_enrollment_user_season'),
    )

    def get_display_name(self):
        """The member's one platform display name (ADR-057); the ledger,
        the sheet rail, emails and the payment memo all read it here."""
        return self.user.get_display_name()

    def __repr__(self):
        return f'<DocketEnrollment user={self.user_id} season={self.season_year}>'


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
    # Weekly designated tiebreaker game. Filled by rule on the Tuesday
    # setup/lines runs (services/tiebreaker_rule.py: the latest-kickoff NFL
    # game = Monday Night Football; Week 1 = the latest game on the slate);
    # moved only by the commissioner (admin_ops.designate_tiebreaker, pre-
    # deadline) — the rule never moves a value on file. use_alter breaks the
    # docket_week <-> docket_game FK cycle at CREATE TABLE time.
    tiebreaker_game_id = db.Column(
        db.Integer,
        db.ForeignKey('docket_game.id', name='fk_docket_week_tiebreaker_game',
                      use_alter=True),
        nullable=True,
    )
    # The closest deadline-reminder tier already sent for this week ('48h',
    # '24h', '2h'), or NULL if none has been. THE de-dup mechanism for D24:
    # the reminder run computes the active tier from deadline_at and skips
    # when that tier is at or behind this one, so correctness comes from the
    # flag and never from the timer's cadence (Golf's last_reminder_type;
    # deliberately NOT CFB's cadence-dependent shape, which double-sends if
    # its timer is ever scheduled more often than its windows are wide).
    last_reminder_tier = db.Column(db.String(10), nullable=True)
    # Set once the "Picks Are Open" announcement has been mailed for this week
    # (games/docket/services/notifications.notify_picks_open); latched by the
    # import run (_run_import) when the week first has games. The preview
    # Week-1 row is back-filled True by migration so an already-enabled timer
    # never announces a stale week before the Sep 1 wipe; a fresh post-wipe
    # import (a new row, default False) announces correctly.
    picks_open_notified = db.Column(db.Boolean, default=False, nullable=False)
    # The week's default tiebreaker error in integer tenths (D20), written by
    # the grading pass: |designated game's locked O/U total - actual combined
    # score|, or 0 when that game was ruled No Contest (post-deadline
    # designation death is a zero-error week for everyone). NULL until the
    # week grades.
    #
    # Persisted rather than re-derived at read time because the season rollup
    # charges it to roster members with no result row that week, including
    # weeks before a late joiner enrolled (Grading Clarifications). Writing it
    # in the same transaction as the docket_week_result rows it must be
    # commensurable with is what keeps them consistent: recomputing at render
    # would let an admin score correction move this default without moving the
    # per-player errors, which only move on recalc.
    default_error_tenths = db.Column(db.Integer, nullable=True)
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
        # is_auto_best marks HOW a designation was made, so it is meaningless
        # without one. Schema-enforced like its siblings above rather than
        # left to the writers.
        db.CheckConstraint('NOT is_auto_best OR is_best',
                           name='ck_docket_pick_auto_best_implies_best'),
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
    # Written only by the deadline pass, and only where the player set no
    # headliner of their own. Distinct from is_autopick because
    # auto-designation can land the double on a pick the player DID make
    # (Grading Clarifications: the fallback chain evaluates the final 8-slot
    # set, own picks included) — is_autopick alone cannot tell that case from
    # a headliner the player chose, and the sheet has to say which it was.
    # Invariant (schema-enforced above): is_auto_best implies is_best.
    is_auto_best = db.Column(db.Boolean, nullable=False, default=False,
                             server_default=db.false())
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


class DocketLineCorrection(db.Model):
    """One audited admin correction of a locked line (D18).

    Locked lines never move (D3) — except when the imported number was
    simply wrong, which is a data error, not a market move. D18 allows the
    fix PRE-DEADLINE ONLY, demands a reason, records old and new here, and
    requires the market's pickers be told to re-decide. A bad line found
    after the deadline is not corrected; it resolves as a No Contest ruling.

    The row is the evidence. Because a pick snapshots its own line
    (DocketPick.line_value/book) and grading reads that snapshot, correcting
    a game's line must also re-snapshot the picks already made on it —
    ``picks_resnapshotted`` records how many moved, so the audit trail
    explains a changed pick row rather than leaving it looking like drift.
    """
    __tablename__ = 'docket_line_correction'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('docket_game.id'),
                        nullable=False, index=True)
    # market: 'spread' | 'total', the same value space as DocketPick.market.
    market = db.Column(db.String(10), nullable=False)
    # A correction only ever edits an already-locked market, so both sides
    # of the change are known.
    old_value = db.Column(db.Float, nullable=False)
    old_book = db.Column(db.String(40), nullable=False)
    new_value = db.Column(db.Float, nullable=False)
    new_book = db.Column(db.String(40), nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                              nullable=False, index=True)
    picks_resnapshotted = db.Column(db.Integer, nullable=False, default=0)

    # Audit timestamp: real wall clock (never the fake-now seam), stripped
    # to naive UTC explicitly rather than trusting driver offset handling.
    created_at = db.Column(
        db.DateTime, default=lambda: to_naive_utc(datetime.now(UTC)))

    game = db.relationship('DocketGame', foreign_keys=[game_id])
    admin = db.relationship('User', foreign_keys=[admin_user_id])

    def __repr__(self):
        return (f'<DocketLineCorrection g{self.game_id} {self.market} '
                f'{self.old_value}->{self.new_value}>')
