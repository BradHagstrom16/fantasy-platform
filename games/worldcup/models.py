"""
World Cup Fantasy Pool — Database Models
==========================================
Models for enrollment, teams, matches, and picks.
All tables use the ``worldcup_`` prefix.
Game-specific user data lives in WorldCupEnrollment, NOT on the shared User model.
"""
from datetime import UTC, datetime

from extensions import db


class WorldCupEnrollment(db.Model):
    """Game-specific user data for World Cup Fantasy Pool.

    Linked to the shared User model via user_id FK.
    Holds pick submission status, tiebreaker guess, score, display name.
    """
    __tablename__ = 'worldcup_enrollment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    season_year = db.Column(db.Integer, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    has_paid = db.Column(db.Boolean, default=False)
    picks_submitted = db.Column(db.Boolean, default=False)
    usa_goals_guess = db.Column(db.Integer, nullable=True)
    total_score = db.Column(db.Float, default=0.0)
    display_name = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    user = db.relationship('User', backref='worldcup_enrollments')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'season_year', name='unique_worldcup_enrollment'),
    )

    def get_display_name(self):
        """Return display_name if set, otherwise fall back to User.username."""
        if self.display_name:
            return self.display_name
        return self.user.username if self.user else 'Unknown'

    def __repr__(self):
        return f'<WorldCupEnrollment user={self.user_id} season={self.season_year}>'


class WorldCupTeam(db.Model):
    """A national team in the World Cup Fantasy Pool.

    Seeded from world_cup_countries.py via ``flask worldcup seed-teams``.
    Score fields are denormalized and rebuildable via ``flask worldcup recalc``.
    """
    __tablename__ = 'worldcup_team'

    id = db.Column(db.Integer, primary_key=True)
    fifa_code = db.Column(db.String(3), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    tier = db.Column(db.Integer, nullable=False)
    multiplier = db.Column(db.Float, nullable=False)
    confederation = db.Column(db.String(10), nullable=False)
    group_letter = db.Column(db.String(1), nullable=False)
    is_eliminated = db.Column(db.Boolean, default=False)
    group_wins = db.Column(db.Integer, default=0)
    group_draws = db.Column(db.Integer, default=0)
    group_losses = db.Column(db.Integer, default=0)
    advancement_method = db.Column(db.String(20), nullable=True)
    best_finish = db.Column(db.String(20), nullable=True)
    base_points = db.Column(db.Float, default=0.0)
    multiplied_points = db.Column(db.Float, default=0.0)
    # football-data.org team id, set by `flask worldcup sync --mode link`.
    api_team_id = db.Column(db.Integer, nullable=True)

    # FIFA codes whose first two letters do NOT match ISO 3166-1 alpha-2.
    # Missing entries fall through to `code[:2]` and render the wrong country's
    # flag. tests/test_worldcup_flag_emoji.py locks all 48 codes against a
    # canonical map so a regression is caught at PR time, not in production.
    _FIFA_TO_ISO: dict[str, str] = {
        'ENG': 'GB', 'SCO': 'GB', 'GER': 'DE', 'NED': 'NL', 'POR': 'PT',
        'SUI': 'CH', 'CRO': 'HR', 'URU': 'UY', 'PAR': 'PY', 'SEN': 'SN',
        'BIH': 'BA', 'ALG': 'DZ', 'KOR': 'KR', 'KSA': 'SA', 'RSA': 'ZA',
        'COD': 'CD', 'CPV': 'CV', 'HAI': 'HT', 'TUR': 'TR', 'CIV': 'CI',
        'SWE': 'SE', 'TUN': 'TN',
        'MEX': 'MX', 'AUT': 'AT', 'CUW': 'CW', 'IRQ': 'IQ',
    }

    @property
    def iso_code(self) -> str:
        """ISO 3166-1 alpha-2 (lowercase) for self-hosted flag-SVG lookup.

        Single source of truth for FIFA -> ISO resolution: reuses the
        `_FIFA_TO_ISO` map with a `code[:2]` fallback, lowercased to match the
        `static/flags/<iso>.svg` filenames. `flag_emoji` derives from this too
        so the SVG flag and the legacy emoji always name the same country.
        """
        code = self.fifa_code or ''
        return self._FIFA_TO_ISO.get(code, code[:2]).lower()

    @property
    def flag_emoji(self) -> str:
        """Derive Unicode flag emoji from the FIFA code (legacy fallback)."""
        return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in self.iso_code.upper())

    def __repr__(self):
        return f'<WorldCupTeam {self.fifa_code} ({self.display_name})>'


