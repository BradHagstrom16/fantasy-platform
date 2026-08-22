"""
Fantasy Sports Platform - User Model
======================================
Shared user model for all games. Game-specific player data
lives in game-specific models linked by user_id foreign key.
"""
import uuid
from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from utils.identifier import normalize_identifier


class User(UserMixin, db.Model):
    """A player on the platform. One account across all games."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    # Session/remember-cookie identity (Flask-Login get_id()). Random and never
    # reused, so a destructive DB reset that restarts the integer `id` sequence
    # can never make a pre-wipe cookie authenticate as a *different* user who
    # later inherits the recycled id. See get_id() below.
    auth_id = db.Column(db.String(32), unique=True, nullable=False, index=True,
                        default=lambda: uuid.uuid4().hex)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100), nullable=True)
    avatar_emoji = db.Column(db.String(4), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    # Platform role
    is_admin = db.Column(db.Boolean, default=False)

    # Payment tracking (platform-level, games can also track per-game payments)
    has_paid = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC),
                           onupdate=lambda: datetime.now(UTC))

    def get_id(self):
        """Identity stored in the session/remember cookie (overrides UserMixin).

        Returns the random `auth_id` rather than the integer PK so a recycled
        `id` (after a DB wipe) can never let a stale, validly-signed cookie load
        a different user.
        """
        return self.auth_id

    def set_password(self, password):
        """Hash and store password.

        ``method`` is pinned rather than inherited from Werkzeug's default,
        which has changed over time (pbkdf2:sha1 -> pbkdf2:sha256 -> scrypt
        in 2.3). Pinning keeps a Werkzeug upgrade from silently changing the
        hash format for new passwords. Existing rows are unaffected either
        way — ``check_password_hash`` reads the algorithm from each stored
        hash's own prefix, so older formats keep verifying for as long as
        Werkzeug still supports them. Note the failure mode if one is ever
        dropped is a raised ``ValueError``, not a ``False`` return: the
        ``try`` in ``check_password_hash`` covers only the prefix split.
        """
        self.password_hash = generate_password_hash(password, method='scrypt')

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    def get_display_name(self):
        """Return display name, falling back to username."""
        return self.display_name or self.username

    # Reserved avatars \u2014 always the ``\U\u2026`` escapes here, never a literal
    # non-BMP char (a literal can break import as an invalid surrogate pair).
    ADMIN_AVATAR = '\U0001F451'     # crown \u2014 platform admins only
    CHAMPION_AVATAR = '\U0001F3C6'  # trophy \u2014 the reigning Survivor champion only
    DEFAULT_AVATAR = '\U0001F3C8'   # football \u2014 anyone who never chose
    # The 2025 Survivor champion reigns through the 2026 season. Re-point this
    # when the 2026 title resolves (the 2025 archive stores only a display
    # name, so the identity has to be declared here). Matched case-insensitively
    # through the same fold every auth lookup uses.
    REIGNING_CHAMPION_USERNAME = 'cubbies22'

    @property
    def is_reigning_champion(self) -> bool:
        """True for the one account that wears the trophy this season."""
        return normalize_identifier(self.username) == normalize_identifier(
            self.REIGNING_CHAMPION_USERNAME)

    def get_avatar(self) -> str:
        """Return the user's avatar emoji, or the platform default.

        Two glyphs are reserved and enforced here \u2014 so every get_avatar()
        call site inherits the rule, not just the picker: the crown renders
        for every platform admin, the trophy for the reigning Survivor
        champion. Precedence: admin crown > champion trophy > stored choice
        > default. Anyone else who has a reserved glyph stored renders the
        default instead.
        """
        if self.is_admin:
            return self.ADMIN_AVATAR
        if self.is_reigning_champion:
            return self.CHAMPION_AVATAR
        if self.avatar_emoji in (self.ADMIN_AVATAR, self.CHAMPION_AVATAR):
            return self.DEFAULT_AVATAR
        return self.avatar_emoji or self.DEFAULT_AVATAR

    def __repr__(self):
        return f'<User {self.username}>'
