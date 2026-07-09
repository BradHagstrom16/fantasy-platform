"""
core/auth/tokens.py
===================
Password reset token generation and verification.
Tokens are signed with the app SECRET_KEY and expire after 1 hour.

Platform-level auth — completely independent of any game.
"""
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

TOKEN_MAX_AGE = 3600  # 1 hour


def generate_reset_token(email: str) -> str:
    """Generate a signed, time-limited reset token for the given email."""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(email, salt='password-reset')


def verify_reset_token(token: str) -> str | None:
    """
    Verify a reset token.
    Returns the email if valid and unexpired. Returns None otherwise.
    """
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email: str = s.loads(token, salt='password-reset', max_age=TOKEN_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
    return email
