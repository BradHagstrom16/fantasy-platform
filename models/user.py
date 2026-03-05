"""
Fantasy Sports Platform - User Model
======================================
Shared user model for all games. Game-specific player data
lives in game-specific models linked by user_id foreign key.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(UserMixin, db.Model):
    """A player on the platform. One account across all games."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100), nullable=True)

    # Platform role
    is_admin = db.Column(db.Boolean, default=False)

    # Payment tracking (platform-level, games can also track per-game payments)
    has_paid = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    def get_display_name(self):
        """Return display name, falling back to username."""
        return self.display_name or self.username

    def __repr__(self):
        return f'<User {self.username}>'
