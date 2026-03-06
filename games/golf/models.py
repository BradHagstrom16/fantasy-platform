"""
Golf Pick 'Em — Database Models
=================================
SQLAlchemy models for the golf pick 'em fantasy league.

Table Naming: All tables prefixed with 'golf_' to namespace within
the shared platform database.

Core Concepts:
- Users pick one golfer (primary + backup) per tournament
- Points = actual prize money earned by their active pick
- Each golfer can only be used once per season
- Backup activates only if primary WDs before completing Round 2
- Majors earn 1.5x points, team events earn half (earnings // 2)
"""
import logging
from datetime import datetime, timezone

import pytz
from sqlalchemy.dialects.sqlite import insert

from extensions import db
from games.golf.utils import format_score_to_par, GOLF_LEAGUE_TZ

logger = logging.getLogger(__name__)


# ============================================================================
# GolfEnrollment — Tracks who's playing golf + their game-specific data
# ============================================================================

class GolfEnrollment(db.Model):
    """
    Tracks which users are enrolled in Golf Pick 'Em for a given season.
    Stores golf-specific user data (total_points, has_paid) that does NOT
    belong on the shared User model.
    """
    __tablename__ = 'golf_enrollment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    season_year = db.Column(db.Integer, nullable=False)

    # Season standings
    total_points = db.Column(db.Integer, default=0)

    # Payment tracking
    has_paid = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref=db.backref('golf_enrollments', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'season_year', name='unique_golf_enrollment'),
    )

    def calculate_total_points(self):
        """Recalculate total points from all completed picks this season."""
        from sqlalchemy import func as sqla_func

        total = db.session.query(
            sqla_func.coalesce(sqla_func.sum(GolfPick.points_earned), 0)
        ).filter(
            GolfPick.user_id == self.user_id,
            GolfPick.points_earned.isnot(None)
        ).join(GolfTournament).filter(
            GolfTournament.status == 'complete',
            GolfTournament.season_year == self.season_year
        ).scalar()

        self.total_points = total
        return total

    def get_used_player_ids(self):
        """Get list of player IDs this user has 'used' (locked) for the season."""
        usages = GolfSeasonPlayerUsage.query.filter_by(
            user_id=self.user_id,
            season_year=self.season_year
        ).all()
        return [usage.player_id for usage in usages]

    def __repr__(self):
        return f'<GolfEnrollment User:{self.user_id} Year:{self.season_year}>'


# ============================================================================
# GolfPlayer — PGA Tour golfers (synced from SlashGolf API)
# ============================================================================

class GolfPlayer(db.Model):
    """A PGA Tour golfer. Synced from SlashGolf API."""
    __tablename__ = 'golf_player'

    id = db.Column(db.Integer, primary_key=True)
    api_player_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    is_amateur = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tournament_results = db.relationship('GolfTournamentResult', backref='player', lazy='dynamic')

    def full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f'<GolfPlayer {self.first_name} {self.last_name}>'


# ============================================================================
# GolfTournament — PGA Tour tournaments
# ============================================================================

