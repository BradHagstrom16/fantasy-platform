"""
CFB Survivor Pool — Database Models
======================================
Models for enrollment, teams, weeks, games, and picks.

All tables use the ``cfb_`` prefix to avoid collision with other games.
Game-specific user data lives in CfbEnrollment, NOT on the shared User model.
"""
from datetime import datetime, timezone

from extensions import db
from games.cfb.constants import TEAM_CONFERENCES


class CfbEnrollment(db.Model):
    """Game-specific user data for CFB Survivor Pool.

    Linked to the shared User model via user_id FK.
    Holds lives, elimination status, payment, cumulative spread, display name.
    """
    __tablename__ = 'cfb_enrollment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    season_year = db.Column(db.Integer, nullable=False)
    lives_remaining = db.Column(db.Integer, default=2)
    is_eliminated = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    has_paid = db.Column(db.Boolean, default=False)
    cumulative_spread = db.Column(db.Float, default=0.0)
    display_name = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='cfb_enrollments')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'season_year', name='unique_cfb_enrollment'),
    )

    def get_display_name(self):
        """Return display_name if set, otherwise fall back to User.username."""
        if self.display_name:
            return self.display_name
        return self.user.username if self.user else 'Unknown'

    def __repr__(self):
        return f'<CfbEnrollment user={self.user_id} season={self.season_year}>'


class CfbTeam(db.Model):
    """A college football team available in the pool.

    Teams are added/removed by the admin via the Manage Teams page.
    Presence in this table means the team is active for the current season.
    The full FBS universe lives in constants.FBS_MASTER_TEAMS.
    """
    __tablename__ = 'cfb_team'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    conference = db.Column(db.String(50))
    national_title_odds = db.Column(db.String(16), nullable=True)

    def get_conference(self):
        """Look up conference from master list (in case DB value is stale)."""
        return TEAM_CONFERENCES.get(self.name, self.conference or 'Unknown')

    def __repr__(self):
        return f'<CfbTeam {self.name}>'


class CfbWeek(db.Model):
    """A week in the CFB Survivor season.

    Weeks 1-14: regular season. Week 15: Conference Championship.
    Weeks 16-19: CFP rounds. Only one week is active at a time.
    """
    __tablename__ = 'cfb_week'

    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, unique=True, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    is_complete = db.Column(db.Boolean, default=False)
    is_playoff_week = db.Column(db.Boolean, default=False)
    round_name = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<CfbWeek {self.week_number}>'


class CfbGame(db.Model):
    """A game within a specific week.

    Stores matchup, spread, scores, and result. The home_team_spread is from
    the home team's perspective (negative = home team favored).

    IMPORTANT: The pick mechanic is outright wins — NOT against the spread.
    The spread is only used as a tiebreaker (cumulative_spread) and
    eligibility filter (16.5+ point favorites are ineligible).
    """
    __tablename__ = 'cfb_game'

    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey('cfb_week.id'), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('cfb_team.id'), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('cfb_team.id'), nullable=True)
    # Fallback team names for games involving non-tracked teams
    home_team_name = db.Column(db.String(100), nullable=True)
    away_team_name = db.Column(db.String(100), nullable=True)
    home_team_spread = db.Column(db.Float)
    game_time = db.Column(db.DateTime)
    home_team_won = db.Column(db.Boolean, default=None)
    api_event_id = db.Column(db.String(64), nullable=True, index=True)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    spread_locked_at = db.Column(db.DateTime, nullable=True)

    week = db.relationship('CfbWeek', backref='games')
    home_team = db.relationship('CfbTeam', foreign_keys=[home_team_id], backref='home_games')
    away_team = db.relationship('CfbTeam', foreign_keys=[away_team_id], backref='away_games')

    def get_home_team_display(self):
        """Return display name for the home team."""
        return self.home_team.name if self.home_team else (self.home_team_name or 'TBD')

    def get_away_team_display(self):
        """Return display name for the away team."""
        return self.away_team.name if self.away_team else (self.away_team_name or 'TBD')

    def get_spread_for_team(self, team_id):
        """Return spread from team's perspective (negative = favored)."""
        if self.home_team_spread is None:
            return None
        if team_id == self.home_team_id:
            return self.home_team_spread
        return -self.home_team_spread

    def __repr__(self):
        return f'<CfbGame {self.get_away_team_display()} @ {self.get_home_team_display()}>'


class CfbPick(db.Model):
    """A user's pick for a specific week.

    One pick per user per week. The user picks a team to win outright.
    is_correct is set after results are processed.
    """
    __tablename__ = 'cfb_pick'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    week_id = db.Column(db.Integer, db.ForeignKey('cfb_week.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('cfb_team.id'), nullable=False)
    is_correct = db.Column(db.Boolean, default=None)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='cfb_picks')
    week = db.relationship('CfbWeek', backref='picks')
    team = db.relationship('CfbTeam', backref='picks')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'week_id', name='unique_cfb_user_week_pick'),
    )

    def __repr__(self):
        return f'<CfbPick user={self.user_id} week={self.week_id}>'