class WorldCupMatch(db.Model):
    """A single match in the 2026 FIFA World Cup.

    All 104 matches are pre-seeded: group matches with teams assigned,
    knockout matches as empty shells (teams filled as bracket resolves).
    """
    __tablename__ = 'worldcup_match'

    id = db.Column(db.Integer, primary_key=True)
    match_number = db.Column(db.Integer, unique=True, nullable=False)
    stage = db.Column(db.String(20), nullable=False, index=True)
    group_letter = db.Column(db.String(1), nullable=True)
    home_team_id = db.Column(db.Integer, db.ForeignKey('worldcup_team.id'), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('worldcup_team.id'), nullable=True)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    home_pen = db.Column(db.Integer, nullable=True)
    away_pen = db.Column(db.Integer, nullable=True)
    winner_team_id = db.Column(db.Integer, db.ForeignKey('worldcup_team.id'), nullable=True)
    is_draw = db.Column(db.Boolean, default=False)
    extra_time = db.Column(db.Boolean, default=False)
    penalties = db.Column(db.Boolean, default=False)
    kickoff_utc = db.Column(db.DateTime, nullable=True)
    venue = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    # football-data.org match id, set by `flask worldcup sync --mode link`.
    api_fixture_id = db.Column(db.Integer, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC),
                           onupdate=lambda: datetime.now(UTC))

    home_team = db.relationship('WorldCupTeam', foreign_keys=[home_team_id])
    away_team = db.relationship('WorldCupTeam', foreign_keys=[away_team_id])
    winner_team = db.relationship('WorldCupTeam', foreign_keys=[winner_team_id])

    def __repr__(self):
        return f'<WorldCupMatch #{self.match_number} {self.stage}>'


class WorldCupPick(db.Model):
    """A player's pick of a national team in the fantasy pool.

    Each enrollment has up to 9 picks (one per tier slot).
    Score fields are denormalized and rebuildable via ``flask worldcup recalc``.
    """
    __tablename__ = 'worldcup_pick'

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('worldcup_enrollment.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('worldcup_team.id'), nullable=False)
    tier = db.Column(db.Integer, nullable=False)
    base_points = db.Column(db.Float, default=0.0)
    multiplied_points = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    enrollment = db.relationship('WorldCupEnrollment', backref='picks')
    team = db.relationship('WorldCupTeam')

    __table_args__ = (
        db.UniqueConstraint('enrollment_id', 'team_id', name='unique_worldcup_enrollment_team_pick'),
    )

    def __repr__(self):
        return f'<WorldCupPick enrollment={self.enrollment_id} team={self.team_id}>'


class WorldCupRankSnapshot(db.Model):
    """Daily snapshot of each enrollment's rank + total_score.

    Written by ``flask worldcup snapshot-ranks``. Intended to run nightly
    via cron once the production deploy plan reaches Task 25 — not yet
    wired up at branch-merge time. Powers the live-state dossier
    sparkline and week-delta calculations on the home page (Spec B).
    """
    __tablename__ = 'worldcup_rank_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer,
        db.ForeignKey('worldcup_enrollment.id', ondelete='CASCADE'),
        nullable=False, index=True
    )
    captured_date = db.Column(db.Date, nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Float, nullable=False)

    enrollment = db.relationship('WorldCupEnrollment', backref='rank_snapshots')

    __table_args__ = (
        db.UniqueConstraint(
            'enrollment_id', 'captured_date',
            name='unique_worldcup_snapshot_per_day'
        ),
    )

    def __repr__(self):
        return f'<WorldCupRankSnapshot enr={self.enrollment_id} on={self.captured_date} rank={self.rank}>'