class GolfTournament(db.Model):
    """A PGA Tour tournament. Synced from SlashGolf API."""
    __tablename__ = 'golf_tournament'

    id = db.Column(db.Integer, primary_key=True)
    api_tourn_id = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    season_year = db.Column(db.Integer, nullable=False)

    # Dates
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    pick_deadline = db.Column(db.DateTime, nullable=True)  # First tee time Thursday

    # Tournament details
    purse = db.Column(db.Integer, default=0)
    is_team_event = db.Column(db.Boolean, default=False)  # Zurich Classic
    is_major = db.Column(db.Boolean, default=False)  # Masters, PGA, US Open, The Open

    # Status tracking
    status = db.Column(db.String(20), default='upcoming')  # upcoming, active, complete
    results_finalized = db.Column(db.Boolean, default=False)

    # Email notification tracking
    picks_open_notified = db.Column(db.Boolean, default=False)
    field_alert_sent = db.Column(db.Boolean, default=False)

    # Week number in the league (1-32)
    week_number = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    picks = db.relationship('GolfPick', backref='tournament', lazy='dynamic')
    results = db.relationship('GolfTournamentResult', backref='tournament', lazy='dynamic')
    field = db.relationship('GolfTournamentField', backref='tournament', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('api_tourn_id', 'season_year', name='unique_golf_tournament_per_season'),
    )

    def is_deadline_passed(self):
        """Check if pick deadline has passed."""
        if not self.pick_deadline:
            return False
        now = datetime.now(GOLF_LEAGUE_TZ)
        deadline = self.pick_deadline
        if deadline.tzinfo is None:
            deadline = GOLF_LEAGUE_TZ.localize(deadline)
        return now > deadline

    def get_field_count(self):
        """Get the number of players in the tournament field."""
        return GolfTournamentField.query.filter_by(tournament_id=self.id).count()

    def has_sufficient_field(self, minimum=50):
        """Check if tournament has a sufficient field size for picks."""
        return self.get_field_count() >= minimum

    def update_status_from_time(self, current_time=None):
        """
        Derive tournament status based on start/end dates and deadlines.

        IMPORTANT: This method NEVER auto-sets 'complete'. Only sync_api should
        do that after verifying results are finalized via the API. This prevents
        premature completion marking.
        """
        now = current_time or datetime.now(GOLF_LEAGUE_TZ)
        if self.status == 'complete':
            return self.status

        deadline = self.pick_deadline or self.start_date
        deadline_localized = deadline if deadline.tzinfo else GOLF_LEAGUE_TZ.localize(deadline)
        end_localized = self.end_date if self.end_date.tzinfo else GOLF_LEAGUE_TZ.localize(self.end_date)

        if now >= end_localized:
            if self.status != 'active':
                self.status = 'active'
        elif now >= deadline_localized:
            self.status = 'active'
        else:
            self.status = 'upcoming'

        return self.status

    def get_deadline_display(self):
        """Return formatted deadline string."""
        if not self.pick_deadline:
            return "TBD"
        deadline = self.pick_deadline
        if deadline.tzinfo is None:
            deadline = GOLF_LEAGUE_TZ.localize(deadline)
        else:
            deadline = deadline.astimezone(GOLF_LEAGUE_TZ)
        return deadline.strftime('%a %b %d, %I:%M %p CT')

    def __repr__(self):
        return f'<GolfTournament {self.name} ({self.season_year})>'


# ============================================================================
# GolfTournamentField — Pre-tournament player field
# ============================================================================

class GolfTournamentField(db.Model):
    """
    Players in a tournament's field. Synced from API before tournament starts.
    Separate from GolfTournamentResult to track the pre-tournament field.
    """
    __tablename__ = 'golf_tournament_field'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('golf_tournament.id'), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey('golf_player.id'), nullable=False, index=True)

    is_alternate = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    player = db.relationship('GolfPlayer', backref='field_entries')

    __table_args__ = (
        db.UniqueConstraint('tournament_id', 'player_id', name='unique_golf_player_tournament_field'),
    )

    def __repr__(self):
        return f'<GolfTournamentField {self.tournament_id} - {self.player_id}>'


# ============================================================================
# GolfSeasonPlayerUsage — Tracks golfer usage per user per season
# ============================================================================

class GolfSeasonPlayerUsage(db.Model):
    """Tracks whether a user has consumed a player for a given season."""
    __tablename__ = 'golf_season_player_usage'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey('golf_player.id'), nullable=False, index=True)
    season_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'player_id', 'season_year', name='unique_golf_player_usage'),
    )

    user = db.relationship('User', backref=db.backref('golf_season_usages', lazy='dynamic'))
    player = db.relationship('GolfPlayer')

    def __repr__(self):
        return f'<GolfSeasonPlayerUsage User:{self.user_id} Player:{self.player_id} Year:{self.season_year}>'


# ============================================================================
# GolfTournamentResult — Player results after tournament completion
# ============================================================================

