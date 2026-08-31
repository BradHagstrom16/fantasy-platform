"""
Fantasy Sports Platform - Authentication Routes
=================================================
Login, register, logout, change password, profile, forgot/reset password.

All routes are platform-level — no game model involvement.
"""
import re
from urllib.parse import urlparse

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select

from core.auth import auth_bp
from core.auth.tokens import generate_reset_token, verify_reset_token
from extensions import db, limiter
from games.worldcup.services import enrollment as worldcup_enrollment
from games.worldcup.services.state import worldcup_state
from models.user import User
from utils.display_name import normalize_display_name
from utils.email import send_platform_email
from utils.identifier import normalize_identifier
from utils.phone import normalize_us_phone


def _is_safe_next(target):
    """True only for a strictly-local, rooted relative path — an open-redirect guard.

    Blocks absolute URLs, scheme-bearing targets (e.g. ``javascript:``),
    protocol-relative ``//host``, and the backslash variants browsers normalize
    to ``//host`` (``/\\host``). Used by login() and register() before honoring a
    `next` redirect, so a crafted `next` can't bounce a user off-site.
    """
    if not target:
        return False
    parsed = urlparse(target)
    return (
        not parsed.scheme
        and not parsed.netloc
        and target.startswith('/')
        and not target.startswith('//')
        and '\\' not in target
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Authenticate by username or email + password, then honor a safe `next`."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Accept either the username or the account email. Username-first,
        # email-fallback is deterministic: if one account's username happens to
        # equal another account's email (username and email are independently
        # unique columns), the username match wins rather than an ambiguous OR
        # returning an arbitrary row.
        user = (
            db.session.scalar(
                select(User).where(
                    func.lower(User.username) == normalize_identifier(identifier))
            )
            or db.session.scalar(
                select(User).where(
                    func.lower(User.email) == normalize_identifier(identifier))
            )
        )

        if user and user.check_password(password):
            login_user(user, remember=True)
            flash('Logged in successfully!', 'success')
            next_page = request.form.get('next') or request.args.get('next')
            if _is_safe_next(next_page):
                return redirect(next_page)
            return redirect(url_for('main.index'))
        else:
            flash('Invalid login or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Create a new platform account (with optional validated phone)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        display_name, display_name_error = normalize_display_name(
            request.form.get('display_name', ''))
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone, phone_error = normalize_us_phone(request.form.get('phone', ''))

        # Validation
        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if display_name_error:
            errors.append(display_name_error)
        if phone_error:
            errors.append(phone_error)

        if db.session.scalar(select(User).where(
                func.lower(User.username) == normalize_identifier(username))):
            errors.append('That username is already taken.')
        if db.session.scalar(select(User).where(
                func.lower(User.email) == normalize_identifier(email))):
            errors.append('That email is already registered.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('auth/register.html')

        user = User(username=username, email=email, display_name=display_name,
                    phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash('Account created! Welcome to the platform.', 'success')

        # Sanctioned signup-time auto-join: while the World Cup pick window is
        # open (pre-deadline), every new account wants in. This is distinct
        # from the banned pick/admin auto-enroll path: it is an intentional
        # signup behavior, and it self-disables once the tournament starts.
        if worldcup_state() == 'pre':
            worldcup_enrollment.admin_enroll(user.id)
            flash("You're in the World Cup pool. Make your picks before they lock.", 'success')

        # Honor a safe relative `next` (the logged-out "Join the Club" CTA passes
        # ?next=/worldcup/join), mirroring login()'s redirect contract. The
        # _is_safe_next guard rejects absolute / scheme / protocol-relative /
        # backslash targets; fall back to the home page otherwise.
        next_page = request.form.get('next') or request.args.get('next')
        if _is_safe_next(next_page):
            return redirect(next_page)
        return redirect(url_for('main.index'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def forgot_password():
    """Email a password-reset link (anti-enumeration: identical response either way)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = db.session.scalar(select(User).where(
            func.lower(User.email) == normalize_identifier(email)))

        # Always show the same message — prevents user enumeration
        flash('If that email is registered, a password reset link has been sent.', 'info')

        if user:
            token = generate_reset_token(user.email)
            # Build external links from the configured SITE_URL (the canonical
            # apex) rather than url_for(_external=True), whose host/scheme derive
            # from the proxied request.host and so inherit whichever www-vs-apex
            # host the requester arrived on. Mirrors the SITE_URL + path pattern
            # the game email builders already use (games/*/services/notifications.py).
            base = current_app.config['SITE_URL'].rstrip('/')
            reset_url = base + url_for('auth.reset_password', token=token)
            seal_url = base + url_for('static', filename='img/logo/seal-email.png')
            plain = render_template('email/reset_password_plain.txt',
                                    reset_url=reset_url, user=user)
            html = render_template('email/reset_password_html.j2',
                                   reset_url=reset_url, seal_url=seal_url, user=user)
            send_platform_email(
                user.email,
                "Reset your password — Corrupt Commish Club",
                plain,
                html,
            )

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    email = verify_reset_token(token)
    if not email:
        flash('That reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = db.session.scalar(select(User).where(
        func.lower(User.email) == normalize_identifier(email)))
    if not user:
        flash('No account found for that reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif new_password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(new_password)
            db.session.commit()
            flash('Password reset successfully. Please log in with your new password.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'error')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('main.index'))

    return render_template('auth/change_password.html')


# The picker's allow-list. Two glyphs are deliberately absent because they are
# reserved and assigned by User.get_avatar(): the crown (platform admins) and
# the trophy (the reigning Survivor champion) — see models/user.py.
AVATAR_CATEGORIES = {
    "Sports & Games": [
        "⚽", "🏈", "⛳", "🏒", "🎾", "🏀", "🎱", "🥊",
        "⚾", "🎯", "🏊", "🚴", "🎿", "🏇", "🤺",
    ],
    "Animals": [
        "🦊", "🐺", "🦁", "🐯", "🦅", "🐬", "🦈", "🐻",
        "🦝", "🐸", "🦉", "🐊", "🦌", "🐆", "🦏",
    ],
    "Characters & Vibes": [
        "🤠", "🃏", "💀", "🥷", "🧙", "🤖", "👻", "🎭",
        "🧐", "🧛", "🧟", "🤡", "🎪", "🦸", "🧝",
        "🎩", "🦹", "🧞",
    ],
    "Food & Drink": [
        "🌮", "🍕", "🍺", "🎂", "🍔", "🫑", "🍣", "🍩",
        "🥃", "🧀", "🍦", "🥐", "🥩", "🍜", "🧁",
    ],
    "Nature & Elements": [
        "🌊", "🗻", "⚡", "🔥", "🌙", "🌤", "🍀", "🌋",
        "🎋", "🌸", "🍂", "🦋", "🌿", "🪨", "🌀",
    ],
}


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and update the current user's profile (name, email, avatar, phone)."""
    if request.method == 'POST':
        # The member's one display name, shown on every standings surface
        # (ADR-057); the validator excludes the member's own row so a
        # re-save never collides with itself.
        display_name, display_name_error = normalize_display_name(
            request.form.get('display_name', ''), exclude_user_id=current_user.id)
        email = request.form.get('email', '').strip().lower()

        avatar_emoji = request.form.get('avatar_emoji', '').strip()
        all_avatars = [e for choices in AVATAR_CATEGORIES.values() for e in choices]
        if avatar_emoji and avatar_emoji not in all_avatars:
            avatar_emoji = None

        phone, phone_error = normalize_us_phone(request.form.get('phone', ''))
        for error in (display_name_error, phone_error):
            if error:
                flash(error, 'error')
                return render_template('auth/profile.html',
                                       avatar_categories=AVATAR_CATEGORIES)

        if email != current_user.email:
            if db.session.scalar(select(User).where(
                    func.lower(User.email) == normalize_identifier(email))):
                flash('That email is already registered.', 'error')
                return render_template('auth/profile.html',
                                       avatar_categories=AVATAR_CATEGORIES)
            current_user.email = email

        current_user.display_name = display_name
        current_user.avatar_emoji = avatar_emoji or None
        current_user.phone = phone
        db.session.commit()
        flash('Profile updated.', 'success')

    return render_template('auth/profile.html', avatar_categories=AVATAR_CATEGORIES)