class GolfTournamentResult(db.Model):
    """A player's result in a completed tournament. Synced from API."""
    __tablename__ = 'golf_tournament_result'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('golf_tournament.id'), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey('golf_player.id'), nullable=False, index=True)

    # Result details
    status = db.Column(db.String(20), nullable=False)  # complete, cut, wd, dq
    final_position = db.Column(db.String(20), nullable=True)  # "1", "T5", "CUT", etc.
    earnings = db.Column(db.Integer, default=0)
    rounds_completed = db.Column(db.Integer, default=0)  # 0-4, key for WD timing
    score_to_par = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('tournament_id', 'player_id', name='unique_golf_player_tournament_result'),
    )

    def wd_before_round_2_complete(self):
        """Check if this was a WD before completing round 2."""
        return self.status == 'wd' and self.rounds_completed < 2

    def format_score_to_par(self):
        """Format score to par for display."""
        return format_score_to_par(self.score_to_par)

    def __repr__(self):
        return f'<GolfTournamentResult {self.tournament_id} - {self.player_id}: {self.earnings}>'


# ============================================================================
# GolfPick — User's pick for a tournament
# ============================================================================

class GolfPick(db.Model):
    """
    A user's pick for a specific tournament.

    Key Logic:
    - User selects primary_player and backup_player before deadline
    - After tournament: resolve_pick() determines which was the "active" pick
    - active_player_id stores who actually counted for points
    - primary_used/backup_used track which player is now "locked" for season

    WD Rules (BATTLE-TESTED — do not modify):
    - Primary WDs BEFORE completing R2 → Backup activates, primary returns to pool
    - Primary WDs AFTER completing R2 → Primary counts (0 pts), backup unused
    - Both WD before R2 → Primary is used (0 pts), backup returns to pool
    """
    __tablename__ = 'golf_pick'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('golf_tournament.id'), nullable=False, index=True)

    # The picks
    primary_player_id = db.Column(db.Integer, db.ForeignKey('golf_player.id'), nullable=False)
    backup_player_id = db.Column(db.Integer, db.ForeignKey('golf_player.id'), nullable=False)

    # Resolved after tournament completes
    active_player_id = db.Column(db.Integer, db.ForeignKey('golf_player.id'), nullable=True)
    points_earned = db.Column(db.Integer, nullable=True)

    # Which players are now "used" for the season
    primary_used = db.Column(db.Boolean, default=False)
    backup_used = db.Column(db.Boolean, default=False)

    # Admin override tracking
    admin_override = db.Column(db.Boolean, default=False)
    admin_override_note = db.Column(db.String(200), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref=db.backref('golf_picks', lazy='dynamic'))
    primary_player = db.relationship('GolfPlayer', foreign_keys=[primary_player_id], backref='primary_picks')
    backup_player = db.relationship('GolfPlayer', foreign_keys=[backup_player_id], backref='backup_picks')
    active_player = db.relationship('GolfPlayer', foreign_keys=[active_player_id], backref='active_picks')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'tournament_id', name='unique_golf_user_tournament_pick'),
    )

    def validate_availability(self, season_year: int):
        """Validate pick adheres to field eligibility and season usage constraints."""
        errors = []

        field_player_ids = [
            entry.player_id
            for entry in GolfTournamentField.query.filter_by(tournament_id=self.tournament_id)
        ]
        if self.primary_player_id not in field_player_ids:
            errors.append('Primary player is not in the tournament field.')
        if self.backup_player_id not in field_player_ids:
            errors.append('Backup player is not in the tournament field.')

        existing_usage = GolfSeasonPlayerUsage.query.filter(
            GolfSeasonPlayerUsage.user_id == self.user_id,
            GolfSeasonPlayerUsage.season_year == season_year,
            GolfSeasonPlayerUsage.player_id.in_([self.primary_player_id, self.backup_player_id])
        ).all()
        used_ids = {usage.player_id for usage in existing_usage}
        if self.primary_player_id in used_ids:
            errors.append('Primary player has already been used this season.')
        if self.backup_player_id in used_ids:
            errors.append('Backup player has already been used this season.')

        return errors

    def resolve_pick(self):
        """
        Determine which player was active and calculate points.
        Call this ONLY after tournament results are imported.

        CRITICAL: This method is ported verbatim from the live Golf Pick 'Em app.
        It has been battle-tested over 7+ tournaments with 19 active players.
        Do NOT simplify, refactor, or "improve" the logic.

        Returns:
            True if resolved successfully, False if missing data
        """
        # Get results for both players
        primary_result = GolfTournamentResult.query.filter_by(
            tournament_id=self.tournament_id,
            player_id=self.primary_player_id
        ).first()

        backup_result = GolfTournamentResult.query.filter_by(
            tournament_id=self.tournament_id,
            player_id=self.backup_player_id
        ).first()

        if not primary_result:
            logger.error(
                "Missing tournament result for primary player %s in tournament %s",
                self.primary_player_id,
                self.tournament_id,
            )
            self.points_earned = None
            self.active_player_id = None
            self.primary_used = False
            self.backup_used = False
            return False

        # Determine if primary WD'd before completing R2
        primary_wd_early = (
            primary_result and
            primary_result.status == 'wd' and
            primary_result.rounds_completed < 2
        )

        # Case 1: Primary WD before R2 — backup activates
        if primary_wd_early:
            backup_wd_early = (
                backup_result and
                backup_result.status == 'wd' and
                backup_result.rounds_completed < 2
            )

            if backup_wd_early:
                # Both WD early: Primary is used with 0 points, backup returns to pool
                self.active_player_id = self.primary_player_id
                self.points_earned = 0
                self.primary_used = True
                self.backup_used = False
            else:
                # Backup activates
                self.active_player_id = self.backup_player_id
                earnings = backup_result.earnings if backup_result else None
                if earnings is None:
                    logger.error(
                        "Backup player %s missing result for pick %s in tournament %s",
                        self.backup_player_id,
                        self.id,
                        self.tournament_id,
                    )
                    self.active_player_id = None
                    self.points_earned = None
                    self.primary_used = False
                    self.backup_used = False
                    return False

                # Handle team event (Zurich) — divide by 2
                if self.tournament.is_team_event:
                    earnings = earnings // 2

                # Handle major multiplier — multiply by 1.5
                if self.tournament.is_major:
                    earnings = int(earnings * 1.5)

                self.points_earned = earnings
                self.primary_used = False  # Returns to pool
                self.backup_used = True

        # Case 2: Primary did not WD early (or didn't WD at all)
        else:
            self.active_player_id = self.primary_player_id
            earnings = primary_result.earnings if primary_result else None
            if earnings is None:
                logger.error(
                    "Primary player %s missing earnings for pick %s in tournament %s",
                    self.primary_player_id,
                    self.id,
                    self.tournament_id,
                )
                self.active_player_id = None
                self.points_earned = None
                self.primary_used = False
                self.backup_used = False
                return False

            # Handle team event (Zurich) — divide by 2
            if self.tournament.is_team_event:
                earnings = earnings // 2

            # Handle major multiplier — multiply by 1.5
            if self.tournament.is_major:
                earnings = int(earnings * 1.5)

            self.points_earned = earnings
            self.primary_used = True
            self.backup_used = False

        # Record season usage for active player
        stmt = insert(GolfSeasonPlayerUsage).values(
            user_id=self.user_id,
            player_id=self.active_player_id,
            season_year=self.tournament.season_year,
        ).on_conflict_do_nothing()
        db.session.execute(stmt)

        return True

    def get_current_earnings(self):
        """Get current earnings for display during active tournaments."""
        if self.points_earned is not None:
            return self.points_earned

        if not self.active_player_id:
            active_id = self.primary_player_id
        else:
            active_id = self.active_player_id

        result = GolfTournamentResult.query.filter_by(
            tournament_id=self.tournament_id,
            player_id=active_id
        ).first()

        if result and result.earnings:
            earnings = result.earnings
            if self.tournament.is_team_event:
                earnings = earnings // 2
            if self.tournament.is_major:
                earnings = int(earnings * 1.5)
            return earnings

        return 0

    def __repr__(self):
        return f'<GolfPick User:{self.user_id} Tournament:{self.tournament_id}>'
